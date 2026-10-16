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
      response_({config.max_pressure_pa, config.initial_pressure_pa, config.rise_rate_pa_s, config.fall_rate_pa_s, config.delay_ns}),
      monitor_({config.max_pressure_pa, config.rise_rate_pa_s*config.healthy_min_rate_fraction,
          config.rise_rate_pa_s*config.healthy_max_rate_fraction, config.fall_rate_pa_s*config.healthy_min_rate_fraction,
          config.fall_rate_pa_s*config.healthy_max_rate_fraction, config.delay_ns, config.response_tolerance_pa,
          config.response_confirmation_ns, config.sensor_age_ns, config.max_tick_gap_ns}) {
    if (!std::isfinite(config.command_max_pa) || !std::isfinite(config.max_pressure_pa) ||
        !std::isfinite(config.initial_pressure_pa) || !std::isfinite(config.rise_rate_pa_s) ||
        !std::isfinite(config.fall_rate_pa_s) || !std::isfinite(config.fault_pressure_floor_pa) ||
        config.command_max_pa <= 0 || config.command_max_pa > can::kBrakePressureWireMaxPa ||
        config.max_pressure_pa <= 0 || config.max_pressure_pa > config.command_max_pa ||
        config.initial_pressure_pa < 0 || config.initial_pressure_pa > config.max_pressure_pa || config.rise_rate_pa_s <= 0 || config.fall_rate_pa_s <= 0 ||
        config.fault_pressure_floor_pa <= 0 || config.fault_pressure_floor_pa > config.max_pressure_pa ||
        config.period_ns < 1000000 || config.period_ns > 100000000 ||
        config.max_tick_gap_ns < config.period_ns || config.max_tick_gap_ns > 1000000000 ||
        config.delay_ns > config.period_ns * 100 || config.max_source_age_ns == 0 ||
        config.max_source_age_ns >= config.timeout_ns || config.timeout_ns > 100000000 ||
        config.healthy_min_rate_fraction > 1 || config.healthy_max_rate_fraction < 1 ||
        config.response_confirmation_ns < config.period_ns || config.response_confirmation_ns > 1000000000 ||
        config.sensor_age_ns > config.max_source_age_ns) {
        throw std::invalid_argument("BrakeActuator configuration");
    }
}
bool BrakeActuator::start_session(std::uint32_t epoch, std::uint64_t enable_ns) {
    if (epoch_ != 0 && enable_ns < last_tick_ns_) return false;
    if (!receiver_.start_session(epoch, enable_ns)) return false;
    if (!response_.begin(enable_ns) || !monitor_.begin(response_.model_epoch(), enable_ns)) return false;
    epoch_ = epoch; last_tick_ns_ = enable_ns; sequence_ = 0; sequence_exhausted_ = false;
    e2e::p05_protect_init(tx_.protection);
    floor_observed_.reset(); fault_ = BrakeFault::None;
    return true; // physical pressure survives a session restart
}
void BrakeActuator::fail(BrakeFault fault, std::uint64_t now_ns) {
    if (fault_ == BrakeFault::None) {
        fault_ = fault;
        // The plant's declared increase-only output primitive does not require
        // reading a hidden physical pressure into the controller's decision.
        response_.request_protection(config_.fault_pressure_floor_pa, now_ns);
    }
    if (fault == BrakeFault::ClockError) { fault_ = fault; floor_observed_.reset(); }
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
std::optional<can::BrakeFrame> BrakeActuator::tick(std::uint64_t now_ns,
        const simulation::BrakePressureResponseInjection& injection, simulation::BrakeSensorAction sensor_action,
        std::optional<double> sensed_pressure_override) {
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
    floor_observed_.reset();
    bool physical_valid = true;
    if (missed_deadline) {
        physical_valid = response_.skip_to(now_ns); // no physics over an unobserved interval
    } else if (!response_.advance(now_ns, injection)) {
        fail(BrakeFault::PhysicalModelError, now_ns); physical_valid = false;
    }
    const auto sensor = physical_valid ? response_.capture(sensor_action, sensed_pressure_override) : std::nullopt;
    const auto& monitoring = monitor_.observe(sensor, now_ns, fault_ == BrakeFault::None && sample.has_value());
    if (monitoring.fault == BrakeMonitorFault::ClockError) { fail(BrakeFault::ClockError, now_ns); return std::nullopt; }
    if (monitoring.fault == BrakeMonitorFault::SensorUnavailable) fail(BrakeFault::SensorUnavailable, now_ns);
    if (monitoring.fault == BrakeMonitorFault::SensorInvalid) fail(BrakeFault::SensorInvalid, now_ns);
    if (monitoring.fault == BrakeMonitorFault::ResponseError) fail(BrakeFault::ResponseError, now_ns);
    if (fault_ == BrakeFault::None && sample) {
        const auto bounded = std::clamp(*sample->pressure_pa, 0.0, config_.max_pressure_pa);
        if (!response_.set_target(bounded, now_ns) || !monitor_.set_target(bounded, now_ns)) fail(BrakeFault::ControlDeadline, now_ns);
    }
    if (fault_ != BrakeFault::None && monitoring.new_measurement && monitoring.measured_pa) {
        floor_observed_ = *monitoring.measured_pa >= config_.fault_pressure_floor_pa;
    }
    last_tick_ns_ = now_ns;
    can::BrakeMessage actual;
    actual.kind = can::BrakeFrameKind::Actual; actual.epoch = epoch_; actual.sequence = sequence_;
    actual.source_time_ns = now_ns;
    const auto& accepted = receiver_.last_accepted();
    actual.causal_sequence = accepted ? accepted->message.sequence : 0;
    actual.local_state = fault_ != BrakeFault::None ? can::BrakeLocalState::FailSafe :
                         sample ? (monitoring.violation_since_ns ? can::BrakeLocalState::Degraded : sample->local_state) : can::BrakeLocalState::Init;
    actual.origin = fault_ != BrakeFault::None ? can::BrakeOrigin::LocalProtection :
                    accepted ? can::BrakeOrigin::NormalPath : can::BrakeOrigin::NoAcceptedInput;
    // No accepted command on startup failure: causal=0 is diagnostic only.
    // Cached/invalid acquisitions cannot be re-stamped as fresh Actuals.
    if ((fault_ == BrakeFault::None || accepted) && monitoring.new_measurement) actual.pressure_pa = monitoring.measured_pa;
    const auto frame = can::encode_brake_frame(actual, tx_);
    if (frame) {
        if (sequence_ == std::numeric_limits<std::uint32_t>::max()) sequence_exhausted_ = true;
        else ++sequence_;
    }
    return frame;
}
}  // namespace stratadrive::vecu
