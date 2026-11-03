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
            std::ofstream physical(out/"physical.csv"); physical<<"source_ns,epoch,model_epoch,model_sequence,distance_m,energy_j,balance_j,torque_nm,pressure_pa,gate,speed_mps,bus_v,contacts\n"<<std::setprecision(17);
            for(const auto& x:r.trace) physical<<x.source_ns<<','<<x.epoch<<','<<x.model_epoch<<','<<x.model_sequence<<','<<x.distance_m<<','<<x.energy_j<<','<<x.vehicle_balance_j<<','<<x.torque_nm<<','<<x.pressure_pa<<','<<x.run_gate<<','<<x.speed_mps<<','<<x.bus_v<<','<<x.contacts<<'\n';
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
class NativeVehicleDiagnosticsSil : public NativeDiagnosticsSil,public ::testing::WithParamInterface<simulation::M4Scenario> {
protected:
    simulation::M4Config vehicle_config(bool recover=true) {
        auto c=config(); c.scenario=GetParam(); c.faults={}; c.native_diagnostics_run=5001;
        c.injection_ns=10000*kMs; c.native_input_restore_ns=10200*kMs;
        if(!recover) { c.recovery_ns=0; c.duration_ns=14000*kMs; c.replace_links=false; }
        return c;
    }
    bool bms() const { return GetParam()==simulation::M4Scenario::BmsInputLoss; }
    const std::optional<NativeObservation>& snapshot(Network& n,const diagnostics::Event& e) {
        const bool fault=e.kind==diagnostics::Kind::Fault;
        if(e.key.monitor==8) { const auto& a=*n.leaf_owners[3]->bms_controller(); return fault?a.fault_observation():a.success_observation(); }
        if(e.key.monitor==9) { const auto& a=*n.leaf_owners[4]->power_controller(); return fault?a.fault_observation():a.success_observation(); }
        const auto& z=*n.zone_owners[e.key.component==7?0:1];
        if(e.key.monitor==6) return fault?z.command_gateway().fault_observation():z.command_gateway().success_observation();
        return fault?z.power_gateway()->fault_observation():z.power_gateway()->success_observation();
    }
};
TEST_P(NativeVehicleDiagnosticsSil, RealInputLossConnectsOriginalDetectorProtectionVehicleAndNewInitRecovery) {
    const auto c=vehicle_config(); Network n(c); const unsigned target=bms()?5:6;
    diagnostics::FileJournal::initialize((directory/"store").string(),5001,{},2);
    diagnostics::FileJournal journal((directory/"store").string()); diagnostics::Recorder writer(journal);
    std::vector<diagnostics::Event> events; std::ostringstream native,samples,bodies;
    native<<"kind,producer,event_sequence,component,monitor,epoch,enable_ns,observed_ns,reason,detail,state,model_epoch,phase_origin_ns,propagation,qualified,root_epoch,root_sequence,root_source_ns,root_expiry_ns,dependency_ns,valid_until_ns,period_ns,max_gap_ns,source_age_ns,dependency_age_ns,trip_dwell_ns,release_dwell_ns\n";
    samples<<"kind,producer,event_sequence,slot,present,model_epoch,sequence,source_ns,dependency_ns,v0,v1,v2,v3\n"<<std::setprecision(17);
    bodies<<"owner,epoch,body_ns,omitted,raw_present,model_epoch,model_sequence,source_ns,dependency_ns,current_a,bus_v,contacts,state,fault,recovery_ready,pending_trips,gate\n"<<std::setprecision(17);
    bool latched=false,recovered=false,init_only=false;
    for(std::uint64_t t=0;t<=c.duration_ns;t+=kIoPoll) {
        n.clock.logical=kLogicalStart+t;
        if(t==c.recovery_ns) n.replace_joined_links();
        if(t%kMs==0) n.step(8);
        for(std::size_t owner=0;owner<8;++owner) {
            const auto epoch_before=owner==5 || owner==6?n.leaf_owners[owner-2]->epoch():0;
            const auto previous=owner==5 || owner==6?n.leaf_owners[owner-2]->last_body_ns():0;
            const auto raw=owner==5 || owner==6?n.sensors[owner].read():std::optional<simulation::OwnerSensors>{};
            n.step(owner);
            if((owner==5 || owner==6) && n.leaf_owners[owner-2]->epoch()==epoch_before && n.leaf_owners[owner-2]->last_body_ns()!=previous) {
                ASSERT_TRUE(raw); ASSERT_TRUE(raw->battery.electrical); ASSERT_TRUE(raw->power); ASSERT_TRUE(raw->power->pack_current_a);
                const auto& leaf=*n.leaf_owners[owner-2]; const auto& p=*raw->power;
                const auto sample=owner==5?native_sample(raw->battery.electrical):native_sample(raw->power);
                const auto contacts=p.contactors.value_or(power::ContactorPositions{});
                const auto& bd=n.leaf_owners[3]->bms_controller()->decision(); const auto& pd=n.leaf_owners[4]->power_controller()->output();
                bodies<<owner<<','<<leaf.epoch()<<','<<leaf.last_body_ns()<<','<<leaf.omit_native_input<<','<<sample.present<<','<<sample.epoch<<','<<sample.sequence<<','<<sample.source_ns<<','<<sample.dependency_ns<<','
                    <<*p.pack_current_a<<','<<p.bus_voltage_v.value_or(-1)<<','<<(static_cast<unsigned>(contacts.positive)|(static_cast<unsigned>(contacts.negative)<<1U)|(static_cast<unsigned>(contacts.precharge)<<2U))<<','
                    <<(owner==5?static_cast<unsigned>(bd.state):static_cast<unsigned>(pd.phase))<<','<<(owner==5?static_cast<unsigned>(bd.fault):static_cast<unsigned>(pd.fault))<<','<<bd.recovery_ready<<','<<bd.pending_trips<<','<<n.gate.allows(leaf.epoch())<<'\n';
            }
        }
        const auto drain=[&](diagnostics::EventQueue& q) {
            diagnostics::Event e; while(q.pop(e)) {
                const auto receipt=writer.record(e); EXPECT_EQ(receipt.result,diagnostics::Result::Accepted); EXPECT_TRUE(receipt.durable); events.push_back(e);
                if(e.kind==diagnostics::Kind::Session && e.session.epoch==2) {
                    ASSERT_EQ(writer.ledger().records().size(),1U); EXPECT_EQ(writer.ledger().records()[0].condition,diagnostics::Condition::Unknown); init_only=true;
                }
                if(e.kind==diagnostics::Kind::Fault || e.kind==diagnostics::Kind::Passed) {
                    ASSERT_GE(e.key.monitor,6U); ASSERT_LE(e.key.monitor,9U); const auto& observation=snapshot(n,e); ASSERT_TRUE(observation); const auto& o=*observation;
                    const auto root=o.root.value_or(NativeRoot{});
                    native<<static_cast<unsigned>(e.kind)<<','<<e.id.producer<<','<<e.id.sequence<<','<<e.key.component<<','<<e.key.monitor<<','<<o.epoch<<','<<o.enable_ns<<','<<o.observed_ns<<','<<o.reason<<','<<o.detail<<','<<o.state<<','<<o.model_epoch<<','<<o.phase_origin_ns<<','<<o.propagation<<','<<o.qualified<<','
                        <<root.epoch<<','<<root.sequence<<','<<root.source_ns<<','<<root.expiry_ns<<','<<root.dependency_ns<<','<<o.valid_until_ns.value_or(0);
                    for(unsigned k=0;k<6;++k) { native<<','<<o.timing[k]; } native<<'\n';
                    for(unsigned k=0;k<o.samples.size();++k) {
                        const auto& a=o.samples[k]; samples<<static_cast<unsigned>(e.kind)<<','<<e.id.producer<<','<<e.id.sequence<<','<<k<<','<<a.present<<','<<a.epoch<<','<<a.sequence<<','<<a.source_ns<<','<<a.dependency_ns;
                        for(const auto& v:a.values) { samples<<','; if(v) samples<<*v; } samples<<'\n';
                    }
                    if(e.kind==diagnostics::Kind::Fault && e.key.monitor==(bms()?8U:9U)) {
                        EXPECT_EQ(o.observed_ns,n.clock.logical); EXPECT_FALSE(o.propagation);
                        if(bms()) { EXPECT_FALSE(o.samples[1].present); EXPECT_EQ(o.detail,static_cast<unsigned>(vecu::BmsInputIssue::Unavailable)); }
                        else { EXPECT_TRUE(o.samples[0].present); EXPECT_FALSE(o.samples[0].values[2]); EXPECT_EQ(o.state,static_cast<unsigned>(vecu::PowerPhase::Ready)); }
                    }
                }
            }
            EXPECT_EQ(q.health().dropped,0U); EXPECT_FALSE(q.health().identity_error);
        };
        drain(*n.diagnostic_queue); for(auto& q:n.native_diagnostic_queues) drain(*q);
        if(t==13000*kMs) {
            ASSERT_EQ(writer.ledger().records().size(),1U); EXPECT_EQ(writer.ledger().records()[0].condition,diagnostics::Condition::Failed);
            EXPECT_FALSE(n.gate.allows(1)); EXPECT_TRUE(n.leaf_owners[target-2]->faulted());
            EXPECT_EQ(n.leaf_owners[4]->power_controller()->output().phase,vecu::PowerPhase::Off); latched=true;
        }
        if(t==23000*kMs) {
            ASSERT_EQ(n.active_epoch,2U); EXPECT_TRUE(n.gate.allows(2)); ASSERT_EQ(writer.ledger().records().size(),1U);
            const auto& d=writer.ledger().records()[0]; EXPECT_EQ(d.condition,diagnostics::Condition::Passed); EXPECT_FALSE(d.cleared); EXPECT_EQ(d.count,1U); EXPECT_EQ(d.generation,1U); recovered=true;
        }
    }
    auto r=n.finish(); r.diagnostic_events=events;
    ASSERT_TRUE(r.passed)<<r.reason; EXPECT_TRUE(r.diagnostics_complete); EXPECT_TRUE(r.physical_ok); EXPECT_TRUE(r.model_preserved); EXPECT_TRUE(latched&&recovered&&init_only);
    const auto& d=writer.ledger().records()[0]; EXPECT_EQ(d.key.component,bms()?10U:6U); EXPECT_EQ(d.key.monitor,bms()?8U:9U); EXPECT_EQ(d.key.code,bms()?diagnostics::Code::BmsLocal:diagnostics::Code::PowerLocal);
    const auto first=std::find_if(events.begin(),events.end(),[](const auto& e){return e.kind==diagnostics::Kind::Fault;}); ASSERT_NE(first,events.end());
    EXPECT_GE(first->times[2].ns,kLogicalStart+c.injection_ns); EXPECT_LE(first->times[2].ns,kLogicalStart+c.injection_ns+(bms()?20:10)*kMs);
    const auto response=std::find_if(r.trace.begin(),r.trace.end(),[&](const auto& x){return x.source_ns>=first->times[2].ns && !x.run_gate && std::abs(x.torque_nm)<=1 && x.pressure_pa>=1000000;});
    ASSERT_NE(response,r.trace.end()); EXPECT_LE(response->source_ns-first->times[2].ns,230*kMs);
    for(const auto& x:r.trace) if(x.elapsed_ns>=13000*kMs && x.elapsed_ns<20000*kMs) { EXPECT_LE(std::abs(x.speed_mps),.01); EXPECT_EQ(x.contacts,0U); EXPECT_LE(x.bus_v,60); EXPECT_FALSE(x.run_gate); }
    const auto name=bms()?"bms-input-loss":"power-input-loss"; save(name,c,r,writer.ledger(),native.str());
    if(const auto* target_dir=std::getenv("STRATADRIVE_M9_NATIVE_EVIDENCE")) {
        const auto out=std::filesystem::path(target_dir)/name; std::ofstream(out/"native-samples.csv")<<samples.str(); std::ofstream(out/"native-bodies.csv")<<bodies.str();
    }
}
TEST_P(NativeVehicleDiagnosticsSil, RestorationWithoutNewInitStaysFailedAndCollectorDoesNotChangePhysics) {
    auto c=vehicle_config(false); const auto on=simulation::run_m4_async(c); c.native_diagnostics_run=0; const auto off=simulation::run_m4_async(c);
    ASSERT_TRUE(on.passed)<<on.reason; ASSERT_TRUE(off.passed)<<off.reason; diagnostics::Ledger ledger;
    for(const auto& e:on.diagnostic_events) { ASSERT_EQ(ledger.record(e),diagnostics::Result::Accepted); EXPECT_NE(e.kind,diagnostics::Kind::Passed); }
    ASSERT_EQ(ledger.records().size(),1U); EXPECT_EQ(ledger.records()[0].condition,diagnostics::Condition::Failed); ASSERT_EQ(on.trace.size(),off.trace.size());
    EXPECT_EQ(on.first_fault_ns,off.first_fault_ns); EXPECT_EQ(on.all_protected_ns,off.all_protected_ns);
    for(std::size_t i=0;i<on.trace.size();++i) {
        const auto& a=on.trace[i]; const auto& b=off.trace[i];
        EXPECT_EQ(a.epoch,b.epoch); EXPECT_EQ(a.run_gate,b.run_gate); EXPECT_EQ(a.model_epoch,b.model_epoch); EXPECT_EQ(a.model_sequence,b.model_sequence); EXPECT_EQ(a.contacts,b.contacts);
        EXPECT_DOUBLE_EQ(a.torque_nm,b.torque_nm); EXPECT_DOUBLE_EQ(a.pressure_pa,b.pressure_pa); EXPECT_DOUBLE_EQ(a.bus_v,b.bus_v);
        EXPECT_DOUBLE_EQ(a.speed_mps,b.speed_mps); EXPECT_DOUBLE_EQ(a.distance_m,b.distance_m); EXPECT_DOUBLE_EQ(a.energy_j,b.energy_j); EXPECT_DOUBLE_EQ(a.soc,b.soc); EXPECT_DOUBLE_EQ(a.vehicle_balance_j,b.vehicle_balance_j);
    }
}
TEST_P(NativeVehicleDiagnosticsSil, PersistentLossCannotProducePassedOrInventMissingCurrentAsZero) {
    auto c=vehicle_config(false); c.native_input_restore_ns=0; Network n(c); simulation::m4_detail::execute_logical(n); const auto r=n.finish();
    ASSERT_TRUE(r.passed)<<r.reason; diagnostics::Ledger ledger;
    for(const auto& e:r.diagnostic_events) { ASSERT_EQ(ledger.record(e),diagnostics::Result::Accepted); EXPECT_NE(e.kind,diagnostics::Kind::Passed); }
    ASSERT_EQ(ledger.records().size(),1U); EXPECT_EQ(ledger.records()[0].condition,diagnostics::Condition::Failed); EXPECT_FALSE(n.gate.allows(1));
    if(!bms()) {
        const auto& output=n.leaf_owners[4]->power_controller()->output(); EXPECT_EQ(output.phase,vecu::PowerPhase::WaitCurrent); EXPECT_TRUE(output.shutdown_blocked);
        for(const auto& x:r.trace) if(x.elapsed_ns>=13000*kMs) { EXPECT_EQ(x.contacts,3U); EXPECT_GT(x.bus_v,300); EXPECT_LE(std::abs(x.speed_mps),.01); }
    }
}
TEST_P(NativeVehicleDiagnosticsSil, RejectsUnscopedOrContradictoryInputWindowsBeforeLaunch) {
    auto c=vehicle_config(); c.wall_time=true; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
    c=vehicle_config(); c.speed_loop=false; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
    c=vehicle_config(); c.native_input_restore_ns=c.injection_ns; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
    c=vehicle_config(); c.native_input_restore_ns=c.duration_ns; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
    c=vehicle_config(); c.native_input_restore_ns=c.recovery_ns; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
    c=vehicle_config(); c.faults={simulation::parse_m4_fault("owner:pause:central:10000:200:0")}; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
    c=vehicle_config(); c.scenario=simulation::M4Scenario::Normal; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
}
INSTANTIATE_TEST_SUITE_P(BmsPower,NativeVehicleDiagnosticsSil,::testing::Values(simulation::M4Scenario::BmsInputLoss,simulation::M4Scenario::PowerInputLoss),
    [](const ::testing::TestParamInfo<simulation::M4Scenario>& p){return p.param==simulation::M4Scenario::BmsInputLoss?"Bms":"Power";});
} // namespace
