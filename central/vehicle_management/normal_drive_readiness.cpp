#include "normal_drive_readiness.hpp"

#include <algorithm>
#include <cmath>

namespace stratadrive::central {
namespace {
bool fresh(std::uint64_t time, std::uint64_t maximum, const NormalDriveReadinessInputs& inputs,
           std::uint64_t now) {
    return time >= inputs.session_enable_ns && time <= now && now - time <= maximum;
}
template <typename Message>
bool current(const Message& message, std::uint64_t maximum, const NormalDriveReadinessInputs& inputs,
             std::uint64_t now) {
    return message.epoch == inputs.epoch && fresh(message.source_time_ns, maximum, inputs, now);
}
template <typename Message>
bool normal(const Message& message) {
    return message.local_state == can::ActuatorLocalState::Normal &&
           message.origin == can::ActuatorOrigin::NormalPath;
}
template <typename Message>
bool actuator_available(const Message& message) {
    // Known non-driving INIT Actual must precede permission, avoiding a startup
    // cycle where the Leaf needs permission before it can publish any feedback.
    return normal(message) || (message.local_state == can::ActuatorLocalState::Init &&
           (message.origin == can::ActuatorOrigin::NoAcceptedInput ||
            message.origin == can::ActuatorOrigin::NormalPath));
}
bool finite(const std::optional<double>& value) { return value && std::isfinite(*value); }
bool drive_available(const can::DriveMessage& m,const NormalDriveReadinessInputs& in,std::uint64_t now,const ReadinessTiming& timing) {
    if(actuator_available(m)) return true;
    if(m.local_state!=can::ActuatorLocalState::Degraded || m.origin!=can::ActuatorOrigin::NormalPath ||
        !finite(m.torque_nm) || !can::actuator_value_in_range(*m.torque_nm,{-200,300}) || !m.wheel_speed || !m.regen_capability ||
        static_cast<unsigned>(m.regen_limit_reason)>static_cast<unsigned>(can::DriveRegenLimitReason::Disabled)) return false;
    const auto& speed=*m.wheel_speed; const auto& cap=*m.regen_capability;
    return can::actuator_value_in_range(speed.value_rad_s,{0,100}) && can::actuator_value_in_range(cap.torque_limit_nm,{0,200}) &&
        fresh(speed.source_time_ns,timing.actual_source_age_ns,in,now) && fresh(cap.source_time_ns,timing.actual_source_age_ns,in,now) &&
        cap.input_time_ns<=cap.source_time_ns && fresh(cap.input_time_ns,timing.bms_dependency_age_ns,in,now) &&
        (m.regen_limit_reason!=can::DriveRegenLimitReason::Disabled || cap.torque_limit_nm==0);
}
bool constrained_limits(const can::BmsCurrentSample& sample) {
    const auto* limit=std::get_if<can::BmsPowerLimits>(&sample.message.content);
    if(!limit || sample.message.local_state!=can::ActuatorLocalState::Degraded || sample.message.origin!=can::ActuatorOrigin::NormalPath) return false;
    const auto direction=[](const std::optional<double>& value,can::BmsLimitReason reason) {
        return value && can::actuator_value_in_range(*value,{0,100000}) &&
            static_cast<unsigned>(reason)<=static_cast<unsigned>(can::BmsLimitReason::Disabled) &&
            (reason!=can::BmsLimitReason::Disabled || *value==0);
    };
    return direction(limit->charge_power_w,limit->charge_reason) && direction(limit->discharge_power_w,limit->discharge_reason) &&
        (limit->charge_reason!=can::BmsLimitReason::Nominal || limit->discharge_reason!=can::BmsLimitReason::Nominal);
}
}  // namespace

bool NormalDriveReadiness::ready() const {
    return std::none_of(blocked.begin(), blocked.end(), [](bool value) { return value; });
}
bool NormalDriveReadiness::is_blocked(ReadinessBlock reason) const {
    const auto index = static_cast<std::size_t>(reason);
    return index >= blocked.size() || blocked[index];
}

namespace {
NormalDriveReadiness evaluate(
    const NormalDriveReadinessInputs& inputs, std::uint64_t now_ns, const ReadinessTiming& timing,
    bool normal_drive) {
    NormalDriveReadiness result;
    // Do not silently widen the existing component budgets. Different vehicle
    // timing needs a reviewed contract, not an arbitrarily permissive parameter.
    if (inputs.epoch == 0 || now_ns < inputs.session_enable_ns ||
        timing.zone_source_age_ns == 0 || timing.zone_source_age_ns > 30000000ULL ||
        timing.actual_source_age_ns == 0 || timing.actual_source_age_ns > 30000000ULL ||
        timing.bms_source_age_ns == 0 || timing.bms_source_age_ns > 50000000ULL ||
        timing.bms_dependency_age_ns == 0 || timing.bms_dependency_age_ns > 70000000ULL) return result;

    auto oldest = now_ns;
    const auto record = [&](ReadinessBlock reason, bool usable, std::uint64_t source) {
        result.blocked[static_cast<std::size_t>(reason)] = !usable;
        if (usable) oldest = std::min(oldest, source);
    };
    record(ReadinessBlock::Context, true, now_ns);
    const auto zone = [&](ReadinessBlock reason, const std::optional<ZoneHealthSnapshot>& sample) {
        record(reason, sample && current(*sample, timing.zone_source_age_ns, inputs, now_ns) &&
               normal(*sample) && sample->ready_for_normal, sample ? sample->source_time_ns : 0);
    };
    zone(ReadinessBlock::FrontZone, inputs.front.health);
    zone(ReadinessBlock::RearZone, inputs.rear.health);

    const auto& steering = inputs.front.steering_actual;
    record(ReadinessBlock::SteeringActual, steering && steering->kind == can::SteeringFrameKind::Actual &&
           current(*steering, timing.actual_source_age_ns, inputs, now_ns) && actuator_available(*steering) &&
           finite(steering->angle_rad), steering ? steering->source_time_ns : 0);
    const auto& brake = inputs.front.brake_actual;
    record(ReadinessBlock::BrakeActual, brake && brake->kind == can::BrakeFrameKind::Actual &&
           current(*brake, timing.actual_source_age_ns, inputs, now_ns) && actuator_available(*brake) &&
           finite(brake->pressure_pa) && *brake->pressure_pa >= 0, brake ? brake->source_time_ns : 0);
    const auto& drive = inputs.rear.drive_actual;
    record(ReadinessBlock::DriveActual, drive && drive->kind == can::DriveFrameKind::Actual &&
           current(*drive, timing.actual_source_age_ns, inputs, now_ns) && drive_available(*drive,inputs,now_ns,timing) &&
           finite(drive->torque_nm), drive ? drive->source_time_ns : 0);

    const auto& power = inputs.rear.power_status;
    const auto* status = power ? std::get_if<can::BmsPowerStatus>(&power->message.content) : nullptr;
    record(ReadinessBlock::PowerStatus, power && status && power->message.kind == can::BmsFrameKind::PowerStatus &&
           current(power->message, timing.bms_source_age_ns, inputs, now_ns) &&
           (normal_drive ? normal(power->message) : actuator_available(power->message)) &&
           status->input_time_ns <= power->message.source_time_ns &&
           fresh(status->input_time_ns, timing.bms_dependency_age_ns, inputs, now_ns) &&
           power->quality[0] == can::BmsFieldQuality::Usable && power->quality[1] == can::BmsFieldQuality::Usable &&
           status->state && status->positive_contactor_closed && status->negative_contactor_closed &&
           status->precharge_contactor_closed && status->condition_validity == 31 &&
           finite(status->hv_bus_voltage_v) && *status->hv_bus_voltage_v >= 0 &&
           (!normal_drive || can::bms_power_is_ready(*power)),
           status ? status->input_time_ns : 0);

    const auto& limits = inputs.rear.power_limits;
    const auto* limit = limits ? std::get_if<can::BmsPowerLimits>(&limits->message.content) : nullptr;
    record(ReadinessBlock::PowerLimits, limits && limit &&
           limits->message.kind == can::BmsFrameKind::PowerLimits &&
           current(limits->message, timing.bms_source_age_ns, inputs, now_ns) &&
           ((normal_drive ? normal(limits->message) : actuator_available(limits->message)) || constrained_limits(*limits)) &&
           limits->quality[0] == can::BmsFieldQuality::Usable && limits->quality[1] == can::BmsFieldQuality::Usable &&
           finite(limit->charge_power_w) && *limit->charge_power_w >= 0 &&
           finite(limit->discharge_power_w) && *limit->discharge_power_w >= 0 &&
           limit->input_time_ns <= limits->message.source_time_ns &&
           fresh(limit->input_time_ns, timing.bms_dependency_age_ns, inputs, now_ns),
           limit ? limit->input_time_ns : 0);
    if (result.ready()) result.oldest_input_time_ns = oldest;
    return result;
}
}  // namespace
NormalDriveReadiness evaluate_normal_drive_readiness(
    const NormalDriveReadinessInputs& inputs, std::uint64_t now_ns, const ReadinessTiming& timing) {
    return evaluate(inputs, now_ns, timing, true);
}
NormalDriveReadiness evaluate_vehicle_input_health(
    const NormalDriveReadinessInputs& inputs, std::uint64_t now_ns, const ReadinessTiming& timing) {
    return evaluate(inputs, now_ns, timing, false);
}
}  // namespace stratadrive::central
