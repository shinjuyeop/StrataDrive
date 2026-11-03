#include "startup_diagnostics.hpp"
#include "diagnostics_fixture.hpp"
#include <gtest/gtest.h>

namespace {
using namespace stratadrive;
using namespace diagnostics_fixture;
constexpr std::uint64_t start=1000000000,ms=1000000;
class Port final : public session::ParticipantPort {
public:
    std::uint64_t now{start}; session::Preparation ready{session::Preparation::Rejected}; unsigned protections{0};
    std::uint64_t now_ns() noexcept override { return now; }
    session::Preparation prepare(const session::Plan&) noexcept override { return ready; }
    bool initialize(const session::Plan&) noexcept override { return true; }
    void protect() noexcept override { ++protections; }
    void service() noexcept override {}
};
Event attempt(unsigned epoch,unsigned seq) { auto e=diagnostics_fixture::session(seq,epoch); e.kind=Kind::Attempt; e.session_enable={}; e.source={true,20,epoch,epoch,stamp(),{}}; return e; }
TEST(StartupDiagnosticsTest, NativeRejectionRetainsFirstPlanAndOnlyActualNewReadyQualifies) {
    Port port; session::SessionParticipant actor(session::Role::Bms,port); const session::Plan first{1,start,start+2000*ms,0,0};
    const auto ack=actor.receive({session::Role::Bms,session::Phase::Prepare,first,start},port.now); ASSERT_TRUE(ack); EXPECT_FALSE(ack->accepted);
    ASSERT_TRUE(actor.fault_observation()); const auto fault=*actor.fault_observation(); EXPECT_EQ(fault.reason,static_cast<unsigned>(session::ParticipantFault::Rejected)); EXPECT_EQ(fault.observed_ns,start);
    port.now+=ms; actor.receive({session::Role::Bms,session::Phase::Abort,first,port.now},port.now); EXPECT_EQ(actor.fault_observation()->observed_ns,start); EXPECT_EQ(port.protections,1U);
    EventQueue q(10,45); diagnostics::StartupDiagnostics hook(q,{10,45,Domain::Simulation,7,1},diagnostics::Component::Bms,5);
    Ledger ledger; ASSERT_EQ(ledger.record(attempt(1,1)),Result::Accepted); hook.attempt(first); hook.observe(fault,std::nullopt,false,false,port.now);
    Event e; while(q.pop(e)) { ASSERT_EQ(ledger.record(e),Result::Accepted); } ASSERT_EQ(ledger.records().size(),1U);
    const auto key=ledger.records()[0].key; EXPECT_EQ(ledger.find(key)->condition,Condition::Failed);
    port.now=start+100*ms; port.ready=session::Preparation::Ready; session::Plan next{2,port.now,port.now+2000*ms,0,0};
    ASSERT_TRUE(actor.receive({session::Role::Bms,session::Phase::Prepare,next,port.now},port.now)); EXPECT_FALSE(actor.fault_observation());
    next.enable_ns=port.now+20*ms; next.commit_deadline_ns=next.enable_ns+20*ms;
    actor.receive({session::Role::Bms,session::Phase::Initialize,next,port.now},port.now); port.now=next.enable_ns; ASSERT_TRUE(actor.poll(port.now));
    EXPECT_FALSE(actor.success_observation()); port.now+=ms; ASSERT_TRUE(actor.receive({session::Role::Bms,session::Phase::Release,next,port.now},port.now)); ASSERT_TRUE(actor.success_observation());
    ASSERT_EQ(ledger.record(attempt(2,2)),Result::Accepted); auto released=diagnostics_fixture::session(3,2); released.session_enable=stamp(next.enable_ns); released.expected_roles=released.received_roles=255;
    ASSERT_EQ(ledger.record(released),Result::Accepted); hook.attempt(next);
    hook.observe(std::nullopt,actor.success_observation(),true,false,port.now); EXPECT_FALSE(q.pop(e));
    const auto good=*actor.success_observation();
    for(unsigned variant=0;variant<8;++variant) {
        auto bad=good; auto now=port.now; bool ready=true,released_gate=true;
        switch(variant) {
        case 0:ready=false;break; case 1:released_gate=false;break;
        case 2:bad.plan.epoch=1;break; case 3:bad.accepted_roles=16;break;
        case 4:bad.state=static_cast<unsigned>(session::ParticipantState::Initialized);break;
        case 5:bad.observed_ns=next.enable_ns-1;break; case 6:bad.observed_ns=next.commit_deadline_ns;break;
        case 7:now+=session::kMessageAgeNs+1;break;
        }
        hook.observe(std::nullopt,bad,ready,released_gate,now); EXPECT_FALSE(q.pop(e))<<variant;
    }
    hook.observe(std::nullopt,good,true,true,port.now); while(q.pop(e)) { ASSERT_EQ(ledger.record(e),Result::Accepted); }
    EXPECT_EQ(ledger.find(key)->condition,Condition::Passed); EXPECT_EQ(ledger.find(key)->count,1U);
}
TEST(StartupDiagnosticsTest, ConsecutiveFailedProposalsRemainSeparateWithoutAnySuccessfulRelease) {
    Port port; session::SessionParticipant actor(session::Role::Bms,port);
    EventQueue q(10,45); diagnostics::StartupDiagnostics hook(q,{10,45,Domain::Simulation,7,1},diagnostics::Component::Bms,5);
    Ledger ledger;
    for(unsigned epoch=1;epoch<=2;++epoch) {
        port.now=start+epoch*ms; const session::Plan p{epoch,port.now,port.now+2000*ms,0,0};
        ASSERT_EQ(ledger.record(attempt(epoch,epoch)),Result::Accepted);
        actor.receive({session::Role::Bms,session::Phase::Prepare,p,port.now},port.now);
        ASSERT_TRUE(actor.fault_observation());
        // Local owners discover a proposal from their native observation.
        hook.observe(actor.fault_observation(),std::nullopt,false,false,port.now);
        Event e; ASSERT_TRUE(q.pop(e)); EXPECT_EQ(e.kind,Kind::Fault); EXPECT_EQ(e.occurrence.epoch,epoch);
        ASSERT_EQ(ledger.record(e),Result::Accepted); EXPECT_FALSE(q.pop(e));
        hook.observe(actor.fault_observation(),std::nullopt,false,false,port.now); EXPECT_FALSE(q.pop(e));
    }
    ASSERT_EQ(ledger.records().size(),1U); EXPECT_EQ(ledger.records()[0].count,2U);
    EXPECT_EQ(ledger.records()[0].condition,Condition::Failed); EXPECT_FALSE(actor.run_enabled());
}
TEST(StartupDiagnosticsTest, DiagnosticOverflowDoesNotChangeNativeFailureOrInventRelease) {
    EventQueue q(10,45); Event fill; fill.id={10,45,1}; for(unsigned i=0;i<EventQueue::kCapacity;++i) { fill.id.sequence=i+1; ASSERT_TRUE(q.publish(fill)); }
    Port port; session::SessionParticipant actor(session::Role::Bms,port); const session::Plan p{1,start,start+2000*ms,0,0};
    actor.receive({session::Role::Bms,session::Phase::Prepare,p,start},start); ASSERT_TRUE(actor.fault_observation());
    diagnostics::StartupDiagnostics hook(q,{10,45,Domain::Simulation,7,1},diagnostics::Component::Bms,5); hook.attempt(p); hook.observe(actor.fault_observation(),std::nullopt,false,false,start);
    EXPECT_FALSE(hook.healthy()); EXPECT_EQ(q.health().dropped,1U); EXPECT_EQ(port.protections,1U); EXPECT_FALSE(actor.run_enabled());
}
} // namespace
