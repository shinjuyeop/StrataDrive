#include "feedback_health.hpp"

#include <cmath>

namespace stratadrive::feedback {
namespace {
bool valid_context(const SourceContext& c) {
    return c.epoch!=0 && c.now_ns>=c.session_enable_ns &&
        c.timing.actual_source_age_ns>0 && c.timing.actual_source_age_ns<=30000000ULL &&
        c.timing.bms_source_age_ns>0 && c.timing.bms_source_age_ns<=50000000ULL &&
        c.timing.bms_dependency_age_ns>0 && c.timing.bms_dependency_age_ns<=70000000ULL;
}
bool fresh(std::uint64_t time, std::uint64_t maximum, const SourceContext& inputs,
           std::uint64_t now) {
    return time >= inputs.session_enable_ns && time <= now && now - time <= maximum;
}
template <typename Message>
bool current(const Message& message, std::uint64_t maximum, const SourceContext& inputs,
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
bool drive_available(const can::DriveMessage& m,const SourceContext& in,std::uint64_t now,const FeedbackTiming& timing) {
    if(actuator_available(m)) return true;
    if(m.local_state!=can::ActuatorLocalState::Degraded || m.origin!=can::ActuatorOrigin::NormalPath ||
        !finite(m.torque_nm) || !can::actuator_value_in_range(*m.torque_nm,{-200,300}) || !m.wheel_speed ||
        static_cast<unsigned>(m.regen_limit_reason)>static_cast<unsigned>(can::DriveRegenLimitReason::InputsInvalid)) return false;
    const auto& speed=*m.wheel_speed;
    if(!can::actuator_value_in_range(speed.value_rad_s,{0,100}) || !fresh(speed.source_time_ns,timing.actual_source_age_ns,in,now)) return false;
    // Optional regen capability may be unavailable while a new permission's
    // older dependency catches up with the capability cursor. This is not a
    // loss of measured torque/speed: allocation must use its friction fallback.
    if(!m.regen_capability) return m.regen_limit_reason==can::DriveRegenLimitReason::InputsInvalid;
    const auto& cap=*m.regen_capability;
    return m.regen_limit_reason!=can::DriveRegenLimitReason::InputsInvalid && can::actuator_value_in_range(cap.torque_limit_nm,{0,200}) && fresh(cap.source_time_ns,timing.actual_source_age_ns,in,now) &&
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

bool steering_available(const std::optional<can::SteeringMessage>& s,const SourceContext& c) {
    return valid_context(c) && s && s->kind==can::SteeringFrameKind::Actual && current(*s,c.timing.actual_source_age_ns,c,c.now_ns) &&
        actuator_available(*s) && finite(s->angle_rad);
}
bool brake_available(const std::optional<can::BrakeMessage>& s,const SourceContext& c) {
    return valid_context(c) && s && s->kind==can::BrakeFrameKind::Actual && current(*s,c.timing.actual_source_age_ns,c,c.now_ns) &&
        actuator_available(*s) && finite(s->pressure_pa) && *s->pressure_pa>=0;
}
bool drive_available(const std::optional<can::DriveMessage>& s,const SourceContext& c) {
    return valid_context(c) && s && s->kind==can::DriveFrameKind::Actual && current(*s,c.timing.actual_source_age_ns,c,c.now_ns) &&
        drive_available(*s,c,c.now_ns,c.timing) && finite(s->torque_nm);
}
bool power_available(const std::optional<can::BmsCurrentSample>& power,const SourceContext& c,bool normal_drive) {
    const auto* status = power ? std::get_if<can::BmsPowerStatus>(&power->message.content) : nullptr;
    return valid_context(c) && power && status && power->message.kind == can::BmsFrameKind::PowerStatus &&
           current(power->message, c.timing.bms_source_age_ns, c, c.now_ns) &&
           (normal_drive ? normal(power->message) : actuator_available(power->message)) &&
           status->input_time_ns <= power->message.source_time_ns &&
           fresh(status->input_time_ns, c.timing.bms_dependency_age_ns, c, c.now_ns) &&
           power->quality[0] == can::BmsFieldQuality::Usable && power->quality[1] == can::BmsFieldQuality::Usable &&
           status->state && status->positive_contactor_closed && status->negative_contactor_closed &&
           status->precharge_contactor_closed && status->condition_validity == 31 &&
           finite(status->hv_bus_voltage_v) && *status->hv_bus_voltage_v >= 0 &&
           (!normal_drive || can::bms_power_is_ready(*power));

}
bool limits_available(const std::optional<can::BmsCurrentSample>& limits,const SourceContext& c,bool normal_drive) {
    const auto* limit = limits ? std::get_if<can::BmsPowerLimits>(&limits->message.content) : nullptr;
    return valid_context(c) && limits && limit &&
           limits->message.kind == can::BmsFrameKind::PowerLimits &&
           current(limits->message, c.timing.bms_source_age_ns, c, c.now_ns) &&
           ((normal_drive ? normal(limits->message) : actuator_available(limits->message)) || constrained_limits(*limits)) &&
           limits->quality[0] == can::BmsFieldQuality::Usable && limits->quality[1] == can::BmsFieldQuality::Usable &&
           finite(limit->charge_power_w) && *limit->charge_power_w >= 0 &&
           finite(limit->discharge_power_w) && *limit->discharge_power_w >= 0 &&
           limit->input_time_ns <= limits->message.source_time_ns &&
           fresh(limit->input_time_ns, c.timing.bms_dependency_age_ns, c, c.now_ns);
}
}  // namespace stratadrive::feedback
