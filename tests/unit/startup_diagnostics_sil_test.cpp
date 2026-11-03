#include "m4_owner_network.hpp"
#include "diagnostics_journal.hpp"
#include <gtest/gtest.h>
#include <filesystem>
#include <fstream>
#include <cstdlib>
#include <iomanip>
#include <sstream>

namespace {
using namespace stratadrive;
using namespace simulation::m4_detail;
class StartupDiagnosticsSil : public ::testing::TestWithParam<const char*> {
protected:
    std::filesystem::path dir;
    void SetUp() override { char p[]="/tmp/stratadrive-startup-XXXXXX"; auto* s=mkdtemp(p); ASSERT_NE(s,nullptr); dir=s; }
    void TearDown() override { std::filesystem::remove_all(dir); }
    simulation::M4Config config(bool recover=true) {
        simulation::M4Config c; c.scenario=simulation::M4Scenario::Fault; c.speed_loop=true; c.renewal=central::CommandRenewal::Host10ms;
        c.startup_diagnostics_run=6001; c.duration_ns=6000*kMs; c.recovery_ns=recover?3000*kMs:0; c.replace_links=recover;
        c.faults={simulation::parse_m4_fault(std::string("session-ack:drop:drive:0:2500:0:")+GetParam())}; return c;
    }
    void save(const simulation::M4Config& c,const simulation::M4Result& r,const diagnostics::Ledger& ledger,const std::string& source) {
        if(const auto* target=std::getenv("STRATADRIVE_M9_STARTUP_EVIDENCE")) {
            const auto out=std::filesystem::path(target)/GetParam(); ASSERT_FALSE(std::filesystem::exists(out)); std::filesystem::create_directories(out);
            simulation::write_m4_result(c,r,out.string()); std::filesystem::copy(dir/"store",out/"store",std::filesystem::copy_options::recursive);
            std::ofstream(out/"startup-source.csv")<<source;
            std::ofstream records(out/"records.csv"); records<<"code,component,monitor,subject,condition,count,generation,cleared\n";
            for(const auto& d:ledger.records()) records<<static_cast<unsigned>(d.key.code)<<','<<d.key.component<<','<<d.key.monitor<<','<<d.key.subject<<','<<static_cast<unsigned>(d.condition)<<','<<d.count<<','<<d.generation<<','<<d.cleared<<'\n';
            std::ofstream physical(out/"physical.csv"); physical<<"source_ns,epoch,model_epoch,model_sequence,speed_mps,distance_m,energy_j,balance_j,bus_v,contacts,torque_nm,pressure_pa,gate\n"<<std::setprecision(17);
            for(const auto& x:r.trace) physical<<x.source_ns<<','<<x.epoch<<','<<x.model_epoch<<','<<x.model_sequence<<','<<x.speed_mps<<','<<x.distance_m<<','<<x.energy_j<<','<<x.vehicle_balance_j<<','<<x.bus_v<<','<<x.contacts<<','<<x.torque_nm<<','<<x.pressure_pa<<','<<x.run_gate<<'\n';
        }
    }
};
TEST_P(StartupDiagnosticsSil, FailedAttemptIsDurableWithoutReleaseAndOnlyFullNewHandshakeQualifies) {
    const auto c=config(); Network n(c); const auto expected=std::string(GetParam())=="release"?1U:9U;
    diagnostics::FileJournal::initialize((dir/"store").string(),6001,{},3);
    diagnostics::FileJournal journal((dir/"store").string()); diagnostics::Recorder writer(journal);
    std::vector<diagnostics::Event> events; std::ostringstream source;
    source<<"kind,producer,event_sequence,epoch,requested_ns,enable_ns,prepare_deadline_ns,commit_deadline_ns,observed_ns,previous_ns,deadline_ns,state,reason,accepted_roles\n";
    bool failed=false,new_attempt=false;
    for(std::uint64_t t=0;t<=c.duration_ns;t+=kIoPoll) {
        n.clock.logical=kLogicalStart+t; if(t==c.recovery_ns) n.replace_joined_links();
        if(t%kMs==0) { n.step(8); }
        for(std::size_t owner=0;owner<8;++owner) n.step(owner);
        const auto drain=[&](diagnostics::EventQueue& q) {
            diagnostics::Event e; while(q.pop(e)) {
                const auto receipt=writer.record(e); EXPECT_EQ(receipt.result,diagnostics::Result::Accepted); EXPECT_TRUE(receipt.durable); events.push_back(e);
                if(e.kind==diagnostics::Kind::Attempt && e.session.epoch==2) {
                    ASSERT_EQ(writer.ledger().records().size(),expected);
                    for(const auto& r:writer.ledger().records()) { EXPECT_EQ(r.condition,diagnostics::Condition::Unknown); } new_attempt=true;
                }
                if(e.key.monitor==10 || e.key.monitor==11) {
                    if(e.kind!=diagnostics::Kind::Fault && e.kind!=diagnostics::Kind::Passed) continue;
                    const auto& o=e.key.monitor==10?(e.kind==diagnostics::Kind::Fault?n.startup.fault_observation():n.startup.success_observation()):
                        (e.kind==diagnostics::Kind::Fault?n.sessions[e.key.subject-1]->fault_observation():n.sessions[e.key.subject-1]->success_observation());
                    ASSERT_TRUE(o); const auto& p=o->plan;
                    source<<static_cast<unsigned>(e.kind)<<','<<e.id.producer<<','<<e.id.sequence<<','<<p.epoch<<','<<p.requested_ns<<','<<p.enable_ns<<','<<p.prepare_deadline_ns<<','<<p.commit_deadline_ns<<','<<o->observed_ns<<','<<o->previous_ns<<','<<o->deadline_ns<<','<<o->state<<','<<o->reason<<','<<o->accepted_roles<<'\n';
                }
            }
            EXPECT_EQ(q.health().dropped,0U); EXPECT_FALSE(q.health().identity_error);
        };
        drain(*n.diagnostic_queue); for(auto& q:n.startup_diagnostic_queues) drain(*q); for(auto& q:n.native_diagnostic_queues) drain(*q);
        if(t==2600*kMs) {
            ASSERT_EQ(writer.ledger().records().size(),expected); EXPECT_EQ(n.active_epoch,0U); EXPECT_FALSE(n.gate.epoch());
            for(const auto& r:writer.ledger().records()) { EXPECT_EQ(r.condition,diagnostics::Condition::Failed); EXPECT_EQ(r.key.code,diagnostics::Code::Startup); }
            EXPECT_FALSE(std::any_of(events.begin(),events.end(),[](const auto& e){return e.kind==diagnostics::Kind::Session || e.kind==diagnostics::Kind::Passed;})); failed=true;
        }
    }
    auto r=n.finish(); r.diagnostic_events=events; ASSERT_TRUE(r.passed)<<r.reason; EXPECT_TRUE(failed&&new_attempt); EXPECT_TRUE(r.diagnostics_complete); EXPECT_TRUE(r.model_preserved);
    ASSERT_EQ(writer.ledger().records().size(),expected);
    for(const auto& d:writer.ledger().records()) { EXPECT_EQ(d.condition,diagnostics::Condition::Passed); EXPECT_EQ(d.count,1U); EXPECT_EQ(d.generation,1U); EXPECT_FALSE(d.cleared); }
    EXPECT_EQ(std::count_if(events.begin(),events.end(),[](const auto& e){return e.kind==diagnostics::Kind::Attempt;}),2);
    EXPECT_EQ(std::count_if(events.begin(),events.end(),[](const auto& e){return e.kind==diagnostics::Kind::Session;}),1);
    for(const auto& x:r.trace) if(x.elapsed_ns<3000*kMs) { EXPECT_FALSE(x.run_gate); EXPECT_LE(std::abs(x.speed_mps),.01); EXPECT_EQ(x.contacts,0U); EXPECT_LE(x.bus_v,30); }
    save(c,r,writer.ledger(),source.str());
}
TEST_P(StartupDiagnosticsSil, RestoredAckWithoutNewAttemptCannotHealAndHookLeavesPhysicalHistoryUnchanged) {
    auto c=config(false); const auto on=simulation::run_m4_async(c); c.startup_diagnostics_run=0; const auto off=simulation::run_m4_async(c);
    ASSERT_TRUE(on.passed)<<on.reason; ASSERT_TRUE(off.passed)<<off.reason; diagnostics::Ledger ledger;
    for(const auto& e:on.diagnostic_events) { ASSERT_EQ(ledger.record(e),diagnostics::Result::Accepted); EXPECT_NE(e.kind,diagnostics::Kind::Session); EXPECT_NE(e.kind,diagnostics::Kind::Passed); }
    ASSERT_FALSE(ledger.records().empty()); for(const auto& d:ledger.records()) { EXPECT_EQ(d.condition,diagnostics::Condition::Failed); }
    ASSERT_EQ(on.trace.size(),off.trace.size()); EXPECT_EQ(on.first_fault_ns,off.first_fault_ns);
    for(std::size_t i=0;i<on.trace.size();++i) {
        const auto& a=on.trace[i]; const auto& b=off.trace[i]; EXPECT_EQ(a.epoch,b.epoch); EXPECT_EQ(a.run_gate,b.run_gate); EXPECT_EQ(a.model_sequence,b.model_sequence); EXPECT_EQ(a.contacts,b.contacts);
        EXPECT_DOUBLE_EQ(a.speed_mps,b.speed_mps); EXPECT_DOUBLE_EQ(a.distance_m,b.distance_m); EXPECT_DOUBLE_EQ(a.energy_j,b.energy_j); EXPECT_DOUBLE_EQ(a.soc,b.soc); EXPECT_DOUBLE_EQ(a.bus_v,b.bus_v);
        EXPECT_DOUBLE_EQ(a.torque_nm,b.torque_nm); EXPECT_DOUBLE_EQ(a.pressure_pa,b.pressure_pa); EXPECT_DOUBLE_EQ(a.vehicle_balance_j,b.vehicle_balance_j);
    }
}
INSTANTIATE_TEST_SUITE_P(Phases,StartupDiagnosticsSil,::testing::Values("prepare","init","release"));
TEST(StartupDiagnosticsConfiguration, RejectsWallAndMixedCollectors) {
    simulation::M4Config c; c.startup_diagnostics_run=6001; c.speed_loop=true; c.renewal=central::CommandRenewal::Host10ms; c.wall_time=true;
    EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
    c.wall_time=false; c.native_diagnostics_run=6001; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
}
TEST(StartupDiagnosticsConfiguration, NormalProfileHasOneAttemptOneReleaseAndZeroFalseDtc) {
    simulation::M4Config c; c.startup_diagnostics_run=6001; c.speed_loop=true; c.renewal=central::CommandRenewal::Host10ms; c.duration_ns=92000*kMs;
    const auto r=simulation::run_m4_async(c); ASSERT_TRUE(r.passed)<<r.reason; diagnostics::Ledger ledger;
    for(const auto& e:r.diagnostic_events) { ASSERT_EQ(ledger.record(e),diagnostics::Result::Accepted); }
    EXPECT_EQ(r.speed_trace.size(),4350U); EXPECT_TRUE(ledger.records().empty());
    EXPECT_EQ(std::count_if(r.diagnostic_events.begin(),r.diagnostic_events.end(),[](const auto& e){return e.kind==diagnostics::Kind::Attempt;}),1);
    EXPECT_EQ(std::count_if(r.diagnostic_events.begin(),r.diagnostic_events.end(),[](const auto& e){return e.kind==diagnostics::Kind::Session && e.received_roles==255;}),1);
}
} // namespace
