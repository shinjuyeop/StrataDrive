#include "steering_actuator.hpp"
#include "brake_actuator.hpp"
#include "drive_actuator.hpp"
#include "drive_controller.hpp"

#include <gtest/gtest.h>
#include <limits>

// This executable links ECU/port libraries only. Simulation headers and plant
// libraries are deliberately absent from its include/link dependencies.
namespace {
using namespace stratadrive;
constexpr std::uint64_t kMs=1000000, kStart=1000000000;
std::uint64_t time_ns(int ms) { return kStart+static_cast<std::uint64_t>(ms)*kMs; }
vecu::SteeringActuatorConfig steering_config() { return {-.5,.5,-.3,.3,0,1,50*kMs}; }
vecu::BrakeActuatorConfig brake_config() { return {2000000,1500000,0,5000000,10000000,1000000,50*kMs}; }
vecu::DriveActuatorConfig drive_config() { return {{-300,500},{-200,300,0,1000,2000,50*kMs}}; }
can::SteeringFrame steering_command(int ms=10) {
    can::SteeringMessage m; m.epoch=1; m.source_time_ns=time_ns(ms); m.angle_rad=.2;
    m.origin=can::SteeringOrigin::NormalPath; m.local_state=can::SteeringLocalState::Normal;
    can::SteeringTxState tx{m.kind}; return can::encode_steering_frame(m,tx).value();
}
can::BrakeFrame brake_command() {
    can::BrakeMessage m; m.epoch=1; m.source_time_ns=time_ns(10); m.pressure_pa=1000000;
    m.origin=can::BrakeOrigin::NormalPath; m.local_state=can::BrakeLocalState::Normal;
    can::BrakeTxState tx{m.kind}; return can::encode_brake_frame(m,tx).value();
}
can::DriveFrame drive_command() {
    can::DriveMessage m; m.epoch=1; m.source_time_ns=time_ns(10); m.torque_nm=200;
    m.origin=can::ActuatorOrigin::NormalPath; m.local_state=can::ActuatorLocalState::Normal;
    can::DriveTxState tx{m.kind}; return can::encode_drive_frame(m,tx).value();
}
TEST(EcuBoundary, SteeringReportsTheInjectedPortAndSelectsTargetWithoutAPlant) {
    vecu::SteeringActuator c(steering_config()); ASSERT_TRUE(c.start_session({1,7,kStart}));
    ASSERT_EQ(c.receive(steering_command(),time_ns(10)).decision,can::SteeringReceiveDecision::Accepted);
    ASSERT_TRUE(c.prepare(time_ns(10))); EXPECT_EQ(c.output().mode,steering::ActuationMode::Hold);
    const auto frame=c.complete(steering::AngleMeasurement{7,42,time_ns(10),.05},time_ns(10)); ASSERT_TRUE(frame);
    EXPECT_DOUBLE_EQ(*can::decode_steering_frame(*frame)->angle_rad,.05);
    EXPECT_EQ(c.output().mode,steering::ActuationMode::Target); EXPECT_DOUBLE_EQ(c.output().target_rad,.2);
    EXPECT_EQ(c.output().issued_time_ns,time_ns(10));
}
TEST(EcuBoundary, SteeringMissingSensorCannotBeFilledFromCommandOrInitialCalibration) {
    vecu::SteeringActuator c(steering_config()); ASSERT_TRUE(c.start_session({1,7,kStart}));
    c.receive(steering_command(),time_ns(10)); ASSERT_TRUE(c.prepare(time_ns(10)));
    const auto f=c.complete(std::nullopt,time_ns(10)); ASSERT_TRUE(f);
    EXPECT_FALSE(can::decode_steering_frame(*f)->angle_rad); EXPECT_EQ(c.fault(),vecu::SteeringFault::SensorUnavailable);
    EXPECT_EQ(c.output().mode,steering::ActuationMode::Hold);
}
TEST(EcuBoundary, SteeringDelayedAcquisitionKeepsItsOriginalSourceTime) {
    vecu::SteeringActuator c(steering_config()); ASSERT_TRUE(c.start_session({1,7,kStart}));
    c.receive(steering_command(20),time_ns(20)); ASSERT_TRUE(c.prepare(time_ns(20)));
    const auto f=c.complete(steering::AngleMeasurement{7,0,time_ns(10),.05},time_ns(20)); ASSERT_TRUE(f);
    EXPECT_EQ(can::decode_steering_frame(*f)->source_time_ns,time_ns(10));
}
TEST(EcuBoundary, SteeringJobPhasesRejectWrongTimeDuplicateCompletionAndAbandonedWork) {
    vecu::SteeringActuator c(steering_config()); EXPECT_FALSE(c.prepare(time_ns(10)));
    ASSERT_TRUE(c.start_session({1,7,kStart})); EXPECT_FALSE(c.complete(std::nullopt,time_ns(10)));
    ASSERT_TRUE(c.prepare(time_ns(10))); EXPECT_FALSE(c.complete(std::nullopt,time_ns(11)));
    ASSERT_TRUE(c.prepare(time_ns(20))); EXPECT_EQ(c.fault(),vecu::SteeringFault::ControlDeadline);
    ASSERT_TRUE(c.complete(steering::AngleMeasurement{7,0,time_ns(20),0},time_ns(20)));
    EXPECT_FALSE(c.complete(std::nullopt,time_ns(20))); EXPECT_FALSE(c.prepare(time_ns(20)));
}
TEST(EcuBoundary, SteeringCannotPublishAfterClockChangesBetweenPhases) {
    vecu::SteeringActuator c(steering_config()); ASSERT_TRUE(c.start_session({1,7,kStart}));
    ASSERT_TRUE(c.prepare(time_ns(10))); c.receive(steering_command(20),time_ns(20));
    EXPECT_FALSE(c.complete(steering::AngleMeasurement{7,0,time_ns(10),0},time_ns(10)));
    EXPECT_EQ(c.fault(),vecu::SteeringFault::ClockError);
}
TEST(EcuBoundary, BrakeProtectionRequestDoesNotEstablishFloorObservation) {
    vecu::BrakeActuator c(brake_config()); ASSERT_TRUE(c.start_session({1,7,kStart}));
    c.receive(brake_command(),time_ns(10)); ASSERT_TRUE(c.prepare(time_ns(10)));
    ASSERT_TRUE(c.complete(brake::PressureMeasurement{7,0,time_ns(10),200000},time_ns(10)));
    c.mark_continuity_lost(time_ns(11)); EXPECT_EQ(c.output().mode,brake::ActuationMode::Protect);
    EXPECT_DOUBLE_EQ(c.output().target_pa,1000000); EXPECT_FALSE(c.protection_floor_observed());
    ASSERT_TRUE(c.prepare(time_ns(20)));
    const auto f=c.complete(brake::PressureMeasurement{7,1,time_ns(20),200000},time_ns(20)); ASSERT_TRUE(f);
    EXPECT_DOUBLE_EQ(*can::decode_brake_frame(*f)->pressure_pa,200000); EXPECT_EQ(c.protection_floor_observed(),false);
}
TEST(EcuBoundary, BrakeMissingOrInvalidFeedbackDoesNotUseRequestedPressure) {
    for(bool missing:{false,true}) {
        vecu::BrakeActuator c(brake_config()); ASSERT_TRUE(c.start_session({1,7,kStart}));
        c.receive(brake_command(),time_ns(10)); ASSERT_TRUE(c.prepare(time_ns(10)));
        const auto sensor=missing ? std::nullopt : std::optional<brake::PressureMeasurement>{{7,0,time_ns(10),std::numeric_limits<double>::quiet_NaN()}};
        const auto f=c.complete(sensor,time_ns(10)); ASSERT_TRUE(f); EXPECT_FALSE(can::decode_brake_frame(*f)->pressure_pa);
        EXPECT_EQ(c.output().mode,brake::ActuationMode::Protect); EXPECT_FALSE(c.protection_floor_observed());
    }
}
TEST(EcuBoundary, BrakeDelayedSourceAndCachedAcquisitionAreNotFreshReports) {
    vecu::BrakeActuator c(brake_config()); ASSERT_TRUE(c.start_session({1,7,kStart}));
    c.receive(brake_command(),time_ns(10)); ASSERT_TRUE(c.prepare(time_ns(10)));
    const brake::PressureMeasurement s{7,0,time_ns(5),0};
    const auto first=c.complete(s,time_ns(10)); ASSERT_TRUE(first); EXPECT_EQ(can::decode_brake_frame(*first)->source_time_ns,time_ns(5));
    ASSERT_TRUE(c.prepare(time_ns(20))); const auto next=c.complete(s,time_ns(20)); ASSERT_TRUE(next);
    EXPECT_FALSE(can::decode_brake_frame(*next)->pressure_pa);
}
TEST(EcuBoundary, BrakeJobGapAndClockErrorAreDetectedWithoutPlantCalls) {
    vecu::BrakeActuator c(brake_config()); ASSERT_TRUE(c.start_session({1,7,kStart}));
    ASSERT_TRUE(c.prepare(time_ns(40))); EXPECT_TRUE(c.execution_gap()); EXPECT_EQ(c.fault(),vecu::BrakeFault::ControlDeadline);
    ASSERT_TRUE(c.complete(brake::PressureMeasurement{7,0,time_ns(40),0},time_ns(40)));
    EXPECT_FALSE(c.prepare(time_ns(39))); EXPECT_EQ(c.fault(),vecu::BrakeFault::ClockError);
}
TEST(EcuBoundary, IsolatedDriveUsesMeasuredTorqueAndReturnsAnActuationRequest) {
    vecu::DriveActuator c(drive_config()); ASSERT_TRUE(c.start_session({1,7,kStart}));
    c.receive(drive_command(),time_ns(10)); ASSERT_TRUE(c.prepare(time_ns(10)));
    EXPECT_DOUBLE_EQ(c.output().target_nm,200);
    const auto f=c.complete(drive::TorqueMeasurement{7,123,time_ns(10),25},time_ns(10)); ASSERT_TRUE(f);
    const auto a=can::decode_drive_frame(*f); ASSERT_TRUE(a); EXPECT_DOUBLE_EQ(*a->torque_nm,25); EXPECT_FALSE(a->regen_capability);
}
TEST(EcuBoundary, IsolatedDriveUnknownTorqueNeverBecomesZeroFeedback) {
    vecu::DriveActuator c(drive_config()); ASSERT_TRUE(c.start_session({1,7,kStart}));
    c.receive(drive_command(),time_ns(10)); ASSERT_TRUE(c.prepare(time_ns(10)));
    const auto f=c.complete(std::nullopt,time_ns(10)); ASSERT_TRUE(f); EXPECT_FALSE(can::decode_drive_frame(*f)->torque_nm);
    EXPECT_EQ(c.fault(),vecu::DriveFault::TorqueFeedbackUnavailable); EXPECT_EQ(c.output().mode,drive::ActuationMode::Zero);
}
TEST(EcuBoundary, IsolatedDriveCachedOrDelayedTorqueCannotRefreshPublication) {
    vecu::DriveActuator c(drive_config()); ASSERT_TRUE(c.start_session({1,7,kStart}));
    const drive::TorqueMeasurement s{7,0,time_ns(10),0}; ASSERT_TRUE(c.prepare(time_ns(10))); ASSERT_TRUE(c.complete(s,time_ns(10)));
    ASSERT_TRUE(c.prepare(time_ns(20))); const auto f=c.complete(s,time_ns(20)); ASSERT_TRUE(f);
    EXPECT_FALSE(can::decode_drive_frame(*f)->torque_nm); EXPECT_EQ(c.fault(),vecu::DriveFault::None);
    ASSERT_TRUE(c.prepare(time_ns(30))); const auto delayed=c.complete(drive::TorqueMeasurement{7,1,time_ns(25),0},time_ns(30));
    ASSERT_TRUE(delayed); EXPECT_FALSE(can::decode_drive_frame(*delayed)->torque_nm);
}
TEST(EcuBoundary, DriveTorqueIdentityEpochRangeAndAgeAreCheckedAtThePort) {
    const drive::TorqueMeasurement invalid[]={{8,0,time_ns(10),0},{7,0,time_ns(11),0},{7,0,kStart-1,0},
        {7,0,time_ns(10),std::numeric_limits<double>::quiet_NaN()},{7,0,time_ns(10),301}};
    for(const auto& s:invalid) {
        vecu::DriveActuator c(drive_config()); ASSERT_TRUE(c.start_session({1,7,kStart})); ASSERT_TRUE(c.prepare(time_ns(10)));
        const auto f=c.complete(s,time_ns(10)); ASSERT_TRUE(f); EXPECT_FALSE(can::decode_drive_frame(*f)->torque_nm);
        EXPECT_EQ(c.fault(),vecu::DriveFault::TorqueFeedbackUnavailable);
    }
    vecu::TorqueFeedback guard; guard.begin(7,kStart); EXPECT_TRUE(guard.observe(drive::TorqueMeasurement{7,0,kStart,0},time_ns(30),-200,300).valid);
    EXPECT_FALSE(guard.observe(drive::TorqueMeasurement{7,0,kStart,0},time_ns(31),-200,300).valid);
}
TEST(EcuBoundary, TorqueCachedIdentityCannotMutateAndNewIdentityRequiresTimeProgress) {
    vecu::TorqueFeedback guard; guard.begin(7,kStart);
    EXPECT_TRUE(guard.observe(drive::TorqueMeasurement{7,1,time_ns(10),1},time_ns(10),-200,300).valid);
    EXPECT_FALSE(guard.observe(drive::TorqueMeasurement{7,1,time_ns(10),2},time_ns(20),-200,300).valid);
    EXPECT_FALSE(guard.observe(drive::TorqueMeasurement{7,0,time_ns(20),1},time_ns(20),-200,300).valid);
    EXPECT_FALSE(guard.observe(drive::TorqueMeasurement{7,2,time_ns(10),1},time_ns(20),-200,300).valid);
}
void feed_gated_drive(vecu::DriveController& c) {
    ASSERT_EQ(c.receive_command(drive_command(),time_ns(10)).decision,can::ActuatorReceiveDecision::Accepted);
    can::BmsMessage limits; limits.kind=can::BmsFrameKind::DriveBatteryLimits; limits.epoch=1; limits.source_time_ns=time_ns(10);
    limits.local_state=can::ActuatorLocalState::Normal; limits.origin=can::ActuatorOrigin::NormalPath;
    limits.content=can::BmsPowerLimits{30000,80000,can::BmsLimitReason::Nominal,can::BmsLimitReason::Nominal,time_ns(10)};
    can::BmsTxState limit_tx{limits.kind}; ASSERT_EQ(c.receive_limits(*can::encode_bms_frame(limits,limit_tx),time_ns(10)).decision,can::ActuatorReceiveDecision::Accepted);
    const can::BmsParentContext parent{1,1000,time_ns(10),time_ns(70)};
    can::BmsMessage grant; grant.kind=can::BmsFrameKind::DrivePermission; grant.epoch=1; grant.source_time_ns=time_ns(10); grant.causal_sequence=1000;
    grant.local_state=can::ActuatorLocalState::Normal; grant.origin=can::ActuatorOrigin::NormalPath;
    grant.content=can::BmsDriveGrant{can::BmsDrivePermission::AllowNormal,0,time_ns(10),time_ns(10),time_ns(70)};
    can::BmsTxState grant_tx{grant.kind}; ASSERT_EQ(c.receive_permission(*can::encode_bms_frame(grant,grant_tx),time_ns(10),&parent).decision,can::ActuatorReceiveDecision::Accepted);
    const battery::ModelIdentity id{7,0,time_ns(10)};
    const drive::LocalSensors local{battery::ModelMeasurement<double>{20,id,time_ns(10)},
        battery::ModelMeasurement<drive::HvFeedback>{{400,true,false},id,time_ns(10)}};
    const auto result=c.observe_local(local,time_ns(10)); ASSERT_EQ(result.hv,drive::SensorDecision::Accepted);
}
TEST(EcuBoundary, GatedDriveProducesBoundedOutputAndCapabilityWithoutSimulatedTorque) {
    vecu::DriveController c({}); ASSERT_TRUE(c.start_session({1,7,kStart})); feed_gated_drive(c);
    ASSERT_TRUE(c.prepare(time_ns(10))); ASSERT_TRUE(c.decision().active); ASSERT_TRUE(c.output().envelope);
    EXPECT_DOUBLE_EQ(c.output().target_nm,200);
    const auto f=c.complete(drive::TorqueMeasurement{7,0,time_ns(10),25},time_ns(10)); ASSERT_TRUE(f);
    const auto a=can::decode_drive_frame(*f); ASSERT_TRUE(a); EXPECT_DOUBLE_EQ(*a->torque_nm,25);
    ASSERT_TRUE(a->regen_capability); EXPECT_DOUBLE_EQ(a->regen_capability->torque_limit_nm,200);
}
TEST(EcuBoundary, GatedDriveRevokesAnActiveRequestWhenTorqueFeedbackIsUnknown) {
    vecu::DriveController c({}); ASSERT_TRUE(c.start_session({1,7,kStart})); feed_gated_drive(c);
    ASSERT_TRUE(c.prepare(time_ns(10))); ASSERT_TRUE(c.decision().active);
    const auto f=c.complete(std::nullopt,time_ns(10)); ASSERT_TRUE(f);
    EXPECT_FALSE(can::decode_drive_frame(*f)->torque_nm); EXPECT_FALSE(c.decision().active);
    EXPECT_EQ(c.output().mode,drive::ActuationMode::Zero); EXPECT_DOUBLE_EQ(c.output().envelope->maximum_nm,0);
    EXPECT_EQ(c.decision().fault,vecu::DriveGateFault::TorqueFeedbackUnavailable);
}
TEST(EcuBoundary, GatedDriveWithoutInputsHasNoInventedCapabilityOrTorque) {
    vecu::DriveController c({}); ASSERT_TRUE(c.start_session({1,7,kStart})); ASSERT_TRUE(c.prepare(time_ns(10)));
    const auto f=c.complete(std::nullopt,time_ns(10)); ASSERT_TRUE(f);
    const auto a=can::decode_drive_frame(*f); ASSERT_TRUE(a); EXPECT_FALSE(a->torque_nm); EXPECT_FALSE(a->regen_capability);
    EXPECT_FALSE(c.decision().active); EXPECT_EQ(c.decision().fault,vecu::DriveGateFault::TorqueFeedbackUnavailable);
    EXPECT_EQ(c.output().mode,drive::ActuationMode::Zero);
}
TEST(EcuBoundary, GatedDriveChecksCompletionClockAndExplicitPhaseOrdering) {
    vecu::DriveController c({}); ASSERT_TRUE(c.start_session({1,7,kStart})); EXPECT_FALSE(c.complete(std::nullopt,time_ns(10)));
    ASSERT_TRUE(c.prepare(time_ns(10))); EXPECT_FALSE(c.complete(std::nullopt,time_ns(11)));
    c.observe_local({},time_ns(20)); EXPECT_FALSE(c.complete(drive::TorqueMeasurement{7,0,time_ns(10),0},time_ns(10)));
    EXPECT_EQ(c.decision().fault,vecu::DriveGateFault::ClockError);
}
} // namespace
