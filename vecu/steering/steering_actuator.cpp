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
bool SteeringActuator::start_session(ActuatorSession session, ActuatorCommandStartup startup) {
    const auto application_epoch = session.application_epoch;
    const auto model_epoch = session.model_epoch;
    const auto enable_ns = session.enable_ns;
    if (application_epoch == 0 || application_epoch <= epoch_ || model_epoch == 0 ||
        (epoch_ != 0 && enable_ns < last_observed_ns_) ||
        (startup != ActuatorCommandStartup::Immediate && startup != ActuatorCommandStartup::NonDriving)) return false;
    if (startup == ActuatorCommandStartup::Immediate && !receiver_.start_session(application_epoch, enable_ns)) return false;
    if (!monitor_.begin(model_epoch, enable_ns)) return false;
    epoch_ = application_epoch; last_tick_ns_ = last_observed_ns_ = enable_ns;
    command_monitoring_ = startup == ActuatorCommandStartup::Immediate; sequence_ = 0; sequence_exhausted_ = false;
    e2e::p05_protect_init(tx_.protection);
    fault_ = SteeringFault::None;
    output_ = {steering::ActuationMode::Hold, 0, enable_ns}; prepared_ns_.reset(); execution_gap_ = false;
    return true; // physical state belongs to the external plant
}
bool SteeringActuator::clock(std::uint64_t now_ns) {
    if (epoch_ == 0) return false;
    if (now_ns < last_observed_ns_) { fail(SteeringFault::ClockError, last_observed_ns_); return false; }
    last_observed_ns_ = now_ns;
    return fault_ != SteeringFault::ClockError;
}
std::optional<can::SteeringMessage> SteeringActuator::current_sample(std::uint64_t now_ns) {
    if (!clock(now_ns) || !command_monitoring_ || fault_ != SteeringFault::None) return std::nullopt;
    return receiver_.current_sample(now_ns);
}
bool SteeringActuator::can_arm_normal_commands(std::uint64_t now_ns) {
    if (!clock(now_ns) || command_monitoring_ || fault_ != SteeringFault::None || prepared_ns_ || sequence_exhausted_) return false;
    if (now_ns-last_tick_ns_ > config_.max_tick_gap_ns) { fail(SteeringFault::ControlDeadline, now_ns); return false; }
    const auto& sensor = monitor_.decision();
    if (sensor.source_time_ns && now_ns-*sensor.source_time_ns > config_.sensor_age_ns) {
        fail(SteeringFault::SensorUnavailable, now_ns); return false;
    }
    return sensor.fault == SteeringMonitorFault::None && sensor.new_measurement && sensor.measured_rad && sensor.source_time_ns;
}
bool SteeringActuator::arm_normal_commands(std::uint64_t now_ns) {
    if (!can_arm_normal_commands(now_ns) || !receiver_.start_session(epoch_, now_ns)) return false;
    command_monitoring_ = true; return true;
}
void SteeringActuator::fail(SteeringFault fault, std::uint64_t now_ns) {
    if (fault_ == SteeringFault::None || fault == SteeringFault::ClockError) {
        fault_ = fault; output_ = {steering::ActuationMode::Hold, 0, now_ns};
    }
}
can::SteeringReceiveResult SteeringActuator::receive(const can::SteeringFrame& frame, std::uint64_t now_ns) {
    if (!clock(now_ns)) return {epoch_ == 0 ? can::SteeringReceiveDecision::NotInitialized : can::SteeringReceiveDecision::ClockError, std::nullopt};
    if (!command_monitoring_) return {can::SteeringReceiveDecision::NotInitialized, std::nullopt};
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
    if (!clock(now_ns)) return;
    if (command_monitoring_) receiver_.mark_continuity_lost(now_ns);
    if (epoch_ != 0) fail(command_monitoring_ && receiver_.health() == can::SteeringReceiverHealth::ClockError ?
                        SteeringFault::ClockError : SteeringFault::ContinuityLost, now_ns);
}
void SteeringActuator::mark_io_error(std::uint64_t now_ns) { fail(SteeringFault::PhysicalModelError, now_ns); }
void SteeringActuator::request_local_protection(std::uint64_t now_ns) {
    if (!clock(now_ns)) return;
    if (command_monitoring_) receiver_.mark_continuity_lost(now_ns);
    fail(SteeringFault::UpstreamProtection, now_ns);
}
void SteeringActuator::mark_output_rejected(std::uint64_t now_ns) { fail(SteeringFault::ControlDeadline, now_ns); }
bool SteeringActuator::prepare(std::uint64_t now_ns) {
    if (!clock(now_ns)) return false;
    if (prepared_ns_ && *prepared_ns_ == now_ns) return true;
    if (prepared_ns_) { fail(SteeringFault::ControlDeadline, now_ns); prepared_ns_.reset(); }
    if (epoch_ == 0) return false;
    const auto sample = command_monitoring_ ? receiver_.current_sample(now_ns) : std::nullopt;
    if ((command_monitoring_ && receiver_.health() == can::SteeringReceiverHealth::ClockError) || now_ns < last_tick_ns_) {
        fail(SteeringFault::ClockError, now_ns); return false;
    }
    if (fault_ == SteeringFault::ClockError || sequence_exhausted_) return false;
    if (now_ns - last_tick_ns_ < config_.period_ns) return false;
    execution_gap_ = now_ns - last_tick_ns_ > config_.max_tick_gap_ns;
    if (execution_gap_) fail(SteeringFault::ControlDeadline, now_ns);
    if (command_monitoring_ && receiver_.health() == can::SteeringReceiverHealth::ContinuityError) fail(SteeringFault::ContinuityLost, now_ns);
    if (command_monitoring_ && !sample && (receiver_.last_accepted() || receiver_.health() == can::SteeringReceiverHealth::Timeout)) {
        fail(SteeringFault::CommandUnavailable, now_ns);
    }
    prepared_ns_ = now_ns;
    return true;
}
std::optional<can::SteeringFrame> SteeringActuator::complete(const std::optional<steering::AngleMeasurement>& sensor, std::uint64_t now_ns) {
    if (!clock(now_ns) || !prepared_ns_ || *prepared_ns_ != now_ns) return std::nullopt;
    prepared_ns_.reset();
    const auto sample = command_monitoring_ ? receiver_.current_sample(now_ns) : std::nullopt;
    if (command_monitoring_ && receiver_.health() == can::SteeringReceiverHealth::ClockError) { fail(SteeringFault::ClockError, now_ns); return std::nullopt; }
    const auto& monitoring = monitor_.observe(sensor, now_ns, fault_ == SteeringFault::None && sample.has_value());
    if (monitoring.fault == SteeringMonitorFault::ClockError) { fail(SteeringFault::ClockError, now_ns); return std::nullopt; }
    if (monitoring.fault == SteeringMonitorFault::SensorUnavailable) fail(SteeringFault::SensorUnavailable, now_ns);
    if (monitoring.fault == SteeringMonitorFault::SensorInvalid) fail(SteeringFault::SensorInvalid, now_ns);
    if (monitoring.fault == SteeringMonitorFault::TrackingError) fail(SteeringFault::TrackingError, now_ns);
    if (fault_ == SteeringFault::None && sample) {
        const auto bounded = std::clamp(*sample->angle_rad, config_.angle_min_rad, config_.angle_max_rad);
        if (!monitor_.set_target(bounded, now_ns)) fail(SteeringFault::ControlDeadline, now_ns);
        else output_ = {steering::ActuationMode::Target, bounded, now_ns};
    }
    last_tick_ns_ = now_ns;
    can::SteeringMessage actual;
    actual.kind = can::SteeringFrameKind::Actual; actual.epoch = epoch_; actual.sequence = sequence_;
    actual.source_time_ns = now_ns;
    const auto accepted = command_monitoring_ ? receiver_.last_accepted() : std::nullopt;
    actual.causal_sequence = accepted ? accepted->message.sequence : 0;
    actual.local_state = fault_ != SteeringFault::None ? can::SteeringLocalState::FailSafe :
                         sample ? (monitoring.violation_since_ns ? can::SteeringLocalState::Degraded : sample->local_state) : can::SteeringLocalState::Init;
    actual.origin = fault_ != SteeringFault::None ? can::SteeringOrigin::LocalProtection :
                    accepted ? can::SteeringOrigin::NormalPath : can::SteeringOrigin::NoAcceptedInput;
    // No accepted command on startup failure: causal=0 is diagnostic only.
    // A cached sensor is not a fresh angle: publish unavailable without
    // replacing its acquisition time by this report's generation time.
    if ((fault_ == SteeringFault::None || accepted) && monitoring.new_measurement) {
        actual.angle_rad = monitoring.measured_rad;
        actual.source_time_ns = *monitoring.source_time_ns;
    }
    const auto frame = can::encode_steering_frame(actual, tx_);
    if (frame) {
        if (sequence_ == std::numeric_limits<std::uint32_t>::max()) sequence_exhausted_ = true;
        else ++sequence_;
    }
    return frame;
}
}  // namespace stratadrive::vecu
