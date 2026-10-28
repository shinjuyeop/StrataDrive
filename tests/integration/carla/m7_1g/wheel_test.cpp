#include "functional_rig.hpp"
#include "wall_execution_watch.hpp"
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
    EXPECT_NEAR(r.returned_wheel->rad_s,1.23456,.005); // original .01 rad/s CAN quantization
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
TEST(M7Wheel, FractionalCarlaClockCannotOverwriteAnUnconsumedSample) {
    FunctionalRig rig(scope,99);Report r;
    for(unsigned i=0;i<=180;++i) {
        auto o=observation(i);o.elapsed_s=3.997146773152053+i*.009999999776482582;
        auto w=wheel(i,i<100?0:2.34567);w.source=static_cast<Time>(std::llround(o.elapsed_s*1e9));
        r=rig.observe(o,w);
        if(i>0) {ASSERT_TRUE(r.sensor_wheel);EXPECT_LE(r.now-r.sensor_wheel->source,tick_ns+1000);}
    }
    EXPECT_TRUE(r.armed);ASSERT_TRUE(r.returned_wheel);
    EXPECT_NEAR(r.returned_wheel->rad_s,2.34567,.005);
    EXPECT_LE(r.now-r.returned_wheel->source,20*ms);
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
    for(unsigned i=0;i<=210;++i) { // original Prepare deadline is 2 seconds
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
TEST(M7WallWatch, TerminalSelectionAtCompletedBarrierDoesNotReplayOrRearm) {
    FunctionalRig rig(scope,99,PlantMode::ExternalWheelZoh,true);Report last;
    EXPECT_THROW(rig.stop_at_barrier(),std::runtime_error);
    for(unsigned i=0;i<=180;++i)last=rig.observe(observation(i),wheel(i));
    ASSERT_TRUE(last.armed);
    const auto stopped=rig.stop_at_barrier();
    EXPECT_EQ(stopped.logical_ns,last.now);
    EXPECT_EQ(stopped.selected_mask,255U);EXPECT_EQ(stopped.credit_mask,0U);EXPECT_FALSE(stopped.normal);
    EXPECT_THROW(rig.observe(observation(181),wheel(181)),std::runtime_error);
}
TEST(M7WallWatch, RealOwnerCallsCompleteSlotsButIdlePollingCannot) {
    FunctionalRig rig(scope,99,PlantMode::ExternalWheelZoh,true);
    for(unsigned i=0;i<=180;++i)rig.observe(observation(i),wheel(i));
    const auto first=WallExecutionWatch::now()+20000000;
    WallExecutionWatch watch(first);rig.execution_watch(&watch);
    stratadrive::simulation::runtime_support::sleep_until(first);
    const auto report=rig.observe(observation(181),wheel(181));
    EXPECT_EQ(report.now,wheel(181).source);
    stratadrive::simulation::runtime_support::sleep_until(first+30000000);
    ASSERT_TRUE(watch.faulted());
    unsigned completed=0,missing=0;
    for(const auto& row:watch.rows())if(row.owner<9) {
        if(row.end_ns) {EXPECT_GE(row.end_ns,row.start_ns);completed|=1U<<row.owner;}
        if(row.detected_ns && !row.end_ns)missing|=1U<<row.owner;
    }
    EXPECT_EQ(completed,511U);EXPECT_EQ(missing,511U);
}
TEST(M7WallWatch, LateCompletionCannotHealIndependentDeadlineFault) {
    const auto first=WallExecutionWatch::now()+20000000;
    WallExecutionWatch watch(first);
    stratadrive::simulation::runtime_support::sleep_until(first);
    const auto job=watch.begin(2);ASSERT_TRUE(job);
    stratadrive::simulation::runtime_support::sleep_until(WallExecutionWatch::now()+30000000);
    ASSERT_TRUE(watch.faulted());watch.finish(2,job);
    bool found=false;
    for(const auto& row:watch.rows())if(row.owner==2 && row.slot==*job) {
        found=true;EXPECT_GT(row.end_ns,row.deadline_ns);EXPECT_GE(row.detected_ns,row.deadline_ns);
    }
    EXPECT_TRUE(found);EXPECT_TRUE(watch.faulted());
}
} // namespace
