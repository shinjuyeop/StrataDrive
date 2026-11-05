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
constexpr std::uint64_t run=9701;
diagnostics::Stamp stamp(std::uint64_t now){return {diagnostics::Domain::Simulation,run,now,true,true};}
TEST(ClockRecoveryVehicle, ActualOwnerRollbackNeedsExplicitTrustAndFreshGlobalRelease) {
    for(const bool trust:{false,true}) {
        simulation::M4Config c;c.speed_loop=true;c.renewal=central::CommandRenewal::Host10ms;c.startup_diagnostics_run=run;
        c.duration_ns=24000*kMs;c.recovery_ns=20000*kMs;c.replace_links=true;
        Network n(c);char pattern[]="/var/tmp/stratadrive-clock-vehicle-XXXXXX";const auto* made=mkdtemp(pattern);ASSERT_NE(made,nullptr);
        const std::filesystem::path path=made;
        struct Cleanup{std::filesystem::path path;~Cleanup(){std::filesystem::remove_all(path);}} cleanup{path};
        diagnostics::FileJournal::initialize((path/"store").string(),run,{},3);
        diagnostics::FileJournal journal((path/"store").string());diagnostics::Recorder writer(journal);
        std::vector<diagnostics::Event> events;std::vector<diagnostics::ClockRecoverySample> samples;
        bool injected=false,latched=false,revalidated=false;std::optional<session::Observation> original;
        for(std::uint64_t t=0;t<=c.duration_ns;t+=kIoPoll) {
            n.clock.logical=kLogicalStart+t;
            if(t==c.recovery_ns)n.replace_joined_links();
            if(t%kMs==0)n.step(8);
            if(t==10000*kMs){
                ASSERT_TRUE(n.gate.allows(1));ASSERT_TRUE(n.core.decision().normal_armed);ASSERT_TRUE(writer.ledger().records().empty());
                n.clock.logical-=2*kMs;n.step(5);original=n.sessions[5]->fault_observation();n.clock.logical+=2*kMs;injected=true;
            }
            if(t==19000*kMs && trust){
                revalidated=n.startup_diagnostic_hooks[5]->revalidate_clock({{run,run,0,0,true},stamp(n.clock.logical),1,2});
            }
            for(unsigned owner=0;owner<8;++owner)n.step(owner);
            if(n.active_epoch==2 && t%kMs==0) {
                const auto* b=n.leaf_owners[3]->bms_controller();const auto good=b->success_observation();
                const auto& release=n.startup.success_observation();
                diagnostics::ClockRecoverySample s{{run,n.active_epoch},n.startup.plan(),release?release->accepted_roles:0,
                    n.gate.allows(2),b->decision().state==vecu::BmsControlState::Active && b->decision().fault==vecu::BmsControlFault::None &&
                        good && good->epoch==2 && n.sessions[5]->run_enabled(),stamp(n.clock.logical),good?stamp(good->observed_ns):diagnostics::Stamp{}};
                n.startup_diagnostic_hooks[5]->observe_clock(s);samples.push_back(s);
            }
            const auto drain=[&](diagnostics::EventQueue& q){diagnostics::Event e;while(q.pop(e)){const auto r=writer.record(e);EXPECT_EQ(r.result,diagnostics::Result::Accepted);EXPECT_TRUE(r.durable);events.push_back(e);}EXPECT_EQ(q.health().dropped,0U);};
            drain(*n.diagnostic_queue);for(auto& q:n.startup_diagnostic_queues)drain(*q);for(auto& q:n.native_diagnostic_queues)drain(*q);
            if(t==14000*kMs){for(const auto& r:writer.ledger().records())if(r.key.code==diagnostics::Code::Clock){EXPECT_EQ(r.condition,diagnostics::Condition::Failed);latched=true;}}
        }
        const auto result=n.finish();
        if(const auto* root=std::getenv("STRATADRIVE_CLOCK_VEHICLE_EVIDENCE")) {
            const auto out=std::filesystem::path(root)/(trust?"revalidated":"init-only");ASSERT_FALSE(std::filesystem::exists(out));std::filesystem::create_directories(out);
            std::filesystem::copy(path/"store",out/"store",std::filesystem::copy_options::recursive);
            std::ofstream f(out/"samples.csv");f<<"observed_ns,source_ns,epoch,release_mask,gate,healthy,requested_ns,enable_ns,commit_ns,prepare_ns\n";
            for(const auto& s:samples)f<<s.observed.ns<<','<<s.source.ns<<','<<s.session.epoch<<','<<s.release_mask<<','<<s.normal_gate<<','<<s.native_healthy<<','<<s.released.requested_ns<<','<<s.released.enable_ns<<','<<s.released.commit_deadline_ns<<','<<s.released.prepare_deadline_ns<<'\n';
            std::ofstream p(out/"physical.csv");p<<"elapsed_ns,source_ns,model_epoch,sequence,gate,speed_mps,torque_nm,pressure_pa,contacts,bus_v\n"<<std::setprecision(17);
            for(const auto& s:result.trace)p<<s.elapsed_ns<<','<<s.source_ns<<','<<s.model_epoch<<','<<s.model_sequence<<','<<s.run_gate<<','<<s.speed_mps<<','<<s.torque_nm<<','<<s.pressure_pa<<','<<s.contacts<<','<<s.bus_v<<'\n';
            std::ofstream r(out/"records.csv");r<<"code,monitor,condition,count,cleared\n";
            for(const auto& d:writer.ledger().records())r<<static_cast<unsigned>(d.key.code)<<','<<d.key.monitor<<','<<static_cast<unsigned>(d.condition)<<','<<d.count<<','<<d.cleared<<'\n';
            std::ofstream meta(out/"recipe.json");meta<<"{\"trust\":"<<(trust?"true":"false")<<",\"revalidated\":"<<(revalidated?"true":"false")<<",\"injection_ns\":11000000000,\"rollback_ns\":2000000,\"checked_ns\":20000000000,\"revision\":1,\"physical_ok\":"<<(result.physical_ok?"true":"false")<<"}\n";
            if(original){std::ofstream o(out/"original.csv");o<<"observed_ns,previous_ns,reason,state,epoch\n"<<original->observed_ns<<','<<original->previous_ns<<','<<original->reason<<','<<original->state<<','<<original->plan.epoch<<'\n';}
        }
        EXPECT_TRUE(injected && latched);EXPECT_EQ(revalidated,trust);ASSERT_TRUE(original);EXPECT_EQ(original->reason,static_cast<unsigned>(session::ParticipantFault::Clock));
        EXPECT_TRUE(result.physical_ok);EXPECT_TRUE(result.diagnostics_complete);EXPECT_FALSE(result.event_overflow);EXPECT_TRUE(n.gate.allows(2));
        const auto records=writer.ledger().records();const auto clock=std::find_if(records.begin(),records.end(),[](const auto& r){return r.key.code==diagnostics::Code::Clock;});ASSERT_NE(clock,records.end());
        EXPECT_EQ(clock->condition,trust?diagnostics::Condition::Passed:diagnostics::Condition::Unknown);EXPECT_EQ(clock->count,1U);EXPECT_FALSE(clock->cleared);
        for(const auto& p:result.trace)if(p.elapsed_ns>=14000*kMs && p.elapsed_ns<20000*kMs){EXPECT_FALSE(p.run_gate);EXPECT_LE(std::abs(p.speed_mps),.01);EXPECT_LE(std::abs(p.torque_nm),1);EXPECT_GE(p.pressure_pa,1000000);EXPECT_EQ(p.contacts,0U);EXPECT_LE(p.bus_v,30);}
    }
}
} // namespace
