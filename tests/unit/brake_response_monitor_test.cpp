#include "brake_response_monitor.hpp"

#include <gtest/gtest.h>
#include <algorithm>
#include <limits>
#include <stdexcept>

namespace {
using namespace stratadrive;
constexpr std::uint64_t kMs=1000000, kStart=1000000000;
std::uint64_t time_ns(int ms) { return kStart+static_cast<std::uint64_t>(ms)*kMs; }
vecu::BrakeMonitorConfig config() { return {1500000,4000000,6000000,8000000,12000000,50*kMs}; }
brake::PressureMeasurement sample(int ms,double pa) { return {7,static_cast<std::uint64_t>(ms),time_ns(ms),pa}; }
class BrakeMonitorTest:public ::testing::Test {
protected:
    vecu::BrakeResponseMonitor monitor{config()};
    void SetUp() override { ASSERT_TRUE(monitor.begin(7,kStart)); monitor.observe(sample(0,0),kStart,true); }
    const vecu::BrakeMonitorDecision& observe(int ms,double pa) { return monitor.observe(sample(ms,pa),time_ns(ms),true); }
};
TEST(BrakeMonitorConfig, BandsToleranceTimingAndInitializationAreValidated) {
    auto c=config(); c.minimum_rise_pa_s=0; EXPECT_THROW(vecu::BrakeResponseMonitor{c},std::invalid_argument);
    c=config(); c.maximum_fall_pa_s=1; EXPECT_THROW(vecu::BrakeResponseMonitor{c},std::invalid_argument);
    c=config(); c.tolerance_pa=0; EXPECT_THROW(vecu::BrakeResponseMonitor{c},std::invalid_argument);
    c=config(); c.sensor_age_ns=0; EXPECT_THROW(vecu::BrakeResponseMonitor{c},std::invalid_argument);
    c=config(); c.maximum_pa=std::numeric_limits<double>::quiet_NaN(); EXPECT_THROW(vecu::BrakeResponseMonitor{c},std::invalid_argument);
    vecu::BrakeResponseMonitor m(config()); EXPECT_EQ(m.observe(sample(0,0),kStart,true).fault,vecu::BrakeMonitorFault::NotInitialized);
    EXPECT_FALSE(m.begin(0,kStart)); EXPECT_FALSE(m.set_target(0,kStart)); ASSERT_TRUE(m.begin(7,kStart));
    EXPECT_FALSE(m.set_target(-1,kStart)); EXPECT_FALSE(m.set_target(2000000,kStart));
}
TEST_F(BrakeMonitorTest, BothRiseAndFallHealthyEdgesAdmitSaturationAndRelease) {
    for(double fraction:{.8,1.,1.2}) {
        vecu::BrakeResponseMonitor m(config()); ASSERT_TRUE(m.begin(7,kStart)); m.observe(sample(0,0),kStart,true);
        ASSERT_TRUE(m.set_target(1000000,kStart));
        for(int ms=10;ms<=400;ms+=10) {
            const auto& d=m.observe(sample(ms,std::clamp((ms-50)*5000*fraction,0.,1000000.)),time_ns(ms),true);
            EXPECT_EQ(d.fault,vecu::BrakeMonitorFault::None); EXPECT_FALSE(d.violation_since_ns);
        }
        ASSERT_TRUE(m.set_target(0,time_ns(400)));
        for(int ms=410;ms<=650;ms+=10) {
            const auto pa=1000000-std::clamp((ms-450)*10000*fraction,0.,1000000.);
            const auto& d=m.observe(sample(ms,pa),time_ns(ms),true);
            EXPECT_EQ(d.fault,vecu::BrakeMonitorFault::None); EXPECT_FALSE(d.violation_since_ns);
        }
    }
}
TEST_F(BrakeMonitorTest, FreshStuckAcquisitionsConfirmOnlyAfterDelayToleranceAndDwell) {
    ASSERT_TRUE(monitor.set_target(1000000,kStart));
    for(int ms=10;ms<120;ms+=10) EXPECT_EQ(observe(ms,0).fault,vecu::BrakeMonitorFault::None);
    const auto& d=observe(120,0); EXPECT_EQ(d.fault,vecu::BrakeMonitorFault::ResponseError);
    EXPECT_EQ(d.violation_since_ns,time_ns(60)); EXPECT_EQ(d.detected_time_ns,time_ns(120));
    EXPECT_DOUBLE_EQ(d.residual_pa,280000);
}
TEST_F(BrakeMonitorTest, RepeatedOrChangedDemandsCannotReseedAStuckPrediction) {
    ASSERT_TRUE(monitor.set_target(1000000,kStart));
    for(int ms=10;ms<=120;ms+=10) {
        observe(ms,0);
        if(ms<120) { ASSERT_TRUE(monitor.set_target(ms%20 ? 1000000:1500000,time_ns(ms))); }
    }
    EXPECT_EQ(monitor.decision().fault,vecu::BrakeMonitorFault::ResponseError);
    EXPECT_EQ(monitor.decision().violation_since_ns,time_ns(60));
}
TEST_F(BrakeMonitorTest, FailureToReleaseUsesTheUpperEnvelopeAndFasterFallRate) {
    ASSERT_TRUE(monitor.begin(7,kStart)); monitor.observe(sample(0,1000000),kStart,true);
    ASSERT_TRUE(monitor.set_target(0,kStart));
    for(int ms=10;ms<=120;ms+=10) observe(ms,1000000);
    const auto& d=monitor.decision(); EXPECT_EQ(d.fault,vecu::BrakeMonitorFault::ResponseError);
    EXPECT_DOUBLE_EQ(*d.expected_max_pa,440000); EXPECT_DOUBLE_EQ(d.residual_pa,560000);
}
TEST_F(BrakeMonitorTest, ExactToleranceIsAcceptedAndOneTransientResetsDwell) {
    for(int ms=10;ms<=100;ms+=10) EXPECT_FALSE(observe(ms,25000).violation_since_ns);
    EXPECT_TRUE(observe(110,30000).violation_since_ns); EXPECT_FALSE(observe(120,0).violation_since_ns);
    for(int ms=130;ms<=190;ms+=10) observe(ms,30000);
    EXPECT_EQ(monitor.decision().violation_since_ns,time_ns(130));
    EXPECT_EQ(monitor.decision().fault,vecu::BrakeMonitorFault::ResponseError);
}
TEST_F(BrakeMonitorTest, CachedPollingCannotConfirmAResponseFault) {
    auto c=config(); c.sensor_age_ns=100*kMs; c.sample_gap_ns=100*kMs;
    vecu::BrakeResponseMonitor m(c); ASSERT_TRUE(m.begin(7,kStart)); m.observe(sample(0,0),kStart,true);
    m.observe(sample(10,30000),time_ns(10),true);
    for(int ms=20;ms<=70;ms+=10) {
        const auto& d=m.observe(sample(10,30000),time_ns(ms),true);
        EXPECT_EQ(d.fault,vecu::BrakeMonitorFault::None); EXPECT_FALSE(d.new_measurement);
    }
    EXPECT_EQ(m.observe(sample(80,30000),time_ns(80),true).fault,vecu::BrakeMonitorFault::ResponseError);
}
TEST_F(BrakeMonitorTest, HeldMeasurementAgeBoundaryAndFreshSamplingGapAreDistinct) {
    EXPECT_EQ(monitor.observe(sample(0,0),time_ns(20),true).fault,vecu::BrakeMonitorFault::None);
    EXPECT_EQ(monitor.observe(sample(0,0),time_ns(21),true).fault,vecu::BrakeMonitorFault::SensorUnavailable);
    ASSERT_TRUE(monitor.begin(7,time_ns(30))); monitor.observe(sample(30,0),time_ns(30),true);
    EXPECT_EQ(observe(70,0).fault,vecu::BrakeMonitorFault::SensorUnavailable);
    EXPECT_TRUE(monitor.decision().new_measurement);
    EXPECT_EQ(observe(80,0).fault,vecu::BrakeMonitorFault::SensorUnavailable);
    EXPECT_TRUE(monitor.decision().new_measurement);
}
TEST_F(BrakeMonitorTest, PredictionUsesAcquisitionTimeRatherThanArrivalTime) {
    auto c=config(); c.minimum_rise_pa_s=c.maximum_rise_pa_s=5000000; c.tolerance_pa=1000;
    vecu::BrakeResponseMonitor m(c); ASSERT_TRUE(m.begin(7,kStart)); m.observe(sample(0,0),kStart,true);
    ASSERT_TRUE(m.set_target(1000000,kStart));
    for(int ms=10;ms<=100;ms+=10) {
        const auto& d=m.observe(sample(ms,std::max(0.,(ms-50)*5000.)),time_ns(ms+20),true);
        EXPECT_EQ(d.fault,vecu::BrakeMonitorFault::None); EXPECT_DOUBLE_EQ(d.residual_pa,0);
    }
}
TEST_F(BrakeMonitorTest, CachedIdentityCannotChangeValueOrTimestamp) {
    EXPECT_EQ(monitor.observe(sample(0,1),time_ns(10),true).fault,vecu::BrakeMonitorFault::SensorInvalid);
    ASSERT_TRUE(monitor.begin(7,time_ns(10))); monitor.observe(sample(10,0),time_ns(10),true);
    auto s=sample(10,0); s.source_time_ns=time_ns(20);
    EXPECT_EQ(monitor.observe(s,time_ns(20),true).fault,vecu::BrakeMonitorFault::SensorInvalid);
}
TEST_F(BrakeMonitorTest, TrustedEpochSourceClockAndFiniteRangeAreRequired) {
    auto s=sample(10,0); s.model_epoch=8;
    EXPECT_EQ(monitor.observe(s,time_ns(10),true).fault,vecu::BrakeMonitorFault::SensorInvalid);
    ASSERT_TRUE(monitor.begin(7,time_ns(10)));
    EXPECT_EQ(monitor.observe(sample(20,0),time_ns(10),true).fault,vecu::BrakeMonitorFault::SensorInvalid);
    ASSERT_TRUE(monitor.begin(7,time_ns(10)));
    EXPECT_EQ(monitor.observe(sample(0,0),time_ns(10),true).fault,vecu::BrakeMonitorFault::SensorInvalid);
    for(double invalid:{-1.,1500001.,std::numeric_limits<double>::quiet_NaN()}) {
        ASSERT_TRUE(monitor.begin(7,time_ns(20))); EXPECT_EQ(observe(20,invalid).fault,vecu::BrakeMonitorFault::SensorInvalid);
        EXPECT_FALSE(monitor.decision().measured_pa);
    }
}
TEST_F(BrakeMonitorTest, SequenceAndSourceMustBothProgress) {
    observe(10,0); auto s=sample(20,0); s.sequence=9;
    EXPECT_EQ(monitor.observe(s,time_ns(20),true).fault,vecu::BrakeMonitorFault::SensorInvalid);
    ASSERT_TRUE(monitor.begin(7,time_ns(20))); monitor.observe(sample(20,0),time_ns(20),true);
    s=sample(30,0); s.source_time_ns=time_ns(20);
    EXPECT_EQ(monitor.observe(s,time_ns(30),true).fault,vecu::BrakeMonitorFault::SensorInvalid);
}
TEST_F(BrakeMonitorTest, MissingSensorAndClockErrorsLatchUntilExplicitTrustedBegin) {
    EXPECT_EQ(monitor.observe(std::nullopt,time_ns(10),true).fault,vecu::BrakeMonitorFault::SensorUnavailable);
    EXPECT_EQ(observe(20,0).fault,vecu::BrakeMonitorFault::SensorUnavailable); EXPECT_TRUE(monitor.decision().new_measurement);
    ASSERT_TRUE(monitor.begin(7,time_ns(20))); EXPECT_EQ(observe(30,0).fault,vecu::BrakeMonitorFault::None);
    EXPECT_EQ(observe(20,0).fault,vecu::BrakeMonitorFault::ClockError); EXPECT_FALSE(monitor.begin(7,time_ns(10)));
}
TEST_F(BrakeMonitorTest, NoExcitationCannotRevealAStationaryStuckActuator) {
    ASSERT_TRUE(monitor.set_target(0,kStart));
    for(int ms=10;ms<=1000;ms+=10) EXPECT_EQ(observe(ms,0).fault,vecu::BrakeMonitorFault::None);
}
TEST_F(BrakeMonitorTest, DisablingNormalTrackingForProtectionDoesNotReinterpretTheOldTarget) {
    ASSERT_TRUE(monitor.set_target(0,kStart)); observe(10,40000); ASSERT_TRUE(monitor.decision().violation_since_ns);
    for(int ms=20;ms<=200;ms+=10) {
        const auto& d=monitor.observe(sample(ms,ms*5000.),time_ns(ms),false);
        EXPECT_FALSE(d.violation_since_ns); EXPECT_EQ(d.fault,vecu::BrakeMonitorFault::None);
    }
}
TEST_F(BrakeMonitorTest, HistoryCapacityAndDueTimeOverflowCannotGrowWithoutBound) {
    auto c=config(); c.delay_ns=1000*kMs; vecu::BrakeResponseMonitor m(c); ASSERT_TRUE(m.begin(7,kStart));
    for(int ms=1;ms<=128;++ms) { ASSERT_TRUE(m.set_target(ms%2 ? 1000000:0,time_ns(ms))); }
    EXPECT_FALSE(m.set_target(1000000,time_ns(129)));
    EXPECT_FALSE(m.set_target(1000000,std::numeric_limits<std::uint64_t>::max()));
}
} // namespace
