#include "steering_response_monitor.hpp"

#include <gtest/gtest.h>
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace {
using namespace stratadrive;
constexpr std::uint64_t kStart = 1000000000, kMs = 1000000;
std::uint64_t time_ns(int ms) { return kStart+static_cast<std::uint64_t>(ms)*kMs; }
vecu::SteeringMonitorConfig config() { return {-0.3, 0.3, 0.8, 1.2, 50*kMs}; }
steering::AngleMeasurement sample(int ms, double angle) { return {7, static_cast<std::uint64_t>(ms), time_ns(ms), angle}; }
class SteeringMonitorTest : public ::testing::Test {
protected:
    vecu::SteeringResponseMonitor monitor{config()};
    void SetUp() override {
        ASSERT_TRUE(monitor.begin(7, kStart));
        EXPECT_EQ(monitor.observe(sample(0, 0), kStart, true).fault, vecu::SteeringMonitorFault::None);
    }
    const vecu::SteeringMonitorDecision& observe(int ms, double angle) { return monitor.observe(sample(ms, angle), time_ns(ms), true); }
};
TEST(SteeringMonitorConfiguration, RejectsInvalidBandsRatesToleranceAndTiming) {
    auto c = config(); c.minimum_rate_rad_s = 0; EXPECT_THROW(vecu::SteeringResponseMonitor{c}, std::invalid_argument);
    c = config(); c.maximum_rate_rad_s = 0.5; EXPECT_THROW(vecu::SteeringResponseMonitor{c}, std::invalid_argument);
    c = config(); c.tolerance_rad = 0; EXPECT_THROW(vecu::SteeringResponseMonitor{c}, std::invalid_argument);
    c = config(); c.maximum_rad = c.minimum_rad; EXPECT_THROW(vecu::SteeringResponseMonitor{c}, std::invalid_argument);
    c = config(); c.sensor_age_ns = 0; EXPECT_THROW(vecu::SteeringResponseMonitor{c}, std::invalid_argument);
    c = config(); c.confirmation_ns = 0; EXPECT_THROW(vecu::SteeringResponseMonitor{c}, std::invalid_argument);
    c = config(); c.minimum_rad = std::numeric_limits<double>::quiet_NaN(); EXPECT_THROW(vecu::SteeringResponseMonitor{c}, std::invalid_argument);
}
TEST(SteeringMonitorConfiguration, NeedsTrustedPhysicalEpochAndExplicitInitialization) {
    vecu::SteeringResponseMonitor m(config());
    EXPECT_EQ(m.observe(sample(0, 0), kStart, true).fault, vecu::SteeringMonitorFault::NotInitialized);
    EXPECT_FALSE(m.set_target(0.1, kStart)); EXPECT_FALSE(m.begin(0, kStart));
    ASSERT_TRUE(m.begin(7, kStart)); EXPECT_TRUE(m.set_target(0.1, kStart));
    EXPECT_FALSE(m.set_target(0.4, kStart)); EXPECT_FALSE(m.set_target(std::numeric_limits<double>::infinity(), kStart));
}
TEST_F(SteeringMonitorTest, DelayAndRateBandAdmitNominalAndBothHealthyEdges) {
    for (const double rate : {0.8, 1.0, 1.2}) {
        vecu::SteeringResponseMonitor m(config()); ASSERT_TRUE(m.begin(7, kStart));
        m.observe(sample(0, 0), kStart, true); ASSERT_TRUE(m.set_target(0.2, kStart));
        for (int ms = 10; ms <= 400; ms += 10) {
            const auto angle = std::clamp(rate*(ms-50)/1000.0, 0.0, 0.2);
            const auto& d = m.observe(sample(ms, angle), time_ns(ms), true);
            EXPECT_EQ(d.fault, vecu::SteeringMonitorFault::None) << rate << ' ' << ms;
            if (ms == 50) { EXPECT_DOUBLE_EQ(*d.expected_min_rad, 0); EXPECT_DOUBLE_EQ(*d.expected_max_rad, 0); }
        }
    }
}
TEST_F(SteeringMonitorTest, FreshUnmovingAcquisitionsConfirmTrackingFaultAfterDelayAndDwell) {
    ASSERT_TRUE(monitor.set_target(0.2, kStart));
    for (int ms = 10; ms < 130; ms += 10) EXPECT_EQ(observe(ms, 0).fault, vecu::SteeringMonitorFault::None);
    const auto& d = observe(130, 0);
    EXPECT_EQ(d.fault, vecu::SteeringMonitorFault::TrackingError);
    EXPECT_EQ(d.violation_since_ns, time_ns(70)); EXPECT_EQ(d.detected_time_ns, time_ns(130));
    EXPECT_NEAR(*d.expected_min_rad, 0.064, 1e-12); EXPECT_NEAR(d.residual_rad, 0.064, 1e-12);
}
TEST_F(SteeringMonitorTest, RepeatedCommandsRefreshNeitherPhysicalDelayNorConfirmationStart) {
    ASSERT_TRUE(monitor.set_target(0.2, kStart));
    for (int ms = 10; ms <= 130; ms += 10) {
        observe(ms, 0);
        if (ms < 130) { ASSERT_TRUE(monitor.set_target(0.2, time_ns(ms))); }
    }
    EXPECT_EQ(monitor.decision().fault, vecu::SteeringMonitorFault::TrackingError);
    EXPECT_EQ(monitor.decision().violation_since_ns, time_ns(70));
}
TEST_F(SteeringMonitorTest, ChangingDemandsDoNotReanchorThePredictionToTheStuckSensor) {
    ASSERT_TRUE(monitor.set_target(0.2, kStart));
    for (int ms = 10; ms <= 130; ms += 10) {
        observe(ms, 0);
        if (ms < 130) { ASSERT_TRUE(monitor.set_target(ms%20 == 0 ? 0.2 : 0.3, time_ns(ms))); }
    }
    EXPECT_EQ(monitor.decision().fault, vecu::SteeringMonitorFault::TrackingError);
}
TEST_F(SteeringMonitorTest, OneTransientResetsConfirmationWhenHealthyObservationsResume) {
    ASSERT_TRUE(monitor.set_target(0.2, kStart));
    for (int ms = 10; ms <= 300; ms += 10) {
        const auto& d = observe(ms, ms == 100 ? 0.12 : std::clamp((ms-50)/1000.0, 0.0, 0.2));
        EXPECT_EQ(d.fault, vecu::SteeringMonitorFault::None);
        if (ms == 100) { EXPECT_TRUE(d.violation_since_ns); }
        if (ms == 110) { EXPECT_FALSE(d.violation_since_ns); }
    }
}
TEST_F(SteeringMonitorTest, ExactToleranceIsAllowedAndPersistentExcessIsDetected) {
    for (int ms = 10; ms <= 100; ms += 10) EXPECT_FALSE(observe(ms, 0.01).violation_since_ns);
    for (int ms = 110; ms < 170; ms += 10) EXPECT_EQ(observe(ms, 0.0101).fault, vecu::SteeringMonitorFault::None);
    EXPECT_EQ(observe(170, 0.0101).fault, vecu::SteeringMonitorFault::TrackingError);
}
TEST_F(SteeringMonitorTest, CachedReadsCannotAdvanceConfirmationOrProduceANewMeasurement) {
    auto c = config(); c.sensor_age_ns = 100*kMs; c.sample_gap_ns = 100*kMs;
    vecu::SteeringResponseMonitor m(c); ASSERT_TRUE(m.begin(7, kStart)); m.observe(sample(0, 0), kStart, true);
    m.observe(sample(10, 0.03), time_ns(10), true);
    for (int ms = 20; ms <= 70; ms += 10) {
        const auto& d = m.observe(sample(10, 0.03), time_ns(ms), true);
        EXPECT_FALSE(d.new_measurement); EXPECT_EQ(d.fault, vecu::SteeringMonitorFault::None);
    }
    EXPECT_EQ(m.observe(sample(80, 0.03), time_ns(80), true).fault, vecu::SteeringMonitorFault::TrackingError);
}
TEST_F(SteeringMonitorTest, HeldAcquisitionExpiresByItsOwnSourceTime) {
    EXPECT_EQ(monitor.observe(sample(0, 0), time_ns(20), true).fault, vecu::SteeringMonitorFault::None);
    EXPECT_EQ(monitor.observe(sample(0, 0), time_ns(21), true).fault, vecu::SteeringMonitorFault::SensorUnavailable);
}
TEST_F(SteeringMonitorTest, FreshArrivalCannotBridgeAnUnobservedSamplingGap) {
    EXPECT_EQ(observe(40, 0).fault, vecu::SteeringMonitorFault::SensorUnavailable);
}
TEST_F(SteeringMonitorTest, ComparesWithPredictionAtAcquisitionRatherThanArrivalTime) {
    auto c = config(); c.minimum_rate_rad_s = c.maximum_rate_rad_s = 1; c.tolerance_rad = 0.001;
    vecu::SteeringResponseMonitor m(c); ASSERT_TRUE(m.begin(7, kStart)); m.observe(sample(0, 0), kStart, true);
    ASSERT_TRUE(m.set_target(0.2, kStart));
    for (int ms = 10; ms <= 100; ms += 10) {
        const auto& d = m.observe(sample(ms, std::max(0.0, (ms-50)/1000.0)), time_ns(ms+20), true);
        EXPECT_EQ(d.fault, vecu::SteeringMonitorFault::None); EXPECT_NEAR(d.residual_rad, 0, 1e-12);
    }
}
TEST_F(SteeringMonitorTest, CachedIdentityCannotMutateValueOrTimestamp) {
    EXPECT_EQ(monitor.observe(sample(0, 0.1), time_ns(10), true).fault, vecu::SteeringMonitorFault::SensorInvalid);
    ASSERT_TRUE(monitor.begin(7, time_ns(10))); monitor.observe(sample(10, 0), time_ns(10), true);
    auto s = sample(10, 0); s.source_time_ns = time_ns(20);
    EXPECT_EQ(monitor.observe(s, time_ns(20), true).fault, vecu::SteeringMonitorFault::SensorInvalid);
}
TEST_F(SteeringMonitorTest, WrongEpochFutureAndPreSessionMeasurementsAreRejected) {
    auto s = sample(10, 0); s.model_epoch = 8;
    EXPECT_EQ(monitor.observe(s, time_ns(10), true).fault, vecu::SteeringMonitorFault::SensorInvalid);
    ASSERT_TRUE(monitor.begin(7, time_ns(10)));
    EXPECT_EQ(monitor.observe(sample(20, 0), time_ns(10), true).fault, vecu::SteeringMonitorFault::SensorInvalid);
    ASSERT_TRUE(monitor.begin(7, time_ns(10)));
    EXPECT_EQ(monitor.observe(sample(0, 0), time_ns(10), true).fault, vecu::SteeringMonitorFault::SensorInvalid);
}
TEST_F(SteeringMonitorTest, NonfiniteAndOutOfRangeSensorsAreNotPhysicalTruthFallbacks) {
    EXPECT_EQ(observe(10, std::numeric_limits<double>::quiet_NaN()).fault, vecu::SteeringMonitorFault::SensorInvalid);
    EXPECT_FALSE(monitor.decision().measured_rad);
    ASSERT_TRUE(monitor.begin(7, time_ns(10)));
    EXPECT_EQ(observe(20, 0.4).fault, vecu::SteeringMonitorFault::SensorInvalid);
}
TEST_F(SteeringMonitorTest, MissingSensorIsUnknownAndClockRegressionLatches) {
    EXPECT_EQ(monitor.observe(std::nullopt, time_ns(10), true).fault, vecu::SteeringMonitorFault::SensorUnavailable);
    EXPECT_FALSE(monitor.decision().measured_rad);
    EXPECT_EQ(monitor.observe(sample(0, 0), kStart, true).fault, vecu::SteeringMonitorFault::ClockError);
    EXPECT_FALSE(monitor.begin(7, kStart));
}
TEST_F(SteeringMonitorTest, GoodDataCannotClearALatchButExplicitBeginResetsTheObserver) {
    monitor.observe(std::nullopt, time_ns(10), true);
    EXPECT_EQ(observe(20, 0).fault, vecu::SteeringMonitorFault::SensorUnavailable);
    EXPECT_TRUE(monitor.decision().new_measurement);
    ASSERT_TRUE(monitor.begin(7, time_ns(20)));
    EXPECT_EQ(observe(30, 0).fault, vecu::SteeringMonitorFault::None);
}
TEST_F(SteeringMonitorTest, NoExcitationCannotDistinguishAStationaryJamFromHealthyHold) {
    ASSERT_TRUE(monitor.set_target(0, kStart));
    for (int ms = 10; ms <= 1000; ms += 10) EXPECT_EQ(observe(ms, 0).fault, vecu::SteeringMonitorFault::None);
}
TEST_F(SteeringMonitorTest, NegativeMotionUsesTheOppositeEnvelopeEdgeForAStalledAngle) {
    ASSERT_TRUE(monitor.set_target(-0.2, kStart));
    for (int ms = 10; ms <= 130; ms += 10) observe(ms, 0);
    EXPECT_EQ(monitor.decision().fault, vecu::SteeringMonitorFault::TrackingError);
    EXPECT_NEAR(*monitor.decision().expected_max_rad, -0.064, 1e-12);
}
TEST_F(SteeringMonitorTest, ANewIdentityRequiresSequenceAndAcquisitionTimeProgress) {
    observe(10, 0); auto s = sample(20, 0); s.sequence = 9;
    EXPECT_EQ(monitor.observe(s, time_ns(20), true).fault, vecu::SteeringMonitorFault::SensorInvalid);
    ASSERT_TRUE(monitor.begin(7, time_ns(20))); monitor.observe(sample(20, 0), time_ns(20), true);
    s = sample(30, 0); s.source_time_ns = time_ns(20);
    EXPECT_EQ(monitor.observe(s, time_ns(30), true).fault, vecu::SteeringMonitorFault::SensorInvalid);
}
TEST_F(SteeringMonitorTest, PendingCommandHistoryIsBoundedAndDueTimeCannotOverflow) {
    auto c = config(); c.delay_ns = 1000*kMs; vecu::SteeringResponseMonitor m(c); ASSERT_TRUE(m.begin(7, kStart));
    m.observe(sample(0, 0), kStart, true);
    for (int ms = 1; ms <= 128; ++ms) { ASSERT_TRUE(m.set_target(ms%2 ? -0.2 : 0.2, time_ns(ms))); }
    EXPECT_FALSE(m.set_target(-0.2, time_ns(129)));
    EXPECT_FALSE(m.set_target(-0.2, std::numeric_limits<std::uint64_t>::max()));
}
}  // namespace
