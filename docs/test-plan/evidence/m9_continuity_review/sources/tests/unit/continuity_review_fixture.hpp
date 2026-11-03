#pragma once
#include "continuity_review.hpp"
#include "remote_diagnostics_context.hpp"
#include "startup_diagnostics.hpp"
#include "run_lease_issuer.hpp"
#include <gtest/gtest.h>
#include <deque>
#include <filesystem>
#include <fstream>

namespace continuity_fixture {
using namespace stratadrive;using namespace diagnostics;
constexpr std::uint64_t run=10,clock_id=99,issuer_id=20,restarted_source=(1ULL<<32)|30;
inline Stamp stamp(std::uint64_t at){return {Domain::Monotonic,clock_id,at,true,true};}
inline ControlContext context(std::uint64_t producer){return {run,producer,Domain::Monotonic,clock_id,1};}
struct Peer:session::ParticipantPort {
    std::uint64_t* now{};remote::RunLeaseGate gate;
    std::uint64_t now_ns() noexcept override{return *now;}
    session::Preparation prepare(const session::Plan&) noexcept override{return session::Preparation::Ready;}
    bool initialize(const session::Plan& p) noexcept override{return gate.bind(p,{clock_id,clock_id,0,0,true},*now);}
    void protect() noexcept override{}void service() noexcept override{}
};
struct Central:session::CoordinatorPort {
    std::uint64_t now{1000000000};std::deque<session::Control> controls;
    std::uint64_t now_ns() noexcept override{return now;}bool quiesce_central() noexcept override{return true;}
    bool send(const session::Control& c) noexcept override{controls.push_back(c);return true;}
    bool commit_central(central::CoordinatorSession) noexcept override{return true;}void protect_central() noexcept override{}
};
class ContinuityReviewTest:public ::testing::Test {
protected:
    Central central;session::SessionCoordinator coordinator{central};central::RunLeaseIssuer issuer{coordinator};
    std::array<Peer,8> peers;std::array<std::unique_ptr<session::SessionParticipant>,8> actors;
    EventQueue queue{run,issuer_id};StartupDiagnostics hook{queue,context(issuer_id),Component::Coordinator,8,true};
    std::filesystem::path root;Event global{},incident{};std::vector<Event> globals;
    std::unique_ptr<FileJournal> local;std::unique_ptr<Recorder> writer;
    std::array<std::unique_ptr<FileJournal>,2> sources,replicas;
    std::array<std::unique_ptr<ContextualOutbox>,2> out;
    const std::vector<StreamBinding> bindings{{500,restarted_source},{501,31}};
    ContinuityInspector inspector{context(99),bindings};
    void SetUp() override {
        char name[]="/tmp/stratadrive-continuity-XXXXXX";auto* p=mkdtemp(name);ASSERT_NE(p,nullptr);root=p;
        std::ofstream(root/"release.csv")<<"epoch,role,ns\n";
        std::ofstream(root/"credits.csv")<<"epoch,role,enable,source,expiry,captured\n";
        for(unsigned i=0;i<8;++i){peers[i].now=&central.now;actors[i]=std::make_unique<session::SessionParticipant>(static_cast<session::Role>(i),peers[i]);}
    }
    void TearDown() override {close_files();std::filesystem::remove_all(root);}
    void close_files(){for(auto& p:out)p.reset();for(auto& p:sources)p.reset();for(auto& p:replicas)p.reset();writer.reset();local.reset();}
    void accepted(const session::Ack& ack){ASSERT_EQ(coordinator.receive(ack,central.now),session::AckResult::Accepted);if(ack.accepted && ack.phase==session::Phase::Release)std::ofstream(root/"release.csv",std::ios::app)<<ack.plan.epoch<<','<<static_cast<unsigned>(ack.role)<<','<<central.now<<'\n';}
    void pump(){while(!central.controls.empty()){const auto c=central.controls.front();central.controls.pop_front();if(const auto ack=actors[static_cast<unsigned>(c.role)]->receive(c,central.now))accepted(*ack);}}
    void release(unsigned epoch){
        if(coordinator.run_enabled()){coordinator.cancel(central.now);pump();}
        ASSERT_TRUE(coordinator.begin(epoch,central.now));hook.attempt(coordinator.plan());pump();central.now=coordinator.plan().enable_ns;
        for(auto& a:actors){const auto ack=a->poll(central.now);ASSERT_TRUE(ack);accepted(*ack);}pump();ASSERT_TRUE(coordinator.run_enabled());
        hook.observe(coordinator.fault_observation(),coordinator.success_observation(),true,true,central.now);Event e;
        while(queue.pop(e)){globals.push_back(e);if(e.kind==Kind::Session)global=e;}ASSERT_EQ(global.kind,Kind::Session);
    }
    remote::RunLeaseEvidence credit(unsigned role){
        const auto lease=issuer.issue(++central.now);EXPECT_TRUE(lease);if(!lease)return {};
        const auto packet=remote::encode_owner_message({session::Role::CentralIngress,static_cast<session::Role>(role),clock_id,*lease});EXPECT_TRUE(packet);if(!packet)return {};
        const auto decoded=remote::decode_owner_message(packet->bytes.data(),packet->size);EXPECT_TRUE(decoded);if(!decoded)return {};
        EXPECT_TRUE(peers[role].gate.receive(std::get<remote::RunLease>(decoded->payload),clock_id,*actors[role],central.now));
        std::ofstream(root/"credits.csv",std::ios::app)<<lease->plan.epoch<<','<<role<<','<<lease->plan.enable_ns<<','<<lease->source_time_ns<<','<<lease->expires_at_ns<<','<<central.now<<'\n';
        return peers[role].gate.diagnostic_evidence();
    }
    void transfer(){
        for(unsigned i=0;i<2;++i){Inbox receiver(*replicas[i]);while(const auto bytes=out[i]->next()){const auto r=receiver.receive(*bytes);ASSERT_TRUE(r.ack);ASSERT_EQ(out[i]->acknowledge(*r.ack),Result::Accepted);}
            for(const auto& e:sources[i]->committed())ASSERT_TRUE(writer->record(std::get<Event>(e)).durable);
        }
    }
    void baseline(){
        release(2);FileJournal::initialize((root/"case").string(),9000,{},4);local=std::make_unique<FileJournal>((root/"case").string());writer=std::make_unique<Recorder>(*local);
        for(const auto& e:globals){ASSERT_TRUE(writer->record(e).durable);}
        for(unsigned i=0;i<2;++i){for(const auto name:{"source-","replica-"})FileJournal::initialize((root/(name+std::to_string(i))).string(),bindings[i].stream,{},3);
            sources[i]=std::make_unique<FileJournal>((root/("source-"+std::to_string(i))).string());replicas[i]=std::make_unique<FileJournal>((root/("replica-"+std::to_string(i))).string());
            out[i]=std::make_unique<ContextualOutbox>(*sources[i],context(bindings[i].producer),issuer_id);ASSERT_EQ(out[i]->context(global,credit(i)),Result::Accepted);
        }
        incident=continuity_fault(context(restarted_source),30,2,Component::Front,2,global.session_enable.ns,global.session_enable.ns-1,central.now);
        ASSERT_EQ(out[0]->submit(incident),Result::Accepted);transfer();ASSERT_TRUE(writer->ledger().unmapped());
    }
    void fresh(unsigned epoch=3){release(epoch);for(const auto& e:globals){if(e.session.epoch==epoch){ASSERT_TRUE(writer->record(e).durable);}}
        for(unsigned i=0;i<2;++i){ASSERT_EQ(out[i]->context(global,credit(i)),Result::Accepted);}
        transfer();}
    ServiceEvidence evidence(){const auto now=stamp(++central.now);return {now,global.session_enable,now,now,now,0,0,100000,true,true};}
    std::vector<StreamState> streams(){return {{sources[0].get(),replicas[0].get(),out[0]->acknowledged(),0,{}},{sources[1].get(),replicas[1].get(),out[1]->acknowledged(),0,{}}};}
    ContinuityPlan plan(std::uint64_t sequence=1){auto result=inspector.prepare(writer->ledger(),incident.id,global,streams(),ContinuityDisposition::AcceptUnknownHistory,evidence(),sequence);EXPECT_EQ(result.blocked,ReviewBlock::None);EXPECT_TRUE(result.plan);return result.plan.value_or(ContinuityPlan{});}
    void approve(const ContinuityPlan& p){ASSERT_TRUE(writer->record(p.proof).durable);ASSERT_TRUE(writer->review(p.review).durable);ASSERT_TRUE(writer->record(p.passed).durable);}
    Clear clear_request(){Clear c;c.id={run,100,1};c.session=global.session;c.evidence=evidence();const auto* r=writer->ledger().find(incident.key);c.targets={{incident.key,r?r->revision:0}};return c;}
};
} // namespace continuity_fixture
