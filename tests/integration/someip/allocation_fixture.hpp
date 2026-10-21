#pragma once
#include "control_allocation.hpp"

// Explicit local component inputs, adapted from control_allocation_test.cpp.
// Rear/management/permission values are SIL fixtures, not remotely obtained
// evidence and not SessionCoordinator Release ACKs. Never use in a vehicle.
inline stratadrive::central::AllocationInputs allocation_fixture(std::uint32_t epoch,std::uint32_t sequence,std::uint64_t start,std::uint64_t t) {
    using namespace stratadrive;
    const auto meta=[&](auto& m) {
        m.epoch=epoch;m.sequence=sequence;m.source_time_ns=t;
        m.origin=can::ActuatorOrigin::NormalPath;m.local_state=can::ActuatorLocalState::Normal;
    };
    central::AllocationInputs in;auto& f=in.feedback;f.epoch=epoch;f.session_enable_ns=start;
    f.front.health.emplace();meta(*f.front.health);f.front.health->ready_for_normal=true;
    f.rear.health.emplace();meta(*f.rear.health);f.rear.health->ready_for_normal=true;
    f.front.health->phase=f.rear.health->phase=zone::ZonePhase::Ready;f.rear.health->scope=zone::ZoneScope::Rear;
    f.front.steering_actual.emplace();meta(*f.front.steering_actual);f.front.steering_actual->kind=can::SteeringFrameKind::Actual;f.front.steering_actual->angle_rad=0;
    f.front.brake_actual.emplace();meta(*f.front.brake_actual);f.front.brake_actual->kind=can::BrakeFrameKind::Actual;f.front.brake_actual->pressure_pa=0;
    f.rear.drive_actual.emplace();meta(*f.rear.drive_actual);f.rear.drive_actual->kind=can::DriveFrameKind::Actual;f.rear.drive_actual->torque_nm=0;
    f.rear.drive_actual->wheel_speed=can::DriveWheelSpeed{20,t};f.rear.drive_actual->regen_capability=can::DriveRegenCapability{200,t,t};
    f.rear.drive_actual->regen_limit_reason=can::DriveRegenLimitReason::Nominal;
    const can::BmsQualities usable{can::BmsFieldQuality::Usable,can::BmsFieldQuality::Usable,can::BmsFieldQuality::NotApplicable};
    f.rear.power_status=can::BmsCurrentSample{can::BmsMessage{},usable};auto& status=f.rear.power_status->message;
    meta(status);status.kind=can::BmsFrameKind::PowerStatus;
    can::BmsPowerStatus actual;actual.state=can::BmsPowerState::HvReady;
    actual.positive_contactor_closed=actual.negative_contactor_closed=true;actual.precharge_contactor_closed=false;
    actual.condition_bits=7;actual.condition_validity=31;actual.hv_bus_voltage_v=400;actual.input_time_ns=t;actual.input_sequence=sequence;status.content=actual;
    f.rear.power_limits=can::BmsCurrentSample{can::BmsMessage{},usable};auto& limits=f.rear.power_limits->message;
    meta(limits);limits.kind=can::BmsFrameKind::PowerLimits;
    limits.content=can::BmsPowerLimits{30000,80000,can::BmsLimitReason::Nominal,can::BmsLimitReason::Nominal,t};
    in.management.state=central::VehicleManagementState::Normal;in.management.normal_allowed=true;
    in.permission=can::BmsCurrentSample{can::BmsMessage{},{can::BmsFieldQuality::Usable,can::BmsFieldQuality::NotApplicable,can::BmsFieldQuality::NotApplicable}};
    auto& permission=in.permission->message;meta(permission);permission.kind=can::BmsFrameKind::DrivePermission;permission.causal_sequence=1000+sequence;
    permission.content=can::BmsDriveGrant{can::BmsDrivePermission::AllowNormal,status.sequence,t,t,t+30000000ULL};
    in.permission_parent=can::BmsParentContext{epoch,permission.causal_sequence,t,t+60000000ULL};return in;
}
