#include "functional_rig.hpp"
#include "run_lease_gate.hpp"
#include <gtest/gtest.h>
#include <chrono>
#include <thread>

namespace {
using namespace stratadrive::m7_functional;
const Scope scope{1,42,7};
Observation observation(unsigned index=0) {return {scope,domain,100+index,1+index*.01,.01};}
void complete(FrameClock& clock) {for(unsigned i=0;i<8;++i)clock.serviced(i);clock.permit_non_driving_tick();}
TEST(M7FrameClock, OriginalElapsedRoundedNotArrivalOrNominalGrid) {
    FrameClock clock(scope);auto o=observation();o.elapsed_s+=.000000017;
    EXPECT_EQ(clock.accept(o),1000000017U);complete(clock);
    o=observation(1);o.elapsed_s+=.000000029;
    EXPECT_EQ(clock.accept(o),1010000029U);complete(clock);
}
TEST(M7FrameClock, AllEightRequiredAndFailureCannotBeHealed) {
    FrameClock clock(scope);clock.accept(observation());
    for(unsigned i=0;i<7;++i)clock.serviced(i);
    EXPECT_THROW(clock.permit_non_driving_tick(),std::runtime_error);
    EXPECT_THROW(clock.serviced(7),std::runtime_error);
    EXPECT_THROW(clock.accept(observation(1)),std::runtime_error);
}
TEST(M7FrameClock, DuplicateReceiptAndDoublePermitFailClosed) {
    FrameClock a(scope);a.accept(observation());a.serviced(0);EXPECT_THROW(a.serviced(0),std::runtime_error);
    FrameClock b(scope);b.accept(observation());complete(b);EXPECT_THROW(b.permit_non_driving_tick(),std::runtime_error);
}
TEST(M7FrameClock, InputBeforeBarrierCannotOverwritePendingFrame) {
    FrameClock clock(scope);clock.accept(observation());EXPECT_THROW(clock.accept(observation(1)),std::runtime_error);
}
TEST(M7FrameClock, DuplicateSkippedAndBackwardFramesRejected) {
    for(const auto frame:{99U,100U,102U}) {
        FrameClock clock(scope);clock.accept(observation());complete(clock);
        auto o=observation(1);o.frame=frame;EXPECT_THROW(clock.accept(o),std::runtime_error);
    }
    FrameClock clock(scope);auto o=observation();o.frame=UINT64_MAX;
    EXPECT_THROW(clock.accept(o),std::runtime_error);
}
TEST(M7FrameClock, ClockDomainAndOldRunApplicationPlantRejected) {
    for(unsigned field=0;field<4;++field) {
        FrameClock clock(scope);auto o=observation();
        if(field==0)++o.clock;
        if(field==1)++o.scope.run;
        if(field==2)++o.scope.application;
        if(field==3)++o.scope.plant;
        EXPECT_THROW(clock.accept(o),std::runtime_error);
    }
}
TEST(M7FrameClock, InvalidOrFiftyMsTimeDoesNotChangeTenMsContract) {
    for(const double seconds:{0.,-1.,static_cast<double>(INFINITY),static_cast<double>(NAN)}) {
        FrameClock clock(scope);auto o=observation();o.elapsed_s=seconds;EXPECT_THROW(clock.accept(o),std::runtime_error);
    }
    FrameClock a(scope);a.accept(observation());complete(a);auto o=observation(1);o.elapsed_s=1.05;
    EXPECT_THROW(a.accept(o),std::runtime_error);
    FrameClock b(scope);o=observation();o.delta_s=.05;EXPECT_THROW(b.accept(o),std::runtime_error);
}
TEST(M7FrameClock, AnotherThreadCannotOwnTheTickBarrier) {
    FrameClock clock(scope);clock.accept(observation());
    bool rejected=false;std::thread other([&]{try{clock.serviced(0);}catch(const std::runtime_error&){rejected=true;}});other.join();
    EXPECT_TRUE(rejected);EXPECT_TRUE(clock.failed());
}
Report run(FunctionalRig& rig,unsigned begin,unsigned end) {
    Report r;for(unsigned i=begin;i<=end;++i)r=rig.observe(observation(i));return r;
}
TEST(M7FunctionalNative, RealEightInitReleaseCreditArmAndOriginalActual) {
    FunctionalRig rig(scope);const auto first=rig.observe(observation());
    EXPECT_EQ(first.release_mask,0U);EXPECT_EQ(first.credit_mask,0U);EXPECT_FALSE(first.armed);
    const auto r=run(rig,1,180);
    EXPECT_EQ(r.release_mask,255U);EXPECT_EQ(r.credit_mask,255U);EXPECT_EQ(r.service_mask,255U);
    EXPECT_TRUE(r.armed);EXPECT_TRUE(r.actual_interval);
    for(unsigned i=0;i<3;++i){EXPECT_GT(r.commands[i],50U);EXPECT_LT(r.actual_sources[i],r.now);EXPECT_LE(r.now+tick_ns-r.actual_sources[i],30*ms);}
    EXPECT_EQ(r.lease_expiry-r.lease_source,stratadrive::remote::kRunLeaseLifetimeNs);
    const auto next=run(rig,181,182);
    EXPECT_EQ(next.controller_releases-r.controller_releases,1U);
    for(unsigned i=0;i<5;++i)EXPECT_EQ(next.leaf_body[i]-r.leaf_body[i],20*ms);
    const auto one=run(rig,183,183);
    for(const unsigned i:{0U,1U,2U,4U})EXPECT_EQ(one.leaf_body[i]-next.leaf_body[i],10*ms);
    EXPECT_TRUE(one.leaf_body[3]-next.leaf_body[3]==0 || one.leaf_body[3]-next.leaf_body[3]==20*ms);
}
TEST(M7FunctionalNative, SlowHostAndPauseDoNotRenewOrRestampLogicalEvidence) {
    FunctionalRig rig(scope);const auto before=run(rig,0,150);
    const auto wall=std::chrono::steady_clock::now();std::this_thread::sleep_for(std::chrono::milliseconds(80));
    EXPECT_GE(std::chrono::steady_clock::now()-wall,std::chrono::milliseconds(70));
    const auto after=run(rig,151,151);
    EXPECT_EQ(after.now-before.now,10*ms);EXPECT_TRUE(after.armed);EXPECT_TRUE(after.actual_interval);
    EXPECT_EQ(after.lease_source-before.lease_source,10*ms);
}
TEST(M7FunctionalNative, MissingRoleNeverCompletesBarrierOrIssuesCredit) {
    for(int role=0;role<8;++role) {
        FunctionalRig rig(scope);rig.omit_role(role);
        EXPECT_THROW(rig.observe(observation()),std::runtime_error);
        rig.omit_role(-1);EXPECT_THROW(rig.observe(observation(1)),std::runtime_error);
    }
}
TEST(M7FunctionalNative, LostCreditStillExpiresAtOriginalThirtyMsSourceAge) {
    FunctionalRig rig(scope);const auto r=run(rig,0,150);rig.stop_credit(true);
    // Original issuer phase is not rounded to the outer 10ms frame grid.
    unsigned last=150;bool rejected=false;
    for(unsigned i=151;i<=155;++i) {
        try {const auto next=rig.observe(observation(i));last=i;EXPECT_LE(next.now-r.lease_source,30*ms);}
        catch(const std::runtime_error&){rejected=true;break;}
    }
    EXPECT_TRUE(rejected);EXPECT_LE(last,153U);
    rig.stop_credit(false);EXPECT_THROW(rig.observe(observation(last+1)),std::runtime_error);
}
TEST(M7FunctionalNative, MissingActualClosesShadowTickInsteadOfReusingItsTime) {
    FunctionalRig rig(scope);run(rig,0,150);rig.drop_actual(true);
    bool rejected=false;
    for(unsigned i=151;i<=156;++i)try{rig.observe(observation(i));}catch(const std::runtime_error&){rejected=true;break;}
    EXPECT_TRUE(rejected);
}
TEST(M7FunctionalNative, FreshInstanceNeedsNewInitAndRejectsOldScope) {
    FunctionalRig old(scope);run(old,0,150);
    const Scope fresh{2,43,8};FunctionalRig rig(fresh);
    auto o=observation();o.scope=fresh;
    const auto first=rig.observe(o);EXPECT_FALSE(first.armed);EXPECT_EQ(first.credit_mask,0U);
    EXPECT_THROW(rig.observe(observation(1)),std::runtime_error);
    FunctionalRig clean(fresh);Report end;
    for(unsigned i=0;i<=150;++i){o=observation(i);o.scope=fresh;end=clean.observe(o);}
    EXPECT_TRUE(end.armed);EXPECT_EQ(end.release_mask,255U);
}
TEST(M7FunctionalNative, ScenarioCannotRewritePastOrAcceptInvalidSchedule) {
    FunctionalRig rig(scope);
    EXPECT_THROW(rig.request_profile({{100,.2,0,0,false},{90,.2,0,0,false}}),std::runtime_error);
    EXPECT_THROW(rig.request_profile({{100,.2,0,2,false}}),std::runtime_error);
    rig.request_profile({{100,.2,0,0,false}});
    rig.observe(observation());
    EXPECT_THROW(rig.request_profile({{1000,1,0,0,false}}),std::runtime_error);
}
} // namespace
