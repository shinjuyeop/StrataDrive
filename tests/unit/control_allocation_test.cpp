#include "control_allocation.hpp"
#include "command_admission.hpp"
#include "drive_sil_plant.hpp"
#include "brake_pressure_response.hpp"
#include "steering_receiver.hpp"
#include "brake_receiver.hpp"
#include "drive_receiver.hpp"
#include "steering_angle_codec.hpp"

#include <gtest/gtest.h>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace {
using namespace stratadrive;
using central::AllocationFault;
using central::AllocationState;
using central::AllocationReceiveDecision;
constexpr std::uint64_t kStart = 1000000000, kMs = 1000000;
std::uint64_t ns(std::uint32_t ms) { return kStart+static_cast<std::uint64_t>(ms)*kMs; }
template <typename Message>
void meta(Message& m, std::uint32_t ms) {
    m.epoch = 3; m.sequence = ms/20; m.source_time_ns = ns(ms);
    m.origin = can::ActuatorOrigin::NormalPath; m.local_state = can::ActuatorLocalState::Normal;
}
central::AllocationInputs inputs(std::uint32_t ms) {
    central::AllocationInputs in; auto& f = in.feedback; f.epoch = 3; f.session_enable_ns = kStart;
    f.front.health.emplace(); meta(*f.front.health, ms); f.front.health->ready_for_normal = true;
    f.rear.health.emplace(); meta(*f.rear.health, ms); f.rear.health->ready_for_normal = true;
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
class ControlAllocationTest : public ::testing::Test {
protected:
    central::ControlAllocation allocator;
    std::optional<central::AllocatedCommands> out;
    std::uint32_t sequence{0};
    double acceleration{0}, braking{0}, curvature{0}; bool hold{false};
    void SetUp() override { ASSERT_TRUE(allocator.start_session(3, kStart)); }
    central::VehicleRequest request(std::uint32_t ms) {
        return {3, sequence++, ns(ms), ns(ms+60), acceleration, curvature, braking, hold};
    }
    void submit(std::uint32_t ms) { ASSERT_EQ(allocator.receive_request(request(ms), ns(ms)), AllocationReceiveDecision::Accepted); }
    void step(std::uint32_t ms, const central::AllocationInputs& in) { submit(ms); out = allocator.tick(in, ns(ms)); }
    void step(std::uint32_t ms) { step(ms, inputs(ms)); }
    void expect_fault(AllocationFault fault) const {
        EXPECT_FALSE(out); EXPECT_EQ(allocator.decision().state, AllocationState::FailSafe);
        EXPECT_EQ(allocator.decision().fault, fault); EXPECT_TRUE(allocator.decision().protection_required);
    }
};
TEST(ControlAllocationConfig, RejectsInvalidCalibrationAndWideTiming) {
    central::AllocationConfig c; c.friction_nm_per_pa = 0; EXPECT_THROW(central::ControlAllocation{c}, std::invalid_argument);
    c = {}; c.mass_kg = std::numeric_limits<double>::infinity(); EXPECT_THROW(central::ControlAllocation{c}, std::invalid_argument);
    c = {}; c.hold_speed_rad_s = 2; EXPECT_THROW(central::ControlAllocation{c}, std::invalid_argument);
    c = {}; c.low_speed_exit_rad_s = 1; EXPECT_THROW(central::ControlAllocation{c}, std::invalid_argument);
    c = {}; c.max_tick_gap_ns = 30000001; EXPECT_THROW(central::ControlAllocation{c}, std::invalid_argument);
    c = {}; c.request_source_age_ns = 30000001; EXPECT_THROW(central::ControlAllocation{c}, std::invalid_argument);
    c = {}; c.readiness.bms_dependency_age_ns = 70000001; EXPECT_THROW(central::ControlAllocation{c}, std::invalid_argument);
    c = {}; c.response_dwell_ns = 0; EXPECT_THROW(central::ControlAllocation{c}, std::invalid_argument);
    c = {}; c.motoring_efficiency_lower_bound = 1.1; EXPECT_THROW(central::ControlAllocation{c}, std::invalid_argument);
}
TEST(ControlAllocationSession, NoOutputBeforeInitAndOnlyNewerTrustedInitRecovers) {
    central::ControlAllocation a; EXPECT_FALSE(a.tick(inputs(20), ns(20)));
    EXPECT_FALSE(a.start_session(0, kStart)); ASSERT_TRUE(a.start_session(3, kStart));
    a.mark_continuity_lost(ns(20)); EXPECT_FALSE(a.start_session(3, ns(20))); EXPECT_FALSE(a.start_session(4, kStart));
    ASSERT_TRUE(a.start_session(4, ns(20))); EXPECT_EQ(a.decision().state, AllocationState::Waiting);
}
TEST_F(ControlAllocationTest, MapsAccelerationAndCurvatureToWheelTorqueAndRoadWheelAngle) {
    acceleration = 1; curvature = 0.1; step(20); ASSERT_TRUE(out);
    EXPECT_DOUBLE_EQ(*out->drive.torque_nm, 300); EXPECT_DOUBLE_EQ(*out->brake.pressure_pa, 0);
    EXPECT_NEAR(*out->steering.angle_rad, std::atan(2.7*0.1), can::kAngleResolutionRad);
    EXPECT_EQ(out->parent.source_time_ns, ns(20)); EXPECT_EQ(out->drive.causal_sequence, out->parent.sequence);
}
TEST_F(ControlAllocationTest, RealAllocatorOutputsPassIndependentScopedZoneAdmission) {
    zone::CommandAdmission front{zone::ZoneScope::Front}, rear{zone::ZoneScope::Rear};
    ASSERT_TRUE(front.start_session(3, kStart)); ASSERT_TRUE(rear.start_session(3, kStart));
    ASSERT_TRUE(front.arm(kStart)); ASSERT_TRUE(rear.arm(kStart));
    for (std::uint32_t ms = 20; ms <= 200; ms += 20) {
        braking = 400.0/1500; const auto root = request(ms);
        ASSERT_EQ(allocator.receive_request(root, ns(ms)), AllocationReceiveDecision::Accepted);
        ASSERT_EQ(front.authorize_request(root, ns(ms)), zone::AdmissionResult::Accepted);
        ASSERT_EQ(rear.authorize_request(root, ns(ms)), zone::AdmissionResult::Accepted);
        out = allocator.tick(inputs(ms), ns(ms)); ASSERT_TRUE(out);
        ASSERT_EQ(front.receive(central::front_commands(*out), ns(ms)), zone::AdmissionResult::Accepted);
        ASSERT_EQ(rear.receive(central::rear_commands(*out), ns(ms)), zone::AdmissionResult::Accepted);
        ASSERT_TRUE(front.current_command(ns(ms+9))); ASSERT_TRUE(rear.current_command(ns(ms+9)));
        const auto accepted = std::get<central::RearCommands>(*rear.current_command(ns(ms+9)));
        EXPECT_EQ(accepted.drive.source_time_ns, out->drive.source_time_ns);
        EXPECT_EQ(accepted.expires_at_ns, out->expires_at_ns); EXPECT_TRUE(central::same_vehicle_request(accepted.parent, root));
    }
    EXPECT_FALSE(front.current_command(out->expires_at_ns)); EXPECT_TRUE(front.decision().protection_required);
    EXPECT_FALSE(rear.current_command(out->expires_at_ns)); EXPECT_TRUE(rear.decision().protection_required);
}
TEST_F(ControlAllocationTest, SaturatesSteeringAndPropulsionWithoutInventingAchievedAcceleration) {
    acceleration = 2; curvature = -1; step(20); ASSERT_TRUE(out);
    EXPECT_GE(*out->steering.angle_rad, -0.3); EXPECT_TRUE(allocator.decision().steering_limited);
    EXPECT_EQ(*out->drive.torque_nm, 300); EXPECT_EQ(allocator.decision().propulsion_deficit_nm, 300);
}
TEST_F(ControlAllocationTest, BrakingWinsOverPositiveAccelerationAndDemandsAreNotAdded) {
    acceleration = 1; braking = 400.0/1500; step(20); ASSERT_TRUE(out);
    EXPECT_TRUE(allocator.decision().brake_priority); EXPECT_NEAR(*allocator.decision().requested_braking_nm, 400, 1e-9);
    EXPECT_NEAR(*out->drive.torque_nm, -200, 0.1); EXPECT_NEAR(*out->brake.pressure_pa, 200000, 1000);
    acceleration = -1; step(40); ASSERT_TRUE(out);
    EXPECT_NEAR(*allocator.decision().requested_braking_nm, 400, 1e-9); // max(300,400), not 700
}
TEST_F(ControlAllocationTest, UsesRegenAloneWhenItCanCoverTheInitialDemand) {
    braking = 100.0/1500; step(20); ASSERT_TRUE(out);
    EXPECT_NEAR(*out->drive.torque_nm, -100, 0.1); EXPECT_EQ(*out->brake.pressure_pa, 0);
    EXPECT_NEAR(*allocator.decision().actual_braking_nm, 0, 1e-9);
    EXPECT_NEAR(*allocator.decision().deficit_nm, 100, 1e-9); EXPECT_TRUE(allocator.decision().response_pending);
}
TEST_F(ControlAllocationTest, KnownZeroAndUnavailableCapabilityUseFrictionButMissingTorqueDoesNot) {
    braking = 200.0/1500; auto in = inputs(20);
    in.feedback.rear.drive_actual->regen_capability->torque_limit_nm = 0;
    step(20, in); ASSERT_TRUE(out); EXPECT_EQ(*out->drive.torque_nm, 0); EXPECT_NEAR(*out->brake.pressure_pa, 200000, 1000);
    EXPECT_EQ(allocator.decision().regen, central::RegenAvailability::Usable);
    in = inputs(40); in.feedback.rear.drive_actual->regen_capability.reset(); step(40, in);
    ASSERT_TRUE(out); EXPECT_EQ(allocator.decision().regen, central::RegenAvailability::Unavailable);
    in = inputs(60); in.feedback.rear.drive_actual->torque_nm.reset(); step(60, in); expect_fault(AllocationFault::CriticalFeedback);
}
TEST_F(ControlAllocationTest, StaleOrInvalidCapabilityNeverAuthorizesNewNegativeTorque) {
    braking = 200.0/1500; auto in = inputs(20);
    in.feedback.rear.drive_actual->regen_capability->source_time_ns = kStart-1;
    step(20, in); ASSERT_TRUE(out); EXPECT_EQ(*out->drive.torque_nm, 0);
    EXPECT_EQ(allocator.decision().regen, central::RegenAvailability::Invalid); // input > source is malformed, not merely old
    in = inputs(40); in.feedback.rear.drive_actual->regen_capability = can::DriveRegenCapability{200,kStart,kStart};
    step(40, in); ASSERT_TRUE(out); EXPECT_EQ(*out->drive.torque_nm, 0);
    EXPECT_EQ(allocator.decision().regen, central::RegenAvailability::Stale);
    in = inputs(60); in.feedback.rear.drive_actual->regen_capability->torque_limit_nm = -1;
    step(60,in); ASSERT_TRUE(out); EXPECT_EQ(*out->drive.torque_nm,0);
    EXPECT_EQ(allocator.decision().regen, central::RegenAvailability::Invalid);
}
TEST_F(ControlAllocationTest, CurrentChargeLimitContractsACachedRegenCapability) {
    braking = 400.0/1500; auto in = inputs(20);
    std::get<can::BmsPowerLimits>(in.feedback.rear.power_limits->message.content).charge_power_w = 1000;
    step(20, in); ASSERT_TRUE(out); EXPECT_NEAR(*out->drive.torque_nm, -50, 0.1);
    EXPECT_NEAR(*out->brake.pressure_pa, 350000, 1000);
}
TEST_F(ControlAllocationTest, BmsDischargeAndMechanicalBoundsApplyAtSpeedAndStandstill) {
    acceleration = 2; auto in = inputs(20);
    std::get<can::BmsPowerLimits>(in.feedback.rear.power_limits->message.content).discharge_power_w = 1000;
    step(20, in); ASSERT_TRUE(out); const auto torque = *out->drive.torque_nm;
    EXPECT_LE(torque*20/0.9+0.01*torque*torque+200, 1000+1e-9);
    in = inputs(40); in.feedback.rear.drive_actual->wheel_speed->value_rad_s = 0;
    std::get<can::BmsPowerLimits>(in.feedback.rear.power_limits->message.content).discharge_power_w = 500;
    step(40, in); ASSERT_TRUE(out); EXPECT_GT(*out->drive.torque_nm, 0);
    EXPECT_LE(0.01*(*out->drive.torque_nm)*(*out->drive.torque_nm)+200, 500+1e-9);
    in = inputs(60); in.feedback.rear.drive_actual->wheel_speed->value_rad_s = 100;
    step(60, in); ASSERT_TRUE(out); EXPECT_LE(*out->drive.torque_nm*100, 20000);
}
TEST_F(ControlAllocationTest, CapabilityContractionCreditsResidualActualBeforeAddingFriction) {
    braking = 400.0/1500; step(20); ASSERT_TRUE(out);
    auto in = inputs(40); in.feedback.rear.drive_actual->torque_nm = -200;
    in.feedback.front.brake_actual->pressure_pa = 200000;
    in.feedback.rear.drive_actual->regen_capability->torque_limit_nm = 0;
    step(40, in); ASSERT_TRUE(out); EXPECT_EQ(*out->drive.torque_nm, 0);
    EXPECT_NEAR(*out->brake.pressure_pa, 200000, 1000); // not 400000 on top of residual -200 Nm
    EXPECT_NEAR(*allocator.decision().actual_braking_nm, 400, 1e-9);
    in = inputs(60); in.feedback.rear.drive_actual->torque_nm = -100;
    in.feedback.front.brake_actual->pressure_pa = 200000;
    step(60, in); ASSERT_TRUE(out); EXPECT_NEAR(*out->brake.pressure_pa, 300000, 1000);
    EXPECT_EQ(*out->drive.torque_nm, 0); // recovered capability does not restore torque during this braking interval
}
TEST_F(ControlAllocationTest, RegenMayReturnOnlyAfterARealReleaseAndANewBrakingInterval) {
    braking = 100.0/1500; auto in = inputs(20); in.feedback.rear.drive_actual->regen_capability.reset(); step(20, in); ASSERT_TRUE(out);
    step(40); ASSERT_TRUE(out); EXPECT_EQ(*out->drive.torque_nm, 0);
    braking = 0; step(60); ASSERT_TRUE(out);
    braking = 100.0/1500; step(80); ASSERT_TRUE(out); EXPECT_LT(*out->drive.torque_nm, 0);
}
TEST_F(ControlAllocationTest, LowSpeedHysteresisAndExplicitStandstillHoldUseFriction) {
    braking = 100.0/1500; auto in = inputs(20); in.feedback.rear.drive_actual->wheel_speed->value_rad_s = 2;
    step(20, in); ASSERT_TRUE(out); EXPECT_EQ(*out->drive.torque_nm, 0);
    braking = 0; in = inputs(40); in.feedback.rear.drive_actual->wheel_speed->value_rad_s = 2.5;
    step(40,in); // observed release while staying inside the hysteresis band
    braking = 100.0/1500; in = inputs(60); in.feedback.rear.drive_actual->wheel_speed->value_rad_s = 2.5;
    step(60, in); ASSERT_TRUE(out); EXPECT_EQ(*out->drive.torque_nm, 0);
    braking = 0; in = inputs(80); in.feedback.rear.drive_actual->wheel_speed->value_rad_s = 3;
    step(80,in);
    braking = 100.0/1500; in = inputs(100); in.feedback.rear.drive_actual->wheel_speed->value_rad_s = 2.5;
    step(100,in); ASSERT_TRUE(out); EXPECT_LT(*out->drive.torque_nm,0);
    braking = 0; hold = true; in = inputs(120); in.feedback.rear.drive_actual->wheel_speed->value_rad_s = 0;
    step(120, in); ASSERT_TRUE(out); EXPECT_NEAR(*out->brake.pressure_pa, 100000, 1000); EXPECT_EQ(*out->drive.torque_nm, 0);
    in = inputs(140); in.feedback.rear.drive_actual->wheel_speed->value_rad_s = 0.6;
    step(140,in); ASSERT_TRUE(out); EXPECT_TRUE(allocator.decision().hold_active);
    EXPECT_NEAR(*out->brake.pressure_pa,100000,1000);
    hold = false; step(160); ASSERT_TRUE(out); EXPECT_FALSE(allocator.decision().hold_active);
}
TEST_F(ControlAllocationTest, NoAutomaticHoldAndLaunchWaitsForMeasuredBrakeAndNegativeTorqueRelease) {
    acceleration = 1; auto in = inputs(20); in.feedback.front.brake_actual->pressure_pa = 100000;
    step(20, in); ASSERT_TRUE(out); EXPECT_EQ(*out->brake.pressure_pa, 0); EXPECT_EQ(*out->drive.torque_nm, 0);
    EXPECT_TRUE(allocator.decision().propulsion_waiting_release);
    in = inputs(40); in.feedback.rear.drive_actual->torque_nm = -100;
    step(40, in); ASSERT_TRUE(out); EXPECT_EQ(*out->drive.torque_nm, 0);
    step(60); ASSERT_TRUE(out); EXPECT_GT(*out->drive.torque_nm, 0);
}
TEST_F(ControlAllocationTest, ActualPositivePropulsionIsNotReportedAsRegenerativeBraking) {
    braking = 200.0/1500; auto in = inputs(20); in.feedback.rear.drive_actual->torque_nm = 100;
    step(20, in); ASSERT_TRUE(out); EXPECT_DOUBLE_EQ(*allocator.decision().actual_braking_nm, -100);
    EXPECT_NEAR(*allocator.decision().deficit_nm, 300, 1e-9);
}
TEST(ControlAllocationCapacity, ReportsUnservedBrakingAndRequestsProtectionInsteadOfAReleaseCommand) {
    central::AllocationConfig c; c.max_pressure_pa = 200000; central::ControlAllocation a(c);
    ASSERT_TRUE(a.start_session(3, kStart));
    ASSERT_EQ(a.receive_request({3,0,ns(20),ns(80),0,0,500.0/1500,false}, ns(20)), AllocationReceiveDecision::Accepted);
    EXPECT_FALSE(a.tick(inputs(20), ns(20))); EXPECT_EQ(a.decision().fault, AllocationFault::BrakingCapacity);
    EXPECT_TRUE(a.decision().protection_required); EXPECT_NEAR(a.decision().capacity_deficit_nm, 100, 1e-9);
}
TEST_F(ControlAllocationTest, WaitsForManagementAndPermissionBeforeIssuingNormalTargets) {
    submit(20); auto in = inputs(20); in.management.state = central::VehicleManagementState::Init; in.management.normal_allowed = false;
    out = allocator.tick(in, ns(20)); EXPECT_FALSE(out); EXPECT_EQ(allocator.decision().state, AllocationState::Waiting);
    step(40); ASSERT_TRUE(out);
    in = inputs(60); in.management.normal_allowed = false; step(60, in); expect_fault(AllocationFault::PermissionUnavailable);
}
TEST_F(ControlAllocationTest, PermissionNeedsItsSeparateLifecycleParentAndOriginalExpiry) {
    acceleration = 1; auto in = inputs(20); in.permission_parent.reset();
    step(20, in); EXPECT_FALSE(out); EXPECT_EQ(allocator.decision().state, AllocationState::Waiting);
    in = inputs(40); ++in.permission_parent->sequence; step(40, in); EXPECT_FALSE(out);
    in = inputs(60); std::get<can::BmsDriveGrant>(in.permission->message.content).expires_at_ns = ns(60);
    step(60, in); EXPECT_FALSE(out);
    step(80); ASSERT_TRUE(out); EXPECT_NE(out->parent.sequence, in.permission->message.causal_sequence);
}
TEST_F(ControlAllocationTest, CriticalFeedbackLossLatchesAndFreshDataCannotRecover) {
    step(20); ASSERT_TRUE(out); auto in = inputs(40); in.feedback.front.brake_actual.reset();
    step(40, in); expect_fault(AllocationFault::CriticalFeedback);
    EXPECT_EQ(allocator.receive_request(request(60), ns(60)), AllocationReceiveDecision::Latched);
    out = allocator.tick(inputs(60), ns(60)); expect_fault(AllocationFault::CriticalFeedback);
}
TEST_F(ControlAllocationTest, UnknownSpeedOrSkewedIndependentActualsAreNotSilentlyPaired) {
    submit(20); auto in = inputs(20); in.feedback.rear.drive_actual->wheel_speed.reset();
    out = allocator.tick(in, ns(20)); expect_fault(AllocationFault::WheelSpeedUnavailable);
}
TEST(ControlAllocationSkew, PreservesAsynchronousAuxiliaryTimesButRejectsAnUnboundedActualPair) {
    central::ControlAllocation a; ASSERT_TRUE(a.start_session(3,kStart));
    ASSERT_EQ(a.receive_request({3,0,ns(20),ns(80),0,0,0,false},ns(20)), AllocationReceiveDecision::Accepted);
    auto in = inputs(20); in.feedback.rear.drive_actual->source_time_ns = ns(10);
    EXPECT_TRUE(a.tick(in,ns(20))); // speed/capability acquisition at 20 may follow torque at 10
    ASSERT_EQ(a.receive_request({3,1,ns(40),ns(100),0,0,0,false},ns(40)), AllocationReceiveDecision::Accepted);
    in = inputs(40); in.feedback.front.brake_actual->source_time_ns = ns(19);
    EXPECT_FALSE(a.tick(in,ns(40))); EXPECT_EQ(a.decision().fault, AllocationFault::FeedbackSkew);
}
TEST_F(ControlAllocationTest, RequestIdentityIsImmutableAndCannotBeExtendedByReplay) {
    const auto r = request(20); ASSERT_EQ(allocator.receive_request(r,ns(20)), AllocationReceiveDecision::Accepted);
    EXPECT_EQ(allocator.receive_request(r,ns(20)), AllocationReceiveDecision::Unchanged);
    auto changed = r; ++changed.expires_at_ns;
    EXPECT_EQ(allocator.receive_request(changed,ns(20)), AllocationReceiveDecision::Invalid); // exceeds 60 ms lifetime
    changed = r; changed.acceleration_mps2 = 1;
    EXPECT_EQ(allocator.receive_request(changed,ns(20)), AllocationReceiveDecision::MutationRejected);
    changed = request(20); EXPECT_EQ(allocator.receive_request(changed,ns(20)), AllocationReceiveDecision::SequenceRejected);
}
TEST_F(ControlAllocationTest, RejectsInvalidUnitsRangeEpochAndFutureRequest) {
    auto r = request(20); r.epoch = 2; EXPECT_EQ(allocator.receive_request(r,ns(20)), AllocationReceiveDecision::EpochMismatch);
    r = request(20); r.braking_demand = 1.1; EXPECT_EQ(allocator.receive_request(r,ns(20)), AllocationReceiveDecision::Invalid);
    r = request(20); r.acceleration_mps2 = std::numeric_limits<double>::quiet_NaN(); EXPECT_EQ(allocator.receive_request(r,ns(20)), AllocationReceiveDecision::Invalid);
    r = request(40); EXPECT_EQ(allocator.receive_request(r,ns(20)), AllocationReceiveDecision::Invalid);
}
TEST_F(ControlAllocationTest, OriginalRequestExpiryIsCheckedBeforeLateFreshRoot) {
    auto r = request(20); r.expires_at_ns = ns(40);
    ASSERT_EQ(allocator.receive_request(r,ns(20)), AllocationReceiveDecision::Accepted); out = allocator.tick(inputs(20),ns(20)); ASSERT_TRUE(out);
    EXPECT_EQ(allocator.receive_request(request(40),ns(40)), AllocationReceiveDecision::Latched);
    out = allocator.tick(inputs(40),ns(40)); expect_fault(AllocationFault::RequestLost);
}
TEST_F(ControlAllocationTest, UsedCapabilityDependencyBoundsOutputButUnusedCapabilityDoesNotBlockPropulsion) {
    acceleration = 1; auto in = inputs(20); in.feedback.rear.drive_actual->regen_capability->input_time_ns = kStart;
    step(20,in); ASSERT_TRUE(out); EXPECT_EQ(out->oldest_input_time_ns, ns(20));
    acceleration = 0; braking = 100.0/1500; in = inputs(40);
    in.feedback.rear.drive_actual->regen_capability->input_time_ns = kStart;
    step(40,in); ASSERT_TRUE(out); EXPECT_EQ(out->oldest_input_time_ns, kStart);
    EXPECT_LE(out->expires_at_ns, kStart+70*kMs+1);
}
TEST_F(ControlAllocationTest, ExpiringOptionalCapabilityFallsBackBeforeItsDeadlineWithoutACriticalLossLatch) {
    braking = 100.0/1500; auto in = inputs(20); in.feedback.rear.drive_actual->regen_capability->input_time_ns = kStart;
    step(20,in); ASSERT_TRUE(out);
    in = inputs(40); in.feedback.rear.drive_actual->regen_capability->input_time_ns = kStart;
    step(40,in); ASSERT_TRUE(out);
    in = inputs(60); in.feedback.rear.drive_actual->regen_capability->input_time_ns = kStart;
    step(60,in); ASSERT_TRUE(out);
    EXPECT_EQ(allocator.decision().regen,central::RegenAvailability::Expiring);
    EXPECT_EQ(*out->drive.torque_nm,0); EXPECT_GT(*out->brake.pressure_pa,0);
    EXPECT_GT(out->expires_at_ns,ns(80));
    in = inputs(80); in.feedback.rear.drive_actual->regen_capability.reset(); step(80,in);
    ASSERT_TRUE(out); EXPECT_EQ(allocator.decision().fault,AllocationFault::None);
    EXPECT_EQ(*out->drive.torque_nm,0); EXPECT_GT(*out->brake.pressure_pa,0);
}
TEST_F(ControlAllocationTest, CriticalSupportExpiryIsCheckedBeforeLateFreshInputCanConcealIt) {
    step(20); ASSERT_TRUE(out);
    auto in=inputs(40); in.feedback.front.health->source_time_ns=ns(20);
    step(40,in); ASSERT_TRUE(out); EXPECT_EQ(out->expires_at_ns,ns(50)+1);
    EXPECT_EQ(allocator.receive_request(request(60),ns(60)),AllocationReceiveDecision::Latched);
    out=allocator.tick(inputs(60),ns(60)); expect_fault(AllocationFault::SupportExpired);
}
TEST_F(ControlAllocationTest, OptionalExpiryDuringAnAllowedSchedulingGapDropsRegenWithoutRevivingIt) {
    braking=100.0/1500; auto in=inputs(20);
    --in.feedback.rear.drive_actual->regen_capability->source_time_ns;
    --in.feedback.rear.drive_actual->regen_capability->input_time_ns;
    std::get<can::BmsDriveGrant>(in.permission->message.content).expires_at_ns=ns(60);
    step(20,in); ASSERT_TRUE(out); EXPECT_LT(*out->drive.torque_nm,0);
    EXPECT_EQ(out->expires_at_ns,ns(50));
    step(50); ASSERT_TRUE(out); // 30 ms is the declared maximum owner gap
    EXPECT_EQ(allocator.decision().fault,AllocationFault::None);
    EXPECT_EQ(*out->drive.torque_nm,0); EXPECT_GT(*out->brake.pressure_pa,0);
}
TEST_F(ControlAllocationTest, RepeatedEarlyTicksDoNotCreateNewCommandsAndGapsOrClockRollbackLatch) {
    step(20); ASSERT_TRUE(out); EXPECT_FALSE(allocator.tick(inputs(20),ns(20)));
    EXPECT_FALSE(allocator.tick(inputs(30),ns(30)));
    EXPECT_EQ(allocator.receive_request(request(60),ns(60)), AllocationReceiveDecision::Latched);
    out = allocator.tick(inputs(60),ns(60)); expect_fault(AllocationFault::ControlDeadline);
    EXPECT_FALSE(allocator.tick(inputs(40),ns(40))); EXPECT_EQ(allocator.decision().fault, AllocationFault::ClockError);
}
TEST_F(ControlAllocationTest, CommandsRoundTowardZeroAndKeepOriginalAncestryOutsideLegacyCan) {
    acceleration = -0.23456; curvature = 0.01; step(20); ASSERT_TRUE(out);
    can::DriveTxState d{can::DriveFrameKind::Command}; can::BrakeTxState b{can::BrakeFrameKind::Command}; can::SteeringTxState s{can::SteeringFrameKind::Command};
    const auto df = can::encode_drive_frame(out->drive,d);
    const auto bf = can::encode_brake_frame(out->brake,b);
    const auto sf = can::encode_steering_frame(out->steering,s); ASSERT_TRUE(df); ASSERT_TRUE(bf); ASSERT_TRUE(sf);
    EXPECT_DOUBLE_EQ(*can::decode_drive_frame(*df)->torque_nm, *out->drive.torque_nm);
    EXPECT_NEAR(*can::decode_steering_frame(*sf)->angle_rad, *out->steering.angle_rad, 1e-12);
    EXPECT_LE(std::abs(*out->drive.torque_nm), 0.23456*1000*0.3);
    EXPECT_LE(out->expires_at_ns, out->parent.expires_at_ns); EXPECT_GT(out->expires_at_ns, ns(20));
}
TEST(ControlAllocationLoss, EachZoneAndCriticalLeafSourceHasAnIndependentGate) {
    for (int source=0; source<7; ++source) {
        SCOPED_TRACE(source); central::ControlAllocation a; ASSERT_TRUE(a.start_session(3,kStart));
        ASSERT_EQ(a.receive_request({3,0,ns(20),ns(80),0,0,0,false},ns(20)),AllocationReceiveDecision::Accepted);
        ASSERT_TRUE(a.tick(inputs(20),ns(20)));
        ASSERT_EQ(a.receive_request({3,1,ns(40),ns(100),0,0,0,false},ns(40)),AllocationReceiveDecision::Accepted);
        auto in=inputs(40);
        switch (source) {
        case 0: in.feedback.front.health.reset(); break;
        case 1: in.feedback.rear.health.reset(); break;
        case 2: in.feedback.front.steering_actual.reset(); break;
        case 3: in.feedback.front.brake_actual.reset(); break;
        case 4: in.feedback.rear.drive_actual.reset(); break;
        case 5: in.feedback.rear.power_status.reset(); break;
        case 6: in.feedback.rear.power_limits.reset(); break;
        }
        EXPECT_FALSE(a.tick(in,ns(40))); EXPECT_EQ(a.decision().fault,AllocationFault::CriticalFeedback);
        EXPECT_TRUE(a.decision().protection_required);
    }
}
TEST(ControlAllocationDwell, CachedActualCannotAdvanceTheResponseFaultClock) {
    for (const bool cached : {false,true}) {
        central::AllocationConfig c; c.response_dwell_ns=20*kMs;
        central::ControlAllocation a(c); ASSERT_TRUE(a.start_session(3,kStart));
        ASSERT_EQ(a.receive_request({3,0,ns(20),ns(80),0,0,200.0/1500,false},ns(20)),AllocationReceiveDecision::Accepted);
        ASSERT_TRUE(a.tick(inputs(20),ns(20)));
        ASSERT_EQ(a.receive_request({3,1,ns(40),ns(100),0,0,200.0/1500,false},ns(40)),AllocationReceiveDecision::Accepted);
        auto in=inputs(40);
        if (cached) {
            in.feedback.rear.drive_actual->source_time_ns=ns(20);
            in.feedback.front.brake_actual->source_time_ns=ns(20);
        }
        const auto out=a.tick(in,ns(40));
        EXPECT_EQ(out.has_value(),cached);
        EXPECT_EQ(a.decision().fault,cached ? AllocationFault::None : AllocationFault::BrakingDeficit);
        EXPECT_EQ(a.decision().actual_source_time_ns,cached ? ns(20) : ns(40));
    }
}
TEST(ControlAllocationManagement, UsesRealOwnerPermissionThroughExistingBmsReceiver) {
    central::VehicleManagement management; central::ControlAllocation allocation;
    ASSERT_TRUE(management.start_session(3,kStart)); ASSERT_TRUE(allocation.start_session(3,kStart));
    can::BmsReceiver receiver({can::BmsFrameKind::DrivePermission,{{0,1000},{-3000,3000},{-50,100},100000}});
    ASSERT_TRUE(receiver.start_session(3,kStart)); can::BmsTxState tx{can::BmsFrameKind::DrivePermission};
    ASSERT_EQ(management.receive_request({{3,0,ns(20),ns(80)},can::BmsPowerAction::Enable},ns(20)),central::LifecycleReceiveDecision::Accepted);
    auto in=inputs(20); auto& status=std::get<can::BmsPowerStatus>(in.feedback.rear.power_status->message.content);
    status.state=can::BmsPowerState::Off; status.positive_contactor_closed=status.negative_contactor_closed=false; status.hv_bus_voltage_v=0;
    auto decision=management.tick(in.feedback,ns(20)); ASSERT_TRUE(decision);
    auto frame=can::encode_bms_frame(decision->drive_permission,tx); ASSERT_TRUE(frame);
    ASSERT_EQ(receiver.receive(*frame,ns(20)).decision,can::ActuatorReceiveDecision::Accepted);
    in.permission=receiver.current_sample(ns(20)); in.permission_parent=decision->permission_parent; in.management=management.decision();
    ASSERT_EQ(allocation.receive_request({3,0,ns(20),ns(80),1,0,0,false},ns(20)),AllocationReceiveDecision::Accepted);
    EXPECT_FALSE(allocation.tick(in,ns(20))); EXPECT_FALSE(allocation.decision().protection_required);
    in=inputs(40); in.feedback.rear.power_status->message.causal_sequence=decision->power_request.sequence;
    std::get<can::BmsPowerStatus>(in.feedback.rear.power_status->message.content).accepted_request_source_time_ns=decision->power_request.source_time_ns;
    decision=management.tick(in.feedback,ns(40)); ASSERT_TRUE(decision); ASSERT_TRUE(management.decision().normal_allowed);
    frame=can::encode_bms_frame(decision->drive_permission,tx); ASSERT_TRUE(frame); ASSERT_TRUE(decision->permission_parent);
    ASSERT_EQ(receiver.receive(*frame,ns(40),&*decision->permission_parent).decision,can::ActuatorReceiveDecision::Accepted);
    in.permission=receiver.current_sample(ns(40)); in.permission_parent=decision->permission_parent; in.management=management.decision();
    ASSERT_EQ(allocation.receive_request({3,1,ns(40),ns(100),1,0,0,false},ns(40)),AllocationReceiveDecision::Accepted);
    const auto out=allocation.tick(in,ns(40)); ASSERT_TRUE(out); EXPECT_GT(*out->drive.torque_nm,0);
    EXPECT_EQ(out->parent.sequence,1); EXPECT_EQ(in.permission_parent->sequence,0);
    EXPECT_LE(out->expires_at_ns,std::get<can::BmsDriveGrant>(in.permission->message.content).expires_at_ns);
}

void response_scenario(int fault) {
    central::ControlAllocation allocator; ASSERT_TRUE(allocator.start_session(3,kStart));
    simulation::DriveSilPlant motor({-200,300,0,1000,2000,50*kMs}); motor.begin(7,kStart);
    simulation::BrakePressureResponse brake({1500000,0,5000000,10000000,50*kMs}); ASSERT_TRUE(brake.begin(kStart));
    can::DriveReceiver motor_rx({can::DriveFrameKind::Actual,{-200,300},100,200,30*kMs,80*kMs,30*kMs,70*kMs});
    can::BrakeReceiver brake_rx({can::BrakeFrameKind::Actual,0,1500000});
    can::DriveTxState actual_tx{can::DriveFrameKind::Actual}, command_tx{can::DriveFrameKind::Command};
    can::BrakeTxState brake_actual_tx{can::BrakeFrameKind::Actual}, brake_command_tx{can::BrakeFrameKind::Command};
    can::DriveReceiver command_rx({can::DriveFrameKind::Command,{-200,300},100,200});
    can::BrakeReceiver brake_command_rx({can::BrakeFrameKind::Command,0,1500000});
    ASSERT_TRUE(motor_rx.start_session(3,kStart)); ASSERT_TRUE(brake_rx.start_session(3,kStart));
    ASSERT_TRUE(command_rx.start_session(3,kStart)); ASSERT_TRUE(brake_command_rx.start_session(3,kStart));
    bool saw_deficit = false, saw_blended = false, saw_launch_wait = false, saw_propulsion = false;
    for (std::uint32_t i=1; i<=180; ++i) {
        const auto ms=i*20;
        const auto now=ns(ms);
        simulation::BrakePressureResponseInjection injection;
        if (fault==1) injection.rise_rate_scale=0.01;
        if (fault==2 && ms>=2000) injection.stuck=true;
        ASSERT_TRUE(motor.advance(now,false)); ASSERT_TRUE(brake.advance(now,injection));
        const auto torque=motor.capture(now);
        const auto pressure=brake.capture(); ASSERT_TRUE(torque); ASSERT_TRUE(pressure);
        auto in=inputs(ms); in.feedback.rear.drive_actual->torque_nm=torque->torque_nm;
        in.feedback.rear.drive_actual->source_time_ns=torque->source_time_ns;
        in.feedback.front.brake_actual->pressure_pa=pressure->pressure_pa;
        in.feedback.front.brake_actual->source_time_ns=pressure->source_time_ns;
        const auto cap=ms>=1000 && ms<1600 ? 0.0 : 200.0;
        in.feedback.rear.drive_actual->regen_capability->torque_limit_nm=cap;
        const auto af=can::encode_drive_frame(*in.feedback.rear.drive_actual,actual_tx);
        const auto pf=can::encode_brake_frame(*in.feedback.front.brake_actual,brake_actual_tx); ASSERT_TRUE(af); ASSERT_TRUE(pf);
        ASSERT_EQ(motor_rx.receive(*af,now).decision,can::ActuatorReceiveDecision::Accepted);
        ASSERT_EQ(brake_rx.receive(*pf,now).decision,can::ActuatorReceiveDecision::Accepted);
        in.feedback.rear.drive_actual=motor_rx.current_sample(now); in.feedback.front.brake_actual=brake_rx.current_sample(now);
        const bool coast=ms>=2000 && ms<2600, brake_again=ms>=2600;
        const auto demand=coast ? 0.0 : brake_again ? 200.0/1500 : 400.0/1500;
        const auto accel=coast ? 1.0 : 0.0;
        ASSERT_EQ(allocator.receive_request({3,i-1,now,now+60*kMs,accel,0,demand,false},now),AllocationReceiveDecision::Accepted);
        const auto out=allocator.tick(in,now);
        if (!out) {
            ASSERT_NE(fault,0); EXPECT_TRUE(allocator.decision().protection_required);
            EXPECT_EQ(allocator.decision().fault,fault==1 ? AllocationFault::BrakingDeficit : AllocationFault::BrakingExcess);
            EXPECT_GT(pressure->pressure_pa,0); return; // no manufactured zero Actual or successful stop
        }
        const auto df=can::encode_drive_frame(out->drive,command_tx);
        const auto bf=can::encode_brake_frame(out->brake,brake_command_tx); ASSERT_TRUE(df); ASSERT_TRUE(bf);
        ASSERT_EQ(command_rx.receive(*df,now).decision,can::ActuatorReceiveDecision::Accepted);
        ASSERT_EQ(brake_command_rx.receive(*bf,now).decision,can::ActuatorReceiveDecision::Accepted);
        const auto drive_command=command_rx.current_sample(now);
        const auto brake_command=brake_command_rx.current_sample(now); ASSERT_TRUE(drive_command); ASSERT_TRUE(brake_command);
        ASSERT_TRUE(motor.apply({drive::ActuationMode::Target,*drive_command->torque_nm,drive::TorqueEnvelope{-cap,300},now}));
        ASSERT_TRUE(brake.set_target(*brake_command->pressure_pa,now));
        EXPECT_FALSE(*drive_command->torque_nm>0 && *brake_command->pressure_pa>0);
        if (ms>=1600 && ms<2000) { EXPECT_EQ(*drive_command->torque_nm,0); }
        saw_deficit=saw_deficit || *allocator.decision().deficit_nm>50;
        saw_blended=saw_blended || (torque->torque_nm<0 && pressure->pressure_pa>0);
        saw_launch_wait=saw_launch_wait || allocator.decision().propulsion_waiting_release;
        saw_propulsion=saw_propulsion || *drive_command->torque_nm>0;
        const auto wire_net=*in.feedback.front.brake_actual->pressure_pa*0.001-*in.feedback.rear.drive_actual->torque_nm;
        EXPECT_NEAR(*allocator.decision().actual_braking_nm,wire_net,1e-8);
        EXPECT_LE(std::abs(wire_net-(pressure->pressure_pa*0.001-torque->torque_nm)),0.5500001);
    }
    EXPECT_EQ(fault,0); EXPECT_TRUE(saw_deficit); EXPECT_TRUE(saw_blended); EXPECT_TRUE(saw_launch_wait); EXPECT_TRUE(saw_propulsion);
}
TEST(ControlAllocationResponse, DelayedMotorAndBrakeBlendCapLossRecoveryReleaseAndLaunch) { response_scenario(0); }
TEST(ControlAllocationResponse, SlowPressureBuildRequestsProtectionAfterTheResponseBudget) { response_scenario(1); }
TEST(ControlAllocationResponse, StuckPressureDuringReleaseCannotBeReportedAsAValidLaunch) { response_scenario(2); }
}  // namespace
