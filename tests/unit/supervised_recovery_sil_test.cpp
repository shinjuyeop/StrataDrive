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
constexpr std::uint64_t run=9402;
const diagnostics::Key key{diagnostics::Code::CentralControl,1,4,4};
TEST(SupervisedRecoverySil, NewAcceptedControlSafeExplicitClearRestartAndRecurrence) {
    simulation::M4Config config;config.speed_loop=true;config.supervised_speed=true;config.diagnostics_run=run;
    config.renewal=central::CommandRenewal::Host10ms;config.scenario=simulation::M4Scenario::SpeedInputLoss;
    config.duration_ns=40'000*kMs;config.injection_ns=10'000*kMs;config.speed_input_restore_ns=12'000*kMs;
    config.recovery_ns=20'000*kMs;config.speed_input_reinject_ns=36'000*kMs;
    Network n(config);
    char name[]="/tmp/stratadrive-supervised-recovery-XXXXXX";const auto* directory=mkdtemp(name);ASSERT_NE(directory,nullptr);
    struct Cleanup {std::filesystem::path path;~Cleanup(){std::filesystem::remove_all(path);}} cleanup{directory};
    const auto store=cleanup.path/"store";diagnostics::FileJournal::initialize(store.string(),run,{},4);
    auto journal=std::make_unique<diagnostics::FileJournal>(store.string());
    auto writer=std::make_unique<diagnostics::Recorder>(*journal);
    std::optional<central::SupervisedSpeedRequest> failed;
    std::vector<diagnostics::Event> events;
    diagnostics::Clear clear;
    bool checked=false,restored=false,passed=false,cleared=false,reopened=false;
    for(std::uint64_t t=0;t<=config.duration_ns;t+=kIoPoll) {
        n.clock.logical=kLogicalStart+t;const auto now=n.clock.logical;
        if(t==31'000*kMs) {ASSERT_TRUE(cleared);n.gate.close();n.startup.cancel(now);ASSERT_TRUE(n.startup.begin(3,now));}
        if(t%kMs==0)n.step(8);
        if(t>=24'000*kMs && t<31'000*kMs && n.active_epoch==2 &&
           (n.core.decision().normal_armed || n.core.decision().stopping) && (!n.last_stop || now-n.last_stop>=20*kMs)) {
            ASSERT_EQ(n.core.receive_stop({{2,n.stop_seq++,now,now+60*kMs},0},now),central::CoordinatorReceive::Accepted);
            n.last_stop=now;
        }
        for(std::size_t owner=0;owner<8;++owner)n.step(owner);
        diagnostics::Event event;
        while(n.diagnostic_queue->pop(event)) {
            const auto receipt=writer->record(event);ASSERT_TRUE(receipt.durable)<<static_cast<int>(receipt.result);
            events.push_back(event);
            if(event.kind==diagnostics::Kind::Passed && event.key==key && !checked) {
                ASSERT_TRUE(failed);const auto input=n.port.feedback();
                ASSERT_TRUE(n.supervised_control.success_observation());
                const auto& success=*n.supervised_control.success_observation();
                EXPECT_EQ(event.command.expiry.ns,success.output.request.expires_at_ns);
                EXPECT_LE(success.output.request.expires_at_ns,n.supervised_control.controller().success_observation()->request.expires_at_ns);
                ASSERT_TRUE(success.output.input.power);ASSERT_TRUE(n.core.last_vehicle_input());
                EXPECT_EQ(n.core.last_vehicle_input()->power->source_time_ns,success.force.source_ns);
                for(unsigned variant=0;variant<13;++variant) {
                    diagnostics::EventQueue queue(run,17);diagnostics::ControlDiagnostics observer(queue,{run,17,diagnostics::Domain::Simulation,run,1});
                    ASSERT_TRUE(observer.start_session(1,failed->fault_observation()->enable_ns));observer.observe(*failed,n.core,now);
                    if(variant!=0) {ASSERT_TRUE(observer.start_session(2,input.session_enable_ns));}
                    auto current=input;auto probe=n.supervised_control;auto at=now;
                    central::ReferenceConfig different;different.capacity_fraction=.8;
                    central::SupervisedSpeedRequest changed(variant==10?different:central::ReferenceConfig{},variant==11?.31:.3);
                    ASSERT_TRUE(changed.start_session(2,variant==9?run+1:run,input.session_enable_ns));
                    if(variant>=9 && variant<=11) {
                        const central::ClassicalSpeedProposal target{2,variant==9?run+1:run,now,now+30*kMs+1,0,true};
                        ASSERT_TRUE(changed.step(now,std::nullopt,target,input.rear.drive_actual,n.force_estimator.estimate(input,now),true));
                    }
                    switch(variant) {
                    case 1:current.epoch=1;break;
                    case 2:++current.session_enable_ns;break;
                    case 3:current.rear.drive_actual.reset();break;
                    case 4:++current.rear.drive_actual->sequence;break;
                    case 5:++current.rear.drive_actual->wheel_speed->source_time_ns;break;
                    case 6:at+=31*kMs;break;
                    case 7:current.rear.power_limits.reset();break;
                    case 12:at=success.output.request.expires_at_ns;break;
                    default:break;
                    }
                    observer.observe_speed_recovery(variant>=8 && variant<=11?changed:probe,n.core,current,at);
                    diagnostics::Event e;unsigned count=0;while(queue.pop(e))if(e.kind==diagnostics::Kind::Passed)++count;
                    EXPECT_EQ(count,0U)<<"variant="<<variant;
                    if(variant==0) {ASSERT_TRUE(observer.start_session(2,input.session_enable_ns));}
                    observer.observe_speed_recovery(n.supervised_control,n.core,input,now);
                    while(queue.pop(e))if(e.kind==diagnostics::Kind::Passed)++count;
                    EXPECT_EQ(count,1U)<<"variant="<<variant;
                    observer.observe_speed_recovery(n.supervised_control,n.core,input,now);EXPECT_FALSE(queue.pop(e));
                }
                checked=true;
            }
        }
        const auto input=n.port.feedback();const auto* record=writer->ledger().find(key);
        const auto evidence=[&](std::uint64_t at){return n.diagnostic_hook->speed_clear_evidence(n.supervised_control,n.core,input,input.rear.drive_actual,at);};
        if(t==13'000*kMs) {
            ASSERT_NE(record,nullptr);EXPECT_EQ(record->condition,diagnostics::Condition::Failed);EXPECT_FALSE(record->cleared);
            EXPECT_FALSE(n.speed_input_lost(now));EXPECT_TRUE(n.supervised_control.protection_required());
            EXPECT_FALSE(n.gate.allows(1));EXPECT_FALSE(evidence(now));failed.emplace(n.supervised_control);restored=true;
        }
        if(t==20'010*kMs) {ASSERT_NE(record,nullptr);EXPECT_EQ(record->condition,diagnostics::Condition::Failed);}
        if(t==22'000*kMs) {
            ASSERT_NE(record,nullptr);EXPECT_EQ(record->condition,diagnostics::Condition::Passed);EXPECT_FALSE(record->cleared);
            EXPECT_GT(input.rear.drive_actual->wheel_speed->value_rad_s,.01);EXPECT_FALSE(evidence(now));passed=true;
        }
        if(t==28'000*kMs) {
            ASSERT_NE(record,nullptr);const auto safe=evidence(now);ASSERT_TRUE(safe);
            EXPECT_FALSE(evidence(now+31*kMs));
            EXPECT_FALSE(n.diagnostic_hook->speed_clear_evidence(n.supervised_control,n.core,input,std::nullopt,now));
            clear={{run,99,1},{run,2},*safe,false,{{key,record->revision}}};
            auto bad=clear;bad.evidence.normal_dispatch_inhibited=false;EXPECT_FALSE(writer->clear(bad).durable);
            bad=clear;bad.evidence.wheel_rad_s=1;EXPECT_FALSE(writer->clear(bad).durable);
            bad=clear;++bad.targets[0].revision;EXPECT_FALSE(writer->clear(bad).durable);
            ASSERT_TRUE(writer->clear(clear).durable);EXPECT_TRUE(writer->ledger().find(key)->cleared);
            EXPECT_FALSE(n.core.decision().normal_armed);EXPECT_FALSE(n.core.decision().management.normal_allowed);EXPECT_TRUE(n.core.decision().management.power_off_confirmed);cleared=true;
        }
        if(t==29'000*kMs) {
            writer.reset();journal.reset();journal=std::make_unique<diagnostics::FileJournal>(store.string());writer=std::make_unique<diagnostics::Recorder>(*journal);
            EXPECT_TRUE(writer->ledger().find(key)->cleared);EXPECT_EQ(writer->ledger().find(key)->condition,diagnostics::Condition::Unknown);
            EXPECT_TRUE(writer->clear(clear).durable);reopened=true;
        }
    }
    const auto result=n.finish();ASSERT_TRUE(result.passed)<<result.reason;EXPECT_TRUE(result.model_preserved);EXPECT_TRUE(result.diagnostics_complete);
    EXPECT_TRUE(checked&&restored&&passed&&cleared&&reopened);
    const auto* record=writer->ledger().find(key);ASSERT_NE(record,nullptr);EXPECT_EQ(record->generation,2U);EXPECT_EQ(record->count,1U);
    EXPECT_EQ(record->condition,diagnostics::Condition::Failed);EXPECT_FALSE(record->cleared);EXPECT_EQ(record->state_session.epoch,3U);
    EXPECT_FALSE(n.gate.allows(3));EXPECT_EQ(writer->ledger().records().size(),1U);
    EXPECT_EQ(std::count_if(events.begin(),events.end(),[](const auto& e){return e.kind==diagnostics::Kind::Fault;}),2);
    EXPECT_EQ(std::count_if(events.begin(),events.end(),[](const auto& e){return e.kind==diagnostics::Kind::Passed;}),2);
    for(std::size_t i=1;i<result.trace.size();++i) {
        EXPECT_EQ(result.trace[i].model_epoch,7U);EXPECT_GT(result.trace[i].model_sequence,result.trace[i-1].model_sequence);
        EXPECT_GE(result.trace[i].distance_m,result.trace[i-1].distance_m);EXPECT_LE(std::abs(result.trace[i].vehicle_balance_j),1e-5);
    }
    if(const auto* target=std::getenv("STRATADRIVE_SUPERVISED_RECOVERY_EVIDENCE")) {
        const std::filesystem::path out(target);ASSERT_FALSE(std::filesystem::exists(out));std::filesystem::create_directories(out);
        simulation::write_m4_result(config,result,out.string());std::filesystem::copy(store,out/"store",std::filesystem::copy_options::recursive);
        std::ofstream raw(out/"events.hex");for(const auto& e:events){for(auto b:diagnostics::encode(e))raw<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(b);raw<<'\n';}
    }
}
TEST(SupervisedRecoverySil, WallOrMissingSpeedScopeCannotEnableSupervision) {
    simulation::M4Config c;c.supervised_speed=true;EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
    c.speed_loop=true;c.diagnostics_run=run;c.wall_time=true;EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
}
} // namespace
