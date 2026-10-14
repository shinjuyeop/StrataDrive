#include "steering_actuator.hpp"

#include "steering_angle_codec.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace stratadrive::vecu {
SteeringActuator::SteeringActuator(SteeringActuatorConfig config)
    : config_(config), receiver_({can::SteeringFrameKind::Command,
          config.command_min_rad, config.command_max_rad, config.max_source_age_ns, config.timeout_ns}),
      actual_(config.initial_angle_rad), target_(actual_) {
    if (!std::isfinite(config.command_min_rad) || !std::isfinite(config.command_max_rad) ||
        !std::isfinite(config.angle_min_rad) || !std::isfinite(config.angle_max_rad) ||
        !std::isfinite(config.initial_angle_rad) || !std::isfinite(config.max_rate_rad_s) ||
        config.command_min_rad >= config.command_max_rad || config.angle_min_rad >= config.angle_max_rad ||
        config.command_min_rad < -can::kAngleWireMaxRad || config.command_max_rad > can::kAngleWireMaxRad ||
        config.angle_min_rad < config.command_min_rad || config.angle_max_rad > config.command_max_rad ||
        actual_ < config.angle_min_rad || actual_ > config.angle_max_rad || config.max_rate_rad_s <= 0 ||
        config.period_ns < 1000000 || config.period_ns > 100000000 ||
        config.max_tick_gap_ns < config.period_ns || config.max_tick_gap_ns > 1000000000 ||
        config.delay_ns > config.period_ns * 100 || config.max_source_age_ns == 0 ||
        config.max_source_age_ns >= config.timeout_ns || config.timeout_ns > 100000000) {
        throw std::invalid_argument("SteeringActuator configuration");
    }
}
bool SteeringActuator::start_session(std::uint32_t epoch, std::uint64_t enable_ns) {
    if (epoch_ != 0 && enable_ns < last_tick_ns_) return false;
    if (!receiver_.start_session(epoch, enable_ns)) return false;
    epoch_ = epoch; last_tick_ns_ = enable_ns; sequence_ = 0; sequence_exhausted_ = false;
    e2e::p05_protect_init(tx_.protection);
    head_ = size_ = 0; staged_.reset(); target_ = actual_; fault_ = SteeringFault::None;
    return true; // physical angle survives a session restart
}
void SteeringActuator::fail(SteeringFault fault) {
    if (fault_ == SteeringFault::None || fault == SteeringFault::ClockError) fault_ = fault;
    head_ = size_ = 0; staged_.reset(); target_ = actual_;
}
can::SteeringReceiveResult SteeringActuator::receive(const can::SteeringFrame& frame, std::uint64_t now_ns) {
    // Monitor even when the model has already latched a local fault.
    const auto previous = receiver_.current_sample(now_ns);
    if (receiver_.health() == can::SteeringReceiverHealth::ClockError) fail(SteeringFault::ClockError);
    if (!previous && (receiver_.last_accepted() || receiver_.health() == can::SteeringReceiverHealth::Timeout)) {
        fail(SteeringFault::CommandUnavailable);
    }
    if (fault_ != SteeringFault::None) {
        return {fault_ == SteeringFault::ClockError ? can::SteeringReceiveDecision::ClockError :
                can::SteeringReceiveDecision::ModeRejected, std::nullopt};
    }
    return receiver_.receive(frame, now_ns);
}
void SteeringActuator::mark_continuity_lost(std::uint64_t now_ns) {
    receiver_.mark_continuity_lost(now_ns);
    if (epoch_ != 0) fail(receiver_.health() == can::SteeringReceiverHealth::ClockError ?
                        SteeringFault::ClockError : SteeringFault::ContinuityLost);
}
void SteeringActuator::move(std::uint64_t elapsed_ns) {
    const auto distance = config_.max_rate_rad_s * (static_cast<double>(elapsed_ns) / 1e9);
    actual_ += std::clamp(target_ - actual_, -distance, distance);
    actual_ = std::clamp(actual_, config_.angle_min_rad, config_.angle_max_rad);
}
void SteeringActuator::advance(std::uint64_t now_ns) {
    auto cursor = last_tick_ns_;
    while (size_ != 0 && pending_[head_].due_ns <= now_ns) {
        const auto demand = pending_[head_];
        move(demand.due_ns - cursor); cursor = demand.due_ns; target_ = demand.angle;
        head_ = (head_ + 1) % pending_.size(); --size_;
    }
    move(now_ns - cursor);
}
std::optional<can::SteeringFrame> SteeringActuator::tick(std::uint64_t now_ns) {
    if (epoch_ == 0) return std::nullopt;
    const auto sample = receiver_.current_sample(now_ns);
    if (receiver_.health() == can::SteeringReceiverHealth::ClockError || now_ns < last_tick_ns_) {
        fail(SteeringFault::ClockError); return std::nullopt;
    }
    if (fault_ == SteeringFault::ClockError || sequence_exhausted_) return std::nullopt;
    if (now_ns - last_tick_ns_ < config_.period_ns) return std::nullopt;
    if (now_ns - last_tick_ns_ > config_.max_tick_gap_ns) fail(SteeringFault::ControlDeadline);
    if (receiver_.health() == can::SteeringReceiverHealth::ContinuityError) fail(SteeringFault::ContinuityLost);
    if (!sample && (receiver_.last_accepted() || receiver_.health() == can::SteeringReceiverHealth::Timeout)) {
        fail(SteeringFault::CommandUnavailable);
    }
    if (fault_ == SteeringFault::None && sample) {
        const auto bounded = std::clamp(*sample->angle_rad, config_.angle_min_rad, config_.angle_max_rad);
        // Repeated identical commands refresh freshness, not the physical delay.
        if (!staged_ || bounded != *staged_) {
            if (size_ == pending_.size() || now_ns > std::numeric_limits<std::uint64_t>::max() - config_.delay_ns) {
                fail(SteeringFault::ControlDeadline);
            } else {
                pending_[(head_ + size_) % pending_.size()] = {bounded, now_ns + config_.delay_ns};
                ++size_; staged_ = bounded;
            }
        }
        if (fault_ == SteeringFault::None) advance(now_ns);
    }
    last_tick_ns_ = now_ns;
    can::SteeringMessage actual;
    actual.kind = can::SteeringFrameKind::Actual; actual.epoch = epoch_; actual.sequence = sequence_;
    actual.source_time_ns = now_ns;
    const auto& accepted = receiver_.last_accepted();
    actual.causal_sequence = accepted ? accepted->message.sequence : 0;
    actual.local_state = fault_ != SteeringFault::None ? can::SteeringLocalState::FailSafe :
                         sample ? sample->local_state : can::SteeringLocalState::Init;
    actual.origin = fault_ != SteeringFault::None ? can::SteeringOrigin::LocalProtection :
                    accepted ? can::SteeringOrigin::NormalPath : can::SteeringOrigin::NoAcceptedInput;
    // No accepted command on startup failure: causal=0 is diagnostic only.
    if (fault_ == SteeringFault::None || accepted) actual.angle_rad = actual_;
    const auto frame = can::encode_steering_frame(actual, tx_);
    if (frame) {
        if (sequence_ == std::numeric_limits<std::uint32_t>::max()) sequence_exhausted_ = true;
        else ++sequence_;
    }
    return frame;
}
}  // namespace stratadrive::vecu
