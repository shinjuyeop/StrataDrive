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
      response_({config.angle_min_rad, config.angle_max_rad, config.initial_angle_rad, config.max_rate_rad_s, config.delay_ns}),
      monitor_({config.angle_min_rad, config.angle_max_rad, config.max_rate_rad_s*config.healthy_min_rate_fraction,
          config.max_rate_rad_s*config.healthy_max_rate_fraction, config.delay_ns, config.tracking_tolerance_rad,
          config.tracking_confirmation_ns, config.sensor_age_ns, config.max_tick_gap_ns}) {
    if (!std::isfinite(config.command_min_rad) || !std::isfinite(config.command_max_rad) ||
        !std::isfinite(config.angle_min_rad) || !std::isfinite(config.angle_max_rad) ||
        !std::isfinite(config.initial_angle_rad) || !std::isfinite(config.max_rate_rad_s) ||
        config.command_min_rad >= config.command_max_rad || config.angle_min_rad >= config.angle_max_rad ||
        config.command_min_rad < -can::kAngleWireMaxRad || config.command_max_rad > can::kAngleWireMaxRad ||
        config.angle_min_rad < config.command_min_rad || config.angle_max_rad > config.command_max_rad ||
        config.initial_angle_rad < config.angle_min_rad || config.initial_angle_rad > config.angle_max_rad || config.max_rate_rad_s <= 0 ||
        config.period_ns < 1000000 || config.period_ns > 100000000 ||
        config.max_tick_gap_ns < config.period_ns || config.max_tick_gap_ns > 1000000000 ||
        config.delay_ns > config.period_ns * 100 || config.max_source_age_ns == 0 ||
        config.max_source_age_ns >= config.timeout_ns || config.timeout_ns > 100000000 ||
        config.healthy_min_rate_fraction > 1 || config.healthy_max_rate_fraction < 1 ||
        config.tracking_confirmation_ns < config.period_ns || config.tracking_confirmation_ns > 1000000000 ||
        config.sensor_age_ns > config.max_source_age_ns) {
        throw std::invalid_argument("SteeringActuator configuration");
    }
}
bool SteeringActuator::start_session(std::uint32_t epoch, std::uint64_t enable_ns) {
    if (epoch_ != 0 && enable_ns < last_tick_ns_) return false;
    if (!receiver_.start_session(epoch, enable_ns)) return false;
    if (!response_.begin(enable_ns) || !monitor_.begin(response_.model_epoch(), enable_ns)) return false;
    epoch_ = epoch; last_tick_ns_ = enable_ns; sequence_ = 0; sequence_exhausted_ = false;
    e2e::p05_protect_init(tx_.protection);
    fault_ = SteeringFault::None;
    return true; // physical angle survives a session restart
}
void SteeringActuator::fail(SteeringFault fault, std::uint64_t now_ns) {
    if (fault_ == SteeringFault::None || fault == SteeringFault::ClockError) fault_ = fault;
    response_.hold(now_ns);
}
can::SteeringReceiveResult SteeringActuator::receive(const can::SteeringFrame& frame, std::uint64_t now_ns) {
    // Monitor even when the model has already latched a local fault.
    const auto previous = receiver_.current_sample(now_ns);
    if (receiver_.health() == can::SteeringReceiverHealth::ClockError) fail(SteeringFault::ClockError, now_ns);
    if (!previous && (receiver_.last_accepted() || receiver_.health() == can::SteeringReceiverHealth::Timeout)) {
        fail(SteeringFault::CommandUnavailable, now_ns);
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
                        SteeringFault::ClockError : SteeringFault::ContinuityLost, now_ns);
}
std::optional<can::SteeringFrame> SteeringActuator::tick(std::uint64_t now_ns,
        simulation::SteeringResponseInjection injection, simulation::SteeringSensorAction sensor_action,
        std::optional<double> sensed_angle_override) {
    if (epoch_ == 0) return std::nullopt;
    const auto sample = receiver_.current_sample(now_ns);
    if (receiver_.health() == can::SteeringReceiverHealth::ClockError || now_ns < last_tick_ns_) {
        fail(SteeringFault::ClockError, now_ns); return std::nullopt;
    }
    if (fault_ == SteeringFault::ClockError || sequence_exhausted_) return std::nullopt;
    if (now_ns - last_tick_ns_ < config_.period_ns) return std::nullopt;
    if (now_ns - last_tick_ns_ > config_.max_tick_gap_ns) fail(SteeringFault::ControlDeadline, now_ns);
    if (receiver_.health() == can::SteeringReceiverHealth::ContinuityError) fail(SteeringFault::ContinuityLost, now_ns);
    if (!sample && (receiver_.last_accepted() || receiver_.health() == can::SteeringReceiverHealth::Timeout)) {
        fail(SteeringFault::CommandUnavailable, now_ns);
    }
    bool physical_valid = true;
    if (fault_ == SteeringFault::None) {
        if (!response_.advance(now_ns, injection)) { fail(SteeringFault::PhysicalModelError, now_ns); physical_valid = false; }
    } else response_.hold(now_ns);
    const auto sensor = physical_valid ? response_.capture(sensor_action, sensed_angle_override) : std::nullopt;
    const auto& monitoring = monitor_.observe(sensor, now_ns, fault_ == SteeringFault::None && sample.has_value());
    if (monitoring.fault == SteeringMonitorFault::ClockError) { fail(SteeringFault::ClockError, now_ns); return std::nullopt; }
    if (monitoring.fault == SteeringMonitorFault::SensorUnavailable) fail(SteeringFault::SensorUnavailable, now_ns);
    if (monitoring.fault == SteeringMonitorFault::SensorInvalid) fail(SteeringFault::SensorInvalid, now_ns);
    if (monitoring.fault == SteeringMonitorFault::TrackingError) fail(SteeringFault::TrackingError, now_ns);
    if (fault_ == SteeringFault::None && sample) {
        const auto bounded = std::clamp(*sample->angle_rad, config_.angle_min_rad, config_.angle_max_rad);
        if (!response_.set_target(bounded, now_ns) || !monitor_.set_target(bounded, now_ns)) fail(SteeringFault::ControlDeadline, now_ns);
    }
    last_tick_ns_ = now_ns;
    can::SteeringMessage actual;
    actual.kind = can::SteeringFrameKind::Actual; actual.epoch = epoch_; actual.sequence = sequence_;
    actual.source_time_ns = now_ns;
    const auto& accepted = receiver_.last_accepted();
    actual.causal_sequence = accepted ? accepted->message.sequence : 0;
    actual.local_state = fault_ != SteeringFault::None ? can::SteeringLocalState::FailSafe :
                         sample ? (monitoring.violation_since_ns ? can::SteeringLocalState::Degraded : sample->local_state) : can::SteeringLocalState::Init;
    actual.origin = fault_ != SteeringFault::None ? can::SteeringOrigin::LocalProtection :
                    accepted ? can::SteeringOrigin::NormalPath : can::SteeringOrigin::NoAcceptedInput;
    // No accepted command on startup failure: causal=0 is diagnostic only.
    // A cached sensor is not a fresh angle: publish unavailable without
    // replacing its acquisition time by this report's generation time.
    if ((fault_ == SteeringFault::None || accepted) && monitoring.new_measurement) actual.angle_rad = monitoring.measured_rad;
    const auto frame = can::encode_steering_frame(actual, tx_);
    if (frame) {
        if (sequence_ == std::numeric_limits<std::uint32_t>::max()) sequence_exhausted_ = true;
        else ++sequence_;
    }
    return frame;
}
}  // namespace stratadrive::vecu
