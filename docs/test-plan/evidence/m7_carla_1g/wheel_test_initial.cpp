#include "functional_rig.hpp"
#include <gtest/gtest.h>
#include <limits>
namespace {
using namespace stratadrive::m7_functional;
constexpr Scope scope{1,42,7};
Observation observation(unsigned i=0) {return {scope,domain,100+i,1+i*.01,.01};}
WheelSample wheel(unsigned i=0,double v=0) {return {99,100+i,1000000000ULL+i*tick_ns,{v,v,v,v}};}
TEST(M7Wheel, RealNativePathPreservesAcquisitionDespiteFasterFixturePublication) {
    FunctionalRig rig(scope,99);Report r;
    for(unsigned i=0;i<=180;++i)r=rig.observe(observation(i),wheel(i,i<100?0:1.23456));
    ASSERT_TRUE(r.armed);ASSERT_TRUE(r.returned_wheel);ASSERT_TRUE(r.sensor_wheel);
    EXPECT_EQ(r.credit_mask,255U);EXPECT_EQ(r.release_mask,255U);
    EXPECT_DOUBLE_EQ(r.sensor_wheel->rad_s,1.23456);
    EXPECT_NEAR(r.returned_wheel->rad_s,1.23456,.00011); // original 1e-4 rad/s CAN quantization
    EXPECT_EQ((r.returned_wheel->source-1000000000ULL)%tick_ns,0U);
    EXPECT_LT(r.returned_wheel->source,r.now);
    EXPECT_LE(r.now+tick_ns-r.returned_wheel->source,30*ms);
}
TEST(M7Wheel, NoFutureObservationUsedByEarlierNativeJobs) {
    FunctionalRig rig(scope,99);
    for(unsigned i=0;i<150;++i)rig.observe(observation(i),wheel(i));
    const auto now=rig.observe(observation(150),wheel(150,8));
    ASSERT_TRUE(now.returned_wheel);EXPECT_EQ(now.returned_wheel->rad_s,0);
    EXPECT_LT(now.returned_wheel->source,wheel(150).source);
    const auto later=rig.observe(observation(151),wheel(151,8));
    ASSERT_TRUE(later.returned_wheel);EXPECT_EQ(later.returned_wheel->rad_s,8);
    EXPECT_EQ(later.returned_wheel->source,wheel(150).source);
}
TEST(M7Wheel, MissingWheelCannotFallBackToStationaryFixtureOrHeal) {
    FunctionalRig rig(scope,99);
    rig.observe(observation(),wheel());
    EXPECT_THROW(rig.observe(observation(1)),std::runtime_error);
    EXPECT_THROW(rig.observe(observation(2),wheel(2)),std::runtime_error);
    FunctionalRig old(scope);EXPECT_THROW(old.observe(observation(),wheel()),std::runtime_error);
}
TEST(M7Wheel, WrongActorFrameOldSourceAndFutureSourceRejected) {
    for(unsigned field=0;field<4;++field) {
        FunctionalRig rig(scope,99);auto w=wheel();
        if(field==0)++w.actor;
        if(field==1)++w.frame;
        if(field==2)--w.source;
        if(field==3)++w.source;
        EXPECT_THROW(rig.observe(observation(),w),std::runtime_error);
    }
}
TEST(M7Wheel, NonfiniteRangeAndReverseNotClampedOrMadePositive) {
    for(const double v:{-1e-9,100.01,std::numeric_limits<double>::quiet_NaN(),std::numeric_limits<double>::infinity()}) {
        FunctionalRig rig(scope,99);EXPECT_THROW(rig.observe(observation(),wheel(0,v)),std::runtime_error);
    }
}
TEST(M7Wheel, OriginalNonDrivingResetDoesNotInitializeFromMovingWheel) {
    FunctionalRig rig(scope,99);bool failed=false;
    for(unsigned i=0;i<100;++i) {
        try {const auto r=rig.observe(observation(i),wheel(i,5));EXPECT_FALSE(r.armed);EXPECT_EQ(r.release_mask,0U);}
        catch(const std::runtime_error&){failed=true;break;}
    }
    EXPECT_TRUE(failed);
}
TEST(M7Wheel, OldScopeDuplicateAndSkippedFrameStillFailClosed) {
    for(unsigned field=0;field<4;++field) {
        FunctionalRig rig(scope,99);rig.observe(observation(),wheel());auto o=observation(1);auto w=wheel(1);
        if(field==0)++o.scope.run;
        if(field==1)++o.scope.application;
        if(field==2){--o.frame;--w.frame;}
        if(field==3){++o.frame;++w.frame;}
        EXPECT_THROW(rig.observe(o,w),std::runtime_error);
    }
}
} // namespace
