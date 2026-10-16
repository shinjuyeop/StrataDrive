#include "brake_pressure_response.hpp"

#include <gtest/gtest.h>
#include <limits>
#include <stdexcept>

namespace {
using namespace stratadrive;
constexpr std::uint64_t kMs = 1000000, kStart = 1000000000;
std::uint64_t time_ns(int ms) { return kStart + static_cast<std::uint64_t>(ms)*kMs; }
simulation::BrakePressureResponseConfig config() { return {1500000, 0, 5000000, 10000000, 50*kMs}; }
TEST(BrakePressureResponse, ConfigurationClockAndTargetsAreValidated) {
    auto c = config(); c.fall_rate_pa_s = 0;
    EXPECT_THROW(simulation::BrakePressureResponse{c}, std::invalid_argument);
    c = config(); c.initial_pa = -1; EXPECT_THROW(simulation::BrakePressureResponse{c}, std::invalid_argument);
    c = config(); c.model_epoch = 0; EXPECT_THROW(simulation::BrakePressureResponse{c}, std::invalid_argument);
    simulation::BrakePressureResponse p(config());
    EXPECT_FALSE(p.advance(kStart)); EXPECT_FALSE(p.capture()); EXPECT_FALSE(p.request_protection(1000000, kStart));
    ASSERT_TRUE(p.begin(kStart)); EXPECT_FALSE(p.set_target(2000000, kStart));
    EXPECT_FALSE(p.set_target(std::numeric_limits<double>::quiet_NaN(), kStart));
    EXPECT_FALSE(p.advance(kStart-1)); EXPECT_FALSE(p.begin(kStart-1));
    EXPECT_FALSE(p.advance(time_ns(10), {false, -1, 1}));
    EXPECT_FALSE(p.advance(time_ns(10), {false, 1, std::numeric_limits<double>::infinity()}));
}
TEST(BrakePressureResponse, DelayRiseFallAndRepeatedDemandHaveSeparateMeaning) {
    simulation::BrakePressureResponse p(config()); ASSERT_TRUE(p.begin(kStart));
    ASSERT_TRUE(p.set_target(1000000, kStart));
    for (int ms=10; ms<=250; ms+=10) {
        ASSERT_TRUE(p.advance(time_ns(ms))); ASSERT_TRUE(p.set_target(1000000, time_ns(ms)));
        EXPECT_DOUBLE_EQ(p.actual_pressure_pa(), ms<=50 ? 0 : (ms-50)*5000);
    }
    ASSERT_TRUE(p.set_target(0, time_ns(250)));
    ASSERT_TRUE(p.advance(time_ns(300))); EXPECT_DOUBLE_EQ(p.actual_pressure_pa(), 1000000);
    ASSERT_TRUE(p.advance(time_ns(350))); EXPECT_DOUBLE_EQ(p.actual_pressure_pa(), 500000);
    ASSERT_TRUE(p.advance(time_ns(500))); EXPECT_DOUBLE_EQ(p.actual_pressure_pa(), 0);
}
TEST(BrakePressureResponse, JitteredIntervalSplitsAtEachTargetDueTime) {
    simulation::BrakePressureResponse p(config()); ASSERT_TRUE(p.begin(kStart));
    ASSERT_TRUE(p.set_target(1000000, kStart)); ASSERT_TRUE(p.set_target(0, time_ns(20)));
    ASSERT_TRUE(p.advance(time_ns(65))); EXPECT_DOUBLE_EQ(p.actual_pressure_pa(), 75000);
    ASSERT_TRUE(p.advance(time_ns(75))); EXPECT_DOUBLE_EQ(p.actual_pressure_pa(), 50000);
}
TEST(BrakePressureResponse, StuckPhysicsStillHasFreshIndependentAcquisitions) {
    simulation::BrakePressureResponse p(config()); ASSERT_TRUE(p.begin(kStart)); ASSERT_TRUE(p.set_target(1000000,kStart));
    ASSERT_TRUE(p.advance(time_ns(100), {true,1,1})); const auto a=p.capture().value();
    ASSERT_TRUE(p.advance(time_ns(110), {true,1,1})); const auto b=p.capture().value();
    EXPECT_DOUBLE_EQ(b.pressure_pa,0); EXPECT_GT(b.sequence,a.sequence); EXPECT_GT(b.source_time_ns,a.source_time_ns);
}
TEST(BrakePressureResponse, RiseAndFallVariationsAreIndependent) {
    auto c=config(); c.delay_ns=0; simulation::BrakePressureResponse p(c); ASSERT_TRUE(p.begin(kStart));
    ASSERT_TRUE(p.set_target(1000000,kStart)); ASSERT_TRUE(p.advance(time_ns(200), {false,.5,.25}));
    EXPECT_DOUBLE_EQ(p.actual_pressure_pa(),500000);
    ASSERT_TRUE(p.set_target(0,time_ns(200))); ASSERT_TRUE(p.advance(time_ns(300),{false,.5,.25}));
    EXPECT_DOUBLE_EQ(p.actual_pressure_pa(),250000);
}
TEST(BrakePressureResponse, ProtectionCancelsDelayedReleaseAndNeverReducesHigherPressure) {
    auto c=config(); c.initial_pa=1500000; simulation::BrakePressureResponse p(c); ASSERT_TRUE(p.begin(kStart));
    ASSERT_TRUE(p.set_target(0,kStart)); ASSERT_TRUE(p.request_protection(1000000,time_ns(20)));
    EXPECT_FALSE(p.set_target(0,time_ns(20))); ASSERT_TRUE(p.advance(time_ns(200)));
    EXPECT_DOUBLE_EQ(p.actual_pressure_pa(),1500000);
}
TEST(BrakePressureResponse, DuplicateProtectionDoesNotRestartRampAndStuckStillApplies) {
    simulation::BrakePressureResponse p(config()); ASSERT_TRUE(p.begin(kStart));
    ASSERT_TRUE(p.request_protection(1000000,time_ns(20)));
    ASSERT_TRUE(p.request_protection(1000000,time_ns(25)));
    ASSERT_TRUE(p.advance(time_ns(30))); EXPECT_DOUBLE_EQ(p.actual_pressure_pa(),50000);
    ASSERT_TRUE(p.advance(time_ns(100),{true,1,1})); EXPECT_DOUBLE_EQ(p.actual_pressure_pa(),50000);
    ASSERT_TRUE(p.advance(time_ns(110))); EXPECT_DOUBLE_EQ(p.actual_pressure_pa(),100000);
    EXPECT_FALSE(p.request_protection(500000,time_ns(110)));
}
TEST(BrakePressureResponse, SkipDoesNotCatchUpAndRestartPreservesPhysicsAndAcquisitionCounter) {
    simulation::BrakePressureResponse p(config()); ASSERT_TRUE(p.begin(kStart));
    ASSERT_TRUE(p.request_protection(1000000,kStart)); ASSERT_TRUE(p.advance(time_ns(10)));
    const auto a=p.capture().value(); ASSERT_TRUE(p.skip_to(time_ns(100)));
    ASSERT_TRUE(p.advance(time_ns(110))); EXPECT_DOUBLE_EQ(p.actual_pressure_pa(),100000);
    ASSERT_TRUE(p.begin(time_ns(110))); ASSERT_TRUE(p.advance(time_ns(120)));
    const auto b=p.capture().value(); EXPECT_DOUBLE_EQ(b.pressure_pa,100000); EXPECT_GT(b.sequence,a.sequence);
    EXPECT_EQ(b.model_epoch,a.model_epoch); EXPECT_TRUE(p.set_target(0,time_ns(120)));
}
TEST(BrakePressureResponse, SensorHoldInvalidationAndOverrideCannotForgeNewAcquisitions) {
    simulation::BrakePressureResponse p(config()); ASSERT_TRUE(p.begin(kStart)); const auto a=p.capture().value();
    EXPECT_FALSE(p.capture()); ASSERT_TRUE(p.advance(time_ns(10)));
    const auto held=p.capture(simulation::BrakeSensorAction::Hold).value(); EXPECT_EQ(held.sequence,a.sequence);
    EXPECT_EQ(held.source_time_ns,a.source_time_ns);
    const auto invalid=p.capture(simulation::BrakeSensorAction::Acquire,std::numeric_limits<double>::quiet_NaN());
    ASSERT_TRUE(invalid); EXPECT_DOUBLE_EQ(p.actual_pressure_pa(),0);
    EXPECT_FALSE(p.capture(simulation::BrakeSensorAction::Invalidate)); EXPECT_FALSE(p.capture());
    ASSERT_TRUE(p.advance(time_ns(20))); EXPECT_GT(p.capture()->sequence,invalid->sequence);
}
TEST(BrakePressureResponse, HistoryAndDueTimeOverflowAreBounded) {
    auto c=config(); c.delay_ns=1000*kMs; simulation::BrakePressureResponse p(c); ASSERT_TRUE(p.begin(kStart));
    for(int ms=1;ms<=128;++ms) { ASSERT_TRUE(p.set_target(ms%2 ? 1000000:0,time_ns(ms))); }
    EXPECT_FALSE(p.set_target(1000000,time_ns(129)));
    EXPECT_FALSE(p.set_target(1000000,std::numeric_limits<std::uint64_t>::max()));
}
} // namespace
