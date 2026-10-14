#include "brake_actuator.hpp"

#include <gtest/gtest.h>
#include <algorithm>
#include <limits>
#include <stdexcept>

namespace {
using namespace stratadrive;
constexpr std::uint64_t kStart = 1000000000, kMs = 1000000;
vecu::BrakeActuatorConfig configuration() { return {2000000, 1500000, 0, 5000000, 10000000, 1000000, 50*kMs}; }
class BrakeActuatorTest : public ::testing::Test {
protected:
    vecu::BrakeActuator model{configuration()};
    can::BrakeTxState tx{can::BrakeFrameKind::Command};
    std::uint32_t sequence{0};
    struct Input { int ms; double pressure; std::uint32_t epoch{1}; };
    void SetUp() override { ASSERT_TRUE(model.start_session(1, kStart)); }
    can::BrakeFrame command(Input input) {
        can::BrakeMessage message;
        message.pressure_pa = input.pressure; message.sequence = sequence++; message.epoch = input.epoch;
        message.source_time_ns = kStart + input.ms*kMs;
        message.local_state = can::BrakeLocalState::Normal; message.origin = can::BrakeOrigin::NormalPath;
        return can::encode_brake_frame(message, tx).value();
    }
    can::BrakeMessage tick(int ms) {
        return can::decode_brake_frame(model.tick(kStart + ms*kMs).value()).value();
    }
    can::BrakeMessage drive(int ms, double pressure) {
        EXPECT_EQ(model.receive(command({ms, pressure}), kStart + ms*kMs).decision, can::BrakeReceiveDecision::Accepted);
        return tick(ms);
    }
};
TEST(BrakeActuatorConfig, InvalidPressureRateFloorAndTimingAreRejected) {
    auto config = configuration(); config.rise_rate_pa_s = 0;
    EXPECT_THROW(vecu::BrakeActuator{config}, std::invalid_argument);
    config = configuration(); config.fall_rate_pa_s = -1;
    EXPECT_THROW(vecu::BrakeActuator{config}, std::invalid_argument);
    config = configuration(); config.fault_pressure_floor_pa = 1600000;
    EXPECT_THROW(vecu::BrakeActuator{config}, std::invalid_argument);
    config = configuration(); config.initial_pressure_pa = std::numeric_limits<double>::quiet_NaN();
    EXPECT_THROW(vecu::BrakeActuator{config}, std::invalid_argument);
    config = configuration(); config.delay_ns = 1001*kMs;
    EXPECT_THROW(vecu::BrakeActuator{config}, std::invalid_argument);
}
TEST_F(BrakeActuatorTest, StartupSilenceIsInitThenDiagnosticUnavailableWithoutPressureJump) {
    for (int ms = 10; ms < 80; ms += 10) {
        const auto actual = tick(ms);
        EXPECT_EQ(actual.local_state, can::BrakeLocalState::Init);
        EXPECT_EQ(actual.origin, can::BrakeOrigin::NoAcceptedInput);
        EXPECT_DOUBLE_EQ(*actual.pressure_pa, 0);
    }
    const auto failed = tick(80);
    EXPECT_FALSE(failed.pressure_pa);
    EXPECT_EQ(failed.local_state, can::BrakeLocalState::FailSafe);
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(), 0);
    EXPECT_FALSE(tick(90).pressure_pa);
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(), 50000);
}
TEST_F(BrakeActuatorTest, RepeatedCommandKeepsDelayRateAndSaturationWithIndependentActual) {
    can::BrakeReceiver feedback({can::BrakeFrameKind::Actual, 0, 1500000});
    ASSERT_TRUE(feedback.start_session(1, kStart));
    for (int ms = 10; ms <= 400; ms += 10) {
        ASSERT_EQ(model.receive(command({ms, 2000000}), kStart + ms*kMs).decision, can::BrakeReceiveDecision::Accepted);
        const auto frame = model.tick(kStart + ms*kMs).value();
        ASSERT_EQ(feedback.receive(frame, kStart + ms*kMs).decision, can::BrakeReceiveDecision::Accepted);
        const auto actual = feedback.current_sample(kStart + ms*kMs).value();
        EXPECT_NEAR(*actual.pressure_pa, std::min(1500000.0, std::max(0.0, (ms-60)*5000.0)), 500.1);
        EXPECT_EQ(actual.causal_sequence, sequence-1);
        EXPECT_EQ(actual.source_time_ns, kStart + ms*kMs);
        EXPECT_EQ(actual.sequence, static_cast<std::uint32_t>(ms/10-1));
    }
    EXPECT_EQ(model.fault(), vecu::BrakeFault::None);
}
TEST_F(BrakeActuatorTest, ValidZeroReleasesWithDelayAndSeparateFasterFallRate) {
    for (int ms = 10; ms <= 300; ms += 10) drive(ms, 1000000);
    for (int ms = 310; ms <= 470; ms += 10) {
        const auto actual = drive(ms, 0);
        ASSERT_TRUE(actual.pressure_pa);
        EXPECT_NEAR(*actual.pressure_pa, std::max(0.0, 1000000.0 - std::max(0, ms-360)*10000.0), 500.1);
    }
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(), 0);
    EXPECT_EQ(model.fault(), vecu::BrakeFault::None);
}
TEST_F(BrakeActuatorTest, TargetChangesHaveSeparateDueTimesAndCanCancelBuildup) {
    for (int ms = 10; ms <= 110; ms += 10) {
        drive(ms, ms < 40 ? 1000000 : 0);
        if (ms == 90) { EXPECT_DOUBLE_EQ(model.actual_pressure_pa(), 150000); }
    }
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(), 0);
}
TEST_F(BrakeActuatorTest, JitteredTickSplitsAtDelayBoundary) {
    for (int ms = 10; ms <= 50; ms += 10) drive(ms, 1000000);
    drive(65, 1000000);
    EXPECT_NEAR(model.actual_pressure_pa(), 25000, 1e-6);
}
TEST_F(BrakeActuatorTest, ExpiryCancelsDelayedReleaseAndProtectiveFloorRampsWithoutRestarting) {
    drive(10, 0); tick(20); tick(30); tick(40);
    EXPECT_DOUBLE_EQ(*tick(50).pressure_pa, 0);
    for (int ms = 60; ms <= 280; ms += 10) {
        const auto actual = tick(ms);
        EXPECT_NEAR(*actual.pressure_pa, std::min(1000000.0, (ms-50)*5000.0), 500.1);
        EXPECT_EQ(actual.origin, can::BrakeOrigin::LocalProtection);
        EXPECT_EQ(actual.local_state, can::BrakeLocalState::FailSafe);
        EXPECT_EQ(actual.causal_sequence, 0U);
    }
}
TEST_F(BrakeActuatorTest, HigherPressureIsRetainedOnLossAndLateZeroCannotReleaseIt) {
    for (int ms = 10; ms <= 400; ms += 10) drive(ms, 2000000);
    drive(410, 0); // release due at 460 ms; expiry must cancel this pending target
    for (int ms = 420; ms <= 450; ms += 10) tick(ms);
    ASSERT_EQ(model.fault(), vecu::BrakeFault::CommandUnavailable);
    EXPECT_EQ(model.receive(command({460, 0}), kStart + 460*kMs).decision, can::BrakeReceiveDecision::ModeRejected);
    tick(460); tick(470);
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(), 1500000);
    EXPECT_EQ(model.receiver().last_accepted()->message.sequence, 40U);
}
TEST_F(BrakeActuatorTest, LossDuringBuildupRampsToFloorInsteadOfJumpingOrReleasing) {
    for (int ms = 10; ms <= 100; ms += 10) drive(ms, 2000000);
    tick(110); tick(120); tick(130);
    EXPECT_DOUBLE_EQ(*tick(140).pressure_pa, 350000);
    EXPECT_DOUBLE_EQ(*tick(150).pressure_pa, 400000);
    for (int ms = 160; ms <= 300; ms += 10) tick(ms);
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(), 1000000);
}
TEST_F(BrakeActuatorTest, ContinuityLossUsesOnlyElapsedTimeAfterDetection) {
    for (int ms = 10; ms <= 100; ms += 10) drive(ms, 1000000);
    model.mark_continuity_lost(kStart + 101*kMs);
    EXPECT_DOUBLE_EQ(*tick(110).pressure_pa, 245000);
    EXPECT_EQ(model.fault(), vecu::BrakeFault::ContinuityLost);
    EXPECT_EQ(model.receive(command({120, 0}), kStart + 120*kMs).decision, can::BrakeReceiveDecision::ModeRejected);
}
TEST_F(BrakeActuatorTest, MissedDeadlineDoesNotBackfillButLaterTicksCanRunProtection) {
    for (int ms = 10; ms <= 100; ms += 10) drive(ms, 1000000);
    ASSERT_EQ(model.receive(command({130, 1000000}), kStart + 130*kMs).decision, can::BrakeReceiveDecision::Accepted);
    EXPECT_DOUBLE_EQ(*tick(140).pressure_pa, 200000);
    EXPECT_EQ(model.fault(), vecu::BrakeFault::ControlDeadline);
    EXPECT_DOUBLE_EQ(*tick(150).pressure_pa, 250000);
}
TEST_F(BrakeActuatorTest, ClockRegressionSuppressesFeedbackAndMotion) {
    drive(10, 1000000);
    EXPECT_FALSE(model.tick(kStart + 10*kMs));
    EXPECT_EQ(drive(20, 1000000).sequence, 1U);
    EXPECT_FALSE(model.tick(kStart + 19*kMs));
    EXPECT_FALSE(model.tick(kStart + 30*kMs));
    EXPECT_EQ(model.fault(), vecu::BrakeFault::ClockError);
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(), 0);
}
TEST_F(BrakeActuatorTest, NewEpochPreservesPhysicalPressureAndResetsFeedbackStream) {
    for (int ms = 10; ms <= 100; ms += 10) drive(ms, 1000000);
    model.mark_continuity_lost(kStart + 101*kMs); tick(110);
    const auto held = model.actual_pressure_pa();
    EXPECT_FALSE(model.start_session(1, kStart + 110*kMs));
    EXPECT_FALSE(model.start_session(2, kStart + 109*kMs));
    ASSERT_TRUE(model.start_session(2, kStart + 110*kMs));
    const auto actual = tick(120);
    EXPECT_DOUBLE_EQ(*actual.pressure_pa, held);
    EXPECT_EQ(actual.epoch, 2U); EXPECT_EQ(actual.sequence, 0U);
    EXPECT_EQ(actual.local_state, can::BrakeLocalState::Init);
    EXPECT_EQ(model.fault(), vecu::BrakeFault::None);
}
TEST_F(BrakeActuatorTest, RangeUnavailableAndCorruptionDoNotRefreshAcceptedCommand) {
    drive(10, 1000000);
    EXPECT_EQ(model.receive(command({20, 2100000}), kStart + 20*kMs).decision, can::BrakeReceiveDecision::PressureOutOfRange);
    auto unavailable = can::decode_brake_frame(command({30, 0})).value(); unavailable.pressure_pa.reset();
    EXPECT_EQ(model.receive(can::encode_brake_frame(unavailable, tx).value(), kStart + 30*kMs).decision,
              can::BrakeReceiveDecision::Unavailable);
    auto corrupt = command({40, 1000000}); corrupt.payload[0] ^= 1;
    EXPECT_NE(model.receive(corrupt, kStart + 40*kMs).decision, can::BrakeReceiveDecision::Accepted);
    EXPECT_EQ(model.receiver().last_accepted()->message.sequence, 0U);
    EXPECT_EQ(model.receive(command({41, 0}), kStart + 41*kMs).decision, can::BrakeReceiveDecision::ModeRejected);
    EXPECT_EQ(model.fault(), vecu::BrakeFault::CommandUnavailable);
}
TEST_F(BrakeActuatorTest, InitialPressureZeroDelayAndDegradedInputRemainDistinct) {
    auto config = configuration(); config.initial_pressure_pa = 500000; config.delay_ns = 0;
    vecu::BrakeActuator other(config); ASSERT_TRUE(other.start_session(1, kStart));
    can::BrakeMessage input;
    input.epoch = 1; input.pressure_pa = 1000000; input.source_time_ns = kStart + 10*kMs;
    input.local_state = can::BrakeLocalState::Degraded; input.origin = can::BrakeOrigin::NormalPath;
    ASSERT_EQ(other.receive(can::encode_brake_frame(input, tx).value(), input.source_time_ns).decision, can::BrakeReceiveDecision::Accepted);
    const auto first = can::decode_brake_frame(other.tick(input.source_time_ns).value()).value();
    EXPECT_DOUBLE_EQ(*first.pressure_pa, 500000);
    EXPECT_EQ(first.local_state, can::BrakeLocalState::Degraded);
    ASSERT_TRUE(other.tick(kStart + 20*kMs)); EXPECT_DOUBLE_EQ(other.actual_pressure_pa(), 550000);
}
TEST_F(BrakeActuatorTest, MaximumDelayAndManyTargetChangesStayWithinBoundedHistory) {
    auto config = configuration(); config.delay_ns = 1000*kMs;
    vecu::BrakeActuator other(config); ASSERT_TRUE(other.start_session(1, kStart));
    for (int ms = 10; ms <= 3000; ms += 10) {
        ASSERT_EQ(other.receive(command({ms, ms % 20 ? 1000000.0 : 0.0}), kStart + ms*kMs).decision,
                  can::BrakeReceiveDecision::Accepted);
        ASSERT_TRUE(other.tick(kStart + ms*kMs));
        ASSERT_EQ(other.fault(), vecu::BrakeFault::None);
        ASSERT_GE(other.actual_pressure_pa(), 0); ASSERT_LE(other.actual_pressure_pa(), 1500000);
    }
}
}  // namespace
