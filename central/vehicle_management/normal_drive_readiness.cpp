#include "normal_drive_readiness.hpp"

#include <algorithm>

namespace stratadrive::central {
namespace {
bool current(const ZoneHealthSnapshot& s,std::uint64_t age,const NormalDriveReadinessInputs& in,std::uint64_t now) {
    return s.epoch==in.epoch && s.source_time_ns>=in.session_enable_ns && s.source_time_ns<=now && now-s.source_time_ns<=age;
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
    const auto zone = [&](ReadinessBlock reason, const std::optional<ZoneHealthSnapshot>& sample,zone::ZoneScope scope) {
        record(reason, sample && sample->scope==scope && current(*sample,timing.zone_source_age_ns,inputs,now_ns) &&
               zone::zone_inputs_healthy(*sample) && (!normal_drive || sample->ready_for_normal),sample?sample->source_time_ns:0);
    };
    zone(ReadinessBlock::FrontZone, inputs.front.health,zone::ZoneScope::Front);
    zone(ReadinessBlock::RearZone, inputs.rear.health,zone::ZoneScope::Rear);
    const feedback::SourceContext context{inputs.epoch,inputs.session_enable_ns,now_ns,timing};
    const auto& steering=inputs.front.steering_actual;
    const auto& brake=inputs.front.brake_actual;
    const auto& drive=inputs.rear.drive_actual;
    const auto& power=inputs.rear.power_status;
    const auto& limits=inputs.rear.power_limits;
    const auto* status=power?std::get_if<can::BmsPowerStatus>(&power->message.content):nullptr;
    const auto* limit=limits?std::get_if<can::BmsPowerLimits>(&limits->message.content):nullptr;
    record(ReadinessBlock::SteeringActual,feedback::steering_available(steering,context),steering?steering->source_time_ns:0);
    record(ReadinessBlock::BrakeActual,feedback::brake_available(brake,context),brake?brake->source_time_ns:0);
    record(ReadinessBlock::DriveActual,feedback::drive_available(drive,context),drive?drive->source_time_ns:0);
    record(ReadinessBlock::PowerStatus,feedback::power_available(power,context,normal_drive),status?status->input_time_ns:0);
    record(ReadinessBlock::PowerLimits,feedback::limits_available(limits,context,normal_drive),limit?limit->input_time_ns:0);
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
