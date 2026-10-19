#include "drive_sil.hpp"

#include <gtest/gtest.h>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace {
using namespace stratadrive;
constexpr std::uint64_t kStart = 1000000000, kMs = 1000000;
std::uint64_t time_ns(std::uint32_t ms) { return kStart+static_cast<std::uint64_t>(ms)*kMs; }
drive::LocalSensors local(std::uint32_t ms) {
    const battery::ModelIdentity id{7, ms/10, time_ns(ms)};
    return {battery::ModelMeasurement<double>{20, id, time_ns(ms)},
        battery::ModelMeasurement<drive::HvFeedback>{{400, true, false}, id, time_ns(ms)}};
}
class DriveControllerTest : public ::testing::Test {
protected:
    simulation::DriveSil controller{vecu::DriveControllerConfig{}};
    can::DriveTxState cmd_tx{can::DriveFrameKind::Command};
    can::BmsTxState bms_tx{can::BmsFrameKind::PowerLimits}, relay_tx{can::BmsFrameKind::DriveBatteryLimits}, grant_tx{can::BmsFrameKind::DrivePermission};
    can::DriveReceiver feedback{{can::DriveFrameKind::Actual, {-300, 500}, 100, 300, 30000000, 80000000, 30000000, 70000000}};
    std::uint32_t cmd_seq{0}, limits_seq{0}, grant_seq{0};
    double command_nm{200}, charge_w{30000}, discharge_w{80000}, omega{20}, hv_v{400};
    bool allow{true}, inverter_ready{true}, hardware_fault{false};
    bool commands{true}, limits{true}, grants{true}, speed_valid{true}, hv_valid{true};
    bool bms_protection{false};
    std::optional<drive::LocalSensors> held_local;
    std::uint32_t limit_dependency_lag_ms{0};
    can::DriveMessage actual{};
    void SetUp() override { ASSERT_TRUE(controller.start_session(1, 7, kStart)); ASSERT_TRUE(feedback.start_session(1, kStart)); }
    can::DriveFrame command(std::uint32_t ms) {
        can::DriveMessage m; m.epoch = 1; m.sequence = cmd_seq++; m.source_time_ns = time_ns(ms); m.torque_nm = command_nm;
        m.local_state = can::ActuatorLocalState::Normal; m.origin = can::ActuatorOrigin::NormalPath;
        return can::encode_drive_frame(m, cmd_tx).value();
    }
    can::BmsMessage limit_message(std::uint32_t ms) {
        can::BmsMessage m; m.kind = can::BmsFrameKind::PowerLimits; m.epoch = 1; m.sequence = limits_seq++;
        m.source_time_ns = time_ns(ms); m.causal_sequence = ms/10;
        m.local_state = bms_protection ? can::ActuatorLocalState::FailSafe : can::ActuatorLocalState::Normal;
        m.origin = bms_protection ? can::ActuatorOrigin::LocalProtection : can::ActuatorOrigin::NormalPath;
        m.content = can::BmsPowerLimits{charge_w, discharge_w, can::BmsLimitReason::Nominal, can::BmsLimitReason::Nominal,
            time_ns(ms-limit_dependency_lag_ms)};
        return m;
    }
    void grant(std::uint32_t ms) {
        const can::BmsParentContext parent{1, 1000+grant_seq, time_ns(ms), time_ns(ms)+60*kMs};
        can::BmsMessage m; m.kind = can::BmsFrameKind::DrivePermission; m.epoch = 1; m.sequence = grant_seq++;
        m.source_time_ns = time_ns(ms); m.causal_sequence = parent.sequence;
        m.local_state = can::ActuatorLocalState::Normal; m.origin = can::ActuatorOrigin::NormalPath;
        m.content = can::BmsDriveGrant{allow ? can::BmsDrivePermission::AllowNormal : can::BmsDrivePermission::Inhibit,
            allow ? ms/10 : 0, allow ? time_ns(ms) : 0, allow ? time_ns(ms) : 0, time_ns(ms)+60*kMs};
        const auto f = can::encode_bms_frame(m, grant_tx); ASSERT_TRUE(f);
        EXPECT_EQ(controller.receive_permission(*f, time_ns(ms), allow ? &parent : nullptr).decision, can::ActuatorReceiveDecision::Accepted);
    }
    void inputs(std::uint32_t ms) {
        if (commands) { EXPECT_EQ(controller.receive_command(command(ms), time_ns(ms)).decision, can::ActuatorReceiveDecision::Accepted); }
        if (limits) {
            const auto f = can::forward_bms_limits(limit_message(ms), relay_tx); ASSERT_TRUE(f);
            EXPECT_EQ(controller.receive_limits(*f, time_ns(ms)).decision, can::ActuatorReceiveDecision::Accepted);
        }
        if (grants) grant(ms);
        auto s = held_local.value_or(local(ms));
        if (!held_local) { s.wheel_speed->value = omega; s.hv->value = {hv_v, inverter_ready, hardware_fault}; }
        if (!speed_valid) s.wheel_speed.reset();
        if (!hv_valid) s.hv.reset();
        controller.observe_local(s, time_ns(ms));
    }
    void tick(std::uint32_t ms) {
        const auto f = controller.tick(time_ns(ms)); ASSERT_TRUE(f);
        const auto decoded = can::decode_drive_frame(*f); ASSERT_TRUE(decoded); actual = *decoded;
        EXPECT_EQ(feedback.receive(*f, time_ns(ms)).decision, can::ActuatorReceiveDecision::Accepted);
    }
    void step(std::uint32_t ms) { inputs(ms); tick(ms); }
    struct TimeRange { std::uint32_t first, last; };
    void run(TimeRange range) { for (auto ms = range.first; ms <= range.last; ms += 10) step(ms); }
};
TEST(DriveControllerConfig, RejectsInvalidCalibrationWithoutAPermissiveBypass) {
    auto c = vecu::DriveControllerConfig{}; c.motoring_efficiency_lower_bound = 0;
    EXPECT_THROW(simulation::DriveSil{c}, std::invalid_argument);
    c = {}; c.copper_loss_w_per_nm2 = 0; EXPECT_THROW(simulation::DriveSil{c}, std::invalid_argument);
    c = {}; c.regen_stop_rad_s = 0; EXPECT_THROW(simulation::DriveSil{c}, std::invalid_argument);
    c = {}; c.regen_full_rad_s = c.regen_stop_rad_s; EXPECT_THROW(simulation::DriveSil{c}, std::invalid_argument);
    c = {}; c.command_nm.maximum = 4000; EXPECT_THROW(simulation::DriveSil{c}, std::invalid_argument);
    c = {}; c.response.maximum_nm = 501; EXPECT_THROW(simulation::DriveSil{c}, std::invalid_argument);
    c = {}; c.minimum_hv_v = 500; EXPECT_THROW(simulation::DriveSil{c}, std::invalid_argument);
    c = {}; c.maximum_bms_power_w = std::numeric_limits<double>::infinity(); EXPECT_THROW(simulation::DriveSil{c}, std::invalid_argument);
    c = {}; c.max_tick_gap_ns = 31000000; EXPECT_THROW(simulation::DriveSil{c}, std::invalid_argument);
}
TEST(DriveControllerConfig, ExplicitApplicationAndPhysicalEpochMappingIsRequired) {
    simulation::DriveSil c({}); EXPECT_FALSE(c.tick(kStart));
    EXPECT_FALSE(c.start_session(0, 7, kStart)); EXPECT_FALSE(c.start_session(1, 0, kStart));
    ASSERT_TRUE(c.start_session(1, 7, kStart)); EXPECT_FALSE(c.start_session(1, 7, kStart));
    EXPECT_FALSE(c.start_session(2, 6, kStart));
}
TEST_F(DriveControllerTest, InitReportsKnownModelTorqueButUnknownCapabilityUntilInputsArrive) {
    tick(10); ASSERT_TRUE(actual.torque_nm); EXPECT_EQ(*actual.torque_nm, 0);
    EXPECT_EQ(actual.local_state, can::ActuatorLocalState::Init); EXPECT_FALSE(actual.wheel_speed); EXPECT_FALSE(actual.regen_capability);
    commands = false; step(20); ASSERT_TRUE(actual.regen_capability);
    EXPECT_EQ(actual.regen_capability->torque_limit_nm, 0); EXPECT_EQ(actual.regen_limit_reason, can::DriveRegenLimitReason::Disabled);
    commands = true; step(30); EXPECT_TRUE(controller.decision().active); EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::None);
}
TEST_F(DriveControllerTest, FreshInhibitAndKnownPhysicalOffCanRemainNonDrivingInit) {
    allow = false; hv_v = 0; inverter_ready = false; command_nm = 500;
    run({10, 200});
    EXPECT_FALSE(controller.decision().active); EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::None);
    EXPECT_EQ(controller.actual_torque_nm(), 0); ASSERT_TRUE(actual.regen_capability);
    EXPECT_EQ(actual.regen_capability->torque_limit_nm, 0); EXPECT_EQ(actual.regen_limit_reason, can::DriveRegenLimitReason::Disabled);
    EXPECT_EQ(actual.local_state, can::ActuatorLocalState::Init);
}
TEST_F(DriveControllerTest, PositiveAndNegativeCommandsStillPassThroughPhysicalDelayAndRate) {
    run({10, 300}); EXPECT_EQ(controller.actual_torque_nm(), 200);
    EXPECT_EQ(actual.causal_sequence, cmd_seq-1); EXPECT_NE(actual.causal_sequence, 1000+grant_seq-1);
    command_nm = -200; step(310); EXPECT_EQ(controller.actual_torque_nm(), 200);
    run({320, 800}); EXPECT_EQ(controller.actual_torque_nm(), -200);
    EXPECT_EQ(actual.wheel_speed->source_time_ns, time_ns(800));
    EXPECT_EQ(actual.regen_capability->torque_limit_nm, 200);
    EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::None);
}
TEST_F(DriveControllerTest, PropulsionHonorsElectricalDrawIncludingIdleAndTorqueSquaredLoss) {
    discharge_w = 1000; command_nm = 500; run({10, 300});
    const auto t = *controller.decision().propulsion_limit_nm;
    EXPECT_LE(t*20/0.9+0.01*t*t+200, discharge_w);
    EXPECT_GT((t+0.1)*20/0.9+0.01*(t+0.1)*(t+0.1)+200, discharge_w);
    EXPECT_NEAR(controller.actual_torque_nm(), t, 1e-9);
    EXPECT_EQ(controller.decision().selected_target_nm, t);
}
TEST_F(DriveControllerTest, StandstillUsesFiniteCopperLossLimitAndNeverDividesByZero) {
    omega = 0; discharge_w = 1000; command_nm = 500; step(10);
    EXPECT_EQ(controller.decision().propulsion_limit_nm, 282.8);
    EXPECT_EQ(controller.decision().regen_limit_nm, 0);
    EXPECT_EQ(actual.wheel_speed->value_rad_s, 0); EXPECT_TRUE(std::isfinite(*controller.decision().propulsion_limit_nm));
    EXPECT_EQ(actual.regen_limit_reason, can::DriveRegenLimitReason::MotorOrSpeedLimited);
}
TEST_F(DriveControllerTest, ValidZeroDischargeBlocksLaunchAndPositiveTorqueButChargeStaysIndependent) {
    omega = 0; discharge_w = 0; command_nm = 500; run({10, 100});
    EXPECT_EQ(controller.decision().propulsion_limit_nm, 0); EXPECT_EQ(controller.actual_torque_nm(), 0);
    omega = 20; step(110); EXPECT_EQ(controller.decision().regen_limit_nm, 200);
    EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::None);
}
TEST_F(DriveControllerTest, ChargeAcceptanceBoundsRegenWithUnitEfficiencyAsConservativeUpperReturn) {
    charge_w = 3000; command_nm = -300; run({10, 300});
    EXPECT_EQ(controller.decision().regen_limit_nm, 150); EXPECT_EQ(controller.actual_torque_nm(), -150);
    EXPECT_LE(*controller.decision().regen_limit_nm*omega, charge_w);
    EXPECT_EQ(actual.regen_limit_reason, can::DriveRegenLimitReason::ChargeAcceptanceLimited);
}
TEST_F(DriveControllerTest, LowSpeedTaperAndMotorConstantPowerEnvelopeLimitCapability) {
    omega = 2; step(10); EXPECT_EQ(controller.decision().regen_limit_nm, 0);
    omega = 3.5; step(20); EXPECT_EQ(controller.decision().regen_limit_nm, 100);
    omega = 5; step(30); EXPECT_EQ(controller.decision().regen_limit_nm, 200);
    omega = 100; step(40); EXPECT_EQ(controller.decision().regen_limit_nm, 100);
    EXPECT_EQ(actual.regen_limit_reason, can::DriveRegenLimitReason::MotorOrSpeedLimited);
}
TEST_F(DriveControllerTest, CapabilityRoundingNeverExceedsPowerAcceptance) {
    charge_w = 2010; omega = 23; step(10);
    ASSERT_TRUE(actual.regen_capability); EXPECT_DOUBLE_EQ(actual.regen_capability->torque_limit_nm, 87.3);
    EXPECT_LE(actual.regen_capability->torque_limit_nm*23, 2010);
}
TEST_F(DriveControllerTest, ValidZeroChargeCancelsQueuedRegenAndRampsResidualWithoutTeleport) {
    command_nm = -200; run({10, 300}); EXPECT_EQ(controller.actual_torque_nm(), -200);
    charge_w = 0; step(310); EXPECT_EQ(controller.actual_torque_nm(), -200);
    EXPECT_TRUE(controller.decision().actual_outside_envelope); EXPECT_EQ(controller.decision().selected_target_nm, 0);
    ASSERT_TRUE(actual.regen_capability); EXPECT_EQ(actual.regen_capability->torque_limit_nm, 0);
    EXPECT_EQ(actual.regen_limit_reason, can::DriveRegenLimitReason::ChargeAcceptanceLimited);
    step(320); EXPECT_EQ(controller.actual_torque_nm(), -180);
    run({330, 450}); EXPECT_EQ(controller.actual_torque_nm(), 0);
    EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::None);
    EXPECT_GT(*controller.decision().propulsion_limit_nm, 0);
}
TEST_F(DriveControllerTest, PositivePowerContractionUsesProtectionRateAndCanResumeOnFreshSoftLimits) {
    run({10, 300}); discharge_w = 1000; step(310);
    EXPECT_GT(controller.actual_torque_nm(), *controller.decision().propulsion_limit_nm);
    step(320); EXPECT_EQ(controller.actual_torque_nm(), 180);
    run({330, 450}); EXPECT_NEAR(controller.actual_torque_nm(), *controller.decision().propulsion_limit_nm, 1e-9);
    discharge_w = 80000; step(460); EXPECT_LT(controller.actual_torque_nm(), 200);
    run({470, 750}); EXPECT_EQ(controller.actual_torque_nm(), 200);
}
TEST_F(DriveControllerTest, PermissionInhibitAfterActivationLatchesAndZerosBothSigns) {
    command_nm = -200; run({10, 300}); allow = false; step(310);
    EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::PermissionInhibit);
    EXPECT_EQ(controller.actual_torque_nm(), -200); EXPECT_EQ(actual.regen_capability->torque_limit_nm, 0);
    EXPECT_EQ(actual.regen_limit_reason, can::DriveRegenLimitReason::Disabled);
    allow = true; run({320, 500}); EXPECT_EQ(controller.actual_torque_nm(), 0);
    EXPECT_FALSE(controller.decision().active); EXPECT_EQ(actual.local_state, can::ActuatorLocalState::FailSafe);
}
TEST_F(DriveControllerTest, ClaimedReadyInPermissionCannotReplaceActualLocalHv) {
    hv_v = 250; run({10, 100}); EXPECT_EQ(controller.actual_torque_nm(), 0);
    EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::HvNotReady);
    EXPECT_TRUE(actual.torque_nm); EXPECT_EQ(actual.regen_capability->torque_limit_nm, 0);
}
TEST_F(DriveControllerTest, InverterHealthIsRequiredEvenWith400VoltBus) {
    inverter_ready = false; step(10); EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::HvNotReady);
}
TEST_F(DriveControllerTest, HardwareFaultRevokesAnAlreadyActiveGate) {
    run({10, 100}); hardware_fault = true; step(110);
    EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::HvNotReady);
    EXPECT_TRUE(actual.torque_nm); EXPECT_FALSE(controller.decision().active);
}
TEST_F(DriveControllerTest, BmsProtectionIsNotTreatedAsAnOrdinarySoftPowerLimit) {
    run({10, 100}); bms_protection = true; charge_w = discharge_w = 0; step(110);
    EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::BmsProtection);
    EXPECT_EQ(actual.regen_capability->torque_limit_nm, 0);
}
TEST_F(DriveControllerTest, MissingSpeedIsUnknownCapabilityWithStillValidResidualTorque) {
    command_nm = -200; run({10, 300}); speed_valid = false; step(310);
    EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::LocalInputsUnavailable);
    EXPECT_FALSE(actual.wheel_speed); EXPECT_FALSE(actual.regen_capability); EXPECT_TRUE(actual.torque_nm);
    EXPECT_EQ(actual.regen_limit_reason, can::DriveRegenLimitReason::InputsInvalid);
    run({320, 450}); EXPECT_EQ(controller.actual_torque_nm(), 0);
}
TEST_F(DriveControllerTest, MissingHvNeverFallsBackToPermissionOrOldSensorValue) {
    run({10, 100}); hv_valid = false; step(110);
    EXPECT_TRUE(actual.wheel_speed); EXPECT_FALSE(actual.regen_capability);
    EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::LocalInputsUnavailable);
}
TEST_F(DriveControllerTest, HeldPhysicalAcquisitionExpiresDespiteFreshCommandAndPermission) {
    run({10, 100}); held_local = local(100); run({110, 130});
    EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::None);
    step(140); EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::LocalInputsUnavailable);
    EXPECT_FALSE(actual.regen_capability);
}
TEST_F(DriveControllerTest, CachedPhysicalValuesCannotBeChangedOrReidentified) {
    step(10); auto s = local(10); s.wheel_speed->value = 21;
    const auto result = controller.observe_local(s, time_ns(20)); EXPECT_EQ(result.wheel_speed, drive::SensorDecision::Identity);
    tick(20); EXPECT_FALSE(actual.wheel_speed); EXPECT_FALSE(actual.regen_capability);
}
TEST_F(DriveControllerTest, PhysicalEpochFutureDependencyAndUnsupportedReverseAreRejected) {
    auto s = local(10); s.wheel_speed->identity.epoch = 8;
    EXPECT_EQ(controller.observe_local(s, time_ns(10)).wheel_speed, drive::SensorDecision::Identity);
    s = local(20); s.hv->input_time_ns = time_ns(20)+1;
    EXPECT_EQ(controller.observe_local(s, time_ns(20)).hv, drive::SensorDecision::Time);
    s = local(40); EXPECT_EQ(controller.observe_local(s, time_ns(30)).hv, drive::SensorDecision::Time);
    s = local(40); s.wheel_speed->value = -1;
    EXPECT_EQ(controller.observe_local(s, time_ns(40)).wheel_speed, drive::SensorDecision::Value);
}
TEST_F(DriveControllerTest, AcquisitionSkewCannotBeHiddenByIndividuallyFreshValues) {
    step(10); auto s = local(40); s.hv = local(10).hv;
    controller.observe_local(s, time_ns(40)); tick(40);
    EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::LocalInputsUnavailable);
}
TEST_F(DriveControllerTest, OverspeedOutsideTheCalibratedEnvelopeInhibits) {
    step(10); omega = 101; step(20);
    EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::Overspeed);
    EXPECT_EQ(actual.regen_capability->torque_limit_nm, 0); EXPECT_EQ(actual.wheel_speed->value_rad_s, 101);
}
TEST_F(DriveControllerTest, StaleLimitsCannotBeRefreshedByOtherStreams) {
    run({10, 100}); limits = false; run({110, 150});
    EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::None);
    step(160); EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::LimitsUnavailable);
    EXPECT_FALSE(actual.regen_capability);
}
TEST_F(DriveControllerTest, PartialLimitsStayUnknownRatherThanBecomingZeroOrCopiedFromOtherDirection) {
    step(10); auto m = limit_message(20); std::get<can::BmsPowerLimits>(m.content).charge_power_w.reset();
    std::get<can::BmsPowerLimits>(m.content).charge_reason = can::BmsLimitReason::InputsInvalid;
    const auto f = can::forward_bms_limits(m, relay_tx); ASSERT_TRUE(f);
    EXPECT_EQ(controller.receive_limits(*f, time_ns(20)).decision, can::ActuatorReceiveDecision::Accepted);
    limits = false; step(20);
    EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::LimitsUnavailable);
    EXPECT_FALSE(actual.regen_capability);
}
TEST_F(DriveControllerTest, OriginalBmsFrameIsNotAcceptedAsTheRoutedDriveLimitsFrame) {
    auto f = can::encode_bms_frame(limit_message(10), bms_tx); ASSERT_TRUE(f);
    EXPECT_NE(controller.receive_limits(*f, time_ns(10)).decision, can::ActuatorReceiveDecision::Accepted);
}
TEST_F(DriveControllerTest, MissingTrustedParentRevokesVerifiedGrantAndCannotAutoLearnItFromCan) {
    step(10); can::BmsMessage m; m.kind = can::BmsFrameKind::DrivePermission;
    m.epoch = 1; m.sequence = grant_seq++; m.source_time_ns = time_ns(20); m.origin = can::ActuatorOrigin::NormalPath;
    m.local_state = can::ActuatorLocalState::Normal; m.causal_sequence = 1234;
    m.content = can::BmsDriveGrant{can::BmsDrivePermission::AllowNormal, 2, time_ns(20), time_ns(20), time_ns(20)+60*kMs};
    auto f = can::encode_bms_frame(m, grant_tx); ASSERT_TRUE(f);
    EXPECT_EQ(controller.receive_permission(*f, time_ns(20), nullptr).issue, can::BmsReceiveIssue::ParentMissing);
    tick(20); EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::PermissionUnavailable);
}
TEST_F(DriveControllerTest, ExpiredGrantCannotBeConcealedByALateFreshRenewalBetweenTicks) {
    run({10, 100}); grants = false; run({110, 150});
    EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::None);
    // Original source is now 51 ms old even though its 60 ms expiry has not arrived.
    grant(151); tick(160);
    EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::PermissionUnavailable);
    EXPECT_FALSE(controller.decision().active);
}
TEST_F(DriveControllerTest, CommandLossUsesZeroRampAndLateCommandCannotRestartIt) {
    run({10, 300}); commands = false; run({310, 330}); step(340);
    EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::CommandUnavailable);
    EXPECT_EQ(actual.regen_capability->torque_limit_nm, 0); EXPECT_TRUE(actual.torque_nm);
}
TEST_F(DriveControllerTest, CapabilityPreservesOldestDependencyWhileItsCalculationSourceAdvances) {
    limit_dependency_lag_ms = 20; run({20, 100});
    ASSERT_TRUE(actual.regen_capability); EXPECT_EQ(actual.regen_capability->input_time_ns, time_ns(80));
    EXPECT_EQ(actual.regen_capability->source_time_ns, time_ns(100));
    tick(110); ASSERT_TRUE(actual.regen_capability);
    EXPECT_EQ(actual.regen_capability->input_time_ns, time_ns(80));
    EXPECT_EQ(actual.regen_capability->source_time_ns, time_ns(110));
    EXPECT_EQ(actual.wheel_speed->source_time_ns, time_ns(100));
}
TEST_F(DriveControllerTest, DependencyRollbackIsNotNormalizedIntoAFreshCapability) {
    run({10, 100}); limit_dependency_lag_ms = 20; step(110);
    // Dependency rollback is rejected by the BMS receiver; do not fake a newer time.
    EXPECT_FALSE(actual.regen_capability);
}
TEST_F(DriveControllerTest, DeadlineHoldsTheMissedIntervalThenRampsToZero) {
    run({10, 300}); inputs(330); tick(340);
    EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::ControlDeadline);
    EXPECT_EQ(controller.actual_torque_nm(), 200); tick(350); EXPECT_EQ(controller.actual_torque_nm(), 180);
}
TEST_F(DriveControllerTest, ContinuityLossStartsAtItsDetectionTimeAndCancelsPendingGoals) {
    run({10, 300}); controller.mark_continuity_lost(time_ns(301)); tick(310);
    EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::ContinuityLost);
    EXPECT_NEAR(controller.actual_torque_nm(), 182, 1e-9);
}
TEST_F(DriveControllerTest, ClockRegressionSuppressesAllOutputWithoutAdvancingPhysics) {
    run({10, 100}); const auto old = controller.actual_torque_nm();
    EXPECT_FALSE(controller.tick(time_ns(99))); EXPECT_FALSE(controller.tick(time_ns(110)));
    EXPECT_EQ(controller.actual_torque_nm(), old); EXPECT_EQ(controller.decision().fault, vecu::DriveGateFault::ClockError);
}
TEST_F(DriveControllerTest, NewApplicationEpochPreservesPhysicalTorqueAndRequiresFreshInputs) {
    run({10, 300}); ASSERT_TRUE(controller.start_session(2, 7, time_ns(300)));
    ASSERT_TRUE(feedback.start_session(2, time_ns(300)));
    EXPECT_EQ(controller.actual_torque_nm(), 200); tick(310);
    EXPECT_EQ(actual.epoch, 2U); EXPECT_EQ(actual.sequence, 0U);
    EXPECT_EQ(actual.local_state, can::ActuatorLocalState::Init); EXPECT_FALSE(actual.regen_capability);
    EXPECT_EQ(controller.actual_torque_nm(), 180);
}
class DriveStartupTest : public DriveControllerTest {
protected:
    void SetUp() override {
        commands=false; allow=false; hv_v=0; inverter_ready=false;
        ASSERT_TRUE(controller.start_session(1,7,kStart,vecu::DriveCommandStartup::NonDriving));
        ASSERT_TRUE(feedback.start_session(1,kStart));
    }
};
TEST_F(DriveStartupTest, FreshInhibitAndLocalInputsAllowLongPrechargeWithoutTorquePackets) {
    run({10,1000}); EXPECT_EQ(controller.decision().fault,vecu::DriveGateFault::None);
    EXPECT_FALSE(controller.decision().active); EXPECT_DOUBLE_EQ(controller.actual_torque_nm(),0);
    EXPECT_FALSE(controller.arm_normal_commands(time_ns(1000)));
}
TEST_F(DriveStartupTest, PacketsCannotArmAndFirstNormalSequenceRemainsZeroAfterExplicitArm) {
    run({10,200}); cmd_seq=9;
    EXPECT_EQ(controller.receive_command(command(200),time_ns(200)).decision,can::ActuatorReceiveDecision::NotInitialized);
    hv_v=400; inverter_ready=true; inputs(210); ASSERT_TRUE(controller.arm_normal_commands(time_ns(210)));
    EXPECT_FALSE(controller.arm_normal_commands(time_ns(210)));
    allow=true; inputs(220); cmd_seq=0;
    EXPECT_EQ(controller.receive_command(command(220),time_ns(220)).decision,can::ActuatorReceiveDecision::Accepted);
    tick(220); EXPECT_TRUE(controller.decision().active); EXPECT_EQ(controller.decision().fault,vecu::DriveGateFault::None);
}
TEST_F(DriveStartupTest, AllowNormalBeforeTrustedArmLatchesWithoutApplyingTorque) {
    run({10,100}); allow=true; hv_v=400; inverter_ready=true; step(110);
    EXPECT_EQ(controller.decision().fault,vecu::DriveGateFault::CommandsNotArmed); EXPECT_FALSE(controller.decision().active);
    EXPECT_FALSE(controller.arm_normal_commands(time_ns(110))); EXPECT_DOUBLE_EQ(controller.actual_torque_nm(),0);
}
TEST_F(DriveStartupTest, MissingStartupPermissionCannotBeHiddenByLateFreshInhibit) {
    step(10); grants=false; run({20,60}); EXPECT_EQ(controller.decision().fault,vecu::DriveGateFault::None);
    step(70); EXPECT_EQ(controller.decision().fault,vecu::DriveGateFault::PermissionUnavailable);
    grants=true; step(80); EXPECT_EQ(controller.decision().fault,vecu::DriveGateFault::PermissionUnavailable);
}
TEST_F(DriveStartupTest, MissingStartupLimitsStillLatchWithContinuingInhibit) {
    step(10); limits=false; run({20,70}); EXPECT_EQ(controller.decision().fault,vecu::DriveGateFault::LimitsUnavailable);
}
TEST_F(DriveStartupTest, StartupLocalSensorLossStillLatchesWithFreshBmsTraffic) {
    step(10); hv_valid=false; run({20,50}); EXPECT_EQ(controller.decision().fault,vecu::DriveGateFault::LocalInputsUnavailable);
    hv_valid=true; step(60); EXPECT_EQ(controller.decision().fault,vecu::DriveGateFault::LocalInputsUnavailable);
}
TEST_F(DriveStartupTest, NormalCommandWaitingBudgetStartsAtExplicitArmAndIsNotExtended) {
    run({10,1000}); hv_v=400; inverter_ready=true; inputs(1010);
    ASSERT_TRUE(controller.arm_normal_commands(time_ns(1010))); tick(1010); run({1020,1080});
    EXPECT_EQ(controller.decision().fault,vecu::DriveGateFault::None);
    step(1090); EXPECT_EQ(controller.decision().fault,vecu::DriveGateFault::CommandUnavailable);
}
}  // namespace
