#include "drive_actuator_sil.hpp"

#include <gtest/gtest.h>
#include <algorithm>
#include <limits>
#include <stdexcept>

namespace {
using namespace stratadrive;
constexpr std::uint64_t kStart = 1000000000, kMs = 1000000;
vecu::DriveActuatorConfig configuration() { return {{-300, 500}, {-200, 300, 0, 1000, 2000, 50*kMs}}; }

TEST(TorqueResponseTest, InvalidConfigurationAndTimeOrderAreRejected) {
    auto config = configuration().response;
    config.zero_rate_nm_s = 0;
    EXPECT_THROW(simulation::TorqueResponse{config}, std::invalid_argument);
    config = configuration().response; config.initial_nm = std::numeric_limits<double>::quiet_NaN();
    EXPECT_THROW(simulation::TorqueResponse{config}, std::invalid_argument);
    config = configuration().response; config.minimum_nm = 0;
    EXPECT_THROW(simulation::TorqueResponse{config}, std::invalid_argument);
    simulation::TorqueResponse plant(configuration().response);
    EXPECT_FALSE(plant.set_target(100, kStart)); EXPECT_FALSE(plant.advance(kStart));
    plant.begin(kStart);
    EXPECT_FALSE(plant.set_target(301, kStart));
    EXPECT_FALSE(plant.set_target(std::numeric_limits<double>::infinity(), kStart));
    ASSERT_TRUE(plant.set_target(100, kStart + 20*kMs));
    EXPECT_FALSE(plant.set_target(-100, kStart + 19*kMs));
    EXPECT_FALSE(plant.advance(kStart + 19*kMs));
    ASSERT_TRUE(plant.advance(kStart + 80*kMs)); EXPECT_DOUBLE_EQ(plant.actual_nm(), 10);
}
TEST(TorqueResponseTest, DelayedGoalsAndJitterAreIntegratedAtTheirOwnBoundaries) {
    simulation::TorqueResponse plant(configuration().response);
    plant.begin(kStart);
    ASSERT_TRUE(plant.set_target(100, kStart + 10*kMs));
    ASSERT_TRUE(plant.set_target(100, kStart + 20*kMs)); // repeated goal does not restart delay
    ASSERT_TRUE(plant.set_target(-100, kStart + 40*kMs));
    ASSERT_TRUE(plant.advance(kStart + 65*kMs)); EXPECT_DOUBLE_EQ(plant.actual_nm(), 5);
    ASSERT_TRUE(plant.advance(kStart + 95*kMs)); EXPECT_DOUBLE_EQ(plant.actual_nm(), 25);
    ASSERT_TRUE(plant.advance(kStart + 120*kMs)); EXPECT_DOUBLE_EQ(plant.actual_nm(), 0);
}
TEST(TorqueResponseTest, ZeroTargetCancelsPendingReversalAndIsNotBackdatedOrRestarted) {
    simulation::TorqueResponse plant(configuration().response);
    plant.begin(kStart); ASSERT_TRUE(plant.set_target(300, kStart));
    ASSERT_TRUE(plant.advance(kStart + 150*kMs)); EXPECT_DOUBLE_EQ(plant.actual_nm(), 100);
    ASSERT_TRUE(plant.set_target(-200, kStart + 150*kMs));
    plant.request_zero(kStart + 151*kMs);
    ASSERT_TRUE(plant.advance(kStart + 160*kMs)); EXPECT_DOUBLE_EQ(plant.actual_nm(), 82);
    plant.request_zero(kStart + 165*kMs);
    ASSERT_TRUE(plant.advance(kStart + 170*kMs)); EXPECT_DOUBLE_EQ(plant.actual_nm(), 62);
    ASSERT_TRUE(plant.advance(kStart + 250*kMs)); EXPECT_DOUBLE_EQ(plant.actual_nm(), 0);
    plant.begin(kStart + 300*kMs);
    ASSERT_TRUE(plant.set_target(300, kStart + 310*kMs));
    plant.skip_to(kStart + 500*kMs); // must not replay an expired delay interval or subtract times backwards
    ASSERT_TRUE(plant.advance(kStart + 510*kMs)); EXPECT_DOUBLE_EQ(plant.actual_nm(), 0);
}
TEST(TorqueResponseTest, CapacityOverflowAndTimestampOverflowFailWithoutAllocation) {
    simulation::TorqueResponse plant(configuration().response); plant.begin(kStart);
    for (int i = 0; i < 128; ++i) ASSERT_TRUE(plant.set_target(i % 2 ? 100 : -100, kStart));
    EXPECT_FALSE(plant.set_target(200, kStart));
    plant.request_zero(kStart); ASSERT_TRUE(plant.advance(kStart + 100*kMs));
    EXPECT_DOUBLE_EQ(plant.actual_nm(), 0);
    const auto near_end = std::numeric_limits<std::uint64_t>::max() - 20*kMs;
    plant.begin(near_end); EXPECT_FALSE(plant.set_target(100, near_end));
}

class DriveActuatorTest : public ::testing::Test {
protected:
    simulation::DriveActuatorSil model{configuration()};
    can::DriveTxState tx{can::DriveFrameKind::Command};
    std::uint32_t sequence{0};
    void SetUp() override { ASSERT_TRUE(model.start_session(1, kStart)); }
    struct Input { int ms; double torque; std::uint32_t epoch{1}; };
    can::DriveFrame command(Input data) {
        can::DriveMessage input;
        input.epoch = data.epoch; input.sequence = sequence++; input.source_time_ns = kStart + data.ms*kMs;
        input.torque_nm = data.torque; input.local_state = can::ActuatorLocalState::Normal;
        input.origin = can::ActuatorOrigin::NormalPath;
        return can::encode_drive_frame(input, tx).value();
    }
    can::DriveMessage tick(int ms) {
        return can::decode_drive_frame(model.tick(kStart + ms*kMs).value()).value();
    }
    can::DriveMessage drive(int ms, double torque) {
        EXPECT_EQ(model.receive(command({ms, torque}), kStart + ms*kMs).decision, can::ActuatorReceiveDecision::Accepted);
        return tick(ms);
    }
};
TEST(TorqueResponseTest, ContractionClampsQueuedGoalsAndRelaxationCannotRestoreOldDemands) {
    simulation::TorqueResponse plant(configuration().response); plant.begin(kStart);
    ASSERT_TRUE(plant.set_target(-200, kStart));
    ASSERT_TRUE(plant.constrain({-50, 300}, kStart+40*kMs));
    ASSERT_TRUE(plant.advance(kStart+100*kMs)); EXPECT_DOUBLE_EQ(plant.actual_nm(), -50);
    ASSERT_TRUE(plant.constrain({-200, 300}, kStart+100*kMs));
    ASSERT_TRUE(plant.advance(kStart+250*kMs)); EXPECT_DOUBLE_EQ(plant.actual_nm(), -50);
    ASSERT_TRUE(plant.set_target(-200, kStart+250*kMs));
    ASSERT_TRUE(plant.advance(kStart+299*kMs)); EXPECT_DOUBLE_EQ(plant.actual_nm(), -50);
    ASSERT_TRUE(plant.advance(kStart+310*kMs)); EXPECT_DOUBLE_EQ(plant.actual_nm(), -60);
}
TEST(TorqueResponseTest, LowerEnvelopePreservesActualAtDetectionThenContractsAtProtectionRate) {
    simulation::TorqueResponse plant(configuration().response); plant.begin(kStart);
    ASSERT_TRUE(plant.set_target(100, kStart)); ASSERT_TRUE(plant.advance(kStart+150*kMs));
    ASSERT_TRUE(plant.constrain({-200, 40}, kStart+160*kMs)); EXPECT_DOUBLE_EQ(plant.actual_nm(), 100);
    ASSERT_TRUE(plant.advance(kStart+170*kMs)); EXPECT_DOUBLE_EQ(plant.actual_nm(), 80);
    ASSERT_TRUE(plant.advance(kStart+180*kMs)); EXPECT_DOUBLE_EQ(plant.actual_nm(), 60);
    ASSERT_TRUE(plant.advance(kStart+190*kMs)); EXPECT_DOUBLE_EQ(plant.actual_nm(), 40);
}
TEST(TorqueResponseTest, ZeroProtectionAndEnvelopeChangeNeverBackdateDetection) {
    simulation::TorqueResponse plant(configuration().response); plant.begin(kStart);
    ASSERT_TRUE(plant.set_target(100, kStart)); ASSERT_TRUE(plant.advance(kStart+150*kMs));
    plant.request_zero(kStart+151*kMs);
    ASSERT_TRUE(plant.constrain({0, 0}, kStart+151*kMs)); EXPECT_DOUBLE_EQ(plant.actual_nm(), 100);
    ASSERT_TRUE(plant.advance(kStart+160*kMs)); EXPECT_DOUBLE_EQ(plant.actual_nm(), 82);
    ASSERT_TRUE(plant.constrain({0, 0}, kStart+165*kMs));
    ASSERT_TRUE(plant.advance(kStart+170*kMs)); EXPECT_DOUBLE_EQ(plant.actual_nm(), 62);
}
TEST(TorqueResponseTest, InvalidEnvelopeIsRejectedAndNewSessionPreservesActualWithResetLimits) {
    simulation::TorqueResponse plant(configuration().response); plant.begin(kStart);
    EXPECT_FALSE(plant.constrain({1, 300}, kStart)); EXPECT_FALSE(plant.constrain({-200, -1}, kStart));
    EXPECT_FALSE(plant.constrain({-201, 300}, kStart));
    EXPECT_FALSE(plant.constrain({-200, std::numeric_limits<double>::infinity()}, kStart));
    ASSERT_TRUE(plant.constrain({-10, 10}, kStart)); EXPECT_FALSE(plant.set_target(20, kStart));
    plant.begin(kStart+10*kMs); EXPECT_TRUE(plant.set_target(20, kStart+10*kMs));
    EXPECT_FALSE(plant.constrain({0, 0}, kStart+9*kMs));
}
TEST(DriveActuatorConfigTest, InvalidWireTimingAndPlantParametersAreRejected) {
    auto config = configuration(); config.command_nm.maximum = 4000;
    EXPECT_THROW(simulation::DriveActuatorSil{config}, std::invalid_argument);
    config = configuration(); config.response.minimum_nm = -301;
    EXPECT_THROW(simulation::DriveActuatorSil{config}, std::invalid_argument);
    config = configuration(); config.response.delay_ns = 1001*kMs;
    EXPECT_THROW(simulation::DriveActuatorSil{config}, std::invalid_argument);
    config = configuration(); config.period_ns = 0;
    EXPECT_THROW(simulation::DriveActuatorSil{config}, std::invalid_argument);
    config = configuration(); config.max_source_age_ns = config.timeout_ns;
    EXPECT_THROW(simulation::DriveActuatorSil{config}, std::invalid_argument);
    config = configuration(); config.max_source_age_ns = 20*kMs;
    simulation::DriveActuatorSil short_age(config); EXPECT_TRUE(short_age.start_session(1, kStart));
}
TEST_F(DriveActuatorTest, StartupIsInitThenUnavailableAndHasNoInventedAuxFeedback) {
    for (int ms = 10; ms < 80; ms += 10) {
        const auto actual = tick(ms);
        EXPECT_EQ(actual.local_state, can::ActuatorLocalState::Init);
        EXPECT_EQ(actual.origin, can::ActuatorOrigin::NoAcceptedInput);
        ASSERT_TRUE(actual.torque_nm); EXPECT_DOUBLE_EQ(*actual.torque_nm, 0);
        EXPECT_FALSE(actual.wheel_speed); EXPECT_FALSE(actual.regen_capability);
        EXPECT_EQ(actual.regen_limit_reason, can::DriveRegenLimitReason::InputsInvalid);
    }
    const auto failed = tick(80);
    EXPECT_FALSE(failed.torque_nm); EXPECT_EQ(failed.local_state, can::ActuatorLocalState::FailSafe);
    EXPECT_FALSE(tick(90).torque_nm);
}
TEST_F(DriveActuatorTest, PositiveSaturationDelayAndIndependentActualMetadata) {
    can::DriveReceiver feedback({can::DriveFrameKind::Actual, {-300, 500}, 100, 300});
    ASSERT_TRUE(feedback.start_session(1, kStart));
    for (int ms = 10; ms <= 400; ms += 10) {
        ASSERT_EQ(model.receive(command({ms, 500}), kStart + ms*kMs).decision, can::ActuatorReceiveDecision::Accepted);
        const auto frame = model.tick(kStart + ms*kMs).value();
        ASSERT_EQ(feedback.receive(frame, kStart + ms*kMs).decision, can::ActuatorReceiveDecision::Accepted);
        const auto actual = feedback.current_sample(kStart + ms*kMs).value();
        EXPECT_NEAR(*actual.torque_nm, std::min(300, std::max(0, ms-60)), 0.051);
        EXPECT_EQ(actual.causal_sequence, sequence-1); EXPECT_EQ(actual.sequence, static_cast<unsigned>(ms/10-1));
        EXPECT_EQ(actual.source_time_ns, kStart + ms*kMs);
        EXPECT_FALSE(actual.wheel_speed); EXPECT_FALSE(actual.regen_capability);
    }
}
TEST_F(DriveActuatorTest, NegativeSaturationIsNotFabricatedChargeCapability) {
    for (int ms = 10; ms <= 300; ms += 10) {
        const auto actual = drive(ms, -300);
        EXPECT_NEAR(*actual.torque_nm, -std::min(200, std::max(0, ms-60)), 0.051);
        EXPECT_FALSE(actual.regen_capability);
    }
    EXPECT_DOUBLE_EQ(model.actual_torque_nm(), -200);
}
TEST_F(DriveActuatorTest, ReversalCrossesZeroAtNormalRateAfterItsOwnDelay) {
    for (int ms = 10; ms <= 200; ms += 10) drive(ms, 100);
    for (int ms = 210; ms <= 460; ms += 10) {
        const auto actual = drive(ms, -100);
        EXPECT_NEAR(*actual.torque_nm, std::max(-100, 100 - std::max(0, ms-260)), 0.051);
    }
    EXPECT_DOUBLE_EQ(model.actual_torque_nm(), -100);
}
TEST_F(DriveActuatorTest, ValidZeroCommandUsesNormalDelayAndRateRatherThanProtection) {
    for (int ms = 10; ms <= 200; ms += 10) drive(ms, 100);
    for (int ms = 210; ms <= 370; ms += 10) {
        const auto actual = drive(ms, 0);
        EXPECT_NEAR(*actual.torque_nm, std::max(0, 100 - std::max(0, ms-260)), 0.051);
        EXPECT_EQ(actual.local_state, can::ActuatorLocalState::Normal);
    }
    EXPECT_EQ(model.fault(), vecu::DriveFault::None);
}
TEST_F(DriveActuatorTest, PositiveLossCancelsPendingReversalAndZeroRampDoesNotRestart) {
    for (int ms = 10; ms <= 200; ms += 10) drive(ms, 100);
    drive(210, -200); // due=260, source expires at the 250 ms control tick
    tick(220); tick(230); tick(240);
    const auto first = tick(250); EXPECT_DOUBLE_EQ(*first.torque_nm, 100);
    EXPECT_EQ(first.local_state, can::ActuatorLocalState::FailSafe);
    for (int ms = 260; ms <= 350; ms += 10) {
        const auto actual = tick(ms);
        EXPECT_NEAR(*actual.torque_nm, std::max(0, 100-2*(ms-250)), 0.051);
        EXPECT_EQ(actual.origin, can::ActuatorOrigin::LocalProtection);
        EXPECT_EQ(actual.causal_sequence, 20U);
    }
    EXPECT_EQ(model.receive(command({360, 500}), kStart + 360*kMs).decision, can::ActuatorReceiveDecision::ModeRejected);
    EXPECT_DOUBLE_EQ(*tick(360).torque_nm, 0);
}
TEST_F(DriveActuatorTest, NegativeLossRampsTowardZeroWithoutPositiveOvershoot) {
    for (int ms = 10; ms <= 200; ms += 10) drive(ms, -200);
    tick(210); tick(220); tick(230);
    EXPECT_DOUBLE_EQ(*tick(240).torque_nm, -170);
    for (int ms = 250; ms <= 350; ms += 10) {
        EXPECT_NEAR(*tick(ms).torque_nm, std::min(0, -170+2*(ms-240)), 0.051);
    }
    EXPECT_DOUBLE_EQ(model.actual_torque_nm(), 0);
}
TEST_F(DriveActuatorTest, LateFreshInputCannotConcealExpiryBetweenControlTicks) {
    for (int ms = 10; ms <= 100; ms += 10) drive(ms, 500);
    tick(110); tick(120); tick(130);
    EXPECT_EQ(model.receive(command({131, -300}), kStart + 131*kMs).decision, can::ActuatorReceiveDecision::ModeRejected);
    EXPECT_DOUBLE_EQ(*tick(140).torque_nm, 52); // 70 Nm held, then 9 ms of zero ramp
    EXPECT_EQ(model.fault(), vecu::DriveFault::CommandUnavailable);
}
TEST_F(DriveActuatorTest, ContinuityLossStartsRampAtDetectionTimeOnly) {
    for (int ms = 10; ms <= 100; ms += 10) drive(ms, 500);
    model.mark_continuity_lost(kStart + 101*kMs);
    EXPECT_DOUBLE_EQ(*tick(110).torque_nm, 22);
    EXPECT_EQ(model.fault(), vecu::DriveFault::ContinuityLost);
    EXPECT_FALSE(model.current_sample(kStart + 110*kMs));
}
TEST_F(DriveActuatorTest, MissedDeadlineHoldsLostIntervalThenRunsZeroRamp) {
    for (int ms = 10; ms <= 100; ms += 10) drive(ms, 500);
    ASSERT_EQ(model.receive(command({130, 500}), kStart + 130*kMs).decision, can::ActuatorReceiveDecision::Accepted);
    EXPECT_DOUBLE_EQ(*tick(140).torque_nm, 40);
    EXPECT_EQ(model.fault(), vecu::DriveFault::ControlDeadline);
    EXPECT_DOUBLE_EQ(*tick(150).torque_nm, 20);
    EXPECT_DOUBLE_EQ(*tick(160).torque_nm, 0);
}
TEST_F(DriveActuatorTest, ClockRegressionSuppressesOutputAndDoesNotAdvancePhysics) {
    drive(10, 100); EXPECT_FALSE(model.tick(kStart + 10*kMs));
    EXPECT_EQ(drive(20, 100).sequence, 1U);
    EXPECT_FALSE(model.tick(kStart + 19*kMs)); EXPECT_FALSE(model.tick(kStart + 30*kMs));
    EXPECT_EQ(model.fault(), vecu::DriveFault::ClockError);
    EXPECT_DOUBLE_EQ(model.actual_torque_nm(), 0);
}
TEST_F(DriveActuatorTest, NewEpochPreservesTorqueCancelsOldDelayAndRestartsActualStream) {
    for (int ms = 10; ms <= 100; ms += 10) drive(ms, 500);
    model.mark_continuity_lost(kStart + 101*kMs); tick(110);
    EXPECT_FALSE(model.start_session(1, kStart + 110*kMs));
    EXPECT_FALSE(model.start_session(2, kStart + 109*kMs));
    ASSERT_TRUE(model.start_session(2, kStart + 110*kMs));
    EXPECT_DOUBLE_EQ(model.actual_torque_nm(), 22);
    const auto actual = tick(120);
    EXPECT_DOUBLE_EQ(*actual.torque_nm, 2); // INIT also requests zero; no torque teleport on restart
    EXPECT_EQ(actual.epoch, 2U); EXPECT_EQ(actual.sequence, 0U);
    EXPECT_EQ(actual.local_state, can::ActuatorLocalState::Init);
    EXPECT_EQ(model.fault(), vecu::DriveFault::None);
    EXPECT_EQ(model.receive(command({120, 100, 1}), kStart + 120*kMs).decision, can::ActuatorReceiveDecision::EpochMismatch);
}
TEST_F(DriveActuatorTest, CorruptUnavailableAndOutOfRangeFramesCannotRefreshCommand) {
    drive(10, 100);
    EXPECT_EQ(model.receive(command({20, 500.1}), kStart + 20*kMs).decision, can::ActuatorReceiveDecision::TorqueOutOfRange);
    tick(20);
    auto absent = can::decode_drive_frame(command({30, 0})).value(); absent.torque_nm.reset();
    EXPECT_EQ(model.receive(can::encode_drive_frame(absent, tx).value(), kStart + 30*kMs).decision, can::ActuatorReceiveDecision::Unavailable);
    tick(30);
    auto corrupt = command({40, 100}); corrupt.payload[0] ^= 1;
    EXPECT_NE(model.receive(corrupt, kStart + 40*kMs).decision, can::ActuatorReceiveDecision::Accepted);
    tick(40);
    EXPECT_EQ(model.receiver().last_accepted()->message.sequence, 0U);
    tick(50); EXPECT_EQ(model.fault(), vecu::DriveFault::CommandUnavailable);
    EXPECT_DOUBLE_EQ(model.actual_torque_nm(), 0);
}
TEST_F(DriveActuatorTest, ZeroDelayInitialStateAndDegradedCommandRemainDistinct) {
    auto config = configuration(); config.response.initial_nm = 50; config.response.delay_ns = 0;
    simulation::DriveActuatorSil other(config); ASSERT_TRUE(other.start_session(1, kStart));
    auto input = can::decode_drive_frame(command({10, 100})).value();
    input.local_state = can::ActuatorLocalState::Degraded;
    ASSERT_EQ(other.receive(can::encode_drive_frame(input, tx).value(), kStart + 10*kMs).decision, can::ActuatorReceiveDecision::Accepted);
    const auto actual = can::decode_drive_frame(other.tick(kStart + 10*kMs).value()).value();
    EXPECT_DOUBLE_EQ(*actual.torque_nm, 30); // previous INIT zero ramp acts until this tick's new goal
    EXPECT_EQ(actual.local_state, can::ActuatorLocalState::Degraded);
    ASSERT_TRUE(other.tick(kStart + 20*kMs)); EXPECT_DOUBLE_EQ(other.actual_torque_nm(), 40);
}
TEST_F(DriveActuatorTest, MaximumDelayAndRepeatedTargetChangesStayBounded) {
    auto config = configuration(); config.response.delay_ns = 1000*kMs;
    simulation::DriveActuatorSil other(config); ASSERT_TRUE(other.start_session(1, kStart));
    for (int ms = 10; ms <= 3000; ms += 10) {
        ASSERT_EQ(other.receive(command({ms, ms % 20 ? 500.0 : -300.0}), kStart + ms*kMs).decision, can::ActuatorReceiveDecision::Accepted);
        ASSERT_TRUE(other.tick(kStart + ms*kMs)); ASSERT_EQ(other.fault(), vecu::DriveFault::None);
        ASSERT_GE(other.actual_torque_nm(), -200); ASSERT_LE(other.actual_torque_nm(), 300);
    }
}
TEST(DriveExecutionBoundary, ExternalTorqueContinuesWithoutEcuAndZeroRequestCannotEraseResidual) {
    vecu::DriveActuator ecu(configuration()); simulation::TorqueResponse plant(configuration().response);
    ASSERT_TRUE(ecu.start_session({1,7,kStart})); plant.begin(kStart);
    can::DriveMessage m; m.epoch=1; m.torque_nm=200; m.source_time_ns=kStart+10*kMs;
    m.local_state=can::ActuatorLocalState::Normal; m.origin=can::ActuatorOrigin::NormalPath;
    can::DriveTxState tx{m.kind}; ASSERT_EQ(ecu.receive(*can::encode_drive_frame(m,tx),m.source_time_ns).decision,can::ActuatorReceiveDecision::Accepted);
    ASSERT_TRUE(ecu.prepare(m.source_time_ns)); ASSERT_TRUE(plant.set_target(ecu.output().target_nm,ecu.output().issued_time_ns));
    ASSERT_TRUE(plant.advance(m.source_time_ns)); ASSERT_TRUE(ecu.complete(drive::TorqueMeasurement{7,0,m.source_time_ns,plant.actual_nm()},m.source_time_ns));
    ASSERT_TRUE(plant.advance(kStart+100*kMs)); EXPECT_DOUBLE_EQ(plant.actual_nm(),40);
    ASSERT_TRUE(ecu.prepare(kStart+100*kMs)); EXPECT_EQ(ecu.fault(),vecu::DriveFault::ControlDeadline);
    plant.request_zero(ecu.output().issued_time_ns);
    const auto frame=ecu.complete(drive::TorqueMeasurement{7,1,kStart+100*kMs,plant.actual_nm()},kStart+100*kMs); ASSERT_TRUE(frame);
    EXPECT_DOUBLE_EQ(*can::decode_drive_frame(*frame)->torque_nm,40);
    ASSERT_TRUE(plant.advance(kStart+110*kMs)); EXPECT_DOUBLE_EQ(plant.actual_nm(),20);
}
}  // namespace
