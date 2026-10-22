#include "m4_owner_network.hpp"
#include <gtest/gtest.h>
#include <cmath>
#include <cstdlib>
using namespace stratadrive;
using namespace stratadrive::simulation;
namespace {
constexpr std::uint64_t ms=1000000;
TEST(M6PhysicalResponse,PositiveMaximumReachesZeroAt149Point5msWithoutInstantZero) {
    auto config=vecu::DriveControllerConfig{}.response;config.initial_nm=config.maximum_nm;
    TorqueResponse m(config);m.begin(0);m.request_zero(0);
    ASSERT_TRUE(m.advance(149*ms));EXPECT_GT(std::abs(m.actual_nm()),1);
    ASSERT_TRUE(m.advance(149500000));EXPECT_NEAR(m.actual_nm(),1,1e-10);
    ASSERT_TRUE(m.advance(150*ms));EXPECT_DOUBLE_EQ(m.actual_nm(),0);
}
TEST(M6PhysicalResponse,NegativeMinimumUsesAbsoluteCompletionAndFiniteRamp) {
    auto config=vecu::DriveControllerConfig{}.response;config.initial_nm=config.minimum_nm;
    TorqueResponse m(config);m.begin(0);m.request_zero(0);
    ASSERT_TRUE(m.advance(99*ms));EXPECT_LT(m.actual_nm(),-1);
    ASSERT_TRUE(m.advance(99500000));EXPECT_NEAR(m.actual_nm(),-1,1e-10);
    ASSERT_TRUE(m.advance(100*ms));EXPECT_DOUBLE_EQ(m.actual_nm(),0);
}
TEST(M6PhysicalResponse,BrakeWorstReleasedPressureNeeds200msAndCancelsNormalDelay) {
    auto c=m4_detail::PhysicalOwner::brake_response_config();c.initial_pa=0;
    BrakePressureResponse m(c);ASSERT_TRUE(m.begin(0));ASSERT_TRUE(m.set_target(0,0));
    ASSERT_TRUE(m.request_protection(1000000,0));ASSERT_TRUE(m.advance(199*ms));
    EXPECT_DOUBLE_EQ(m.actual_pressure_pa(),995000);
    ASSERT_TRUE(m.advance(200*ms));EXPECT_DOUBLE_EQ(m.actual_pressure_pa(),1000000);
    ASSERT_TRUE(m.advance(250*ms));EXPECT_DOUBLE_EQ(m.actual_pressure_pa(),1000000);
}
TEST(M6PhysicalResponse,InitialPressureNeeds160msAndHigherPressureIsNotReleased) {
    auto c=m4_detail::PhysicalOwner::brake_response_config();BrakePressureResponse m(c);
    ASSERT_TRUE(m.begin(0));ASSERT_TRUE(m.request_protection(1000000,0));
    ASSERT_TRUE(m.advance(160*ms));EXPECT_DOUBLE_EQ(m.actual_pressure_pa(),1000000);
    c.initial_pa=1200000;BrakePressureResponse high(c);ASSERT_TRUE(high.begin(0));
    ASSERT_TRUE(high.request_protection(1000000,0));ASSERT_TRUE(high.advance(300*ms));EXPECT_DOUBLE_EQ(high.actual_pressure_pa(),1200000);
}
TEST(M6PhysicalResponse,StuckBrakeDoesNotBecomeCompleteWhenTargetWasSelected) {
    auto c=m4_detail::PhysicalOwner::brake_response_config();c.initial_pa=0;BrakePressureResponse m(c);
    ASSERT_TRUE(m.begin(0));ASSERT_TRUE(m.request_protection(1000000,0));
    ASSERT_TRUE(m.advance(230*ms,{true,1,1}));EXPECT_LT(m.actual_pressure_pa(),1000000);
}
TEST(M6PhysicalResponse,ModelCompletionAgainstSelectedDeadline) {
    // Test-only replay switch: run once at old100ms (expected FAIL), then the
    // explicit M6 JSON budget. This does not configure any model/controller.
    const auto* env=std::getenv("STRATADRIVE_M6_REPLAY_DEADLINE_NS");
    const auto deadline=env?std::stoull(env):230000000ULL;
    auto dc=vecu::DriveControllerConfig{}.response;dc.initial_nm=dc.maximum_nm;
    TorqueResponse motor(dc);motor.begin(0);motor.request_zero(0);
    auto bc=m4_detail::PhysicalOwner::brake_response_config();bc.initial_pa=0;
    BrakePressureResponse brake(bc);ASSERT_TRUE(brake.begin(0));ASSERT_TRUE(brake.request_protection(1000000,0));
    ASSERT_TRUE(motor.advance(deadline));ASSERT_TRUE(brake.advance(deadline));
    EXPECT_LE(std::abs(motor.actual_nm()),1);EXPECT_GE(brake.actual_pressure_pa(),1000000);
}
TEST(M6PhysicalResponse,ParallelEndpointResponsesFit230msWithoutChangingCalibration) {
    const auto dc=vecu::DriveControllerConfig{}.response;const auto bc=m4_detail::PhysicalOwner::brake_response_config();
    EXPECT_DOUBLE_EQ(dc.minimum_nm,-200);EXPECT_DOUBLE_EQ(dc.maximum_nm,300);EXPECT_DOUBLE_EQ(dc.zero_rate_nm_s,2000);
    EXPECT_EQ(dc.delay_ns,50*ms);EXPECT_EQ(bc.delay_ns,50*ms);EXPECT_DOUBLE_EQ(bc.rise_rate_pa_s,5000000);
    for(double initial:{dc.minimum_nm,dc.maximum_nm}) {
        auto c=dc;c.initial_nm=initial;TorqueResponse motor(c);motor.begin(0);motor.request_zero(0);
        auto b=bc;b.initial_pa=0;BrakePressureResponse brake(b);ASSERT_TRUE(brake.begin(0));ASSERT_TRUE(brake.request_protection(1000000,0));
        std::uint64_t first=0;
        for(std::uint64_t t=500000;t<=230*ms;t+=500000) {
            ASSERT_TRUE(motor.advance(t));ASSERT_TRUE(brake.advance(t));
            if(!first && std::abs(motor.actual_nm())<=1 && brake.actual_pressure_pa()>=1000000)first=t;
        }
        EXPECT_EQ(first,200*ms); // max(149.5,200), not sum; unchanged modeled rates
    }
}
}
