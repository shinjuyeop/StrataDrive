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
class NativeDiagnosticsSil : public ::testing::Test {
protected:
    std::filesystem::path directory;
    void SetUp() override { char p[]="/tmp/stratadrive-native-diag-XXXXXX"; auto* s=mkdtemp(p); ASSERT_NE(s,nullptr); directory=s; }
    void TearDown() override { std::filesystem::remove_all(directory); }
    simulation::M4Config config() {
        simulation::M4Config c; c.speed_loop=true; c.renewal=central::CommandRenewal::Host10ms; c.native_diagnostics_run=4001;
        c.scenario=simulation::M4Scenario::Fault; c.faults={simulation::parse_m4_fault("owner:pause:central:10000:200:0")};
        c.duration_ns=24000*kMs; c.recovery_ns=20000*kMs; c.replace_links=true; return c;
    }
    void save(const char* name,const simulation::M4Config& c,const simulation::M4Result& r,const diagnostics::Ledger& ledger,const std::string& native="") {
        if(const auto* target=std::getenv("STRATADRIVE_M9_NATIVE_EVIDENCE")) {
            const auto out=std::filesystem::path(target)/name; ASSERT_FALSE(std::filesystem::exists(out)); std::filesystem::create_directories(out);
            simulation::write_m4_result(c,r,out.string()); std::filesystem::copy(directory/"store",out/"store",std::filesystem::copy_options::recursive);
            std::ofstream(out/"native.csv")<<native;
            std::ofstream records(out/"records.csv"); records<<"code,component,monitor,subject,condition,count,generation,cleared\n";
            for(const auto& d:ledger.records()) records<<static_cast<unsigned>(d.key.code)<<','<<d.key.component<<','<<d.key.monitor<<','<<d.key.subject<<','<<static_cast<unsigned>(d.condition)<<','<<d.count<<','<<d.generation<<','<<d.cleared<<'\n';
            std::ofstream physical(out/"physical.csv"); physical<<"source_ns,epoch,model_epoch,model_sequence,distance_m,energy_j,balance_j,torque_nm,pressure_pa,gate\n"<<std::setprecision(17);
            for(const auto& x:r.trace) physical<<x.source_ns<<','<<x.epoch<<','<<x.model_epoch<<','<<x.model_sequence<<','<<x.distance_m<<','<<x.energy_j<<','<<x.vehicle_balance_j<<','<<x.torque_nm<<','<<x.pressure_pa<<','<<x.run_gate<<'\n';
        }
    }
};
TEST_F(NativeDiagnosticsSil, CentralPauseRecordsOriginalGatewayCauseAndActualNewEpochDispatchRecovery) {
    const auto c=config(); Network n(c);
    diagnostics::FileJournal::initialize((directory/"store").string(),4001,{},2);
    diagnostics::FileJournal journal((directory/"store").string()); diagnostics::Recorder writer(journal);
    std::vector<diagnostics::Event> events; std::ostringstream native;
    native<<"kind,component,monitor,epoch,enable_ns,observed_ns,reason,propagation,writes,root_epoch,root_sequence,root_source_ns,root_expiry_ns,dependency_ns,valid_until_ns\n";
    bool latched=false,recovered=false;
    for(std::uint64_t t=0;t<=c.duration_ns;t+=kIoPoll) {
        n.clock.logical=kLogicalStart+t;
        if(t==c.recovery_ns) n.replace_joined_links();
        if(t%kMs==0) n.step(8);
        for(std::size_t owner=0;owner<8;++owner) n.step(owner);
        const auto drain=[&](diagnostics::EventQueue& q) {
            diagnostics::Event e; while(q.pop(e)) {
                const auto receipt=writer.record(e); EXPECT_EQ(receipt.result,diagnostics::Result::Accepted); EXPECT_TRUE(receipt.durable); events.push_back(e);
                if((e.kind==diagnostics::Kind::Fault || e.kind==diagnostics::Kind::Passed) && e.key.monitor>=6 && e.key.monitor<=7) {
                    const auto& z=*n.zone_owners[e.key.component==7?0:1]; const bool fault=e.kind==diagnostics::Kind::Fault;
                    const auto& o=e.key.monitor==6?(fault?z.command_gateway().fault_observation():z.command_gateway().success_observation()):
                        (fault?z.power_gateway()->fault_observation():z.power_gateway()->success_observation());
                    EXPECT_TRUE(o); if(o) {
                        const auto root=o->root.value_or(NativeRoot{});
                        native<<static_cast<unsigned>(e.kind)<<','<<e.key.component<<','<<e.key.monitor<<','<<o->epoch<<','<<o->enable_ns<<','<<o->observed_ns<<','<<o->reason<<','<<o->propagation<<','<<o->writes<<','<<root.epoch<<','<<root.sequence<<','<<root.source_ns<<','<<root.expiry_ns<<','<<root.dependency_ns<<','<<o->valid_until_ns.value_or(0)<<'\n';
                    }
                }
            }
            EXPECT_EQ(q.health().dropped,0U); EXPECT_FALSE(q.health().identity_error);
        };
        drain(*n.diagnostic_queue); for(auto& q:n.native_diagnostic_queues) drain(*q);
        if(t==13000*kMs) {
            ASSERT_FALSE(writer.ledger().records().empty()); EXPECT_FALSE(n.gate.allows(1));
            for(const auto& d:writer.ledger().records()) { EXPECT_EQ(d.condition,diagnostics::Condition::Failed); }
            latched=true;
        }
        if(t==23000*kMs) {
            ASSERT_EQ(n.active_epoch,2U); EXPECT_TRUE(n.gate.allows(2));
            for(const auto& d:writer.ledger().records()) { EXPECT_EQ(d.condition,diagnostics::Condition::Passed); EXPECT_FALSE(d.cleared); EXPECT_EQ(d.count,1U); } recovered=true;
        }
    }
    auto r=n.finish(); r.diagnostic_events=events;
    ASSERT_TRUE(r.passed)<<r.reason; EXPECT_TRUE(r.physical_ok); EXPECT_TRUE(r.model_preserved); EXPECT_TRUE(latched&&recovered);
    ASSERT_FALSE(writer.ledger().records().empty());
    for(const auto& d:writer.ledger().records()) { EXPECT_EQ(d.key.monitor,6U); EXPECT_EQ(d.key.code,diagnostics::Code::CommandLoss); }
    for(const auto& e:events) if(e.kind==diagnostics::Kind::Fault) {
        EXPECT_TRUE(e.id.producer==30 || e.id.producer==31); EXPECT_EQ(e.session.epoch,1U); EXPECT_FALSE(e.cause_unknown);
        EXPECT_TRUE(e.command.present); EXPECT_EQ(e.times[1].ns,e.command.expiry.ns); EXPECT_GE(e.times[2].ns,e.times[1].ns);
    }
    for(const auto& x:r.trace) if(x.elapsed_ns>=10400*kMs && x.elapsed_ns<20000*kMs) { EXPECT_FALSE(x.run_gate); EXPECT_LE(std::abs(x.torque_nm),1); EXPECT_GE(x.pressure_pa,1000000); }
    save("central-pause",c,r,writer.ledger(),native.str());
}
TEST_F(NativeDiagnosticsSil, HookOnOffPreservesPhysicalAndAuthoritySamples) {
    auto c=config(); c.duration_ns=13000*kMs; c.recovery_ns=0;
    const auto on=simulation::run_m4_async(c); c.native_diagnostics_run=0; const auto off=simulation::run_m4_async(c);
    ASSERT_TRUE(on.passed)<<on.reason; ASSERT_TRUE(off.passed)<<off.reason; ASSERT_EQ(on.trace.size(),off.trace.size());
    EXPECT_EQ(on.first_fault_ns,off.first_fault_ns); EXPECT_EQ(on.all_protected_ns,off.all_protected_ns);
    for(std::size_t i=0;i<on.trace.size();++i) {
        const auto& a=on.trace[i]; const auto& b=off.trace[i];
        EXPECT_EQ(a.epoch,b.epoch); EXPECT_EQ(a.run_gate,b.run_gate); EXPECT_EQ(a.model_sequence,b.model_sequence);
        EXPECT_DOUBLE_EQ(a.torque_nm,b.torque_nm); EXPECT_DOUBLE_EQ(a.pressure_pa,b.pressure_pa); EXPECT_DOUBLE_EQ(a.distance_m,b.distance_m);
        EXPECT_DOUBLE_EQ(a.energy_j,b.energy_j); EXPECT_DOUBLE_EQ(a.soc,b.soc);
    }
}
TEST_F(NativeDiagnosticsSil, NormalFullProfileHasNoFalseRootAndRejectsInvalidConfiguration) {
    auto c=config(); c.scenario=simulation::M4Scenario::Normal; c.faults={}; c.recovery_ns=0; c.duration_ns=92000*kMs;
    const auto r=simulation::run_m4_async(c); ASSERT_TRUE(r.passed)<<r.reason; EXPECT_TRUE(r.diagnostics_complete);
    diagnostics::FileJournal::initialize((directory/"store").string(),4001,{},2); diagnostics::FileJournal j((directory/"store").string()); diagnostics::Recorder w(j);
    for(const auto& e:r.diagnostic_events) ASSERT_TRUE(w.record(e).durable);
    EXPECT_TRUE(w.ledger().records().empty()); EXPECT_EQ(r.speed_trace.size(),4350U); save("normal",c,r,w.ledger());
    c.wall_time=true; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
    c.wall_time=false; c.diagnostics_run=999; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
    c.diagnostics_run=0; c.owner_diagnostics_run=999; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
    c.owner_diagnostics_run=0; c.speed_loop=false; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
}
} // namespace
