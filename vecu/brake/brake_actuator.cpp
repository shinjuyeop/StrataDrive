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
bool BrakeActuator::start_session(ActuatorSession session, ActuatorCommandStartup startup) {
    const auto application_epoch = session.application_epoch;
    const auto model_epoch = session.model_epoch;
    const auto enable_ns = session.enable_ns;
    if (application_epoch == 0 || application_epoch <= epoch_ || model_epoch == 0 ||
        (epoch_ != 0 && enable_ns < last_observed_ns_) ||
        (startup != ActuatorCommandStartup::Immediate && startup != ActuatorCommandStartup::NonDriving)) return false;
    if (startup == ActuatorCommandStartup::Immediate && !receiver_.start_session(application_epoch, enable_ns)) return false;
    if (!monitor_.begin(model_epoch, enable_ns)) return false;
    epoch_ = application_epoch; last_tick_ns_ = last_observed_ns_ = enable_ns;
    stop_.reset(enable_ns);
    command_monitoring_ = startup == ActuatorCommandStartup::Immediate; sequence_ = 0; sequence_exhausted_ = false;
    e2e::p05_protect_init(tx_.protection);
    floor_observed_.reset(); fault_ = BrakeFault::None;
    output_ = {brake::ActuationMode::Hold, 0, enable_ns}; prepared_ns_.reset(); execution_gap_ = false;
    return true; // physical state belongs to the external plant
}
bool BrakeActuator::clock(std::uint64_t now_ns) {
    if (epoch_ == 0) return false;
    if (now_ns < last_observed_ns_) { fail(BrakeFault::ClockError, last_observed_ns_); return false; }
    last_observed_ns_ = now_ns;
    if(stop_.active() && !stop_.live(now_ns)) fail(BrakeFault::StopLeaseExpired,now_ns);
    return fault_ != BrakeFault::ClockError;
}
std::optional<can::BrakeMessage> BrakeActuator::current_sample(std::uint64_t now_ns) {
    if (!clock(now_ns) || !command_monitoring_ || fault_ != BrakeFault::None) return std::nullopt;
    return receiver_.current_sample(now_ns);
}
bool BrakeActuator::can_arm_normal_commands(std::uint64_t now_ns) {
    if (!clock(now_ns) || command_monitoring_ || stop_.active() || fault_ != BrakeFault::None || prepared_ns_ || sequence_exhausted_) return false;
    if (now_ns-last_tick_ns_ > config_.max_tick_gap_ns) { fail(BrakeFault::ControlDeadline, now_ns); return false; }
    const auto& sensor = monitor_.decision();
    if (sensor.source_time_ns && now_ns-*sensor.source_time_ns > config_.sensor_age_ns) {
        fail(BrakeFault::SensorUnavailable, now_ns); return false;
    }
    return sensor.fault == BrakeMonitorFault::None && sensor.new_measurement && sensor.measured_pa && sensor.source_time_ns;
}
bool BrakeActuator::arm_normal_commands(std::uint64_t now_ns) {
    if (!can_arm_normal_commands(now_ns) || !receiver_.start_session(epoch_, now_ns)) return false;
    command_monitoring_ = true; return true;
}
bool BrakeActuator::select_normal_stop(const ActuatorStopLease& lease, std::uint64_t now_ns) {
    if(!clock(now_ns) || fault_!=BrakeFault::None || prepared_ns_) return false;
    auto next=stop_; if(!next.accept(lease,epoch_,now_ns)) return false;
    const auto& sensor=monitor_.decision();
    if(now_ns-last_tick_ns_>config_.max_tick_gap_ns || sensor.violation_since_ns || !sensor.new_measurement || !sensor.measured_pa || !sensor.source_time_ns ||
        now_ns-*sensor.source_time_ns>config_.sensor_age_ns || *sensor.measured_pa<kStopPressurePa) return false;
    if(!stop_.active()) {
        if(!command_monitoring_ || !receiver_.current_sample(now_ns)) return false;
        if(!monitor_.hold(now_ns)) return false;
        output_={brake::ActuationMode::Hold,0,now_ns};
    }
    stop_=next; command_monitoring_=false; return true;
}
void BrakeActuator::fail(BrakeFault fault, std::uint64_t now_ns) {
    if (fault_ == BrakeFault::None) {
        fault_ = fault;
        output_ = {brake::ActuationMode::Protect, config_.fault_pressure_floor_pa, now_ns};
    }
    if (fault == BrakeFault::ClockError) { fault_ = fault; floor_observed_.reset(); }
}
can::BrakeReceiveResult BrakeActuator::receive(const can::BrakeFrame& frame, std::uint64_t now_ns) {
    if (!clock(now_ns)) return {epoch_ == 0 ? can::BrakeReceiveDecision::NotInitialized : can::BrakeReceiveDecision::ClockError, std::nullopt};
    if(stop_.active()) return {can::BrakeReceiveDecision::ModeRejected,std::nullopt};
    if (!command_monitoring_) return {can::BrakeReceiveDecision::NotInitialized, std::nullopt};
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
    if (!clock(now_ns)) return;
    if (command_monitoring_) receiver_.mark_continuity_lost(now_ns);
    if (epoch_ != 0) fail(command_monitoring_ && receiver_.health() == can::BrakeReceiverHealth::ClockError ?
                        BrakeFault::ClockError : BrakeFault::ContinuityLost, now_ns);
}
void BrakeActuator::mark_io_error(std::uint64_t now_ns) { fail(BrakeFault::PhysicalModelError, now_ns); }
void BrakeActuator::request_local_protection(std::uint64_t now_ns) {
    if (!clock(now_ns)) return;
    if (command_monitoring_) receiver_.mark_continuity_lost(now_ns);
    fail(BrakeFault::UpstreamProtection, now_ns);
}
void BrakeActuator::mark_output_rejected(std::uint64_t now_ns) { fail(BrakeFault::ControlDeadline, now_ns); }
bool BrakeActuator::prepare(std::uint64_t now_ns) {
    if (!clock(now_ns)) return false;
    if (prepared_ns_ && *prepared_ns_ == now_ns) return true;
    if (prepared_ns_) { fail(BrakeFault::ControlDeadline, now_ns); prepared_ns_.reset(); }
    if (epoch_ == 0) return false;
    const auto sample = command_monitoring_ ? receiver_.current_sample(now_ns) : std::nullopt;
    if ((command_monitoring_ && receiver_.health() == can::BrakeReceiverHealth::ClockError) || now_ns < last_tick_ns_) {
        fail(BrakeFault::ClockError, now_ns); return false;
    }
    if (fault_ == BrakeFault::ClockError || sequence_exhausted_) return false;
    if (now_ns - last_tick_ns_ < config_.period_ns) return false;
    execution_gap_ = now_ns - last_tick_ns_ > config_.max_tick_gap_ns;
    if (execution_gap_) fail(BrakeFault::ControlDeadline, now_ns);
    if (command_monitoring_ && receiver_.health() == can::BrakeReceiverHealth::ContinuityError) fail(BrakeFault::ContinuityLost, now_ns);
    if (command_monitoring_ && !sample && (receiver_.last_accepted() || receiver_.health() == can::BrakeReceiverHealth::Timeout)) {
        fail(BrakeFault::CommandUnavailable, now_ns);
    }
    prepared_ns_ = now_ns;
    return true;
}
std::optional<can::BrakeFrame> BrakeActuator::complete(const std::optional<brake::PressureMeasurement>& sensor, std::uint64_t now_ns) {
    if (!clock(now_ns) || !prepared_ns_ || *prepared_ns_ != now_ns) return std::nullopt;
    prepared_ns_.reset();
    const auto sample = command_monitoring_ ? receiver_.current_sample(now_ns) : std::nullopt;
    if (command_monitoring_ && receiver_.health() == can::BrakeReceiverHealth::ClockError) { fail(BrakeFault::ClockError, now_ns); return std::nullopt; }
    floor_observed_.reset();
    const auto& monitoring = monitor_.observe(sensor, now_ns, fault_ == BrakeFault::None && (sample.has_value() || stop_.active()));
    if (monitoring.fault == BrakeMonitorFault::ClockError) { fail(BrakeFault::ClockError, now_ns); return std::nullopt; }
    if (monitoring.fault == BrakeMonitorFault::SensorUnavailable) fail(BrakeFault::SensorUnavailable, now_ns);
    if (monitoring.fault == BrakeMonitorFault::SensorInvalid) fail(BrakeFault::SensorInvalid, now_ns);
    if (monitoring.fault == BrakeMonitorFault::ResponseError) fail(BrakeFault::ResponseError, now_ns);
    if (fault_ == BrakeFault::None && sample) {
        const auto bounded = std::clamp(*sample->pressure_pa, 0.0, config_.max_pressure_pa);
        if (!monitor_.set_target(bounded, now_ns)) fail(BrakeFault::ControlDeadline, now_ns);
        else output_ = {brake::ActuationMode::Target, bounded, now_ns};
    }
    if(stop_.active() && monitoring.new_measurement && monitoring.measured_pa && *monitoring.measured_pa<kStopPressurePa) fail(BrakeFault::NormalStopInvalid,now_ns);
    if (fault_ != BrakeFault::None && monitoring.new_measurement && monitoring.measured_pa) {
        floor_observed_ = *monitoring.measured_pa >= config_.fault_pressure_floor_pa;
    }
    last_tick_ns_ = now_ns;
    can::BrakeMessage actual;
    actual.kind = can::BrakeFrameKind::Actual; actual.epoch = epoch_; actual.sequence = sequence_;
    actual.source_time_ns = now_ns;
    const auto accepted = (command_monitoring_ || stop_.active()) ? receiver_.last_accepted() : std::nullopt;
    actual.causal_sequence = accepted ? accepted->message.sequence : 0;
    actual.local_state = fault_ != BrakeFault::None ? can::BrakeLocalState::FailSafe :
                         sample ? (monitoring.violation_since_ns ? can::BrakeLocalState::Degraded : sample->local_state) : can::BrakeLocalState::Init;
    actual.origin = fault_ != BrakeFault::None ? can::BrakeOrigin::LocalProtection :
                    accepted ? can::BrakeOrigin::NormalPath : can::BrakeOrigin::NoAcceptedInput;
    // No accepted command on startup failure: causal=0 is diagnostic only.
    // Cached/invalid acquisitions cannot be re-stamped as fresh Actuals.
    if ((fault_ == BrakeFault::None || accepted) && monitoring.new_measurement) {
        actual.pressure_pa = monitoring.measured_pa;
        actual.source_time_ns = *monitoring.source_time_ns;
    }
    const auto frame = can::encode_brake_frame(actual, tx_);
    if (frame) {
        if (sequence_ == std::numeric_limits<std::uint32_t>::max()) sequence_exhausted_ = true;
        else ++sequence_;
    }
    return frame;
}
}  // namespace stratadrive::vecu
