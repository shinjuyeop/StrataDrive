#include "steering_response.hpp"

#include <gtest/gtest.h>
#include <limits>
#include <stdexcept>

namespace {
using namespace stratadrive;
constexpr std::uint64_t kStart = 1000000000, kMs = 1000000;
simulation::SteeringResponseConfig config() { return {-0.3, 0.3, 0, 1, 50*kMs, 7}; }
TEST(SteeringResponseTest, InvalidPhysicalConfigurationAndUninitializedCallsAreRejected) {
    auto c = config(); c.initial_rad = 0.4; EXPECT_THROW(simulation::SteeringResponse{c}, std::invalid_argument);
    c = config(); c.rate_rad_s = 0; EXPECT_THROW(simulation::SteeringResponse{c}, std::invalid_argument);
    c = config(); c.model_epoch = 0; EXPECT_THROW(simulation::SteeringResponse{c}, std::invalid_argument);
    simulation::SteeringResponse p(config()); EXPECT_FALSE(p.capture()); EXPECT_FALSE(p.advance(kStart)); EXPECT_FALSE(p.set_target(0.2, kStart));
}
TEST(SteeringResponseTest, DelayBoundaryAndJitterHaveAnalyticalMotionWithoutCommandEcho) {
    simulation::SteeringResponse p(config()); ASSERT_TRUE(p.begin(kStart)); ASSERT_TRUE(p.set_target(0.2, kStart+10*kMs));
    ASSERT_TRUE(p.advance(kStart+60*kMs)); EXPECT_DOUBLE_EQ(p.actual_angle_rad(), 0);
    ASSERT_TRUE(p.advance(kStart+65*kMs)); EXPECT_NEAR(p.actual_angle_rad(), 0.005, 1e-12);
    ASSERT_TRUE(p.advance(kStart+300*kMs)); EXPECT_DOUBLE_EQ(p.actual_angle_rad(), 0.2);
    EXPECT_FALSE(p.set_target(0.4, kStart+300*kMs));
}
TEST(SteeringResponseTest, JamStopsMotionButFreshAcquisitionsContinueAdvancing) {
    simulation::SteeringResponse p(config()); ASSERT_TRUE(p.begin(kStart)); ASSERT_TRUE(p.set_target(0.2, kStart));
    ASSERT_TRUE(p.advance(kStart+100*kMs)); const auto before = p.capture().value();
    ASSERT_TRUE(p.advance(kStart+110*kMs, {true, 1})); const auto jammed = p.capture().value();
    EXPECT_EQ(before.angle_rad, jammed.angle_rad); EXPECT_GT(jammed.sequence, before.sequence); EXPECT_GT(jammed.source_time_ns, before.source_time_ns);
    ASSERT_TRUE(p.advance(kStart+120*kMs)); EXPECT_NEAR(p.actual_angle_rad(), 0.06, 1e-12);
}
TEST(SteeringResponseTest, SlowAndFastPhysicalVariationsApplyOnlyToTheDeclaredInterval) {
    simulation::SteeringResponse p(config()); ASSERT_TRUE(p.begin(kStart)); ASSERT_TRUE(p.set_target(-0.2, kStart));
    ASSERT_TRUE(p.advance(kStart+100*kMs)); EXPECT_NEAR(p.actual_angle_rad(), -0.05, 1e-12);
    ASSERT_TRUE(p.advance(kStart+120*kMs, {false, 0.5})); EXPECT_NEAR(p.actual_angle_rad(), -0.06, 1e-12);
    ASSERT_TRUE(p.advance(kStart+130*kMs, {false, 2})); EXPECT_NEAR(p.actual_angle_rad(), -0.08, 1e-12);
}
TEST(SteeringResponseTest, HoldAndSessionBeginCancelPendingMotionWithoutResettingPhysicalAngleOrSensorIdentity) {
    simulation::SteeringResponse p(config()); ASSERT_TRUE(p.begin(kStart)); ASSERT_TRUE(p.set_target(0.2, kStart));
    ASSERT_TRUE(p.advance(kStart+100*kMs)); const auto a = p.capture().value();
    ASSERT_TRUE(p.hold(kStart+140*kMs)); ASSERT_TRUE(p.advance(kStart+200*kMs)); EXPECT_EQ(p.actual_angle_rad(), a.angle_rad);
    ASSERT_TRUE(p.begin(kStart+200*kMs)); ASSERT_TRUE(p.advance(kStart+210*kMs)); const auto b = p.capture().value();
    EXPECT_EQ(b.model_epoch, a.model_epoch); EXPECT_GT(b.sequence, a.sequence); EXPECT_EQ(b.angle_rad, a.angle_rad);
}
TEST(SteeringResponseTest, HeldAndInvalidSensorsCannotBeRecreatedByReadingPhysicalTruth) {
    simulation::SteeringResponse p(config()); ASSERT_TRUE(p.begin(kStart)); const auto a = p.capture().value();
    ASSERT_TRUE(p.set_target(0.2, kStart)); ASSERT_TRUE(p.advance(kStart+100*kMs));
    const auto held = p.capture(simulation::SteeringSensorAction::Hold).value();
    EXPECT_EQ(held.sequence, a.sequence); EXPECT_EQ(held.source_time_ns, a.source_time_ns); EXPECT_EQ(held.angle_rad, a.angle_rad);
    EXPECT_NE(p.actual_angle_rad(), held.angle_rad);
    EXPECT_FALSE(p.capture(simulation::SteeringSensorAction::Invalidate)); EXPECT_FALSE(p.capture(simulation::SteeringSensorAction::Hold));
    const auto acquired = p.capture().value(); EXPECT_GT(acquired.sequence, a.sequence); EXPECT_EQ(acquired.angle_rad, p.actual_angle_rad());
}
TEST(SteeringResponseTest, SensorOverrideDoesNotChangeThePlantAndDuplicateCaptureIsNotNewAcquisition) {
    simulation::SteeringResponse p(config()); ASSERT_TRUE(p.begin(kStart));
    EXPECT_DOUBLE_EQ(p.capture(simulation::SteeringSensorAction::Acquire, 0.1)->angle_rad, 0.1);
    EXPECT_DOUBLE_EQ(p.actual_angle_rad(), 0); EXPECT_FALSE(p.capture());
    p.capture(simulation::SteeringSensorAction::Invalidate); EXPECT_FALSE(p.capture());
    ASSERT_TRUE(p.advance(kStart+10*kMs)); EXPECT_DOUBLE_EQ(p.capture()->angle_rad, 0);
}
TEST(SteeringResponseTest, InvalidTimeInjectionAndOverflowDoNotAdvancePhysicalState) {
    simulation::SteeringResponse p(config()); ASSERT_TRUE(p.begin(kStart)); ASSERT_TRUE(p.set_target(0.2, kStart));
    EXPECT_FALSE(p.advance(kStart-1)); EXPECT_FALSE(p.advance(kStart+100*kMs, {false, -1}));
    EXPECT_FALSE(p.advance(kStart+100*kMs, {false, std::numeric_limits<double>::infinity()})); EXPECT_DOUBLE_EQ(p.actual_angle_rad(), 0);
    ASSERT_TRUE(p.advance(kStart+100*kMs)); const auto held = p.actual_angle_rad();
    EXPECT_FALSE(p.begin(kStart)); EXPECT_DOUBLE_EQ(p.actual_angle_rad(), held);
    EXPECT_FALSE(p.set_target(-0.2, std::numeric_limits<std::uint64_t>::max()));
}
TEST(SteeringResponseTest, DelayedDemandHistoryHasAFixedCapacity) {
    auto c = config(); c.delay_ns = 1000*kMs; simulation::SteeringResponse p(c); ASSERT_TRUE(p.begin(kStart));
    for (std::uint64_t ms = 1; ms <= 128; ++ms) { ASSERT_TRUE(p.set_target(ms%2 ? -0.2 : 0.2, kStart+ms*kMs)); }
    EXPECT_FALSE(p.set_target(-0.2, kStart+129*kMs)); EXPECT_DOUBLE_EQ(p.actual_angle_rad(), 0);
}
}  // namespace
