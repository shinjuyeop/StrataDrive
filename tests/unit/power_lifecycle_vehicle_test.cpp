#include "m4_owner_network.hpp"
#include "diagnostics_journal.hpp"
#include <gtest/gtest.h>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>

namespace {
using namespace stratadrive;
using namespace simulation::m4_detail;
using Fault=vecu::PowerControlFault;
using Inject=simulation::PowerLifecycleSensorFault;
class PowerLifecycleVehicle:public ::testing::TestWithParam<Fault> {};
TEST_P(PowerLifecycleVehicle, OriginalDetectorPhysicalProtectionAndNewEpochRecovery) {
    const auto expected=GetParam();
    const bool startup=expected==Fault::PrechargeTimeout || expected==Fault::StartupEnergized;
    for(const bool recover:{false,true}) {
        simulation::M4Config c;c.speed_loop=true;c.renewal=central::CommandRenewal::Host10ms;c.native_diagnostics_run=9601;
        c.duration_ns=(recover?24000:15000)*kMs;c.recovery_ns=recover?20000*kMs:0;c.replace_links=recover;
        if(expected==Fault::RequestLost) {
            c.scenario=simulation::M4Scenario::Fault;
            c.faults={simulation::parse_m4_fault("zone-leaf:drop:power:10000:200:0")};
        }
        Network n(c);char pattern[]="/var/tmp/stratadrive-power-vehicle-XXXXXX";const auto* made=mkdtemp(pattern);ASSERT_NE(made,nullptr);
        const std::filesystem::path path=made;
        struct Cleanup {std::filesystem::path path;~Cleanup(){std::filesystem::remove_all(path);}} cleanup{path};
        diagnostics::FileJournal::initialize((path/"store").string(),9601,{},2);
        diagnostics::FileJournal journal((path/"store").string());diagnostics::Recorder recorder(journal);
        std::vector<std::pair<diagnostics::Event,NativeObservation>> snapshots;
        std::vector<diagnostics::Event> events;std::optional<NativeObservation> first,good;
        bool normal_before=false,latched=false;std::uint64_t injected=0,restored=0;
        std::vector<std::pair<std::uint64_t,unsigned>> injection_rows;
        for(std::uint64_t t=0;t<=c.duration_ns;t+=kIoPoll) {
            n.clock.logical=kLogicalStart+t;
            if(recover && t==c.recovery_ns)n.replace_joined_links();
            if(t%kMs==0)n.step(8);
            if(t==10000*kMs && (expected==Fault::ShutdownCurrentBlocked || expected==Fault::DischargeTimeout))
                n.core.request_protection(n.clock.logical); // real shutdown request precedes a shutdown-stage detector
            for(std::size_t owner=0;owner<8;++owner) {
                if(owner==6) {
                    auto& leaf=*n.leaf_owners[4];Inject fault=Inject::None;
                    if(expected==Fault::PrechargeTimeout && t<3000*kMs)fault=Inject::PrechargeStall;
                    if(expected==Fault::StartupEnergized && t<200*kMs)fault=Inject::StartupEnergized;
                    if(expected==Fault::ShutdownCurrentBlocked && t>=10000*kMs && t<11500*kMs)fault=Inject::CurrentHeld;
                    if(expected==Fault::DischargeTimeout && t>=10000*kMs && t<12500*kMs && leaf.power_controller()->output().phase==vecu::PowerPhase::Discharging)fault=Inject::DischargeHeld;
                    if(fault!=leaf.native_power_lifecycle_fault) {
                        injection_rows.emplace_back(n.clock.logical,static_cast<unsigned>(fault));
                        if(fault!=Inject::None && !injected)injected=n.clock.logical;
                        if(fault==Inject::None)restored=n.clock.logical;
                    }
                    leaf.native_power_lifecycle_fault=fault;
                }
                n.step(owner);
            }
            if(!first && n.leaf_owners[4]->power_controller()->fault_observation())first=n.leaf_owners[4]->power_controller()->fault_observation();
            if(recover && n.active_epoch==2 && n.leaf_owners[4]->power_controller()->success_observation())good=n.leaf_owners[4]->power_controller()->success_observation();
            const auto drain=[&](diagnostics::EventQueue& q){diagnostics::Event e;while(q.pop(e)){const auto r=recorder.record(e);EXPECT_TRUE(r.durable);EXPECT_EQ(r.result,diagnostics::Result::Accepted);events.push_back(e);
                if(e.key.monitor==9 && (e.kind==diagnostics::Kind::Fault || e.kind==diagnostics::Kind::Passed)) {
                    const auto& raw=e.kind==diagnostics::Kind::Fault?n.leaf_owners[4]->power_controller()->fault_observation():n.leaf_owners[4]->power_controller()->success_observation();
                    ASSERT_TRUE(raw);snapshots.emplace_back(e,*raw);
                }}EXPECT_EQ(q.health().dropped,0U);};
            drain(*n.diagnostic_queue);for(auto& q:n.native_diagnostic_queues)drain(*q);
            if(t==9900*kMs && !startup){EXPECT_TRUE(n.core.decision().normal_armed);EXPECT_TRUE(n.gate.allows(1));EXPECT_TRUE(recorder.ledger().records().empty());normal_before=true;}
            if(t==14000*kMs) {
                const auto records=recorder.ledger().records();
                latched=std::any_of(records.begin(),records.end(),[&](const auto& r){return r.key.monitor==(expected==Fault::RequestLost?6U:9U) && r.condition==diagnostics::Condition::Failed;});
            }
        }
        const auto result=n.finish();
        if(const auto* root=std::getenv("STRATADRIVE_POWER_VEHICLE_EVIDENCE")) {
            const auto out=std::filesystem::path(root)/(std::to_string(static_cast<unsigned>(expected))+(recover?"-recover":"-latched"));
            ASSERT_FALSE(std::filesystem::exists(out));std::filesystem::create_directories(out);
            std::filesystem::copy(path/"store",out/"store",std::filesystem::copy_options::recursive);
            std::ofstream(out/"recipe.json")<<"{\"reason\":"<<static_cast<unsigned>(expected)<<",\"recovery\":"<<(recover?"true":"false")<<",\"startup\":"<<(startup?"true":"false")<<",\"injected_ns\":"<<injected<<",\"restored_ns\":"<<restored<<",\"duration_ns\":"<<c.duration_ns<<",\"physical_ok\":"<<(result.physical_ok?"true":"false")<<",\"diagnostics_complete\":"<<(result.diagnostics_complete?"true":"false")<<"}\n";
            std::ofstream physical(out/"physical.csv");physical<<"elapsed_ns,source_ns,epoch,model_epoch,model_sequence,speed_mps,torque_nm,pressure_pa,gate,bus_v,contacts,balance_j,distance_m\n"<<std::setprecision(17);
            for(const auto& p:result.trace)physical<<p.elapsed_ns<<','<<p.source_ns<<','<<p.epoch<<','<<p.model_epoch<<','<<p.model_sequence<<','<<p.speed_mps<<','<<p.torque_nm<<','<<p.pressure_pa<<','<<p.run_gate<<','<<p.bus_v<<','<<p.contacts<<','<<p.vehicle_balance_j<<','<<p.distance_m<<'\n';
            std::ofstream native(out/"native.csv");native<<"kind,producer,event_sequence,reason,epoch,observed_ns,phase_origin_ns,state,qualified,model_epoch,propagation,enable_ns,detail";
            for(unsigned i=0;i<12;++i)native<<",timing"<<i;
            native<<'\n';
            std::ofstream samples(out/"samples.csv");samples<<"producer,event_sequence,slot,present,epoch,sequence,source_ns,dependency_ns,v0,v1,v2,v3\n"<<std::setprecision(17);
            for(const auto& [e,o]:snapshots) {
                native<<static_cast<unsigned>(e.kind)<<','<<e.id.producer<<','<<e.id.sequence<<','<<o.reason<<','<<o.epoch<<','<<o.observed_ns<<','<<o.phase_origin_ns<<','<<o.state<<','<<o.qualified<<','<<o.model_epoch<<','<<o.propagation<<','<<o.enable_ns<<','<<o.detail;
                for(const auto v:o.timing)native<<','<<v;
                native<<'\n';
                for(unsigned i=0;i<o.samples.size();++i) {
                    const auto& v=o.samples[i];samples<<e.id.producer<<','<<e.id.sequence<<','<<i<<','<<v.present<<','<<v.epoch<<','<<v.sequence<<','<<v.source_ns<<','<<v.dependency_ns;
                    for(const auto x:v.values){samples<<',';if(x)samples<<*x;}samples<<'\n';
                }
            }
            std::ofstream records(out/"records.csv");records<<"code,component,monitor,subject,condition,count,generation,cleared\n";
            for(const auto& r:recorder.ledger().records())records<<static_cast<unsigned>(r.key.code)<<','<<r.key.component<<','<<r.key.monitor<<','<<r.key.subject<<','<<static_cast<unsigned>(r.condition)<<','<<r.count<<','<<r.generation<<','<<r.cleared<<'\n';
            std::ofstream injections(out/"injections.csv");injections<<"ns,fault\n";for(const auto& [time,fault]:injection_rows)injections<<time<<','<<fault<<'\n';
            std::ofstream faults(out/"owner-events.csv");faults<<"ns,event,owner,epoch,source,deadline,reference,code\n";
            for(const auto& e:result.events)faults<<e.time_ns<<','<<e.kind<<','<<e.owner<<','<<e.epoch<<','<<e.source_ns<<','<<e.deadline_ns<<','<<e.reference_ns<<','<<e.code<<'\n';
        }
        if(expected==Fault::RequestLost) {
            // Global transaction/command expiry protects Power before its own
            // request watchdog. Preserve the actual gateway root, not a DTC
            // for a local detector that never ran in this protected vehicle.
            EXPECT_FALSE(first);
            EXPECT_TRUE(std::any_of(events.begin(),events.end(),[](const auto& e){return e.kind==diagnostics::Kind::Fault && e.key.monitor==6 && e.key.code==diagnostics::Code::CommandLoss;}));
            EXPECT_FALSE(std::any_of(events.begin(),events.end(),[](const auto& e){return e.key.monitor==9 && (e.kind==diagnostics::Kind::Fault || e.kind==diagnostics::Kind::Passed);}));
        } else {
            ASSERT_TRUE(first) << static_cast<unsigned>(expected);
            EXPECT_EQ(first->reason,static_cast<unsigned>(expected));EXPECT_FALSE(first->propagation);
        }
        EXPECT_TRUE(result.physical_ok);EXPECT_TRUE(result.diagnostics_complete);EXPECT_FALSE(result.event_overflow);
        EXPECT_TRUE(startup || normal_before);EXPECT_TRUE(latched);
        const auto records=recorder.ledger().records();
        const auto record=std::find_if(records.begin(),records.end(),[&](const auto& r){return r.key.monitor==(expected==Fault::RequestLost?6U:9U);});ASSERT_NE(record,records.end());
        if(expected!=Fault::RequestLost){EXPECT_EQ(record->key.subject,static_cast<unsigned>(expected));}
        EXPECT_EQ(record->count,1U);EXPECT_FALSE(record->cleared);
        EXPECT_EQ(record->condition,recover?diagnostics::Condition::Passed:diagnostics::Condition::Failed);
        EXPECT_EQ(n.active_epoch,recover?2U:1U);if(recover){ASSERT_TRUE(good);EXPECT_EQ(good->epoch,2U);EXPECT_EQ(good->state,static_cast<unsigned>(vecu::PowerPhase::Ready));}
        for(const auto& p:result.trace)if(p.elapsed_ns>=14000*kMs && p.elapsed_ns<20000*kMs){EXPECT_FALSE(p.run_gate);EXPECT_LE(std::abs(p.speed_mps),.01);EXPECT_LE(std::abs(p.torque_nm),1);EXPECT_GE(p.pressure_pa,1000000);EXPECT_EQ(p.contacts,0U);EXPECT_LE(p.bus_v,30);}
    }
}
INSTANTIATE_TEST_SUITE_P(RemainingPower,PowerLifecycleVehicle,::testing::Values(Fault::PrechargeTimeout,Fault::RequestLost,Fault::ShutdownCurrentBlocked,Fault::StartupEnergized,Fault::DischargeTimeout),[](const auto& info){return "Reason"+std::to_string(static_cast<unsigned>(info.param));});
} // namespace
