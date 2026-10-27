#include "actuator_electrical.hpp"
#include <gtest/gtest.h>
#include <limits>

namespace {
using namespace stratadrive;
using namespace m7_external;
constexpr Time start=1000000000,ms=1000000;
SolverWork receipt(Time end=start+10*ms) {
    SolverWork w;w.frame=101;w.begin=start;w.end=end;w.oldest=start;w.dt=double(.01f*(1.f/320.f));
    w.wheel={0,{7,100,start},start};return w;
}
std::array<std::optional<simulation::OwnerActuation>,5> none{};
TEST(M7SolverWork, ConservativeProjectionPreservesSignedDiscreteWorkAtFractionalBoundaries) {
    for(int ns:{-1,0,1})for(double torque:{-100.,0.,100.}) {
        auto w=receipt(start+10*ms+ns);w.torque=torque;
        double expected=0,partitioned=0;
        for(unsigned k=0;k<320;++k){w.rear_mean[k]=double(k)/10;expected+=torque*w.rear_mean[k]*w.dt;}
        ASSERT_TRUE(w.valid());Time cursor=start;
        while(cursor<w.end) {const auto end=std::min(cursor+ms,w.end);partitioned+=w.work(cursor,end);cursor=end;}
        EXPECT_NEAR(w.work(w.begin,w.end),expected,1e-12);
        EXPECT_NEAR(partitioned,expected,1e-12);
        EXPECT_EQ(w.wheel.identity.source_time_ns,start);
    }
}
TEST(M7SolverWork, MissingDuplicateScopeTimeAndSignedInvalidityNeverSettle) {
    for(unsigned fault=0;fault<9;++fault) {
        ActuatorElectrical p(start,42,true);auto w=receipt();
        switch(fault) {
        case 0:--w.begin;break;
        case 1:w.dt=.01;break;
        case 2:w.oldest=start-30*ms;break;
        case 3:w.torque=1;w.rear_mean[7]=-1e-12;break;
        case 4:w.rear_mean[7]=std::numeric_limits<double>::quiet_NaN();break;
        case 5:w.sleeping=true;w.torque=1;break;
        case 6:++w.wheel.identity.source_time_ns;break;
        case 7:++w.wheel.identity.epoch;break;
        default:w.frame=0;
        }
        EXPECT_FALSE(p.begin_work_frame(w));EXPECT_EQ(p.electrical_time(),start);EXPECT_DOUBLE_EQ(p.settled_work(),0);
        EXPECT_FALSE(p.begin_work_frame(receipt()));
    }
    ActuatorElectrical missing(start,42,true);
    EXPECT_FALSE(missing.step(start+ms,receipt().wheel,none,0));EXPECT_EQ(missing.electrical_time(),start);
}
TEST(M7SolverWork, MidFrameFailureRollsBackEntireSingleOwnerWithoutPublishingSensors) {
    ActuatorElectrical p(start,42,true);auto w=receipt();ASSERT_TRUE(p.begin_work_frame(w));
    ASSERT_TRUE(p.step(start+ms,w.wheel,none,0))<<p.error();
    EXPECT_EQ(p.electrical_time(),start+ms);
    auto out=none;simulation::OwnerActuation invalid;
    invalid.epoch=42;invalid.source_ns=start+3*ms;
    invalid.drive=drive::Actuation{drive::ActuationMode::Target,1,std::nullopt,start+3*ms};out[2]=invalid;
    EXPECT_FALSE(p.step(start+2*ms,w.wheel,out,0));p.abort_work_frame();
    EXPECT_EQ(p.electrical_time(),start);EXPECT_EQ(p.last_success(),start);EXPECT_DOUBLE_EQ(p.settled_work(),0);
    EXPECT_EQ(p.audit().end,0U);EXPECT_FALSE(p.sensors());
    EXPECT_FALSE(p.begin_work_frame(w));
}
TEST(M7SolverWork, PartialTailSettlesOnceAndNextFrameKeepsOriginalSources) {
    ActuatorElectrical p(start,42,true);auto w=receipt(start+10*ms-1);
    ASSERT_TRUE(p.begin_work_frame(w));
    for(unsigned i=1;i<10;++i)ASSERT_TRUE(p.step(start+i*ms,w.wheel,none,0))<<p.error();
    ASSERT_TRUE(p.finish_work_frame(w.end))<<p.error();p.commit_work_frame();
    EXPECT_EQ(p.electrical_time(),w.end);EXPECT_EQ(p.last_success(),start+9*ms);
    EXPECT_EQ(p.audit().wheel_source,start);EXPECT_EQ(p.audit().end,w.end);
    auto next=w;next.begin=w.end;next.end=w.end+10*ms;next.oldest=next.begin;++next.frame;
    next.wheel={0,{7,101,next.begin},next.begin};
    ASSERT_TRUE(p.begin_work_frame(next));
    ASSERT_TRUE(p.step(start+10*ms,w.wheel,none,0))<<p.error();
    EXPECT_EQ(p.audit().begin,next.begin);EXPECT_EQ(p.audit().end,start+10*ms);
    EXPECT_EQ(p.audit().wheel_source,next.begin);
    p.abort_work_frame();EXPECT_EQ(p.electrical_time(),w.end);
}
TEST(M7SolverWork, ReplayedCommittedReceiptAndMissingTailCannotCommitAgain) {
    ActuatorElectrical p(start,42,true);auto w=receipt();ASSERT_TRUE(p.begin_work_frame(w));
    for(unsigned i=1;i<=10;++i)ASSERT_TRUE(p.step(start+i*ms,w.wheel,none,0))<<p.error();
    ASSERT_TRUE(p.finish_work_frame(w.end));p.commit_work_frame();
    EXPECT_FALSE(p.begin_work_frame(w));EXPECT_EQ(p.electrical_time(),w.end);
    ActuatorElectrical gap(start,42,true);ASSERT_TRUE(gap.begin_work_frame(w));
    ASSERT_TRUE(gap.step(start+ms,w.wheel,none,0));
    EXPECT_FALSE(gap.finish_work_frame(w.end));EXPECT_EQ(gap.electrical_time(),start);
}
}
