#include "brake_actuator.hpp"

#include "brake_pressure_codec.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace stratadrive::vecu {
BrakeActuator::BrakeActuator(BrakeActuatorConfig config)
    : config_(config), receiver_({can::BrakeFrameKind::Command, 0,
          config.command_max_pa, config.max_source_age_ns, config.timeout_ns}),
      actual_(config.initial_pressure_pa), target_(actual_) {
    if (!std::isfinite(config.command_max_pa) || !std::isfinite(config.max_pressure_pa) ||
        !std::isfinite(config.initial_pressure_pa) || !std::isfinite(config.rise_rate_pa_s) ||
        !std::isfinite(config.fall_rate_pa_s) || !std::isfinite(config.fault_pressure_floor_pa) ||
        config.command_max_pa <= 0 || config.command_max_pa > can::kBrakePressureWireMaxPa ||
        config.max_pressure_pa <= 0 || config.max_pressure_pa > config.command_max_pa ||
        actual_ < 0 || actual_ > config.max_pressure_pa || config.rise_rate_pa_s <= 0 || config.fall_rate_pa_s <= 0 ||
        config.fault_pressure_floor_pa <= 0 || config.fault_pressure_floor_pa > config.max_pressure_pa ||
        config.period_ns < 1000000 || config.period_ns > 100000000 ||
        config.max_tick_gap_ns < config.period_ns || config.max_tick_gap_ns > 1000000000 ||
        config.delay_ns > config.period_ns * 100 || config.max_source_age_ns == 0 ||
        config.max_source_age_ns >= config.timeout_ns || config.timeout_ns > 100000000) {
        throw std::invalid_argument("BrakeActuator configuration");
    }
}
bool BrakeActuator::start_session(std::uint32_t epoch, std::uint64_t enable_ns) {
    if (epoch_ != 0 && enable_ns < last_tick_ns_) return false;
    if (!receiver_.start_session(epoch, enable_ns)) return false;
    epoch_ = epoch; last_tick_ns_ = enable_ns; sequence_ = 0; sequence_exhausted_ = false;
    e2e::p05_protect_init(tx_.protection);
    head_ = size_ = 0; staged_.reset(); target_ = actual_; fault_ = BrakeFault::None;
    return true; // physical pressure survives a session restart
}
void BrakeActuator::fail(BrakeFault fault, std::uint64_t now_ns) {
    if (fault_ == BrakeFault::None) {
        fault_ = fault; protection_enable_ns_ = now_ns;
        // Cancel normal demand without releasing an already higher pressure.
        target_ = std::max(actual_, config_.fault_pressure_floor_pa);
        head_ = size_ = 0; staged_.reset();
    }
    if (fault == BrakeFault::ClockError) fault_ = fault;
}
can::BrakeReceiveResult BrakeActuator::receive(const can::BrakeFrame& frame, std::uint64_t now_ns) {
    // Monitor even when the model has already latched a local fault.
    const auto previous = receiver_.current_sample(now_ns);
    if (receiver_.health() == can::BrakeReceiverHealth::ClockError) fail(BrakeFault::ClockError, now_ns);
    if (!previous && (receiver_.last_accepted() || receiver_.health() == can::BrakeReceiverHealth::Timeout)) {
        fail(BrakeFault::CommandUnavailable, now_ns);
    }
    if (fault_ != BrakeFault::None) {
        return {fault_ == BrakeFault::ClockError ? can::BrakeReceiveDecision::ClockError :
                can::BrakeReceiveDecision::ModeRejected, std::nullopt};
    }
    return receiver_.receive(frame, now_ns);
}
void BrakeActuator::mark_continuity_lost(std::uint64_t now_ns) {
    receiver_.mark_continuity_lost(now_ns);
    if (epoch_ != 0) fail(receiver_.health() == can::BrakeReceiverHealth::ClockError ?
                        BrakeFault::ClockError : BrakeFault::ContinuityLost, now_ns);
}
void BrakeActuator::move(std::uint64_t elapsed_ns) {
    const auto rate = target_ >= actual_ ? config_.rise_rate_pa_s : config_.fall_rate_pa_s;
    const auto distance = rate * (static_cast<double>(elapsed_ns) / 1e9);
    actual_ += std::clamp(target_ - actual_, -distance, distance);
    actual_ = std::clamp(actual_, 0.0, config_.max_pressure_pa);
}
void BrakeActuator::advance(std::uint64_t now_ns) {
    auto cursor = last_tick_ns_;
    while (size_ != 0 && pending_[head_].due_ns <= now_ns) {
        const auto demand = pending_[head_];
        move(demand.due_ns - cursor); cursor = demand.due_ns; target_ = demand.pressure;
        head_ = (head_ + 1) % pending_.size(); --size_;
    }
    move(now_ns - cursor);
}
std::optional<can::BrakeFrame> BrakeActuator::tick(std::uint64_t now_ns) {
    if (epoch_ == 0) return std::nullopt;
    const auto sample = receiver_.current_sample(now_ns);
    if (receiver_.health() == can::BrakeReceiverHealth::ClockError || now_ns < last_tick_ns_) {
        fail(BrakeFault::ClockError, now_ns); return std::nullopt;
    }
    if (fault_ == BrakeFault::ClockError || sequence_exhausted_) return std::nullopt;
    if (now_ns - last_tick_ns_ < config_.period_ns) return std::nullopt;
    const bool missed_deadline = now_ns - last_tick_ns_ > config_.max_tick_gap_ns;
    if (missed_deadline) fail(BrakeFault::ControlDeadline, now_ns);
    if (receiver_.health() == can::BrakeReceiverHealth::ContinuityError) fail(BrakeFault::ContinuityLost, now_ns);
    if (!sample && (receiver_.last_accepted() || receiver_.health() == can::BrakeReceiverHealth::Timeout)) {
        fail(BrakeFault::CommandUnavailable, now_ns);
    }
    if (fault_ == BrakeFault::None && sample) {
        const auto bounded = std::clamp(*sample->pressure_pa, 0.0, config_.max_pressure_pa);
        // Repeated identical commands refresh freshness, not the physical delay.
        if (!staged_ || bounded != *staged_) {
            if (size_ == pending_.size() || now_ns > std::numeric_limits<std::uint64_t>::max() - config_.delay_ns) {
                fail(BrakeFault::ControlDeadline, now_ns);
            } else {
                pending_[(head_ + size_) % pending_.size()] = {bounded, now_ns + config_.delay_ns};
                ++size_; staged_ = bounded;
            }
        }
        if (fault_ == BrakeFault::None) advance(now_ns);
    }
    if (fault_ != BrakeFault::None && !missed_deadline) {
        // The fault starts at detection time; never backdate protective motion.
        move(now_ns - std::max(last_tick_ns_, protection_enable_ns_));
    }
    last_tick_ns_ = now_ns;
    can::BrakeMessage actual;
    actual.kind = can::BrakeFrameKind::Actual; actual.epoch = epoch_; actual.sequence = sequence_;
    actual.source_time_ns = now_ns;
    const auto& accepted = receiver_.last_accepted();
    actual.causal_sequence = accepted ? accepted->message.sequence : 0;
    actual.local_state = fault_ != BrakeFault::None ? can::BrakeLocalState::FailSafe :
                         sample ? sample->local_state : can::BrakeLocalState::Init;
    actual.origin = fault_ != BrakeFault::None ? can::BrakeOrigin::LocalProtection :
                    accepted ? can::BrakeOrigin::NormalPath : can::BrakeOrigin::NoAcceptedInput;
    // No accepted command on startup failure: causal=0 is diagnostic only.
    if (fault_ == BrakeFault::None || accepted) actual.pressure_pa = actual_;
    const auto frame = can::encode_brake_frame(actual, tx_);
    if (frame) {
        if (sequence_ == std::numeric_limits<std::uint32_t>::max()) sequence_exhausted_ = true;
        else ++sequence_;
    }
    return frame;
}
}  // namespace stratadrive::vecu
