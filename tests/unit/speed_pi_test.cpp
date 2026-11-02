#include "speed_pi.hpp"
#include "reference_feasibility.hpp"

#include <gtest/gtest.h>
#include <cfenv>
#include <cmath>
#include <limits>

namespace stratadrive::central {
namespace {
TEST(SpeedPIPropulsion, ExternalClippingFreezesOnlyPositiveIntegration) {
    SpeedPI legacy,aware;legacy.initialize(1);aware.initialize(1);
    for(std::uint64_t i=0;i<500;++i) {
        SpeedSample x{1,i,i*20000000,0};
        ASSERT_TRUE(legacy.step(x.source_ns,.5,x,true).valid);
        ASSERT_TRUE(aware.step(x.source_ns,.5,x,true,true).valid);
    }
    EXPECT_GT(legacy.state().integral,.1);EXPECT_DOUBLE_EQ(aware.state().integral,0);
    const auto before=legacy.state().integral;
    for(std::uint64_t i=500;i<600;++i) {
        SpeedSample x{1,i,i*20000000,1};
        ASSERT_TRUE(legacy.step(x.source_ns,.5,x,true,true).valid);
    }
    EXPECT_LT(legacy.state().integral,before);
}
TEST(SpeedPIPropulsion, ReferenceGuardRejectsInfeasibleAndMalformedRamps) {
    EXPECT_FALSE(inertial_ramp_feasible(0,30/3.6,10,1696,.355,300,1500));
    EXPECT_TRUE(inertial_ramp_feasible(0,30/3.6,20,1696,.355,300,1500));
    EXPECT_TRUE(inertial_ramp_feasible(1,2,1,100,.5,50,50));
    EXPECT_FALSE(inertial_ramp_feasible(1,2,.999,100,.5,50,50));
    EXPECT_FALSE(inertial_ramp_feasible(2,1,.999,100,.5,50,50));
    for(double d:{0.,-1.,std::numeric_limits<double>::quiet_NaN(),std::numeric_limits<double>::infinity()})
        EXPECT_FALSE(inertial_ramp_feasible(0,1,d,1696,.355,300,1500));
}
constexpr auto period = SpeedPI::kPeriodNs;
SpeedSample sample(std::uint64_t ns, double speed = 0, std::uint64_t sequence = 0,
                   std::uint32_t epoch = 1) {
    return {epoch, sequence, ns, speed};
}

TEST(SpeedPI,Binary64NearestRoundingAndFirstOutput) {
    EXPECT_EQ(std::fegetround(), FE_TONEAREST);
    SpeedPI controller;
    ASSERT_TRUE(controller.initialize(1));
    const auto out = controller.step(0, 1, sample(0), true);
    ASSERT_TRUE(out.valid);
    ASSERT_TRUE(out.acceleration_mps2);
    EXPECT_NEAR(*out.acceleration_mps2, .04, 1e-15);
    EXPECT_DOUBLE_EQ(out.integral, 0); // slew-limited error cannot wind up
    EXPECT_EQ(out.source_ns, 0U);
}

TEST(SpeedPI,UnconstrainedOutputUsesIntegralFromPreviousTick) {
    SpeedPI controller;
    ASSERT_TRUE(controller.initialize(1));
    const auto first = controller.step(0, .02, sample(0), true);
    const auto second = controller.step(period, .02, sample(period, 0, 1), true);
    ASSERT_TRUE(first.valid && second.valid);
    EXPECT_NEAR(*first.acceleration_mps2, .02, 1e-15);
    EXPECT_NEAR(first.integral, .00008, 1e-15);
    EXPECT_NEAR(*second.acceleration_mps2, .02008, 1e-15);
    EXPECT_NEAR(second.integral, .00016, 1e-15);
}

TEST(SpeedPI,ReferenceDerivativeAndBrakingPreviewHaveAnalyticOutputs) {
    SpeedPI controller;
    ASSERT_TRUE(controller.initialize(1));
    ASSERT_TRUE(controller.step(0, 2, sample(0, 2), true).valid);
    auto out = controller.step(period, 2.0002, sample(period, 2.0002, 1), true);
    ASSERT_TRUE(out.valid);
    EXPECT_NEAR(*out.acceleration_mps2, .01, 1e-12);
    EXPECT_NEAR(out.integral, 0, 1e-15);
    // Falling target: rate=-0.01; preview shifts 2.0 to 1.9988.
    out = controller.step(2 * period, 2, sample(2 * period, 1.9988, 2), true);
    ASSERT_TRUE(out.valid);
    EXPECT_NEAR(*out.acceleration_mps2, -.01, 1e-12);
    EXPECT_NEAR(out.integral, 0, 1e-15);
}

TEST(SpeedPI,BrakingPreviewClampsReferenceAtZero) {
    SpeedPI controller;
    ASSERT_TRUE(controller.initialize(1));
    ASSERT_TRUE(controller.step(0, .0002, sample(0, .0002), true).valid);
    const auto out = controller.step(period, 0, sample(period, .001, 1), true);
    ASSERT_TRUE(out.valid);
    EXPECT_NEAR(*out.acceleration_mps2, -.011, 1e-15);
    EXPECT_NEAR(out.integral, -.000004, 1e-15);
}

TEST(SpeedPI,SustainedSaturationAndRecoveryRespectBothLimits) {
    SpeedPI controller;
    ASSERT_TRUE(controller.initialize(1));
    double previous = 0;
    for (std::uint64_t i = 0; i < 1000; ++i) {
        const double target = i < 300 ? SpeedPI::kMaxTargetMps : i < 700 ? 0 : 1;
        const double speed = i < 300 ? 0 : i < 700 ? 10 : 1;
        const auto out = controller.step(i * period, target, sample(i * period, speed, i), true);
        ASSERT_TRUE(out.valid);
        const double acceleration = *out.acceleration_mps2;
        EXPECT_GE(acceleration, -5);
        EXPECT_LE(acceleration, 2);
        EXPECT_LE(std::abs(acceleration - previous), .040000000000001);
        if (i == 299) { EXPECT_DOUBLE_EQ(acceleration, 2); }
        if (i == 699) { EXPECT_DOUBLE_EQ(acceleration, -5); }
        EXPECT_DOUBLE_EQ(out.integral, 0);
        previous = acceleration;
    }
    EXPECT_DOUBLE_EQ(previous, 0);
}

TEST(SpeedPI,CachedSampleKeepsItsSourceAndExpiresAfterInclusiveAgeLimit) {
    SpeedPI controller;
    ASSERT_TRUE(controller.initialize(1));
    const auto held = sample(0, 1);
    for (std::uint64_t i = 0; i <= 3; ++i) {
        const auto out = controller.step(i * period, 1, held, true);
        ASSERT_TRUE(out.valid);
        EXPECT_EQ(out.source_ns, 0U);
    }
    const auto out = controller.step(4 * period, 1, held, true);
    EXPECT_EQ(out.reason, SpeedPIReason::SourceAge);
    EXPECT_FALSE(out.acceleration_mps2);
    EXPECT_EQ(controller.state().last_ns, 3 * period);
}

TEST(SpeedPI,SourceAgeAndTargetBoundariesAreInclusive) {
    for (const auto age : {SpeedPI::kMaxAgeNs - 1, SpeedPI::kMaxAgeNs, SpeedPI::kMaxAgeNs + 1}) {
        SpeedPI controller;
        ASSERT_TRUE(controller.initialize(1));
        const auto out = controller.step(age, 0, sample(0), true);
        EXPECT_EQ(out.valid, age <= SpeedPI::kMaxAgeNs);
    }
    for (const auto target : {0.0, SpeedPI::kMaxTargetMps, std::nextafter(SpeedPI::kMaxTargetMps, INFINITY)}) {
        SpeedPI controller;
        ASSERT_TRUE(controller.initialize(1));
        EXPECT_EQ(controller.step(0, target, sample(0), true).valid, target <= SpeedPI::kMaxTargetMps);
    }
}

TEST(SpeedPI,ClockGapDuplicateEarlyLateAndRegressionLatch) {
    for (const auto now : {0ULL, period - 1ULL, period + 1ULL, 2ULL * period}) {
        SpeedPI controller;
        ASSERT_TRUE(controller.initialize(1));
        ASSERT_TRUE(controller.step(0, 0, sample(0), true).valid);
        EXPECT_EQ(controller.step(now, 0, sample(now, 0, 1), true).reason, SpeedPIReason::SampleTime);
        EXPECT_EQ(controller.step(period, 0, sample(period, 0, 2), true).reason, SpeedPIReason::Latched);
    }
    SpeedPI controller;
    ASSERT_TRUE(controller.initialize(1));
    ASSERT_TRUE(controller.step(2 * period, 0, sample(2 * period), true).valid);
    EXPECT_EQ(controller.step(period, 0, sample(period, 0, 1), true).reason, SpeedPIReason::SampleTime);
}

TEST(SpeedPI,InvalidStepPreservesControlStateAndReportsSuppliedSource) {
    SpeedPI controller;
    ASSERT_TRUE(controller.initialize(1));
    ASSERT_TRUE(controller.step(0, .02, sample(0), true).valid);
    const auto before = controller.state();
    const auto out = controller.step(period, 9, sample(period, 5, 1), false);
    EXPECT_EQ(out.reason, SpeedPIReason::Permission);
    EXPECT_FALSE(out.valid);
    EXPECT_FALSE(out.acceleration_mps2);
    EXPECT_EQ(out.source_ns, period);
    const auto& after = controller.state();
    EXPECT_TRUE(after.fault);
    EXPECT_EQ(after.epoch, before.epoch);
    EXPECT_EQ(after.last_ns, before.last_ns);
    EXPECT_EQ(after.target_mps, before.target_mps);
    EXPECT_DOUBLE_EQ(after.integral, before.integral);
    EXPECT_DOUBLE_EQ(after.previous_mps2, before.previous_mps2);
    ASSERT_TRUE(after.sample && before.sample);
    EXPECT_EQ(after.sample->sequence, before.sample->sequence);
    EXPECT_EQ(after.sample->source_ns, before.sample->source_ns);
    EXPECT_DOUBLE_EQ(after.sample->speed_mps, before.sample->speed_mps);
}

TEST(SpeedPI,OnlyNewerInitClearsFaultAndAllControlHistory) {
    SpeedPI controller;
    EXPECT_FALSE(controller.initialize(0));
    EXPECT_EQ(controller.step(0, 0, std::nullopt, false).reason, SpeedPIReason::Uninitialized);
    ASSERT_TRUE(controller.initialize(1));
    ASSERT_TRUE(controller.step(0, .02, sample(0), true).valid);
    EXPECT_EQ(controller.step(period, 0, sample(period, 0, 1), false).reason, SpeedPIReason::Permission);
    EXPECT_FALSE(controller.initialize(0));
    EXPECT_FALSE(controller.initialize(1));
    EXPECT_EQ(controller.step(2 * period, 0, sample(2 * period, 0, 2), true).reason, SpeedPIReason::Latched);
    ASSERT_TRUE(controller.initialize(2));
    EXPECT_FALSE(controller.state().fault);
    EXPECT_FALSE(controller.state().last_ns);
    EXPECT_FALSE(controller.state().sample);
    EXPECT_FALSE(controller.state().target_mps);
    EXPECT_DOUBLE_EQ(controller.state().integral, 0);
    EXPECT_DOUBLE_EQ(controller.state().previous_mps2, 0);
    EXPECT_TRUE(controller.step(3 * period, 0, sample(3 * period, 0, 0, 2), true).valid);
}

TEST(SpeedPI,CachedMutationAndNonprogressingIdentityAreRejected) {
    for (const auto bad : {sample(0, .1, 1), sample(1, 0, 1), sample(0, 0, 0), sample(0, 0, 2)}) {
        SpeedPI controller;
        ASSERT_TRUE(controller.initialize(1));
        ASSERT_TRUE(controller.step(0, 0, sample(0, 0, 1), true).valid);
        EXPECT_EQ(controller.step(period, 0, bad, true).reason, SpeedPIReason::Identity);
    }
}

TEST(SpeedPI,InvalidValuesAndFaultPrecedenceMatchTheContract) {
    const auto nan = std::numeric_limits<double>::quiet_NaN();
    const auto infinity = std::numeric_limits<double>::infinity();
    for (const auto speed : {nan, infinity, -infinity, -1.0}) {
        SpeedPI controller;
        ASSERT_TRUE(controller.initialize(1));
        EXPECT_EQ(controller.step(0, 0, sample(0, speed), true).reason, SpeedPIReason::InvalidSpeed);
    }
    SpeedPI controller;
    ASSERT_TRUE(controller.initialize(1));
    EXPECT_EQ(controller.step(0, nan, std::nullopt, false).reason, SpeedPIReason::Permission);
    ASSERT_TRUE(controller.initialize(2));
    EXPECT_EQ(controller.step(0, nan, std::nullopt, true).reason, SpeedPIReason::Target);
    ASSERT_TRUE(controller.initialize(3));
    EXPECT_EQ(controller.step(0, 0, std::nullopt, true).reason, SpeedPIReason::InvalidSpeed);
    ASSERT_TRUE(controller.initialize(4));
    EXPECT_EQ(controller.step(0, 0, sample(1), true).reason, SpeedPIReason::Epoch);
    ASSERT_TRUE(controller.initialize(5));
    EXPECT_EQ(controller.step(0, 0, sample(1, 0, 0, 5), true).reason, SpeedPIReason::SourceAge);
}

TEST(SpeedPI,UnsignedTimeAndSequenceLimitsDoNotWrap) {
    SpeedPI controller;
    constexpr auto maximum = std::numeric_limits<std::uint64_t>::max();
    constexpr auto epoch = std::numeric_limits<std::uint32_t>::max();
    ASSERT_TRUE(controller.initialize(epoch));
    ASSERT_TRUE(controller.step(maximum - period, 0, sample(maximum - period, 0, maximum - 1, epoch), true).valid);
    ASSERT_TRUE(controller.step(maximum, 0, sample(maximum, 0, maximum, epoch), true).valid);
    EXPECT_EQ(controller.step(period - 1, 0, sample(period - 1, 0, 0, epoch), true).reason, SpeedPIReason::SampleTime);
    EXPECT_FALSE(controller.initialize(epoch));
    EXPECT_FALSE(controller.initialize(0));
}

TEST(SpeedPI,SignedZeroSubnormalAndLargestFiniteSpeedAreHandled) {
    SpeedPI controller;
    ASSERT_TRUE(controller.initialize(1));
    ASSERT_TRUE(controller.step(0, -0.0, sample(0, -0.0), true).valid);
    EXPECT_TRUE(controller.step(period, 0.0, sample(0, 0.0), true).valid);
    EXPECT_TRUE(controller.step(2 * period, std::numeric_limits<double>::denorm_min(),
                                sample(2 * period, std::numeric_limits<double>::denorm_min(), 1), true).valid);
    const auto out = controller.step(3 * period, 0, sample(3 * period, std::numeric_limits<double>::max(), 2), true);
    ASSERT_TRUE(out.valid);
    EXPECT_TRUE(std::isfinite(*out.acceleration_mps2));
    EXPECT_GE(*out.acceleration_mps2, -.04);
}
}  // namespace
}  // namespace stratadrive::central
