#include "steering_actuator.hpp"

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
    vecu::SteeringActuator model{configuration()};
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
};
TEST(SteeringActuatorConfig, InvalidParametersAreRejectedBeforeRunning) {
    auto config = configuration(); config.max_rate_rad_s = 0;
    EXPECT_THROW(vecu::SteeringActuator{config}, std::invalid_argument);
    config = configuration(); config.delay_ns = 1001*kMs;
    EXPECT_THROW(vecu::SteeringActuator{config}, std::invalid_argument);
    config = configuration(); config.initial_angle_rad = std::numeric_limits<double>::quiet_NaN();
    EXPECT_THROW(vecu::SteeringActuator{config}, std::invalid_argument);
    config = configuration(); config.angle_max_rad = 0.6;
    EXPECT_THROW(vecu::SteeringActuator{config}, std::invalid_argument);
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
    vecu::SteeringActuator other(config);
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
}  // namespace
