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
}  // namespace

bool NormalDriveReadiness::ready() const {
    return std::none_of(blocked.begin(), blocked.end(), [](bool value) { return value; });
}
bool NormalDriveReadiness::is_blocked(ReadinessBlock reason) const {
    const auto index = static_cast<std::size_t>(reason);
    return index >= blocked.size() || blocked[index];
}

NormalDriveReadiness evaluate_normal_drive_readiness(
    const NormalDriveReadinessInputs& inputs, std::uint64_t now_ns, const ReadinessTiming& timing) {
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
           current(*drive, timing.actual_source_age_ns, inputs, now_ns) && actuator_available(*drive) &&
           finite(drive->torque_nm), drive ? drive->source_time_ns : 0);

    const auto& power = inputs.rear.power_status;
    const auto* status = power ? std::get_if<can::BmsPowerStatus>(&power->message.content) : nullptr;
    record(ReadinessBlock::PowerStatus, power && status &&
           current(power->message, timing.bms_source_age_ns, inputs, now_ns) && normal(power->message) &&
           status->input_time_ns <= power->message.source_time_ns &&
           fresh(status->input_time_ns, timing.bms_dependency_age_ns, inputs, now_ns) &&
           can::bms_power_is_ready(*power) && finite(status->hv_bus_voltage_v),
           status ? status->input_time_ns : 0);

    const auto& limits = inputs.rear.power_limits;
    const auto* limit = limits ? std::get_if<can::BmsPowerLimits>(&limits->message.content) : nullptr;
    record(ReadinessBlock::PowerLimits, limits && limit &&
           limits->message.kind == can::BmsFrameKind::PowerLimits &&
           current(limits->message, timing.bms_source_age_ns, inputs, now_ns) && normal(limits->message) &&
           limits->quality[0] == can::BmsFieldQuality::Usable && limits->quality[1] == can::BmsFieldQuality::Usable &&
           finite(limit->charge_power_w) && *limit->charge_power_w >= 0 &&
           finite(limit->discharge_power_w) && *limit->discharge_power_w >= 0 &&
           limit->input_time_ns <= limits->message.source_time_ns &&
           fresh(limit->input_time_ns, timing.bms_dependency_age_ns, inputs, now_ns),
           limit ? limit->input_time_ns : 0);
    if (result.ready()) result.oldest_input_time_ns = oldest;
    return result;
}
}  // namespace stratadrive::central
