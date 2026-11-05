#include "clock_recovery.hpp"
#include <gtest/gtest.h>

namespace {
using namespace stratadrive;
using namespace diagnostics;
constexpr std::uint64_t ms=1000000,start=1000000000,run=9701;
Stamp stamp(std::uint64_t ns){return {Domain::Simulation,run,ns,true,true};}
Event fault(unsigned epoch=1,unsigned sequence=1){Event e;e.id={run,45,sequence};e.session={run,epoch};e.kind=Kind::Fault;e.key={Code::Clock,10,11,6};e.occurrence={run,45,epoch,11,sequence};return e;}
ClockRevalidation check(unsigned revision=1,unsigned epoch=2){return {{run,run,0,0,true},stamp(start),revision,epoch};}
ClockRecoverySample sample(unsigned t=0){const session::Plan p{2,start,start+2000*ms,start+20*ms,start+40*ms};return {{run,2},p,255,true,true,stamp(p.enable_ns+t*ms),stamp(p.enable_ns+t*ms)};}
void feed(ClockRecovery& c,unsigned begin,unsigned end){for(unsigned t=begin;t<=end;t+=10)c.observe(sample(t));}
TEST(ClockRecovery, InitAloneCannotHealAndProofRetainsOriginalOccurrence) {
    ClockRecovery c;ASSERT_TRUE(c.remember(fault()));feed(c,0,200);EXPECT_FALSE(c.take_ready());
    ASSERT_TRUE(c.revalidate(check(),Domain::Simulation,run));feed(c,0,90);EXPECT_FALSE(c.take_ready());
    c.observe(sample(100));const auto proof=c.take_ready();ASSERT_TRUE(proof);
    EXPECT_EQ(proof->related,fault().id);EXPECT_EQ(proof->occurrence,fault().occurrence);EXPECT_EQ(proof->proof,Proof::Control);
    EXPECT_EQ(proof->times[1].ns,sample().source.ns);EXPECT_EQ(proof->measured,100*ms);EXPECT_EQ(proof->state_before,1U);EXPECT_FALSE(c.take_ready());
}
class BadClockTrust:public ::testing::TestWithParam<unsigned>{};
TEST_P(BadClockTrust, RejectsUntrustedAuthority) {
    ClockRecovery c;c.remember(fault());auto a=check();
    switch(GetParam()){
    case 0:a.agreement.established=false;break;case 1:++a.agreement.local_domain;break;case 2:++a.agreement.source_domain;break;
    case 3:a.agreement.offset_ns=1;break;case 4:a.agreement.uncertainty_ns=1;break;case 5:a.checked.trusted=false;break;
    case 6:a.checked.present=false;break;case 7:a.checked.domain=Domain::Monotonic;break;case 8:++a.checked.instance;break;
    case 9:a.revision=0;break;case 10:a.recovery_epoch=1;break;case 11:a.checked.ns=0;break;
    }
    EXPECT_FALSE(c.revalidate(a,Domain::Simulation,run));feed(c,0,200);EXPECT_FALSE(c.take_ready());
}
INSTANTIATE_TEST_SUITE_P(Authority,BadClockTrust,::testing::Range(0U,12U));
class BadClockWindow:public ::testing::TestWithParam<unsigned>{};
TEST_P(BadClockWindow, InvalidObservationCannotCompleteWindow) {
    ClockRecovery c;c.remember(fault());ASSERT_TRUE(c.revalidate(check(),Domain::Simulation,run));feed(c,0,90);auto s=sample(100);
    switch(GetParam()){
    case 0:s.release_mask=127;break;case 1:s.normal_gate=false;break;case 2:s.native_healthy=false;break;
    case 3:s.session.epoch=1;break;case 4:s.released.epoch=1;break;case 5:s.source.trusted=false;break;
    case 6:s.source.ns=s.observed.ns+1;break;case 7:s.source.ns-=31*ms;break;case 8:s.source.ns-=20*ms;break;
    case 9:--s.released.enable_ns;break;case 10:++s.released.prepare_deadline_ns;break;case 11:s.released.commit_deadline_ns=s.released.enable_ns;break;
    case 12:s.source.ns=sample(90).source.ns;break;case 13:s.session.run=run+1;break;
    }
    c.observe(s);EXPECT_FALSE(c.take_ready());
    if(GetParam()==12){c.observe(sample(110));EXPECT_TRUE(c.take_ready());return;}
    feed(c,110,190);EXPECT_FALSE(c.take_ready());feed(c,200,220);EXPECT_TRUE(c.take_ready());
}
INSTANTIATE_TEST_SUITE_P(Window,BadClockWindow,::testing::Range(0U,14U));
TEST(ClockRecovery, RollbackRequiresNewRevisionAndNewFaultInvalidatesTrust) {
    ClockRecovery c;c.remember(fault());ASSERT_TRUE(c.revalidate(check(),Domain::Simulation,run));feed(c,0,90);
    c.observe(sample(80));feed(c,100,300);EXPECT_FALSE(c.take_ready());EXPECT_FALSE(c.revalidate(check(),Domain::Simulation,run));
    auto next=check(2);next.checked=stamp(start+110*ms);ASSERT_TRUE(c.revalidate(next,Domain::Simulation,run));
    auto later=sample();later.released.requested_ns=next.checked.ns;later.released.prepare_deadline_ns=next.checked.ns+session::kPrepareBudgetNs;
    later.released.enable_ns=next.checked.ns+20*ms;later.released.commit_deadline_ns=later.released.enable_ns+20*ms;
    for(unsigned t=0;t<=100;t+=10){later.observed=later.source=stamp(later.released.enable_ns+t*ms);c.observe(later);}
    ASSERT_TRUE(c.take_ready());ASSERT_TRUE(c.remember(fault(2,3)));EXPECT_FALSE(c.take_ready());
    next.revision=3;EXPECT_FALSE(c.revalidate(next,Domain::Simulation,run));
}
TEST(ClockRecovery, MissingObservationsAndCachedSourcesDoNotAdvanceWindow) {
    ClockRecovery c;c.remember(fault());ASSERT_TRUE(c.revalidate(check(),Domain::Simulation,run));feed(c,0,90);
    feed(c,130,220);EXPECT_FALSE(c.take_ready());c.observe(sample(230));EXPECT_TRUE(c.take_ready());
}
TEST(ClockRecovery, BoundedRetentionNeverEvictsAnOldClockIncident) {
    ClockRecovery c;
    for(unsigned i=0;i<32;++i){auto e=fault(1,i+1);e.key.subject=i+1;ASSERT_TRUE(c.remember(e));}
    auto extra=fault(1,33);extra.key.subject=33;EXPECT_FALSE(c.remember(extra));
    ASSERT_TRUE(c.revalidate(check(),Domain::Simulation,run));feed(c,0,100);
    unsigned count=0;while(c.take_ready())++count;EXPECT_EQ(count,32U);
}
} // namespace
