#include "remote_diagnostics_context.hpp"
#include "startup_diagnostics.hpp"
#include "run_lease_issuer.hpp"
#include <gtest/gtest.h>
#include <cstdlib>
#include <deque>
#include <filesystem>
#include <fstream>
#include <memory>

namespace {
using namespace stratadrive;
using namespace diagnostics;
constexpr std::uint64_t run=10,central_id=20,clock_id=99,ms=1000000;
const remote::ClockAgreement clock_agreement{clock_id,clock_id,0,0,true};
struct Peer final:session::ParticipantPort {
    std::uint64_t* now{}; remote::RunLeaseGate credit;
    std::uint64_t now_ns() noexcept override {return *now;}
    session::Preparation prepare(const session::Plan&) noexcept override {return session::Preparation::Ready;}
    bool initialize(const session::Plan& p) noexcept override {return credit.bind(p,clock_agreement,*now);}
    void protect() noexcept override {}
    void service() noexcept override {}
};
struct Central final:session::CoordinatorPort {
    std::uint64_t now{1000000000};std::deque<session::Control> controls;
    std::uint64_t now_ns() noexcept override {return now;}
    bool quiesce_central() noexcept override {return true;}
    bool send(const session::Control& c) noexcept override {controls.push_back(c);return true;}
    bool commit_central(central::CoordinatorSession) noexcept override {return true;}
    void protect_central() noexcept override {}
};
class RemoteDiagnosticsContext:public ::testing::Test {
protected:
    Central central;session::SessionCoordinator coordinator{central};central::RunLeaseIssuer issuer{coordinator};
    std::array<Peer,8> peers;std::array<std::unique_ptr<session::SessionParticipant>,8> actors;
    EventQueue global_queue{run,central_id};StartupDiagnostics hook{global_queue,{run,central_id,Domain::Monotonic,clock_id,1},Component::Coordinator,8,true};
    Event global;std::filesystem::path root;
    void SetUp() override {
        char name[]="/tmp/stratadrive-context-XXXXXX";auto* p=mkdtemp(name);ASSERT_NE(p,nullptr);root=p;
        for(unsigned i=0;i<8;++i) {peers[i].now=&central.now;actors[i]=std::make_unique<session::SessionParticipant>(static_cast<session::Role>(i),peers[i]);}
    }
    void TearDown() override {std::filesystem::remove_all(root);}
    void pump() {
        while(!central.controls.empty()) {
            const auto c=central.controls.front();central.controls.pop_front();
            const auto ack=actors[static_cast<unsigned>(c.role)]->receive(c,central.now);
            if(ack) {ASSERT_EQ(coordinator.receive(*ack,central.now),session::AckResult::Accepted);}
        }
    }
    void release(unsigned epoch=1) {
        if(coordinator.run_enabled()) {coordinator.cancel(central.now);pump();}
        ASSERT_TRUE(coordinator.begin(epoch,central.now));hook.attempt(coordinator.plan());pump();
        central.now=coordinator.plan().enable_ns;
        for(auto& a:actors) {const auto ack=a->poll(central.now);ASSERT_TRUE(ack);ASSERT_EQ(coordinator.receive(*ack,central.now),session::AckResult::Accepted);}
        pump();ASSERT_TRUE(coordinator.run_enabled());
        hook.observe(coordinator.fault_observation(),coordinator.success_observation(),true,true,central.now);
        Event e;while(global_queue.pop(e))if(e.kind==Kind::Session)global=e;
        ASSERT_EQ(global.kind,Kind::Session);ASSERT_EQ(global.received_roles,255U);
    }
    remote::RunLeaseEvidence credit(unsigned peer=0) {
        const auto lease=issuer.issue(++central.now);EXPECT_TRUE(lease);if(!lease)return {};
        // Use the original typed control codec before the actual receiver gate.
        const auto packet=remote::encode_owner_message({session::Role::CentralIngress,static_cast<session::Role>(peer),clock_id,*lease});
        EXPECT_TRUE(packet);if(!packet)return {};
        const auto decoded=remote::decode_owner_message(packet->bytes.data(),packet->size);EXPECT_TRUE(decoded);if(!decoded)return {};
        EXPECT_TRUE(peers[peer].credit.receive(std::get<remote::RunLease>(decoded->payload),decoded->clock_domain,*actors[peer],central.now));
        return peers[peer].credit.diagnostic_evidence();
    }
    std::filesystem::path provision(const char* name,std::uint64_t stream=101,Limits limits={}) {
        const auto p=root/name;FileJournal::initialize(p.string(),stream,limits,3);return p;
    }
    ControlContext manifest(std::uint64_t producer=30) {return {run,producer,Domain::Monotonic,clock_id,1};}
    Event fault(std::uint64_t producer=30,std::uint64_t sequence=1,unsigned epoch=1) {
        Event e;e.id={run,producer,sequence};e.session={run,epoch};e.profile=1;e.kind=Kind::Fault;
        e.session_enable=global.session_enable;e.key={Code::Gateway,producer==30?7U:8U,6,4};
        e.occurrence={run,producer,epoch,6,sequence};e.native_reason=1;e.latch=Latch::Set;
        e.times[static_cast<std::size_t>(Time::Detected)]={Domain::Monotonic,clock_id,central.now,true,true};return e;
    }
};
TEST_F(RemoteDiagnosticsContext, LocalReadyAndSevenReleaseAcksCannotCreateGlobalContext) {
    ASSERT_TRUE(coordinator.begin(1,central.now));pump();central.now=coordinator.plan().enable_ns;
    for(auto& a:actors) {const auto ack=a->poll(central.now);ASSERT_TRUE(ack);ASSERT_EQ(coordinator.receive(*ack,central.now),session::AckResult::Accepted);}
    std::optional<session::Ack> last;
    while(!central.controls.empty()) {
        const auto c=central.controls.front();central.controls.pop_front();const auto ack=actors[static_cast<unsigned>(c.role)]->receive(c,central.now);ASSERT_TRUE(ack);
        if(c.role==session::Role::CentralIngress)last=ack;else ASSERT_EQ(coordinator.receive(*ack,central.now),session::AckResult::Accepted);
    }
    EXPECT_TRUE(actors[0]->run_enabled());EXPECT_FALSE(issuer.issue(central.now));
    EXPECT_FALSE(peers[0].credit.diagnostic_evidence().accepted);ASSERT_TRUE(last);
    ASSERT_EQ(coordinator.receive(*last,central.now),session::AckResult::Accepted);
    hook.observe(std::nullopt,coordinator.success_observation(),true,true,central.now);Event e;while(global_queue.pop(e))if(e.kind==Kind::Session)global=e;
    FileJournal journal(provision("source").string());ContextualOutbox source(journal,manifest(),central_id);
    EXPECT_EQ(source.context(global,peers[0].credit.diagnostic_evidence()),Result::NotReady);EXPECT_TRUE(journal.committed().empty());
    EXPECT_EQ(source.context(global,credit()),Result::Accepted);
}
TEST_F(RemoteDiagnosticsContext, DelayedContextCommitsOriginalSessionThenBufferedFaultWithoutRenewingCredit) {
    release();const auto evidence=credit();EventQueue q(run,30);const auto original=fault();ASSERT_TRUE(q.publish(original));
    FileJournal journal(provision("source").string());ContextualOutbox source(journal,manifest(),central_id);
    EXPECT_EQ(source.drain(q),1U);EXPECT_EQ(source.pending(),1U);EXPECT_FALSE(source.next());
    central.now=evidence.accepted->expires_at_ns;EXPECT_FALSE(peers[0].credit.allows(*actors[0],central.now));
    const auto reason=peers[0].credit.fault();EXPECT_EQ(source.context(global,peers[0].credit.diagnostic_evidence()),Result::Accepted);
    ASSERT_EQ(journal.committed().size(),2U);EXPECT_EQ(encode(journal.committed()[0]),encode(global));EXPECT_EQ(encode(journal.committed()[1]),encode(original));
    EXPECT_EQ(source.pending(),0U);EXPECT_EQ(source.ledger().find(original.key)->condition,Condition::Failed);
    EXPECT_FALSE(peers[0].credit.allows(*actors[0],central.now));EXPECT_EQ(peers[0].credit.fault(),reason);
    EXPECT_EQ(source.context(global,evidence),Result::Duplicate);EXPECT_EQ(journal.committed().size(),2U);
}
TEST_F(RemoteDiagnosticsContext, WrongPeerClockProfilePlanAndPartialMasksDoNotMutateTheStore) {
    release();const auto evidence=credit();FileJournal journal(provision("source").string());ContextualOutbox source(journal,manifest(),central_id);
    for(unsigned variant=0;variant<13;++variant) {
        auto e=global;auto a=evidence;
        switch(variant) {
        case 0:++e.id.producer;break;case 1:++e.id.run;break;case 2:++e.profile;break;
        case 3:e.expected_roles=127;break;case 4:e.received_roles=127;break;case 5:++e.session_enable.ns;break;
        case 6:++e.source.expiry.ns;break;case 7:e.source.source.ns=e.session_enable.ns-1;break;
        case 8:e.source.source.ns=evidence.accepted->plan.commit_deadline_ns;break;
        case 9:++e.session_enable.instance;break;case 10:e.source.source.trusted=false;break;
        case 11:a.clock.established=false;break;case 12:a.clock.offset_ns=1;break;
        }
        EXPECT_EQ(source.context(e,a),Result::Invalid)<<variant;EXPECT_TRUE(source.healthy());EXPECT_TRUE(journal.committed().empty());
    }
    EXPECT_EQ(source.context(global,evidence),Result::Accepted);
}
TEST_F(RemoteDiagnosticsContext, ChangedCanonicalContextMakesTheStreamIncomplete) {
    release();const auto evidence=credit();FileJournal journal(provision("source").string());ContextualOutbox source(journal,manifest(),central_id);
    ASSERT_EQ(source.context(global,evidence),Result::Accepted);auto changed=global;changed.native_reason=42;
    EXPECT_EQ(source.context(changed,evidence),Result::Conflict);EXPECT_FALSE(source.healthy());EXPECT_FALSE(source.next());
}
TEST_F(RemoteDiagnosticsContext, NewEpochDoesNotSkipUnresolvedOldFaults) {
    release();const auto first=global;const auto old_credit=credit();const auto original=fault();
    FileJournal journal(provision("source").string());ContextualOutbox source(journal,manifest(),central_id);ASSERT_EQ(source.submit(original),Result::Accepted);
    ++central.now;release(2);const auto fresh=credit();EXPECT_EQ(source.context(global,old_credit),Result::NotReady);
    EXPECT_EQ(source.context(global,fresh),Result::NotReady);EXPECT_TRUE(journal.committed().empty());
    ASSERT_EQ(source.context(first,old_credit),Result::Accepted);ASSERT_EQ(source.context(global,fresh),Result::Accepted);
    EXPECT_EQ(source.ledger().find(original.key)->condition,Condition::Unknown);
    EXPECT_EQ(source.context(first,fresh),Result::NotReady);
}
TEST_F(RemoteDiagnosticsContext, QueueLossAndPendingCapacityAreStickyAndNeverExposeUncommittedEvents) {
    release();FileJournal journal(provision("source").string());ContextualOutbox source(journal,manifest(),central_id);
    for(unsigned i=0;i<ContextualOutbox::kPending;++i)ASSERT_EQ(source.submit(fault(30,i+1)),Result::Accepted);
    EXPECT_EQ(source.submit(fault(30,33)),Result::Capacity);EXPECT_FALSE(source.healthy());EXPECT_TRUE(journal.committed().empty());EXPECT_FALSE(source.next());
    FileJournal other(provision("other",102).string());ContextualOutbox lost(other,manifest(),central_id);EventQueue q(run,30);
    for(unsigned i=0;i<EventQueue::kCapacity;++i) {ASSERT_TRUE(q.publish(fault(30,i+1)));}
    EXPECT_FALSE(q.publish(fault(30,257)));
    EXPECT_EQ(lost.drain(q),0U);EXPECT_FALSE(lost.healthy());EXPECT_TRUE(other.committed().empty());
}
TEST_F(RemoteDiagnosticsContext, AbandonedPendingEventsInvalidateTheStoreAcrossRestart) {
    release();const auto path=provision("source");{FileJournal j(path.string());ContextualOutbox source(j,manifest(),central_id);ASSERT_EQ(source.submit(fault()),Result::Accepted);}
    FileJournal j(path.string());EXPECT_FALSE(j.writable());ContextualOutbox source(j,manifest(),central_id);EXPECT_FALSE(source.healthy());
}
TEST_F(RemoteDiagnosticsContext, TwoSourceStreamsRetainOneCanonicalContextAndIndependentDurableAcks) {
    release();const auto front_credit=credit(0),rear_credit=credit(1);const auto f=fault(),r=fault(31);
    FileJournal fsrc(provision("front",101).string()),rsrc(provision("rear",102).string());
    FileJournal fdst(provision("front-replica",101).string()),rdst(provision("rear-replica",102).string());
    ContextualOutbox front(fsrc,manifest(),central_id),rear(rsrc,manifest(31),central_id);Inbox fi(fdst),ri(rdst);Ledger merged;
    ASSERT_EQ(front.submit(f),Result::Accepted);ASSERT_EQ(rear.submit(r),Result::Accepted);
    ASSERT_EQ(front.context(global,front_credit),Result::Accepted);ASSERT_EQ(rear.context(global,rear_credit),Result::Accepted);
    for(auto pair:{std::make_pair(&front,&fi),std::make_pair(&rear,&ri)}) {
        while(auto bytes=pair.first->next()) {
            const auto delivery=pair.second->receive(*bytes);ASSERT_TRUE(delivery.ack);const auto decoded=wire::decode(*bytes);const auto& e=std::get<wire::Data>(decoded).event;
            // Global context is the exact same original event in both streams.
            const auto result=merged.record(e);EXPECT_EQ(result,e.kind==Kind::Session && merged.events().size()>1?Result::Duplicate:Result::Accepted);
            ASSERT_EQ(pair.first->acknowledge(*delivery.ack),Result::Accepted);
        }
    }
    EXPECT_EQ(merged.events().size(),3U);EXPECT_EQ(merged.records().size(),2U);EXPECT_EQ(front.acknowledged(),2U);EXPECT_EQ(rear.acknowledged(),2U);
    const auto foreign=wire::encode(wire::Ack{102,2,3,wire::event_crc(r)});EXPECT_EQ(front.acknowledge(foreign),Result::Invalid);
    // Optional component evidence export; normal regressions keep no artifacts.
    if(const auto* output=std::getenv("STRATADRIVE_CONTEXT_EVIDENCE")) {
        const std::filesystem::path p(output);ASSERT_FALSE(std::filesystem::exists(p));ASSERT_TRUE(std::filesystem::create_directories(p));
        for(const auto* name:{"front","rear","front-replica","rear-replica"})
            std::filesystem::copy(root/name,p/name,std::filesystem::copy_options::recursive);
        for(const auto& item:{std::make_pair("global-event.bin",global),std::make_pair("front-event.bin",f),std::make_pair("rear-event.bin",r)}) {
            const auto bytes=encode(item.second);std::ofstream out(p/item.first,std::ios::binary);
            out.write(reinterpret_cast<const char*>(bytes.data()),static_cast<std::streamsize>(bytes.size()));ASSERT_TRUE(out.good());
        }
    }
}
TEST_F(RemoteDiagnosticsContext, ReplayAndContextRebindingCannotHealRestartUnknown) {
    release();const auto evidence=credit();const auto original=fault();const auto path=provision("source");
    {FileJournal j(path.string());ContextualOutbox source(j,manifest(),central_id);ASSERT_EQ(source.context(global,evidence),Result::Accepted);ASSERT_EQ(source.submit(original),Result::Accepted);}
    FileJournal j(path.string());ContextualOutbox source(j,manifest(),central_id);ASSERT_EQ(source.ledger().find(original.key)->condition,Condition::Unknown);
    ASSERT_EQ(source.submit(original),Result::Accepted);EXPECT_EQ(source.pending(),1U);EXPECT_EQ(source.context(global,evidence),Result::Duplicate);
    EXPECT_EQ(source.pending(),0U);EXPECT_EQ(j.committed().size(),2U);EXPECT_EQ(source.ledger().find(original.key)->condition,Condition::Unknown);
    EXPECT_THROW((ContextualOutbox(j,manifest(31),central_id)),std::invalid_argument);
}
TEST_F(RemoteDiagnosticsContext, LocalSessionAttemptAndForeignEventsCannotBypassContext) {
    release();FileJournal j(provision("source").string());ContextualOutbox source(j,manifest(),central_id);
    for(unsigned variant=0;variant<6;++variant) {
        auto e=fault();
        switch(variant) {
        case 0:e.kind=Kind::Session;break;case 1:e.kind=Kind::Attempt;break;
        case 2:++e.id.producer;break;case 3:++e.id.run;break;case 4:++e.profile;break;case 5:e.session.epoch=0;break;
        }
        EXPECT_EQ(source.submit(e),Result::Invalid)<<variant;
    }
    EXPECT_EQ(source.pending(),0U);EXPECT_TRUE(j.committed().empty());EXPECT_TRUE(source.healthy());
}
TEST_F(RemoteDiagnosticsContext, CommitCapacityFailureNeverExportsTheUncommittedFault) {
    release();const auto evidence=credit();FileJournal j(provision("source",101,{1,1,1,1}).string());ContextualOutbox source(j,manifest(),central_id);
    ASSERT_EQ(source.submit(fault()),Result::Accepted);EXPECT_EQ(source.context(global,evidence),Result::Capacity);
    EXPECT_EQ(j.committed().size(),1U);EXPECT_EQ(source.pending(),1U);EXPECT_FALSE(source.healthy());EXPECT_FALSE(source.next());
}
TEST_F(RemoteDiagnosticsContext, MismatchedBufferedEnableAndQueueIdentityCannotBeSilentlyLost) {
    release();const auto evidence=credit();FileJournal j(provision("source").string());ContextualOutbox source(j,manifest(),central_id);
    auto wrong=fault();++wrong.session_enable.ns;ASSERT_EQ(source.submit(wrong),Result::Accepted);
    EXPECT_EQ(source.context(global,evidence),Result::Conflict);EXPECT_FALSE(source.healthy());EXPECT_EQ(source.pending(),1U);
    FileJournal other(provision("other",102).string());ContextualOutbox identity(other,manifest(),central_id);EventQueue q(run,30);
    EXPECT_FALSE(q.publish(fault(31)));EXPECT_EQ(identity.drain(q),0U);EXPECT_FALSE(identity.healthy());
}
TEST_F(RemoteDiagnosticsContext, UnboundRecoveryIsNeverBufferedForRetroactiveQualification) {
    release();const auto evidence=credit();FileJournal j(provision("source").string());ContextualOutbox source(j,manifest(),central_id);
    auto e=fault();e.kind=Kind::Actual;e.proof=Proof::Control;
    EXPECT_EQ(source.submit(e),Result::NotReady);e.kind=Kind::Passed;EXPECT_EQ(source.submit(e),Result::NotReady);
    EXPECT_EQ(source.pending(),0U);EXPECT_TRUE(j.committed().empty());EXPECT_TRUE(source.healthy());
    EXPECT_EQ(source.context(global,evidence),Result::Accepted);EXPECT_EQ(j.committed().size(),1U);EXPECT_TRUE(source.ledger().records().empty());
}
TEST_F(RemoteDiagnosticsContext, RestartRequiresActualAcceptedEvidenceAndReplaysOriginalBytesWithoutHealingUnknown) {
    release();const auto evidence=credit();const auto path=provision("source");const auto original=fault();
    {FileJournal j(path.string());ContextualOutbox out(j,manifest(),central_id);ASSERT_EQ(out.context(global,evidence),Result::Accepted);ASSERT_EQ(out.submit(original),Result::Accepted);}
    FileJournal j(path.string());ContextualOutbox out(j,manifest(),central_id);
    EXPECT_EQ(out.acknowledged(),0U);EXPECT_EQ(out.ledger().find(original.key)->condition,Condition::Unknown);
    auto proof=original;proof.id.sequence=2;proof.kind=Kind::Passed;
    EXPECT_EQ(out.submit(proof),Result::NotReady);EXPECT_EQ(out.restore({}),Result::Invalid);
    auto missing=evidence;missing.accepted.reset();EXPECT_EQ(out.restore(missing),Result::NotReady);
    auto wrong=evidence;wrong.accepted->plan.enable_ns++;EXPECT_EQ(out.restore(wrong),Result::Invalid);
    // Expired credit remains original historical evidence and cannot be renewed.
    central.now=evidence.accepted->expires_at_ns;EXPECT_FALSE(peers[0].credit.allows(*actors[0],central.now));
    EXPECT_EQ(out.restore(peers[0].credit.diagnostic_evidence()),Result::Duplicate);
    EXPECT_EQ(out.ledger().find(original.key)->condition,Condition::Unknown);EXPECT_EQ(out.ledger().find(original.key)->count,1U);
    ASSERT_TRUE(out.next());EXPECT_EQ(encode(std::get<wire::Data>(wire::decode(*out.next())).event),encode(global));
    EXPECT_EQ(j.committed().size(),2U);EXPECT_EQ(encode(j.committed()[1]),encode(original));EXPECT_FALSE(peers[0].credit.allows(*actors[0],central.now));
}
TEST_F(RemoteDiagnosticsContext, EmptyRestartCannotAdoptSessionFromLocalReadyOrAcceptedCreditAlone) {
    release();const auto evidence=credit();FileJournal j(provision("empty").string());ContextualOutbox out(j,manifest(),central_id);
    EXPECT_EQ(out.restore(evidence),Result::NotReady);EXPECT_TRUE(j.committed().empty());EXPECT_FALSE(out.next());
}
} // namespace
