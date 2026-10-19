#include "steering_sil.hpp"

#include <gtest/gtest.h>
#include <algorithm>
#include <limits>
#include <stdexcept>

namespace {
using namespace stratadrive;
constexpr std::uint64_t kStart = 1000000000, kMs = 1000000;
vecu::SteeringActuatorConfig configuration() { return {-0.5, 0.5, -0.3, 0.3, 0, 1, 50*kMs}; }
class SteeringActuatorTest : public ::testing::Test {
protected:
    simulation::SteeringSil model{configuration()};
    can::SteeringTxState tx{can::SteeringFrameKind::Command};
    std::uint32_t sequence{0};
    void SetUp() override { ASSERT_TRUE(model.start_session(1, kStart)); }
    struct CommandInput { int ms; double angle; std::uint32_t epoch{1}; };
    can::SteeringFrame command(CommandInput input) {
        const auto ms = input.ms; const auto angle = input.angle; const auto epoch = input.epoch;
        can::SteeringMessage message;
        message.angle_rad = angle; message.sequence = sequence++; message.epoch = epoch;
        message.source_time_ns = kStart + ms*kMs;
        message.local_state = can::SteeringLocalState::Normal;
        message.origin = can::SteeringOrigin::NormalPath;
        return can::encode_steering_frame(message, tx).value();
    }
    can::SteeringMessage tick(int ms) {
        return can::decode_steering_frame(model.tick(kStart + ms*kMs).value()).value();
    }
    can::SteeringMessage drive(int ms, double angle) {
        EXPECT_EQ(model.receive(command({ms, angle}), kStart + ms*kMs).decision,
                  can::SteeringReceiveDecision::Accepted);
        return tick(ms);
    }
    can::SteeringMessage injected(int ms, double angle, simulation::SteeringResponseInjection injection = {},
            simulation::SteeringSensorAction action = simulation::SteeringSensorAction::Acquire,
            std::optional<double> sensed = std::nullopt) {
        EXPECT_EQ(model.receive(command({ms, angle}), kStart+ms*kMs).decision, can::SteeringReceiveDecision::Accepted);
        return can::decode_steering_frame(model.tick(kStart+ms*kMs, injection, action, sensed).value()).value();
    }
};
TEST(SteeringActuatorConfig, InvalidParametersAreRejectedBeforeRunning) {
    auto config = configuration(); config.max_rate_rad_s = 0;
    EXPECT_THROW(simulation::SteeringSil{config}, std::invalid_argument);
    config = configuration(); config.delay_ns = 1001*kMs;
    EXPECT_THROW(simulation::SteeringSil{config}, std::invalid_argument);
    config = configuration(); config.initial_angle_rad = std::numeric_limits<double>::quiet_NaN();
    EXPECT_THROW(simulation::SteeringSil{config}, std::invalid_argument);
    config = configuration(); config.angle_max_rad = 0.6;
    EXPECT_THROW(simulation::SteeringSil{config}, std::invalid_argument);
}
TEST_F(SteeringActuatorTest, StartupIsInitAndSilentTimeoutIsUnavailable) {
    for (int ms = 10; ms < 80; ms += 10) {
        const auto actual = tick(ms);
        EXPECT_EQ(actual.local_state, can::SteeringLocalState::Init);
        EXPECT_EQ(actual.origin, can::SteeringOrigin::NoAcceptedInput);
        EXPECT_DOUBLE_EQ(*actual.angle_rad, 0);
    }
    const auto failed = tick(80);
    EXPECT_FALSE(failed.angle_rad);
    EXPECT_EQ(failed.local_state, can::SteeringLocalState::FailSafe);
    EXPECT_EQ(model.fault(), vecu::SteeringFault::CommandUnavailable);
}
TEST_F(SteeringActuatorTest, IdenticalRefreshDoesNotPostponeDelayAndActualIsNotEcho) {
    can::SteeringReceiver feedback({can::SteeringFrameKind::Actual, -0.3, 0.3});
    ASSERT_TRUE(feedback.start_session(1, kStart));
    for (int ms = 10; ms <= 300; ms += 10) {
        ASSERT_EQ(model.receive(command({ms, 0.2}), kStart + ms*kMs).decision, can::SteeringReceiveDecision::Accepted);
        const auto frame = model.tick(kStart + ms*kMs).value();
        ASSERT_EQ(feedback.receive(frame, kStart + ms*kMs).decision, can::SteeringReceiveDecision::Accepted);
        const auto actual = feedback.current_sample(kStart + ms*kMs).value();
        EXPECT_NEAR(*actual.angle_rad, std::min(0.2, std::max(0.0, (ms-60)/1000.0)), 0.000051);
        EXPECT_EQ(actual.causal_sequence, sequence-1);
        EXPECT_EQ(actual.source_time_ns, kStart + ms*kMs);
        EXPECT_EQ(actual.sequence, static_cast<std::uint32_t>(ms/10-1));
    }
    EXPECT_EQ(model.fault(), vecu::SteeringFault::None);
}
TEST_F(SteeringActuatorTest, NegativeSaturationAndCommandRangeHaveDifferentResponsibilities) {
    for (int ms = 10; ms <= 500; ms += 10) drive(ms, -0.4);
    EXPECT_NEAR(model.actual_angle_rad(), -0.3, 1e-12);
    EXPECT_EQ(model.receive(command({510, -0.6}), kStart + 510*kMs).decision,
              can::SteeringReceiveDecision::AngleOutOfRange);
    EXPECT_EQ(model.receiver().last_accepted()->message.sequence, sequence-2);
}
TEST_F(SteeringActuatorTest, ChangedDemandKeepsItsOwnDelayAndThenReversesAtLimitedRate) {
    for (int ms = 10; ms <= 160; ms += 10) {
        drive(ms, ms < 100 ? 0.2 : -0.2);
        if (ms == 150) { EXPECT_NEAR(model.actual_angle_rad(), 0.09, 1e-12); }
    }
    EXPECT_NEAR(model.actual_angle_rad(), 0.08, 1e-12);
}
TEST_F(SteeringActuatorTest, StaleCommandDiscardsPendingMotionAndCannotHealWithoutNewEpoch) {
    drive(10, 0.2);
    tick(20); tick(30); tick(40); // source age exactly 30 ms still usable
    const auto failed = tick(50);
    EXPECT_DOUBLE_EQ(model.actual_angle_rad(), 0);
    EXPECT_EQ(failed.origin, can::SteeringOrigin::LocalProtection);
    EXPECT_EQ(failed.local_state, can::SteeringLocalState::FailSafe);
    EXPECT_EQ(failed.causal_sequence, 0U);
    EXPECT_EQ(model.receive(command({60, 0.2}), kStart + 60*kMs).decision,
              can::SteeringReceiveDecision::ModeRejected);
    tick(60); tick(70); EXPECT_DOUBLE_EQ(model.actual_angle_rad(), 0);
    EXPECT_FALSE(model.start_session(1, kStart + 70*kMs));
    ASSERT_TRUE(model.start_session(2, kStart + 70*kMs));
    sequence = 0; e2e::p05_protect_init(tx.protection);
    EXPECT_EQ(model.receive(command({80, 0.2, 2}), kStart + 80*kMs).decision, can::SteeringReceiveDecision::Accepted);
    EXPECT_EQ(tick(80).sequence, 0U);
    EXPECT_EQ(model.fault(), vecu::SteeringFault::None);
}
TEST_F(SteeringActuatorTest, CorruptTrafficCannotRefreshFreshnessOrCauseMotion) {
    drive(10, 0.2);
    for (int ms = 20; ms <= 50; ms += 10) {
        auto frame = command({ms, -0.2}); frame.payload[0] ^= 1;
        EXPECT_NE(model.receive(frame, kStart + ms*kMs).decision, can::SteeringReceiveDecision::Accepted);
        tick(ms);
    }
    EXPECT_DOUBLE_EQ(model.actual_angle_rad(), 0);
    EXPECT_EQ(model.fault(), vecu::SteeringFault::CommandUnavailable);
}
TEST_F(SteeringActuatorTest, ContinuityLossHoldsAndRestartPreservesPhysicalAngle) {
    for (int ms = 10; ms <= 100; ms += 10) drive(ms, 0.2);
    const auto held = model.actual_angle_rad();
    model.mark_continuity_lost(kStart + 101*kMs);
    EXPECT_EQ(tick(110).origin, can::SteeringOrigin::LocalProtection);
    tick(120); EXPECT_DOUBLE_EQ(model.actual_angle_rad(), held);
    ASSERT_TRUE(model.start_session(2, kStart + 120*kMs));
    const auto actual = tick(130);
    EXPECT_NEAR(*actual.angle_rad, held, 0.000051);
    EXPECT_EQ(actual.local_state, can::SteeringLocalState::Init);
    EXPECT_EQ(actual.sequence, 0U);
}
TEST_F(SteeringActuatorTest, MissedControlDeadlineDoesNotCatchUpPhysics) {
    for (int ms = 10; ms <= 100; ms += 10) drive(ms, 0.2);
    const auto held = model.actual_angle_rad();
    ASSERT_EQ(model.receive(command({130, 0.2}), kStart + 130*kMs).decision, can::SteeringReceiveDecision::Accepted);
    EXPECT_EQ(tick(140).local_state, can::SteeringLocalState::FailSafe);
    EXPECT_EQ(model.fault(), vecu::SteeringFault::ControlDeadline);
    EXPECT_DOUBLE_EQ(model.actual_angle_rad(), held);
}
TEST_F(SteeringActuatorTest, ClockRegressionSuppressesPublicationAndDuplicateTickDoesNotConsumeSequence) {
    drive(10, 0.2);
    EXPECT_FALSE(model.tick(kStart + 10*kMs));
    EXPECT_EQ(drive(20, 0.2).sequence, 1U);
    EXPECT_FALSE(model.tick(kStart + 19*kMs));
    EXPECT_EQ(model.fault(), vecu::SteeringFault::ClockError);
    EXPECT_FALSE(model.tick(kStart + 30*kMs));
    EXPECT_FALSE(model.start_session(2, kStart + 19*kMs));
}
TEST_F(SteeringActuatorTest, DelayBoundaryInsideJitteredTickUsesOnlyTimeAfterBoundary) {
    drive(10, 0.2); drive(20, 0.2); drive(30, 0.2); drive(40, 0.2); drive(50, 0.2);
    drive(65, 0.2);
    EXPECT_NEAR(model.actual_angle_rad(), 0.005, 1e-12);
}
TEST_F(SteeringActuatorTest, LateFreshCommandCannotHideExpiryBeforeNextControlTick) {
    drive(10, 0.2);
    EXPECT_EQ(model.receive(command({41, -0.2}), kStart + 41*kMs).decision,
              can::SteeringReceiveDecision::ModeRejected);
    EXPECT_EQ(model.receiver().last_accepted()->message.sequence, 0U);
    EXPECT_EQ(model.fault(), vecu::SteeringFault::CommandUnavailable);
}
TEST_F(SteeringActuatorTest, ZeroDelayInitialAngleAndDegradedInputArePreserved) {
    auto config = configuration(); config.initial_angle_rad = 0.1; config.delay_ns = 0;
    simulation::SteeringSil other(config);
    ASSERT_TRUE(other.start_session(1, kStart));
    can::SteeringMessage input;
    input.epoch = 1; input.angle_rad = -0.2; input.source_time_ns = kStart + 10*kMs;
    input.local_state = can::SteeringLocalState::Degraded; input.origin = can::SteeringOrigin::NormalPath;
    ASSERT_EQ(other.receive(can::encode_steering_frame(input, tx).value(), input.source_time_ns).decision,
              can::SteeringReceiveDecision::Accepted);
    const auto first = can::decode_steering_frame(other.tick(input.source_time_ns).value()).value();
    EXPECT_NEAR(*first.angle_rad, 0.1, 0.000051);
    EXPECT_EQ(first.local_state, can::SteeringLocalState::Degraded);
    ASSERT_TRUE(other.tick(kStart + 20*kMs));
    EXPECT_NEAR(other.actual_angle_rad(), 0.09, 1e-12);
}
TEST_F(SteeringActuatorTest, FreshCommandsAndFreshConstantAnglesDetectJamWithoutCommunicationTimeout) {
    for (int ms = 10; ms <= 100; ms += 10) drive(ms, 0.2);
    const auto held = model.actual_angle_rad();
    can::SteeringMessage actual;
    for (int ms = 110; ms <= 190; ms += 10) actual = injected(ms, 0.2, {true, 1});
    EXPECT_EQ(model.fault(), vecu::SteeringFault::TrackingError);
    EXPECT_EQ(model.receiver().health(), can::SteeringReceiverHealth::Receiving);
    EXPECT_EQ(model.monitor_decision().violation_since_ns, kStart+130*kMs);
    EXPECT_EQ(model.monitor_decision().detected_time_ns, kStart+190*kMs);
    EXPECT_EQ(actual.local_state, can::SteeringLocalState::FailSafe); EXPECT_EQ(actual.origin, can::SteeringOrigin::LocalProtection);
    ASSERT_TRUE(actual.angle_rad); EXPECT_NEAR(*actual.angle_rad, held, 0.000051);
    EXPECT_EQ(actual.source_time_ns, kStart+190*kMs); EXPECT_EQ(actual.causal_sequence, sequence-1);
    EXPECT_EQ(model.receive(command({200, -0.2}), kStart+200*kMs).decision, can::SteeringReceiveDecision::ModeRejected);
    tick(200); tick(210); EXPECT_DOUBLE_EQ(model.actual_angle_rad(), held); // clearing the physical jam does not resume old targets
}
TEST_F(SteeringActuatorTest, SlowPhysicalMotionIsDetectedUsingTheSensorRatherThanTheInjectionFlag) {
    for (int ms = 10; ms <= 300 && model.fault() == vecu::SteeringFault::None; ms += 10) injected(ms, 0.2, {false, 0.25});
    EXPECT_EQ(model.fault(), vecu::SteeringFault::TrackingError);
    EXPECT_GT(model.actual_angle_rad(), 0); EXPECT_LT(model.actual_angle_rad(), 0.2);
    EXPECT_EQ(model.receiver().health(), can::SteeringReceiverHealth::Receiving);
}
TEST_F(SteeringActuatorTest, SensorBiasWithHealthyMechanicsAlsoProducesTrackingErrorWithoutClaimingRootCause) {
    for (int ms = 10; ms <= 100; ms += 10) drive(ms, 0.2);
    can::SteeringMessage actual;
    for (int ms = 110; ms <= 170; ms += 10) actual = injected(ms, 0.2, {}, simulation::SteeringSensorAction::Acquire, 0.3);
    EXPECT_EQ(model.fault(), vecu::SteeringFault::TrackingError);
    EXPECT_NEAR(*actual.angle_rad, 0.3, 0.000051); EXPECT_LT(model.actual_angle_rad(), 0.2);
}
TEST_F(SteeringActuatorTest, HealthyRateVariationReversalAndCommandSaturationDoNotTriggerTracking) {
    for (double rate : {0.8, 1.2}) {
        simulation::SteeringSil c(configuration()); ASSERT_TRUE(c.start_session(1, kStart));
        sequence = 0; e2e::p05_protect_init(tx.protection);
        for (int ms = 10; ms <= 1500; ms += 10) {
            ASSERT_EQ(c.receive(command({ms, ms < 700 ? 0.4 : -0.4}), kStart+ms*kMs).decision, can::SteeringReceiveDecision::Accepted);
            ASSERT_TRUE(c.tick(kStart+ms*kMs, {false, rate})); EXPECT_EQ(c.fault(), vecu::SteeringFault::None) << rate << ' ' << ms;
        }
    }
}
TEST_F(SteeringActuatorTest, HeldSensorsPublishUnavailableAndCannotRefreshActualReceiverAge) {
    can::SteeringReceiver feedback({can::SteeringFrameKind::Actual, -0.3, 0.3}); ASSERT_TRUE(feedback.start_session(1, kStart));
    for (int ms = 10; ms <= 100; ms += 10) {
        ASSERT_EQ(model.receive(command({ms, 0.2}), kStart+ms*kMs).decision, can::SteeringReceiveDecision::Accepted);
        ASSERT_EQ(feedback.receive(model.tick(kStart+ms*kMs).value(), kStart+ms*kMs).decision, can::SteeringReceiveDecision::Accepted);
    }
    for (int ms = 110; ms <= 130; ms += 10) {
        ASSERT_EQ(model.receive(command({ms, 0.2}), kStart+ms*kMs).decision, can::SteeringReceiveDecision::Accepted);
        const auto f = model.tick(kStart+ms*kMs, {}, simulation::SteeringSensorAction::Hold).value();
        EXPECT_FALSE(can::decode_steering_frame(f)->angle_rad);
        EXPECT_EQ(feedback.receive(f, kStart+ms*kMs).decision, can::SteeringReceiveDecision::Unavailable);
        EXPECT_EQ(feedback.last_accepted()->received_time_ns, kStart+100*kMs);
    }
    EXPECT_EQ(model.fault(), vecu::SteeringFault::SensorUnavailable);
    EXPECT_EQ(model.monitor_decision().fault, vecu::SteeringMonitorFault::SensorUnavailable);
    EXPECT_GT(model.actual_angle_rad(), 0); // a diagnostic truth value exists but never substitutes for the lost sensor
}
TEST_F(SteeringActuatorTest, InvalidAngleIsUnavailableInsteadOfFallingBackToThePlant) {
    drive(10, 0.2);
    const auto actual = injected(20, 0.2, {}, simulation::SteeringSensorAction::Acquire, std::numeric_limits<double>::quiet_NaN());
    EXPECT_FALSE(actual.angle_rad); EXPECT_EQ(model.fault(), vecu::SteeringFault::SensorInvalid);
    EXPECT_EQ(actual.local_state, can::SteeringLocalState::FailSafe);
}
TEST_F(SteeringActuatorTest, NewEpochResetsTheMonitorAndRechecksSensorsWhilePhysicalAngleSurvives) {
    for (int ms = 10; ms <= 100; ms += 10) drive(ms, 0.2);
    for (int ms = 110; ms <= 190; ms += 10) injected(ms, 0.2, {true, 1});
    const auto held = model.actual_angle_rad(); EXPECT_FALSE(model.start_session(1, kStart+190*kMs));
    ASSERT_TRUE(model.start_session(2, kStart+190*kMs)); sequence = 0; e2e::p05_protect_init(tx.protection);
    for (int ms = 200; ms <= 500; ms += 10) {
        ASSERT_EQ(model.receive(command({ms, 0.2, 2}), kStart+ms*kMs).decision, can::SteeringReceiveDecision::Accepted);
        const auto actual = tick(ms);
        EXPECT_EQ(model.fault(), vecu::SteeringFault::None);
        if (ms == 200) { EXPECT_EQ(actual.sequence, 0U); EXPECT_NEAR(*actual.angle_rad, held, 0.000051); }
    }
    EXPECT_NEAR(model.actual_angle_rad(), 0.2, 1e-12);
}
TEST_F(SteeringActuatorTest, InvalidPhysicalIntervalDoesNotProduceAFreshValidAngle) {
    drive(10, 0.2);
    const auto actual = injected(20, 0.2, {false, -1});
    EXPECT_FALSE(actual.angle_rad); EXPECT_EQ(model.fault(), vecu::SteeringFault::PhysicalModelError);
    EXPECT_DOUBLE_EQ(model.actual_angle_rad(), 0);
}
TEST_F(SteeringActuatorTest, TransientResidualIsDegradedThenReturnsToNormalBeforeFaultConfirmation) {
    for (int ms = 10; ms <= 150; ms += 10) drive(ms, 0.2);
    const auto transient = injected(160, 0.2, {}, simulation::SteeringSensorAction::Acquire, 0.3);
    EXPECT_EQ(transient.local_state, can::SteeringLocalState::Degraded); EXPECT_EQ(model.fault(), vecu::SteeringFault::None);
    const auto recovered = drive(170, 0.2);
    EXPECT_EQ(recovered.local_state, can::SteeringLocalState::Normal); EXPECT_FALSE(model.monitor_decision().violation_since_ns);
}
TEST(SteeringExecutionBoundary, ExternalPlantContinuesWhileEcuCallsStopAndResumeDoesNotRewindIt) {
    vecu::SteeringActuator ecu(configuration()); simulation::SteeringResponse plant({-.3,.3,0,1,50*kMs});
    ASSERT_TRUE(ecu.start_session({1,1,kStart})); ASSERT_TRUE(plant.begin(kStart));
    can::SteeringMessage m; m.epoch=1; m.angle_rad=.2; m.source_time_ns=kStart+10*kMs;
    m.local_state=can::SteeringLocalState::Normal; m.origin=can::SteeringOrigin::NormalPath;
    can::SteeringTxState tx{m.kind}; ASSERT_EQ(ecu.receive(*can::encode_steering_frame(m,tx),m.source_time_ns).decision,can::SteeringReceiveDecision::Accepted);
    ASSERT_TRUE(ecu.prepare(m.source_time_ns)); ASSERT_TRUE(plant.advance(m.source_time_ns)); ASSERT_TRUE(ecu.complete(plant.capture(),m.source_time_ns));
    ASSERT_TRUE(plant.set_target(ecu.output().target_rad,ecu.output().issued_time_ns));
    // No ECU method is called while the external plant advances 90 ms.
    ASSERT_TRUE(plant.advance(kStart+100*kMs)); EXPECT_NEAR(plant.actual_angle_rad(),.04,1e-12);
    ASSERT_TRUE(ecu.prepare(kStart+100*kMs)); EXPECT_EQ(ecu.fault(),vecu::SteeringFault::ControlDeadline);
    ASSERT_TRUE(plant.hold(kStart+100*kMs)); ASSERT_TRUE(ecu.complete(plant.capture(),kStart+100*kMs));
    EXPECT_NEAR(plant.actual_angle_rad(),.04,1e-12); EXPECT_EQ(ecu.output().mode,steering::ActuationMode::Hold);
}

class SteeringStartupTest : public SteeringActuatorTest {
protected:
    void SetUp() override { ASSERT_TRUE(model.start_session(1,kStart,ActuatorCommandStartup::NonDriving)); }
    void wait_until(int last) { for (int ms=10;ms<=last;ms+=10) ASSERT_TRUE(model.tick(kStart+ms*kMs)); }
};
TEST_F(SteeringStartupTest, LongStartupPublishesKnownInitWithoutNormalPackets) {
    can::SteeringMessage actual;
    for (int ms=10;ms<=1000;ms+=10) {
        actual=tick(ms); ASSERT_TRUE(actual.angle_rad); EXPECT_EQ(actual.local_state,can::SteeringLocalState::Init);
        EXPECT_EQ(actual.origin,can::SteeringOrigin::NoAcceptedInput); EXPECT_EQ(actual.causal_sequence,0U);
    }
    EXPECT_EQ(model.fault(),vecu::SteeringFault::None); EXPECT_EQ(actual.sequence,99U);
    EXPECT_EQ(model.receiver().health(),can::SteeringReceiverHealth::NotInitialized);
    EXPECT_FALSE(model.current_sample(kStart+1000*kMs));
}
TEST_F(SteeringStartupTest, EarlyPacketsCannotArmOrConsumeFirstNormalIdentity) {
    wait_until(200); sequence=9;
    EXPECT_EQ(model.receive(command({200,0.2}),kStart+200*kMs).decision,can::SteeringReceiveDecision::NotInitialized);
    ASSERT_TRUE(model.tick(kStart+210*kMs)); ASSERT_TRUE(model.arm_normal_commands(kStart+210*kMs));
    EXPECT_FALSE(model.arm_normal_commands(kStart+210*kMs)); sequence=0;
    EXPECT_EQ(model.receive(command({200,0.2}),kStart+210*kMs).decision,can::SteeringReceiveDecision::SourceBeforeSession);
    sequence=0; EXPECT_EQ(model.receive(command({220,0.2}),kStart+220*kMs).decision,can::SteeringReceiveDecision::Accepted);
    ASSERT_TRUE(model.receiver().last_accepted()); EXPECT_EQ(model.receiver().last_accepted()->message.sequence,0U);
    EXPECT_EQ(tick(220).sequence,21U); EXPECT_EQ(model.fault(),vecu::SteeringFault::None);
}
TEST_F(SteeringStartupTest, ArmNeedsANewValidAcquisitionRatherThanCachedPublication) {
    EXPECT_FALSE(model.arm_normal_commands(kStart)); wait_until(100);
    ASSERT_TRUE(model.tick(kStart+110*kMs,{},simulation::SteeringSensorAction::Hold));
    EXPECT_FALSE(model.arm_normal_commands(kStart+110*kMs)); EXPECT_EQ(model.fault(),vecu::SteeringFault::None);
    ASSERT_TRUE(model.tick(kStart+120*kMs)); EXPECT_TRUE(model.arm_normal_commands(kStart+120*kMs));
}
TEST_F(SteeringStartupTest, ExpiredSensorAtArmLatchesBeforeLateFreshAcquisition) {
    wait_until(100); EXPECT_FALSE(model.arm_normal_commands(kStart+121*kMs));
    EXPECT_EQ(model.fault(),vecu::SteeringFault::SensorUnavailable);
    ASSERT_TRUE(model.tick(kStart+130*kMs)); EXPECT_FALSE(model.arm_normal_commands(kStart+130*kMs));
}
TEST_F(SteeringStartupTest, MissingSensorStillSelectsProtectionDuringStartup) {
    wait_until(100); ASSERT_TRUE(model.tick(kStart+110*kMs,{},simulation::SteeringSensorAction::Invalidate));
    EXPECT_EQ(model.fault(),vecu::SteeringFault::SensorUnavailable); EXPECT_FALSE(model.arm_normal_commands(kStart+110*kMs));
}
TEST_F(SteeringStartupTest, ControlGapCannotBeHiddenByArm) {
    wait_until(100); EXPECT_FALSE(model.arm_normal_commands(kStart+131*kMs));
    EXPECT_EQ(model.fault(),vecu::SteeringFault::ControlDeadline);
}
TEST_F(SteeringStartupTest, WaitingBudgetStartsAtArmAndCannotBeRearmed) {
    wait_until(1000); ASSERT_TRUE(model.arm_normal_commands(kStart+1000*kMs));
    for (int ms=1010;ms<1080;ms+=10) { ASSERT_TRUE(model.tick(kStart+ms*kMs)); EXPECT_EQ(model.fault(),vecu::SteeringFault::None); }
    EXPECT_FALSE(model.arm_normal_commands(kStart+1070*kMs)); ASSERT_TRUE(model.tick(kStart+1080*kMs));
    EXPECT_EQ(model.fault(),vecu::SteeringFault::CommandUnavailable);
}
TEST_F(SteeringStartupTest, NewNonDrivingEpochPreservesPhysicsButNotOldCommandCausality) {
    wait_until(10); ASSERT_TRUE(model.arm_normal_commands(kStart+10*kMs));
    for (int ms=20;ms<=300;ms+=10) drive(ms,0.2);
    const auto physical=model.actual_angle_rad(); ASSERT_TRUE(model.start_session(2,kStart+300*kMs,ActuatorCommandStartup::NonDriving));
    const auto actual=tick(310); ASSERT_TRUE(actual.angle_rad); EXPECT_NEAR(*actual.angle_rad,physical,0.000051);
    EXPECT_EQ(actual.sequence,0U); EXPECT_EQ(actual.causal_sequence,0U); EXPECT_EQ(actual.origin,can::SteeringOrigin::NoAcceptedInput);
    EXPECT_FALSE(model.current_sample(kStart+310*kMs)); EXPECT_EQ(model.fault(),vecu::SteeringFault::None);
}
TEST_F(SteeringStartupTest, StartupClockAndInitCannotRegressBehindIngress) {
    wait_until(100); EXPECT_EQ(model.receive(command({110,0.2}),kStart+110*kMs).decision,can::SteeringReceiveDecision::NotInitialized);
    EXPECT_FALSE(model.start_session(2,kStart+109*kMs,ActuatorCommandStartup::NonDriving));
    EXPECT_FALSE(model.arm_normal_commands(kStart+109*kMs)); EXPECT_EQ(model.fault(),vecu::SteeringFault::ClockError);
}
}  // namespace
