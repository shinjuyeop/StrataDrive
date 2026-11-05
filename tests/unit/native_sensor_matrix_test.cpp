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
using PowerFault=simulation::PowerSensorFault;
struct Recipe { unsigned bms; PowerFault power; };
std::vector<Recipe> recipes() {
    std::vector<Recipe> out;
    for(const auto mask:{1U,2U,4U,8U,16U,32U,64U,128U,170U}) out.push_back({mask,PowerFault::None});
    for(const auto f:{PowerFault::ChargerConnected,PowerFault::ContactorMismatch,PowerFault::BusLow}) {
        out.push_back({0,f}); out.push_back({170,f});
    }
    return out;
}
std::string name(Recipe r) { return "bms"+std::to_string(r.bms)+"_power"+std::to_string(static_cast<unsigned>(r.power)); }
bool power_root(Recipe r) { return r.power!=PowerFault::None && !(r.bms && r.power==PowerFault::BusLow); }
simulation::M4Config config(Recipe r,bool recover) {
    simulation::M4Config c; c.scenario=simulation::M4Scenario::NativeSensorFault;
    c.speed_loop=true; c.renewal=central::CommandRenewal::Host10ms; c.native_diagnostics_run=9501;
    c.injection_ns=10000*kMs; c.native_input_restore_ns=10200*kMs;
    c.duration_ns=(recover?24000:14000)*kMs; c.recovery_ns=recover?20000*kMs:0; c.replace_links=recover;
    c.native_bms_trip_mask=r.bms; c.native_power_fault=r.power; return c;
}
class NativeSensorMatrix : public ::testing::TestWithParam<Recipe> {};
TEST_P(NativeSensorMatrix, EightRolesPreserveCauseRespondPhysicallyAndRequireNewRelease) {
    const auto recipe=GetParam();
    for(const bool recover:{false,true}) {
        SCOPED_TRACE(recover?"new release":"restored without INIT");
        const auto c=config(recipe,recover); Network n(c);
        char temporary[]="/tmp/stratadrive-sensor-matrix-XXXXXX";
        const auto* made=mkdtemp(temporary); ASSERT_NE(made,nullptr);
        const std::filesystem::path path=made;
        struct Cleanup { std::filesystem::path p; ~Cleanup(){ std::filesystem::remove_all(p); } } cleanup{path};
        diagnostics::FileJournal::initialize((path/"store").string(),9501,{},2);
        diagnostics::FileJournal journal((path/"store").string()); diagnostics::Recorder writer(journal);
        std::vector<diagnostics::Event> events;
        std::array<std::optional<NativeObservation>,2> original;
        std::vector<std::pair<diagnostics::Event,NativeObservation>> snapshots;
        bool normal_before=false,latched_after_restore=false;
        for(std::uint64_t t=0;t<=c.duration_ns;t+=kIoPoll) {
            n.clock.logical=kLogicalStart+t;
            if(c.recovery_ns && t==c.recovery_ns) n.replace_joined_links();
            if(t%kMs==0) n.step(8);
            for(std::size_t owner=0;owner<8;++owner) n.step(owner);
            const auto drain=[&](diagnostics::EventQueue& q) {
                diagnostics::Event e;
                while(q.pop(e)) {
                    const auto receipt=writer.record(e);
                    EXPECT_EQ(receipt.result,diagnostics::Result::Accepted); EXPECT_TRUE(receipt.durable);
                    events.push_back(e);
                    if((e.kind==diagnostics::Kind::Fault || e.kind==diagnostics::Kind::Passed) && (e.key.monitor==8 || e.key.monitor==9)) {
                        const bool failed=e.kind==diagnostics::Kind::Fault;
                        const auto& source=e.key.monitor==8?
                            (failed?n.leaf_owners[3]->bms_controller()->fault_observation():n.leaf_owners[3]->bms_controller()->success_observation()):
                            (failed?n.leaf_owners[4]->power_controller()->fault_observation():n.leaf_owners[4]->power_controller()->success_observation());
                        ASSERT_TRUE(source); snapshots.emplace_back(e,*source);
                    }
                    if(e.kind==diagnostics::Kind::Fault && e.key.monitor==8) original[0]=n.leaf_owners[3]->bms_controller()->fault_observation();
                    if(e.kind==diagnostics::Kind::Fault && e.key.monitor==9) original[1]=n.leaf_owners[4]->power_controller()->fault_observation();
                }
                EXPECT_EQ(q.health().dropped,0U); EXPECT_FALSE(q.health().identity_error);
            };
            drain(*n.diagnostic_queue); for(auto& q:n.native_diagnostic_queues) drain(*q);
            if(t==9900*kMs) {
                EXPECT_TRUE(n.gate.allows(1)); EXPECT_TRUE(n.core.decision().normal_armed);
                EXPECT_TRUE(writer.ledger().records().empty()); normal_before=true;
            }
            if(t==13000*kMs) {
                EXPECT_FALSE(n.gate.allows(1));
                EXPECT_EQ(writer.ledger().records().size(),(recipe.bms?1U:0U)+(power_root(recipe)?1U:0U));
                for(const auto& record:writer.ledger().records()) EXPECT_EQ(record.condition,diagnostics::Condition::Failed);
                latched_after_restore=true;
            }
        }
        auto result=n.finish(); result.diagnostic_events=events;
        EXPECT_TRUE(result.passed)<<result.reason; EXPECT_TRUE(result.physical_ok); EXPECT_TRUE(result.model_preserved);
        EXPECT_TRUE(normal_before && latched_after_restore); EXPECT_TRUE(result.diagnostics_complete);
        EXPECT_EQ(n.active_epoch,recover?2U:1U); EXPECT_EQ(n.gate.allows(2),recover);
        for(const auto& record:writer.ledger().records()) {
            EXPECT_EQ(record.condition,recover?diagnostics::Condition::Passed:diagnostics::Condition::Failed);
            EXPECT_EQ(record.count,1U); EXPECT_EQ(record.generation,1U); EXPECT_FALSE(record.cleared);
        }
        for(unsigned slot=0;slot<2;++slot) {
            const bool needed=slot==0?recipe.bms!=0:power_root(recipe);
            ASSERT_EQ(original[slot].has_value(),needed); if(!needed) continue;
            const auto& o=*original[slot]; EXPECT_FALSE(o.propagation); EXPECT_EQ(o.epoch,1U);
            EXPECT_GE(o.observed_ns,kLogicalStart+c.injection_ns);
            if(slot==1 && recipe.bms && recipe.power==PowerFault::ContactorMismatch) {
                // BMS inhibition starts shutdown first. Contact feedback then
                // fails the ORIGINAL OpenContactors timeout, not the Ready check.
                EXPECT_EQ(o.state,static_cast<unsigned>(vecu::PowerPhase::OpenContactors));
                EXPECT_EQ(o.timing[5],100*kMs); EXPECT_EQ(o.observed_ns-o.phase_origin_ns,o.timing[5]);
            } else EXPECT_LE(o.observed_ns,kLogicalStart+c.injection_ns+(slot==0?60:10)*kMs);
            if(slot==0) {
                EXPECT_EQ(o.detail,recipe.bms); EXPECT_EQ(o.timing[4],40*kMs);
                ASSERT_TRUE(o.violation_ns); EXPECT_EQ(o.observed_ns-*o.violation_ns,40*kMs);
            } else {
                const auto expected=recipe.power==PowerFault::ChargerConnected?vecu::PowerControlFault::ConditionsUnsafe:
                    recipe.power==PowerFault::ContactorMismatch?vecu::PowerControlFault::ContactorResponse:vecu::PowerControlFault::BusNotReady;
                EXPECT_EQ(o.reason,static_cast<unsigned>(expected));
            }
            const auto fault=std::find_if(events.begin(),events.end(),[&](const auto& e){return e.kind==diagnostics::Kind::Fault && e.key.monitor==slot+8;});
            ASSERT_NE(fault,events.end()); EXPECT_EQ(fault->times[2].ns,o.observed_ns);
            EXPECT_EQ(fault->native_reason,o.reason); EXPECT_FALSE(fault->cause_unknown);
            const auto physical=std::find_if(result.trace.begin(),result.trace.end(),[&](const auto& p){
                return p.source_ns>=o.observed_ns && !p.run_gate && std::abs(p.torque_nm)<=1 && p.pressure_pa>=1000000;});
            ASSERT_NE(physical,result.trace.end()); EXPECT_LE(physical->source_ns-o.observed_ns,230*kMs);
        }
        if(recipe.bms && (recipe.power==PowerFault::ContactorMismatch || recipe.power==PowerFault::BusLow)) {
            const auto propagation=std::find_if(events.begin(),events.end(),[](const auto& e){return e.kind==diagnostics::Kind::Observation && e.key.monitor==9 && e.cause_unknown;});
            ASSERT_NE(propagation,events.end()); EXPECT_EQ(propagation->key.code,diagnostics::Code::None);
            EXPECT_EQ(propagation->native_reason,static_cast<unsigned>(vecu::PowerControlFault::BmsInhibit));
            ASSERT_TRUE(original[0]); EXPECT_LT(propagation->times[2].ns,original[0]->observed_ns);
        }
        for(const auto& p:result.trace) if(p.elapsed_ns>=13000*kMs && (!recover || p.elapsed_ns<20000*kMs)) {
            EXPECT_FALSE(p.run_gate); EXPECT_LE(std::abs(p.speed_mps),.01); EXPECT_LE(std::abs(p.torque_nm),1);
            EXPECT_GE(p.pressure_pa,1000000); EXPECT_EQ(p.contacts,0U); EXPECT_LE(p.bus_v,30);
        }
        if(const auto* root=std::getenv("STRATADRIVE_M9_MATRIX_EVIDENCE")) {
            const auto out=std::filesystem::path(root)/(name(recipe)+(recover?"_recover":"_latched"));
            ASSERT_FALSE(std::filesystem::exists(out)); std::filesystem::create_directories(out);
            simulation::write_m4_result(c,result,out.string());
            std::filesystem::copy(path/"store",out/"store",std::filesystem::copy_options::recursive);
            std::ofstream physical(out/"physical.csv"); physical<<"source_ns,epoch,model_epoch,model_sequence,speed_mps,distance_m,energy_j,balance_j,torque_nm,pressure_pa,gate,bus_v,contacts\n"<<std::setprecision(17);
            for(const auto& p:result.trace) physical<<p.source_ns<<','<<p.epoch<<','<<p.model_epoch<<','<<p.model_sequence<<','<<p.speed_mps<<','<<p.distance_m<<','<<p.energy_j<<','<<p.vehicle_balance_j<<','<<p.torque_nm<<','<<p.pressure_pa<<','<<p.run_gate<<','<<p.bus_v<<','<<p.contacts<<'\n';
            std::ofstream native(out/"native.csv"); native<<"kind,producer,event_sequence,monitor,reason,detail,violation_ns,observed_ns,epoch,model_epoch,enable_ns,propagation,qualified,state,phase_origin_ns,source_age_ns,dependency_age_ns,contactor_timeout_ns\n";
            std::ofstream samples(out/"samples.csv"); samples<<"producer,event_sequence,slot,present,epoch,sequence,source_ns,dependency_ns,v0,v1,v2,v3\n"<<std::setprecision(17);
            for(const auto& [e,o]:snapshots) {
                native<<static_cast<unsigned>(e.kind)<<','<<e.id.producer<<','<<e.id.sequence<<','<<e.key.monitor<<','<<o.reason<<','<<o.detail<<','<<o.violation_ns.value_or(0)<<','<<o.observed_ns<<','<<o.epoch<<','<<o.model_epoch<<','<<o.enable_ns<<','<<o.propagation<<','<<o.qualified<<','<<o.state<<','<<o.phase_origin_ns<<','<<o.timing[2]<<','<<o.timing[3]<<','<<o.timing[5]<<'\n';
                for(unsigned i=0;i<o.samples.size();++i) {
                    const auto& s=o.samples[i]; samples<<e.id.producer<<','<<e.id.sequence<<','<<i<<','<<s.present<<','<<s.epoch<<','<<s.sequence<<','<<s.source_ns<<','<<s.dependency_ns;
                    for(const auto& v:s.values) { samples<<','; if(v) samples<<*v; } samples<<'\n';
                }
            }
            std::ofstream records(out/"records.csv"); records<<"code,component,monitor,subject,condition,count,generation,cleared\n";
            for(const auto& r:writer.ledger().records()) records<<static_cast<unsigned>(r.key.code)<<','<<r.key.component<<','<<r.key.monitor<<','<<r.key.subject<<','<<static_cast<unsigned>(r.condition)<<','<<r.count<<','<<r.generation<<','<<r.cleared<<'\n';
        }
    }
}
INSTANTIATE_TEST_SUITE_P(BmsPower,NativeSensorMatrix,::testing::ValuesIn(recipes()),[](const auto& info){return name(info.param);});
TEST(NativeSensorMatrixConfiguration, RejectsWrongScopeUnsupportedMasksAndInvalidWindows) {
    auto c=config({170,PowerFault::None},true); c.wall_time=true; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
    c=config({170,PowerFault::None},true); c.native_bms_trip_mask=3; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
    c=config({170,PowerFault::None},true); c.scenario=simulation::M4Scenario::Normal; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
    c=config({170,PowerFault::None},true); c.native_input_restore_ns=c.recovery_ns; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
    c=config({0,PowerFault::None},true); EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
}
} // namespace
