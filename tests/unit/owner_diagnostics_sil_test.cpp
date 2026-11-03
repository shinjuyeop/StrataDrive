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
class OwnerDiagnosticsSil : public ::testing::Test {
protected:
    std::filesystem::path directory;
    void SetUp() override { char path[]="/tmp/stratadrive-owner-diag-XXXXXX"; const auto* p=mkdtemp(path); ASSERT_NE(p,nullptr); directory=p; }
    void TearDown() override { std::filesystem::remove_all(directory); }
    simulation::M4Config config() {
        simulation::M4Config c; c.speed_loop=true; c.renewal=central::CommandRenewal::Host10ms; c.owner_diagnostics_run=3001;
        c.scenario=simulation::M4Scenario::Fault; c.faults={simulation::parse_m4_fault("owner:pause:central:10000:200:0"),
            simulation::parse_m4_fault("owner:pause:front:10000:200:0"),simulation::parse_m4_fault("owner:pause:rear:10000:200:0")};
        c.duration_ns=24000*kMs; c.recovery_ns=20000*kMs; c.replace_links=true; return c;
    }
    void save(const char* name,const simulation::M4Config& c,const simulation::M4Result& r,const diagnostics::Ledger& ledger,
        const std::string& native="",const std::string& zones="") {
        if(const auto* target=std::getenv("STRATADRIVE_M9_OWNER_EVIDENCE")) {
            const auto out=std::filesystem::path(target)/name; ASSERT_FALSE(std::filesystem::exists(out)); std::filesystem::create_directories(out);
            simulation::write_m4_result(c,r,out.string()); std::filesystem::copy(directory/"store",out/"store",std::filesystem::copy_options::recursive);
            if(!native.empty()) std::ofstream(out/"native-authority.csv")<<native;
            if(!zones.empty()) std::ofstream(out/"native-zone.csv")<<zones;
            std::ofstream records(out/"records.csv"); records<<"code,component,monitor,subject,condition,count,generation,cleared\n";
            for(const auto& d:ledger.records()) records<<static_cast<unsigned>(d.key.code)<<','<<d.key.component<<','<<d.key.monitor<<','<<d.key.subject<<','<<static_cast<unsigned>(d.condition)<<','<<d.count<<','<<d.generation<<','<<d.cleared<<'\n';
            std::ofstream physical(out/"physical.csv"); physical<<"source_ns,epoch,model_epoch,model_sequence,distance_m,energy_j,balance_j,torque_nm,pressure_pa,gate\n"<<std::setprecision(17);
            for(const auto& x:r.trace) physical<<x.source_ns<<','<<x.epoch<<','<<x.model_epoch<<','<<x.model_sequence<<','<<x.distance_m<<','<<x.energy_j<<','<<x.vehicle_balance_j<<','<<x.torque_nm<<','<<x.pressure_pa<<','<<x.run_gate<<'\n';
        }
    }
};
TEST_F(OwnerDiagnosticsSil, UpstreamOwnersPauseLetsRealLeafAuthorityExpireAndNewInitQualifiesRecovery) {
    const auto c=config(); Network n(c);
    diagnostics::FileJournal::initialize((directory/"store").string(),3001);
    diagnostics::FileJournal journal((directory/"store").string()); diagnostics::Recorder writer(journal);
    std::vector<diagnostics::Event> collected; bool paused_protection=false,still_latched=false,passed=false;
    std::array<std::optional<transport::LeafAuthorityObservation>,3> original_expiry;
    std::ostringstream native,zones;
    native<<"kind,component,epoch,enable_ns,observed_ns,independent,parent_epoch,parent_sequence,parent_source_ns,parent_expiry_ns,oldest_input_ns,command_expiry_ns,token,sent_ns,envelope_deadline_ns\n";
    zones<<"kind,component,epoch,enable_ns,observed_ns,fault,healthy_mask,violation_ns\n";
    for(std::uint64_t t=0;t<=c.duration_ns;t+=kIoPoll) {
        n.clock.logical=kLogicalStart+t;
        if(c.replace_links && t==c.recovery_ns) n.replace_joined_links();
        if(t%kMs==0) n.step(8);
        for(std::size_t owner=0;owner<8;++owner) n.step(owner);
        const auto drain=[&](diagnostics::EventQueue& q) {
            diagnostics::Event e; while(q.pop(e)) {
                const auto receipt=writer.record(e); EXPECT_EQ(receipt.result,diagnostics::Result::Accepted); EXPECT_TRUE(receipt.durable); collected.push_back(e);
                if(e.kind==diagnostics::Kind::Fault || e.kind==diagnostics::Kind::Passed) {
                    const bool fault=e.kind==diagnostics::Kind::Fault;
                    if(e.key.monitor==5) {
                        const auto i=e.key.component==9?0U:e.key.component==5?1U:2U;
                        const auto& o=fault?n.leaf_owners[i]->expiry_observation():n.leaf_owners[i]->command_success_observation();
                        EXPECT_TRUE(o);
                        if(o && o->accepted.command) {
                            const auto& a=o->accepted; const auto& ctx=*a.command; const auto& p=ctx.parent;
                            native<<static_cast<unsigned>(e.kind)<<','<<e.key.component<<','<<o->epoch<<','<<o->enable_ns<<','<<o->observed_ns<<','<<o->independently_expired<<','
                                <<p.epoch<<','<<p.sequence<<','<<p.source_time_ns<<','<<p.expires_at_ns<<','<<ctx.oldest_input_time_ns<<','<<ctx.expires_at_ns<<','<<a.token<<','<<a.sent_ns<<','<<a.deadline_ns<<'\n';
                        }
                    } else if(e.key.monitor==4) {
                        const auto& m=n.zone_owners[e.key.component==7?0:1]->feedback_monitor();
                        const auto& o=fault?m.fault_observation():m.success_observation(); EXPECT_TRUE(o);
                        if(o) zones<<static_cast<unsigned>(e.kind)<<','<<e.key.component<<','<<o->epoch<<','<<o->enable_ns<<','<<o->observed_ns<<','<<static_cast<unsigned>(o->fault)<<','<<o->healthy_mask<<','<<o->violation_ns.value_or(0)<<'\n';
                    }
                }
            }
            EXPECT_EQ(q.health().dropped,0U); EXPECT_FALSE(q.health().identity_error);
        };
        drain(*n.diagnostic_queue); for(auto& q:n.owner_diagnostic_queues) drain(*q);
        if(t==10090*kMs) {
            EXPECT_TRUE(n.paused[7]); EXPECT_FALSE(n.gate.allows(1));
            ASSERT_FALSE(writer.ledger().records().empty())<<"zone faults "
                <<static_cast<int>(n.zone_owners[0]->feedback_monitor().fault())<<'/'<<static_cast<int>(n.zone_owners[1]->feedback_monitor().fault())
                <<" leaf faults "<<n.leaf_owners[0]->fault_code()<<'/'<<n.leaf_owners[1]->fault_code()<<'/'<<n.leaf_owners[2]->fault_code()
                <<" expiry "<<static_cast<bool>(n.leaf_owners[0]->expiry_observation())<<'/'
                <<(n.leaf_owners[0]->expiry_observation()?n.leaf_owners[0]->expiry_observation()->independently_expired:false);
            paused_protection=true;
            for(const auto& d:writer.ledger().records()) EXPECT_EQ(d.condition,diagnostics::Condition::Failed);
        }
        if(t==11000*kMs) {
            EXPECT_FALSE(n.paused[7]); EXPECT_FALSE(n.gate.allows(1)); still_latched=true;
            for(const auto& d:writer.ledger().records()) EXPECT_EQ(d.condition,diagnostics::Condition::Failed);
            for(std::size_t i=0;i<3;++i) original_expiry[i]=n.leaf_owners[i]->expiry_observation();
        }
        if(t==23000*kMs) {
            EXPECT_EQ(n.active_epoch,2U); EXPECT_TRUE(n.core.decision().normal_armed); EXPECT_TRUE(n.gate.allows(2));
            for(const auto& d:writer.ledger().records()) { EXPECT_EQ(d.condition,diagnostics::Condition::Passed); EXPECT_FALSE(d.cleared); EXPECT_EQ(d.count,1U); } passed=true;
            const std::array<diagnostics::Component,3> actors{diagnostics::Component::Steering,diagnostics::Component::Brake,diagnostics::Component::Drive};
            for(std::size_t i=0;i<3;++i) {
                ASSERT_TRUE(original_expiry[i]); ASSERT_TRUE(original_expiry[i]->independently_expired);
                const auto& success=n.leaf_owners[i]->command_success_observation(); ASSERT_TRUE(success);
                for(unsigned variant=0;variant<8;++variant) {
                    diagnostics::EventQueue q(3001,100+i);
                    diagnostics::OwnerDiagnostics observer(q,{3001,100+i,diagnostics::Domain::Simulation,3001,1},actors[i]);
                    ASSERT_TRUE(observer.start_session(1,original_expiry[i]->enable_ns));
                    observer.leaf(original_expiry[i],std::nullopt,false,false,std::nullopt,n.clock.logical);
                    ASSERT_TRUE(observer.start_session(2,success->enable_ns));
                    auto bad=success; auto now=n.clock.logical; bool healthy=true,gate=true;
                    switch(variant) {
                    case 0:gate=false;break;
                    case 1:healthy=false;break;
                    case 2:bad.reset();break;
                    case 3:bad->epoch=1;break;
                    case 4:++bad->enable_ns;break;
                    case 5:bad->accepted.command->expires_at_ns=now;break;
                    case 6:bad->accepted.command->oldest_input_time_ns=now-71*kMs;break;
                    case 7:now=bad->observed_ns+31*kMs;break;
                    }
                    observer.leaf(std::nullopt,bad,healthy,gate,std::nullopt,now);
                    diagnostics::Event e; unsigned passes=0; while(q.pop(e)) if(e.kind==diagnostics::Kind::Passed) ++passes;
                    EXPECT_EQ(passes,0U)<<"actor="<<i<<" variant="<<variant;
                    observer.leaf(std::nullopt,success,true,true,std::nullopt,n.clock.logical);
                    while(q.pop(e)) if(e.kind==diagnostics::Kind::Passed) ++passes;
                    EXPECT_EQ(passes,1U);
                }
            }
        }
    }
    auto r=n.finish(); r.diagnostic_events=collected;
    ASSERT_TRUE(r.passed)<<r.reason; ASSERT_TRUE(r.diagnostics_complete); ASSERT_TRUE(r.physical_ok); EXPECT_TRUE(r.model_preserved);
    EXPECT_TRUE(paused_protection&&still_latched&&passed); EXPECT_TRUE(writer.ledger().complete());
    ASSERT_FALSE(writer.ledger().records().empty());
    ASSERT_EQ(writer.ledger().records().size(),5U);
    for(const auto& d:writer.ledger().records()) {
        EXPECT_TRUE(d.key.code==diagnostics::Code::CommandLoss || d.key.code==diagnostics::Code::Deadline);
        EXPECT_EQ(d.key.monitor,d.key.code==diagnostics::Code::CommandLoss?5U:4U);
    }
    for(const auto& e:collected) if(e.kind==diagnostics::Kind::Fault) {
        EXPECT_NE(e.id.producer,7U); EXPECT_EQ(e.session.epoch,1U);
        if(e.key.code==diagnostics::Code::CommandLoss) {
            EXPECT_EQ(e.native_reason,1U); EXPECT_EQ(e.times[1].ns,e.command.expiry.ns); EXPECT_LE(e.times[2].ns-e.times[1].ns,kIoPoll);
            EXPECT_LT(e.times[2].ns,kLogicalStart+10200*kMs); // Upstream owners are still not executing.
        } else { EXPECT_EQ(e.native_reason,2U); EXPECT_EQ(e.times[2].ns,kLogicalStart+10200*kMs); }
    }
    for(const auto& row:r.trace) if(row.elapsed_ns>=10400*kMs && row.elapsed_ns<20000*kMs) {
        EXPECT_FALSE(row.run_gate); EXPECT_LE(std::abs(row.torque_nm),1); EXPECT_GE(row.pressure_pa,1000000);
    }
    save("upstream-pause",c,r,writer.ledger(),native.str(),zones.str());
}
TEST_F(OwnerDiagnosticsSil, EarlierZoneGatewayProtectionRemainsPropagationAtLeaf) {
    auto c=config(); c.faults.resize(1); c.recovery_ns=0; c.duration_ns=13000*kMs;
    const auto r=simulation::run_m4_async(c); ASSERT_TRUE(r.passed)<<r.reason;
    diagnostics::Ledger ledger; for(const auto& e:r.diagnostic_events) { ASSERT_EQ(ledger.record(e),diagnostics::Result::Accepted); }
    EXPECT_TRUE(ledger.records().empty());
    EXPECT_TRUE(std::any_of(r.diagnostic_events.begin(),r.diagnostic_events.end(),[](const auto& e){return e.kind==diagnostics::Kind::Observation && e.key.monitor==5 && e.cause_unknown;}));
}
TEST_F(OwnerDiagnosticsSil, OwnerHookOnOffPreserveEveryPhysicalSampleAndNativeTiming) {
    auto c=config(); c.duration_ns=13000*kMs; c.recovery_ns=0;
    const auto on=simulation::run_m4_async(c); c.owner_diagnostics_run=0;
    const auto off=simulation::run_m4_async(c);
    ASSERT_TRUE(on.passed)<<on.reason; ASSERT_TRUE(off.passed)<<off.reason; ASSERT_EQ(on.trace.size(),off.trace.size());
    EXPECT_EQ(on.first_fault_ns,off.first_fault_ns); EXPECT_EQ(on.all_protected_ns,off.all_protected_ns);
    for(std::size_t i=0;i<on.trace.size();++i) {
        const auto& a=on.trace[i]; const auto& b=off.trace[i];
        EXPECT_EQ(a.epoch,b.epoch); EXPECT_EQ(a.run_gate,b.run_gate); EXPECT_EQ(a.model_sequence,b.model_sequence);
        EXPECT_DOUBLE_EQ(a.torque_nm,b.torque_nm); EXPECT_DOUBLE_EQ(a.pressure_pa,b.pressure_pa);
        EXPECT_DOUBLE_EQ(a.distance_m,b.distance_m); EXPECT_DOUBLE_EQ(a.energy_j,b.energy_j); EXPECT_DOUBLE_EQ(a.soc,b.soc);
    }
}
TEST_F(OwnerDiagnosticsSil, NormalFullProfileHasNoLocalFalseDtcAndConfigurationRejectsMixedRuns) {
    auto c=config(); c.scenario=simulation::M4Scenario::Normal; c.faults={}; c.recovery_ns=0; c.duration_ns=92000*kMs;
    const auto r=simulation::run_m4_async(c); ASSERT_TRUE(r.passed)<<r.reason; EXPECT_TRUE(r.diagnostics_complete);
    diagnostics::FileJournal::initialize((directory/"store").string(),3001);
    diagnostics::FileJournal journal((directory/"store").string()); diagnostics::Recorder writer(journal);
    for(const auto& e:r.diagnostic_events) { ASSERT_TRUE(writer.record(e).durable); }
    EXPECT_TRUE(writer.ledger().records().empty()); EXPECT_EQ(r.speed_trace.size(),4350U); save("normal",c,r,writer.ledger());
    c.wall_time=true; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
    c.wall_time=false; c.diagnostics_run=999; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
    c.diagnostics_run=0; c.speed_loop=false; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
}
} // namespace
