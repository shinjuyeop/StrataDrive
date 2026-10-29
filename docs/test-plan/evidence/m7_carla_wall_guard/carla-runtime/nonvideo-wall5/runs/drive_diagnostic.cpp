#include "drive_controller.hpp"

#include "drive_value_codec.hpp"

#include <algorithm>
#include <iostream>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace stratadrive::vecu {
namespace {
bool equal(double a, double b) { return a == b; }
bool equal(drive::HvFeedback a, drive::HvFeedback b) {
    return a.bus_voltage_v == b.bus_voltage_v && a.inverter_ready == b.inverter_ready && a.local_fault == b.local_fault;
}
struct SensorContext { std::uint32_t epoch; std::uint64_t enable_ns, now_ns, age_ns; };
template <typename T> drive::SensorDecision check(const battery::ModelMeasurement<T>& x,
        const std::optional<battery::ModelMeasurement<T>>& old, const SensorContext& context) {
    if (x.identity.epoch != context.epoch) return drive::SensorDecision::Identity;
    if (x.input_time_ns < context.enable_ns || x.input_time_ns > x.identity.source_time_ns || x.identity.source_time_ns > context.now_ns ||
        context.now_ns-x.identity.source_time_ns > context.age_ns || context.now_ns-x.input_time_ns > context.age_ns) return drive::SensorDecision::Time;
    if (old) {
        const bool cached = x.identity.sequence == old->identity.sequence;
        if (x.identity.sequence < old->identity.sequence || x.input_time_ns < old->input_time_ns ||
            (cached && (x.identity.source_time_ns != old->identity.source_time_ns || x.input_time_ns != old->input_time_ns || !equal(x.value, old->value))) ||
            (!cached && x.identity.source_time_ns <= old->identity.source_time_ns)) return drive::SensorDecision::Identity;
    }
    return drive::SensorDecision::Accepted;
}
double floor_torque(double x) { return std::max(0.0, std::floor(x*10.0)/10.0); }
bool live(can::ActuatorReceiverHealth health) { return health == can::ActuatorReceiverHealth::Timeout || health == can::ActuatorReceiverHealth::ContinuityError; }
bool operational(const can::BmsMessage& limits) {
    return limits.origin == can::ActuatorOrigin::NormalPath &&
        (limits.local_state == can::ActuatorLocalState::Normal || limits.local_state == can::ActuatorLocalState::Degraded);
}
}  // namespace

DriveController::DriveController(DriveControllerConfig config) : config_(config),
    command_({can::DriveFrameKind::Command, config.command_nm, can::kDriveWheelSpeedWireMaxRadS, -config.command_nm.minimum}),
    limits_({can::BmsFrameKind::DriveBatteryLimits, {{0, 1000}, {-3000, 3000}, {-50, 150}, config.maximum_bms_power_w}}),
    permission_({can::BmsFrameKind::DrivePermission, {{0, 1000}, {-3000, 3000}, {-50, 150}, config.maximum_bms_power_w}}) {
    for (const auto x : {config.command_nm.minimum, config.command_nm.maximum, config.max_wheel_speed_rad_s,
        config.regen_stop_rad_s, config.regen_full_rad_s, config.propulsion_mechanical_power_w, config.regen_mechanical_power_w,
        config.motoring_efficiency_lower_bound, config.copper_loss_w_per_nm2, config.fixed_power_reserve_w,
        config.minimum_hv_v, config.maximum_hv_v, config.maximum_bms_power_w}) {
        if (!std::isfinite(x)) throw std::invalid_argument("DriveController finite calibration");
    }
    if (!drive::valid_response_config(config.response) || config.command_nm.minimum >= 0 || config.command_nm.maximum <= 0 || config.command_nm.minimum < -can::kDriveTorqueWireMaxNm ||
        config.command_nm.maximum > can::kDriveTorqueWireMaxNm || config.response.minimum_nm < config.command_nm.minimum ||
        config.response.maximum_nm > config.command_nm.maximum || config.max_wheel_speed_rad_s <= config.regen_full_rad_s ||
        config.max_wheel_speed_rad_s > can::kDriveWheelSpeedWireMaxRadS || config.regen_stop_rad_s <= 0 ||
        config.regen_full_rad_s <= config.regen_stop_rad_s || config.propulsion_mechanical_power_w <= 0 || config.regen_mechanical_power_w <= 0 ||
        config.motoring_efficiency_lower_bound <= 0 || config.motoring_efficiency_lower_bound > 1 || config.copper_loss_w_per_nm2 <= 0 ||
        config.fixed_power_reserve_w < 0 || config.minimum_hv_v <= 0 || config.maximum_hv_v <= config.minimum_hv_v || config.maximum_hv_v > 1000 ||
        config.maximum_bms_power_w <= 0 || config.maximum_bms_power_w > 655340 || config.period_ns < 1000000 ||
        config.period_ns > 30000000 || config.max_tick_gap_ns < config.period_ns || config.max_tick_gap_ns > 30000000 ||
        config.response.delay_ns > config.period_ns*100 || config.local_age_ns == 0 || config.local_age_ns > 30000000 ||
        config.local_skew_ns > config.local_age_ns ||
        !std::isfinite(std::pow(config.max_wheel_speed_rad_s/config.motoring_efficiency_lower_bound, 2)+
            4*config.copper_loss_w_per_nm2*config.maximum_bms_power_w)) throw std::invalid_argument("DriveController configuration");
}
bool DriveController::start_session(ActuatorSession session, DriveCommandStartup startup) {
    const auto application_epoch = session.application_epoch;
    const auto model_epoch = session.model_epoch;
    const auto enable_ns = session.enable_ns;
    if (application_epoch == 0 || model_epoch == 0 || (epoch_ != 0 &&
        (application_epoch <= epoch_ || model_epoch < model_epoch_ || enable_ns < last_observed_ns_))) return false;
    if (startup != DriveCommandStartup::Immediate && startup != DriveCommandStartup::NonDriving) return false;
    if ((startup == DriveCommandStartup::Immediate && !command_.start_session(application_epoch, enable_ns)) || !limits_.start_session(application_epoch, enable_ns) ||
        !permission_.start_session(application_epoch, enable_ns)) return false;
    epoch_ = application_epoch; model_epoch_ = model_epoch; enable_ns_ = last_observed_ns_ = last_tick_ns_ = enable_ns;
    sequence_ = 0; armed_ = stopped_ = false; decision_ = {};
    stop_.reset(enable_ns); last_torque_.reset();
    command_monitoring_ = startup == DriveCommandStartup::Immediate; startup_inputs_seen_ = false;
    speed_.reset(); speed_cursor_.reset(); hv_.reset(); hv_cursor_.reset(); permission_parent_.reset(); last_capability_input_ns_.reset();
    feedback_.begin(session); e2e::p05_protect_init(tx_.protection);
    output_ = {drive::ActuationMode::Zero, 0, std::nullopt, enable_ns};
    prepared_ns_.reset(); prepared_inputs_.reset(); execution_gap_ = false;
    return true;
}
bool DriveController::arm_normal_commands(std::uint64_t now_ns) {
    if (!clock(now_ns) || command_monitoring_ || stop_.active() || decision_.fault != DriveGateFault::None) return false;
    const auto in = monitor(now_ns);
    if (decision_.fault != DriveGateFault::None || !in.complete || !in.permission ||
        can::bms_permission_allows_normal(*in.permission) ||
        in.permission->message.local_state == can::ActuatorLocalState::FailSafe ||
        in.hv->value.local_fault || !in.hv->value.inverter_ready ||
        in.hv->value.bus_voltage_v < config_.minimum_hv_v || in.hv->value.bus_voltage_v > config_.maximum_hv_v) return false;
    if (!command_.start_session(epoch_, now_ns)) return false;
    command_monitoring_ = true; return true;
}
bool DriveController::select_normal_stop(const ActuatorStopLease& lease,std::uint64_t now_ns) {
    if(!clock(now_ns) || decision_.fault!=DriveGateFault::None || prepared_ns_) return false;
    auto next=stop_; if(!next.accept(lease,epoch_,now_ns)) return false;
    const auto in=monitor(now_ns);
    if(decision_.fault!=DriveGateFault::None || !in.complete || !last_torque_ || now_ns-last_torque_->source_time_ns>30000000 ||
        std::abs(last_torque_->torque_nm)>kStopTorqueNm || in.speed->value>kStopSpeedRadS ||
        (!stop_.active() && (!command_monitoring_ || !in.command))) return false;
    stop_=next; command_monitoring_=false; startup_inputs_seen_=true; decision_.active=false;
    output_={drive::ActuationMode::Zero,0,drive::TorqueEnvelope{0,0},now_ns}; return true;
}
bool DriveController::clock(std::uint64_t now_ns) {
    if (epoch_ == 0 || stopped_) return false;
    if (now_ns < last_observed_ns_) {
        fail(DriveGateFault::ClockError, now_ns); stopped_ = true; return false;
    }
    last_observed_ns_ = now_ns;
    if(stop_.active() && !stop_.live(now_ns)) fail(DriveGateFault::StopLeaseExpired,now_ns);
    return true;
}
void DriveController::fail(DriveGateFault fault, std::uint64_t now_ns) {
    if (decision_.fault == DriveGateFault::None || fault == DriveGateFault::ClockError || fault == DriveGateFault::ControlDeadline) {
        decision_.fault = fault;
    }
    if(fault==DriveGateFault::LocalInputsUnavailable) {
      std::cerr<<"local_failure at="<<now_ns;
      if(speed_)std::cerr<<" speed_source="<<speed_->identity.source_time_ns<<" speed_input="<<speed_->input_time_ns;
      if(hv_)std::cerr<<" hv_source="<<hv_->identity.source_time_ns<<" hv_input="<<hv_->input_time_ns;
      std::cerr<<std::endl;
    }
    decision_.active = false; decision_.selected_target_nm = 0;
    if (fault != DriveGateFault::ClockError) output_ = {drive::ActuationMode::Zero, 0, drive::TorqueEnvelope{0, 0}, now_ns};
}
DriveController::Inputs DriveController::monitor(std::uint64_t now_ns) {
    Inputs in;
    if (command_monitoring_) in.command = command_.current_sample(now_ns);
    in.limits = limits_.current_sample(now_ns); in.permission = permission_.current_sample(now_ns);
    if (speed_ && now_ns-speed_->identity.source_time_ns <= config_.local_age_ns && now_ns-speed_->input_time_ns <= config_.local_age_ns) in.speed = speed_;
    if (hv_ && now_ns-hv_->identity.source_time_ns <= config_.local_age_ns && now_ns-hv_->input_time_ns <= config_.local_age_ns) in.hv = hv_;
    if (in.speed && in.hv && std::max(in.speed->identity.source_time_ns, in.hv->identity.source_time_ns)-
        std::min(in.speed->identity.source_time_ns, in.hv->identity.source_time_ns) > config_.local_skew_ns) in.hv.reset();
    const bool limits_known = in.limits && in.limits->quality[0] == can::BmsFieldQuality::Usable && in.limits->quality[1] == can::BmsFieldQuality::Usable;
    const bool permission_known = in.permission && in.permission->quality[0] == can::BmsFieldQuality::Usable;
    in.complete = limits_known && permission_known && in.speed && in.hv;
    const bool grant = permission_known && can::bms_permission_allows_normal(*in.permission);
    const bool limits_ok = limits_known && operational(in.limits->message);
    const bool hv_ok = in.hv && in.hv->value.bus_voltage_v >= config_.minimum_hv_v && in.hv->value.bus_voltage_v <= config_.maximum_hv_v &&
        in.hv->value.inverter_ready && !in.hv->value.local_fault;
    in.allowed = in.complete && grant && limits_ok && hv_ok && in.speed->value <= config_.max_wheel_speed_rad_s;
    const bool timed_out = (command_monitoring_ && live(command_.health())) || live(limits_.health()) || live(permission_.health());
    const bool local_timeout = now_ns-enable_ns_ >= 80000000 && (!in.speed || !in.hv);
    if (!command_monitoring_) {
        if (grant && !stop_.active()) fail(DriveGateFault::CommandsNotArmed, now_ns);
        if(stop_.active() && in.speed && in.speed->value>kStopSpeedRadS) fail(DriveGateFault::NormalStopInvalid,now_ns);
        if (startup_inputs_seen_ || timed_out || local_timeout) {
            if (!limits_known) fail(DriveGateFault::LimitsUnavailable, now_ns);
            else if (!permission_known) fail(DriveGateFault::PermissionUnavailable, now_ns);
            else if (!in.speed || !in.hv) fail(DriveGateFault::LocalInputsUnavailable, now_ns);
            else if (in.permission->message.local_state == can::ActuatorLocalState::FailSafe ||
                in.permission->message.origin == can::ActuatorOrigin::LocalProtection) fail(DriveGateFault::UpstreamProtection, now_ns);
            else if (in.limits->message.local_state == can::ActuatorLocalState::FailSafe || in.hv->value.local_fault) fail(DriveGateFault::BmsProtection, now_ns);
        }
        startup_inputs_seen_ = startup_inputs_seen_ || in.complete;
        return in;
    }
    // Explicit fresh Inhibit + known physical OFF is a legitimate non-driving INIT.
    // After activation, any loss closes the gate and latches until a newer trusted INIT.
    if (armed_ || timed_out || local_timeout || (grant && in.complete && in.command)) {
        if (!in.command) fail(DriveGateFault::CommandUnavailable, now_ns);
        else if (!limits_known) fail(DriveGateFault::LimitsUnavailable, now_ns);
        else if (!permission_known) fail(DriveGateFault::PermissionUnavailable, now_ns);
        else if (!in.speed || !in.hv) fail(DriveGateFault::LocalInputsUnavailable, now_ns);
        else if (armed_ && !grant) fail(DriveGateFault::PermissionInhibit, now_ns);
        else if (grant && !limits_ok) fail(DriveGateFault::BmsProtection, now_ns);
        else if (grant && !hv_ok) fail(DriveGateFault::HvNotReady, now_ns);
        else if (grant && in.speed->value > config_.max_wheel_speed_rad_s) fail(DriveGateFault::Overspeed, now_ns);
    }
    return in;
}
can::DriveReceiveResult DriveController::receive_command(const can::DriveFrame& frame, std::uint64_t now_ns) {
    if (!clock(now_ns)) return {epoch_ == 0 ? can::ActuatorReceiveDecision::NotInitialized : can::ActuatorReceiveDecision::ClockError, std::nullopt};
    monitor(now_ns); // late fresh data cannot conceal a preceding expiry
    if(stop_.active()) return {can::ActuatorReceiveDecision::ModeRejected,std::nullopt};
    if (!command_monitoring_) return {can::ActuatorReceiveDecision::NotInitialized, std::nullopt};
    return command_.receive(frame, now_ns);
}
can::BmsReceiveResult DriveController::receive_limits(const can::BmsFrame& frame, std::uint64_t now_ns) {
    if (!clock(now_ns)) return {epoch_ == 0 ? can::ActuatorReceiveDecision::NotInitialized : can::ActuatorReceiveDecision::ClockError, std::nullopt};
    monitor(now_ns); return limits_.receive(frame, now_ns);
}
can::BmsReceiveResult DriveController::receive_permission(const can::BmsFrame& frame, std::uint64_t now_ns, const can::BmsParentContext* parent) {
    if (!clock(now_ns)) return {epoch_ == 0 ? can::ActuatorReceiveDecision::NotInitialized : can::ActuatorReceiveDecision::ClockError, std::nullopt};
    monitor(now_ns);
    auto result = permission_.receive(frame, now_ns, parent);
    if (result.decision == can::ActuatorReceiveDecision::Accepted && result.quality[0] == can::BmsFieldQuality::Usable) {
        const auto& value = std::get<can::BmsDriveGrant>(permission_.last_accepted()->message.content);
        if (value.permission == can::BmsDrivePermission::AllowNormal && parent) permission_parent_ = *parent;
        else permission_parent_.reset();
    }
    return result;
}
drive::SensorResult DriveController::observe_local(const drive::LocalSensors& sensors, std::uint64_t now_ns) {
    using drive::SensorDecision;
    if (!clock(now_ns)) {
        const auto reason = epoch_ == 0 ? SensorDecision::NotInitialized : SensorDecision::ClockError; return {reason, reason};
    }
    monitor(now_ns);
    const SensorContext context{model_epoch_, enable_ns_, now_ns, config_.local_age_ns};
    drive::SensorResult result{SensorDecision::Unavailable, SensorDecision::Unavailable};
    speed_.reset(); hv_.reset();
    if (sensors.wheel_speed) {
        result.wheel_speed = check(*sensors.wheel_speed, speed_cursor_, context);
        if (!std::isfinite(sensors.wheel_speed->value) || sensors.wheel_speed->value < 0 || sensors.wheel_speed->value > can::kDriveWheelSpeedWireMaxRadS) result.wheel_speed = SensorDecision::Value;
        if (result.wheel_speed == SensorDecision::Accepted) speed_ = speed_cursor_ = sensors.wheel_speed;
    }
    if (sensors.hv) {
        result.hv = check(*sensors.hv, hv_cursor_, context);
        if (!std::isfinite(sensors.hv->value.bus_voltage_v) || sensors.hv->value.bus_voltage_v < 0 || sensors.hv->value.bus_voltage_v > 1000) result.hv = SensorDecision::Value;
        if (result.hv == SensorDecision::Accepted) hv_ = hv_cursor_ = sensors.hv;
    }
    if(now_ns>272852964856476ULL && (result.wheel_speed!=SensorDecision::Accepted || result.hv!=SensorDecision::Accepted)) {
        std::cerr<<"sensor_reject at="<<now_ns<<" wheel="<<int(result.wheel_speed)<<" hv="<<int(result.hv);
        if(sensors.wheel_speed)std::cerr<<" wheel_source="<<sensors.wheel_speed->identity.source_time_ns<<" wheel_input="<<sensors.wheel_speed->input_time_ns<<" wheel_value="<<sensors.wheel_speed->value;
        if(sensors.hv)std::cerr<<" hv_source="<<sensors.hv->identity.source_time_ns<<" hv_input="<<sensors.hv->input_time_ns;
        std::cerr<<std::endl;
    }
    monitor(now_ns);
    return result;
}
void DriveController::mark_continuity_lost(std::uint64_t now_ns) {
    if (!clock(now_ns)) return;
    command_.mark_continuity_lost(now_ns); limits_.mark_continuity_lost(now_ns); permission_.mark_continuity_lost(now_ns);
    fail(DriveGateFault::ContinuityLost, now_ns);
}
void DriveController::request_local_protection(std::uint64_t now_ns) {
    if (epoch_ == 0) return;
    const bool ordered = clock(now_ns);
    command_.mark_continuity_lost(now_ns);
    // fail selects Zero even if clock() already latched ClockError/stopped.
    // Preserve that diagnostic; do not keep a previous motor target on this port.
    fail(DriveGateFault::UpstreamProtection, ordered ? now_ns : last_observed_ns_);
}
void DriveController::calculate(const Inputs& in) {
    decision_.propulsion_limit_nm.reset(); decision_.regen_limit_nm.reset(); decision_.capability_input_time_ns = 0;
    decision_.regen_reason = can::DriveRegenLimitReason::InputsInvalid;
    if (!in.complete) return;
    const auto& limits = std::get<can::BmsPowerLimits>(in.limits->message.content);
    const auto& grant = std::get<can::BmsDriveGrant>(in.permission->message.content);
    auto dependency = std::min({in.speed->input_time_ns, in.hv->input_time_ns, limits.input_time_ns,
        in.limits->message.source_time_ns, in.permission->message.source_time_ns});
    if (grant.permission == can::BmsDrivePermission::AllowNormal && permission_parent_) {
        dependency = std::min({dependency, grant.input_time_ns, grant.power_status_source_time_ns, permission_parent_->source_time_ns});
    }
    decision_.capability_input_time_ns = dependency;
    if (decision_.fault != DriveGateFault::None || !decision_.active || !in.allowed) {
        decision_.propulsion_limit_nm = decision_.regen_limit_nm = 0;
        decision_.regen_reason = can::DriveRegenLimitReason::Disabled; return;
    }
    const auto speed = in.speed->value;
    const auto available = std::max(0.0, *limits.discharge_power_w-config_.fixed_power_reserve_w);
    const auto b = speed/config_.motoring_efficiency_lower_bound;
    const auto a = config_.copper_loss_w_per_nm2;
    // Stable positive quadratic root, also finite at standstill (no P/0 shortcut).
    const auto electrical_torque = available == 0 ? 0 : 2*available/(b+std::sqrt(b*b+4*a*available));
    auto propulsion = std::min(config_.response.maximum_nm, electrical_torque);
    if (speed > 0) propulsion = std::min(propulsion, config_.propulsion_mechanical_power_w/speed);
    decision_.propulsion_limit_nm = floor_torque(propulsion);
    const auto base = -config_.response.minimum_nm;
    const auto taper = std::clamp((speed-config_.regen_stop_rad_s)/(config_.regen_full_rad_s-config_.regen_stop_rad_s), 0.0, 1.0);
    auto motor = base*taper;
    if (speed > 0) motor = std::min(motor, config_.regen_mechanical_power_w/speed);
    const auto charge = speed > config_.regen_stop_rad_s ? *limits.charge_power_w/speed : 0;
    decision_.regen_limit_nm = floor_torque(std::min(motor, charge));
    decision_.regen_reason = *limits.charge_power_w == 0 || charge < motor ? can::DriveRegenLimitReason::ChargeAcceptanceLimited :
        motor < base ? can::DriveRegenLimitReason::MotorOrSpeedLimited : can::DriveRegenLimitReason::Nominal;
}
bool DriveController::prepare(std::uint64_t now_ns) {
    if (prepared_ns_ && *prepared_ns_ == now_ns) return true;
    if (prepared_ns_) { fail(DriveGateFault::ControlDeadline, now_ns); prepared_ns_.reset(); }
    if (!clock(now_ns)) return false;
    if (now_ns-last_tick_ns_ < config_.period_ns) return false;
    execution_gap_ = now_ns-last_tick_ns_ > config_.max_tick_gap_ns;
    if (execution_gap_) fail(DriveGateFault::ControlDeadline, now_ns);
    const auto in = monitor(now_ns);
    if (decision_.fault == DriveGateFault::None && in.allowed && in.command) armed_ = true;
    decision_.active = armed_ && decision_.fault == DriveGateFault::None && in.allowed && in.command.has_value();
    calculate(in);
    decision_.selected_target_nm = 0;
    const drive::TorqueEnvelope envelope{decision_.active ? -*decision_.regen_limit_nm : 0,
        decision_.active ? *decision_.propulsion_limit_nm : 0};
    if (decision_.active) {
        decision_.selected_target_nm = std::clamp(*in.command->torque_nm, envelope.minimum_nm, envelope.maximum_nm) + 0.0;
    }
    output_ = {decision_.active ? drive::ActuationMode::Target : drive::ActuationMode::Zero,
        decision_.selected_target_nm, envelope, now_ns};
    prepared_ns_ = now_ns; prepared_inputs_ = in; return true;
}
std::optional<can::DriveFrame> DriveController::complete(const std::optional<drive::TorqueMeasurement>& sensor, std::uint64_t now_ns) {
    if (!prepared_ns_ || *prepared_ns_ != now_ns || !prepared_inputs_) return std::nullopt;
    prepared_ns_.reset();
    if (!clock(now_ns)) return std::nullopt;
    const auto in = *prepared_inputs_; prepared_inputs_.reset();
    const auto measured = feedback_.observe(sensor, now_ns, config_.response.minimum_nm, config_.response.maximum_nm);
    if(measured.fresh) last_torque_=measured.fresh;
    if(stop_.active() && measured.valid && std::abs(sensor->torque_nm)>kStopTorqueNm) fail(DriveGateFault::NormalStopInvalid,now_ns);
    if (!measured.valid) { fail(DriveGateFault::TorqueFeedbackUnavailable, now_ns); calculate(in); }
    last_tick_ns_ = now_ns;
    decision_.actual_outside_envelope = measured.valid &&
        (sensor->torque_nm < (decision_.active ? -*decision_.regen_limit_nm : 0) ||
         sensor->torque_nm > (decision_.active ? *decision_.propulsion_limit_nm : 0));
    can::DriveMessage actual; actual.kind = can::DriveFrameKind::Actual; actual.epoch = epoch_; actual.sequence = sequence_;
    actual.source_time_ns = measured.fresh ? measured.fresh->source_time_ns : now_ns;
    if (measured.fresh) actual.torque_nm = measured.fresh->torque_nm;
    const auto& accepted = command_.last_accepted(); actual.causal_sequence = accepted ? accepted->message.sequence : 0;
    actual.local_state = decision_.fault != DriveGateFault::None ? can::ActuatorLocalState::FailSafe : !decision_.active ? can::ActuatorLocalState::Init :
        (decision_.selected_target_nm != *in.command->torque_nm || decision_.actual_outside_envelope ||
         decision_.regen_reason != can::DriveRegenLimitReason::Nominal || in.command->local_state == can::ActuatorLocalState::Degraded) ?
            can::ActuatorLocalState::Degraded : can::ActuatorLocalState::Normal;
    actual.origin = decision_.fault != DriveGateFault::None ? can::ActuatorOrigin::LocalProtection :
        accepted ? can::ActuatorOrigin::NormalPath : can::ActuatorOrigin::NoAcceptedInput;
    if (in.speed) actual.wheel_speed = can::DriveWheelSpeed{in.speed->value, in.speed->identity.source_time_ns};
    if (decision_.regen_limit_nm && actual.wheel_speed &&
        (!last_capability_input_ns_ || decision_.capability_input_time_ns >= *last_capability_input_ns_)) {
        actual.regen_capability = can::DriveRegenCapability{*decision_.regen_limit_nm, now_ns, decision_.capability_input_time_ns};
        actual.regen_limit_reason = decision_.regen_reason;
        last_capability_input_ns_ = decision_.capability_input_time_ns;
    }
    const auto result = can::encode_drive_frame(actual, tx_);
    if (result) {
        if (sequence_ == std::numeric_limits<std::uint32_t>::max()) { fail(DriveGateFault::SequenceExhausted, now_ns); stopped_ = true; }
        else ++sequence_;
    }
    return result;
}
}  // namespace stratadrive::vecu
