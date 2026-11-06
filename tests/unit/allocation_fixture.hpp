#pragma once
#include "control_allocation.hpp"

namespace allocation_fixture {
using namespace stratadrive;
constexpr std::uint64_t kStart = 1000000000, kMs = 1000000;
inline std::uint64_t ns(std::uint32_t ms) { return kStart+static_cast<std::uint64_t>(ms)*kMs; }
template <typename Message>
void meta(Message& m, std::uint32_t ms) {
    m.epoch = 3; m.sequence = ms/20; m.source_time_ns = ns(ms);
    m.origin = can::ActuatorOrigin::NormalPath; m.local_state = can::ActuatorLocalState::Normal;
}
inline central::AllocationInputs inputs(std::uint32_t ms) {
    central::AllocationInputs in; auto& f = in.feedback; f.epoch = 3; f.session_enable_ns = kStart;
    f.front.health.emplace(); meta(*f.front.health, ms); f.front.health->ready_for_normal = true;
    f.rear.health.emplace(); meta(*f.rear.health, ms); f.rear.health->ready_for_normal = true;
    f.front.health->phase=f.rear.health->phase=zone::ZonePhase::Ready;
    f.rear.health->scope=zone::ZoneScope::Rear;
    f.front.steering_actual.emplace(); meta(*f.front.steering_actual, ms);
    f.front.steering_actual->kind = can::SteeringFrameKind::Actual; f.front.steering_actual->angle_rad = 0;
    f.front.brake_actual.emplace(); meta(*f.front.brake_actual, ms);
    f.front.brake_actual->kind = can::BrakeFrameKind::Actual; f.front.brake_actual->pressure_pa = 0;
    f.rear.drive_actual.emplace(); meta(*f.rear.drive_actual, ms);
    f.rear.drive_actual->kind = can::DriveFrameKind::Actual; f.rear.drive_actual->torque_nm = 0;
    f.rear.drive_actual->wheel_speed = can::DriveWheelSpeed{20, ns(ms)};
    f.rear.drive_actual->regen_capability = can::DriveRegenCapability{200, ns(ms), ns(ms)};
    f.rear.drive_actual->regen_limit_reason = can::DriveRegenLimitReason::Nominal;
    const can::BmsQualities usable{can::BmsFieldQuality::Usable, can::BmsFieldQuality::Usable, can::BmsFieldQuality::NotApplicable};
    f.rear.power_status = can::BmsCurrentSample{can::BmsMessage{}, usable}; auto& status = f.rear.power_status->message;
    meta(status, ms); status.kind = can::BmsFrameKind::PowerStatus;
    can::BmsPowerStatus actual; actual.state = can::BmsPowerState::HvReady;
    actual.positive_contactor_closed = actual.negative_contactor_closed = true; actual.precharge_contactor_closed = false;
    actual.condition_bits = 7; actual.condition_validity = 31; actual.hv_bus_voltage_v = 400;
    actual.input_time_ns = ns(ms); actual.input_sequence = ms/20; status.content = actual;
    f.rear.power_limits = can::BmsCurrentSample{can::BmsMessage{}, usable}; auto& limits = f.rear.power_limits->message;
    meta(limits, ms); limits.kind = can::BmsFrameKind::PowerLimits;
    limits.content = can::BmsPowerLimits{30000, 80000, can::BmsLimitReason::Nominal, can::BmsLimitReason::Nominal, ns(ms)};
    in.management.state = central::VehicleManagementState::Normal; in.management.normal_allowed = true;
    in.permission = can::BmsCurrentSample{can::BmsMessage{}, {can::BmsFieldQuality::Usable, can::BmsFieldQuality::NotApplicable, can::BmsFieldQuality::NotApplicable}};
    auto& permission = in.permission->message; meta(permission, ms); permission.kind = can::BmsFrameKind::DrivePermission;
    permission.causal_sequence = 1000+ms/20;
    permission.content = can::BmsDriveGrant{can::BmsDrivePermission::AllowNormal, status.sequence, ns(ms), ns(ms), ns(ms+30)};
    in.permission_parent = can::BmsParentContext{3, permission.causal_sequence, ns(ms), ns(ms+60)};
    return in;
}
} // namespace allocation_fixture
