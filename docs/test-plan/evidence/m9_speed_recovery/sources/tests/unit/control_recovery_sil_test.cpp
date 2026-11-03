#include "m4_owner_network.hpp"
#include "diagnostics_journal.hpp"
#include "diagnostics_fixture.hpp"
#include <gtest/gtest.h>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <memory>
#include <sstream>

namespace {
using namespace stratadrive;
using namespace simulation::m4_detail;
constexpr std::uint64_t kRun=2001;
const diagnostics::Key kKey{diagnostics::Code::SpeedInput,1,1,1};
class ControlRecoverySil : public ::testing::Test {
protected:
    std::filesystem::path directory;
    void SetUp() override {
        char path[]="/tmp/stratadrive-recovery-XXXXXX";
        const auto* p=mkdtemp(path); ASSERT_NE(p,nullptr); directory=p;
    }
    void TearDown() override { std::filesystem::remove_all(directory); }
    simulation::M4Config config() {
        simulation::M4Config c; c.speed_loop=true; c.renewal=central::CommandRenewal::Host10ms;
        c.scenario=simulation::M4Scenario::SpeedInputLoss; c.diagnostics_run=kRun;
        c.duration_ns=40'000*kMs; c.injection_ns=10'000*kMs; c.speed_input_restore_ns=12'000*kMs;
        c.recovery_ns=20'000*kMs; c.rejoin_epoch=2; c.speed_input_reinject_ns=36'000*kMs; return c;
    }
};
TEST_F(ControlRecoverySil, RealRecoveryExplicitSafeClearAndRecurrencePreservePhysicalAndDiagnosticHistory) {
    const auto c=config(); Network n(c);
    diagnostics::FileJournal::initialize((directory/"store").string(),kRun);
    auto journal=std::make_unique<diagnostics::FileJournal>((directory/"store").string());
    auto recorder=std::make_unique<diagnostics::Recorder>(*journal);
    std::vector<diagnostics::Event> events;
    std::ostringstream checkpoints; checkpoints<<std::setprecision(17);
    checkpoints<<"now_ns,epoch,gate,normal_armed,stopping,stop_state,core_fault,speed_fault,wheel_rad_s,torque_nm,pressure_pa,condition,cleared,generation,count,revision\n";
    diagnostics::Clear clear; diagnostics::Record before_clear{};
    std::optional<central::SpeedRequest> failed_source;
    bool qualification_checked=false;
    bool cleared=false,restarted=false,restored=false,passed=false;
    for(std::uint64_t t=0;t<=c.duration_ns;t+=kIoPoll) {
        n.clock.logical=kLogicalStart+t; const auto now=n.clock.logical;
        if(t==31'000*kMs) {
            ASSERT_TRUE(cleared); n.gate.close(); n.startup.cancel(now); ASSERT_TRUE(n.startup.begin(3,now));
            n.owner_events[7].push_back({now,"recovery-request",7,3,0,0,0,0});
        }
        if(t%kMs==0) n.step(8);
        if(t>=24'000*kMs && t<31'000*kMs && n.active_epoch==2 &&
           (n.core.decision().normal_armed || n.core.decision().stopping) && (!n.last_stop || now-n.last_stop>=20*kMs)) {
            ASSERT_EQ(n.core.receive_stop({{2,n.stop_seq++,now,now+60*kMs},0},now),central::CoordinatorReceive::Accepted);
            n.last_stop=now;
        }
        for(std::size_t owner=0;owner<8;++owner) n.step(owner);
        diagnostics::Event e;
        while(n.diagnostic_queue->pop(e)) {
            const auto receipt=recorder->record(e);
            ASSERT_EQ(receipt.result,diagnostics::Result::Accepted)<<"kind="<<static_cast<int>(e.kind)<<" epoch="<<e.session.epoch;
            ASSERT_TRUE(receipt.durable); events.push_back(e);
            if(e.kind==diagnostics::Kind::Passed) {
                ASSERT_TRUE(failed_source); const auto current=n.port.feedback();
                for(unsigned variant=0;variant<10;++variant) {
                    diagnostics::EventQueue q(kRun,17);
                    diagnostics::ControlDiagnostics observer(q,{kRun,17,diagnostics::Domain::Simulation,kRun,1});
                    ASSERT_TRUE(observer.start_session(1,failed_source->fault_observation()->enable_ns)); observer.observe(*failed_source,now);
                    if(variant!=8) { ASSERT_TRUE(observer.start_session(2,current.session_enable_ns)); }
                    auto bad=current; auto probe=n.speed_control; auto probe_now=now;
                    central::SpeedRequest empty; ASSERT_TRUE(empty.start_session(2,current.session_enable_ns));
                    switch(variant) {
                    case 0: bad.epoch=1; break;
                    case 1: ++bad.session_enable_ns; break;
                    case 2: bad.rear.drive_actual.reset(); break;
                    case 3: ++bad.rear.drive_actual->sequence; break;
                    case 4: ++bad.rear.drive_actual->wheel_speed->source_time_ns; break;
                    case 5: probe_now+=31*kMs; break;
                    case 6: break; // Same native INIT2, no successful input/request yet.
                    case 7: bad.rear.power_status.reset(); break;
                    case 9: {
                        probe_now=probe.success_observation()->issued_ns+20*kMs;
                        auto unaccepted=*current.rear.drive_actual;
                        unaccepted.source_time_ns=probe_now-kMs; unaccepted.wheel_speed->source_time_ns=probe_now-kMs; ++unaccepted.sequence;
                        ASSERT_TRUE(probe.step(probe_now,0,unaccepted,true)); bad.rear.drive_actual=unaccepted; break;
                    }
                    default: break; // No new diagnostics session, despite healthy epoch2 input.
                    }
                    observer.observe_speed_recovery(variant==6?empty:probe,n.core,bad,probe_now);
                    diagnostics::Event observed; unsigned passes=0;
                    while(q.pop(observed)) if(observed.kind==diagnostics::Kind::Passed) ++passes;
                    EXPECT_EQ(passes,0U)<<"variant="<<variant;
                    if(variant==8) { ASSERT_TRUE(observer.start_session(2,current.session_enable_ns)); }
                    observer.observe_speed_recovery(n.speed_control,n.core,current,now);
                    while(q.pop(observed)) if(observed.kind==diagnostics::Kind::Passed) ++passes;
                    EXPECT_EQ(passes,1U)<<"variant="<<variant;
                    observer.observe_speed_recovery(n.speed_control,n.core,current,now);
                    EXPECT_FALSE(q.pop(observed));
                }
                qualification_checked=true;
            }
        }
        const auto in=n.port.feedback(); const auto d=n.core.decision(); const auto* record=recorder->ledger().find(kKey);
        if(t==13'000*kMs) {
            ASSERT_TRUE(in.rear.drive_actual); ASSERT_TRUE(in.rear.drive_actual->wheel_speed);
            EXPECT_FALSE(n.speed_input_lost(now)); EXPECT_EQ(n.active_epoch,1U);
            EXPECT_FALSE(n.gate.allows(1)); EXPECT_FALSE(d.normal_armed); EXPECT_NE(n.speed_control.fault(),central::SpeedRequestFault::None);
            EXPECT_FALSE(n.speed_control.step(now,0,in.rear.drive_actual,true));
            ASSERT_NE(record,nullptr); EXPECT_EQ(record->condition,diagnostics::Condition::Failed); EXPECT_FALSE(record->cleared);
            EXPECT_FALSE(n.diagnostic_hook->speed_clear_evidence(n.speed_control,n.core,in,in.rear.drive_actual,now)); restored=true;
            failed_source.emplace(n.speed_control);
        }
        if(t==20'010*kMs) {
            // A request for INIT, even during preparation, is not recovery evidence.
            ASSERT_NE(record,nullptr); EXPECT_EQ(record->condition,diagnostics::Condition::Failed); EXPECT_FALSE(record->cleared);
        }
        if(t==22'000*kMs) {
            ASSERT_EQ(n.active_epoch,2U); EXPECT_TRUE(n.gate.allows(2)); EXPECT_TRUE(d.normal_armed);
            ASSERT_NE(record,nullptr); EXPECT_EQ(record->condition,diagnostics::Condition::Passed);
            EXPECT_FALSE(record->cleared); EXPECT_EQ(record->count,1U); EXPECT_EQ(record->generation,1U);
            ASSERT_TRUE(in.rear.drive_actual); ASSERT_TRUE(in.rear.drive_actual->wheel_speed);
            EXPECT_GT(in.rear.drive_actual->wheel_speed->value_rad_s,.01);
            EXPECT_FALSE(n.diagnostic_hook->speed_clear_evidence(n.speed_control,n.core,in,in.rear.drive_actual,now)); passed=true;
        }
        if(t==28'000*kMs) {
            ASSERT_NE(record,nullptr); before_clear=*record;
            const auto evidence=n.diagnostic_hook->speed_clear_evidence(n.speed_control,n.core,in,in.rear.drive_actual,now);
            ASSERT_TRUE(evidence)<<"stop="<<static_cast<int>(d.stop.state)<<" core="<<static_cast<int>(d.fault)<<" wheel="<<(in.rear.drive_actual&&in.rear.drive_actual->wheel_speed?in.rear.drive_actual->wheel_speed->value_rad_s:-1);
            EXPECT_FALSE(n.diagnostic_hook->speed_clear_evidence(n.speed_control,n.core,in,std::nullopt,now));
            EXPECT_FALSE(n.diagnostic_hook->speed_clear_evidence(n.speed_control,n.core,in,in.rear.drive_actual,now+31*kMs));
            clear={{kRun,99,1},{kRun,2},*evidence,false,{{kKey,record->revision}}};
            diagnostics_fixture::MemoryJournal failed_store;
            diagnostics::Recorder failed_writer(failed_store);
            for(const auto& native:events) { ASSERT_TRUE(failed_writer.record(native).durable); }
            auto failed_clear=clear; failed_clear.targets[0].revision=failed_writer.ledger().find(kKey)->revision;
            failed_store.fail=true; const auto failed_receipt=failed_writer.clear(failed_clear);
            EXPECT_EQ(failed_receipt.result,diagnostics::Result::StorageFailure); EXPECT_FALSE(failed_receipt.durable);
            EXPECT_FALSE(failed_writer.ledger().find(kKey)->cleared); EXPECT_FALSE(failed_writer.ledger().complete());
            auto rejected=clear; rejected.id.sequence=2; ++rejected.targets[0].revision;
            EXPECT_EQ(recorder->clear(rejected).result,diagnostics::Result::NotReady);
            rejected=clear; rejected.id.sequence=3; rejected.evidence.normal_dispatch_inhibited=false;
            EXPECT_EQ(recorder->clear(rejected).result,diagnostics::Result::NotReady);
            rejected=clear; rejected.id.sequence=4; rejected.evidence.wheel_rad_s=1;
            EXPECT_EQ(recorder->clear(rejected).result,diagnostics::Result::NotReady);
            rejected=clear; rejected.id.sequence=5; rejected.evidence.brake.trusted=false;
            EXPECT_EQ(recorder->clear(rejected).result,diagnostics::Result::NotReady);
            const auto receipt=recorder->clear(clear); ASSERT_EQ(receipt.result,diagnostics::Result::Accepted); ASSERT_TRUE(receipt.durable);
            const auto duplicate=recorder->clear(clear); EXPECT_EQ(duplicate.result,diagnostics::Result::Duplicate); EXPECT_TRUE(duplicate.durable);
            ASSERT_TRUE(recorder->ledger().find(kKey)->cleared); EXPECT_EQ(n.core.decision().stop.state,d.stop.state);
            EXPECT_FALSE(n.core.decision().normal_armed); EXPECT_EQ(n.speed_control.fault(),central::SpeedRequestFault::None);
            n.owner_events[7].push_back({now,"explicit-dtc-clear",7,2,0,0,0,0}); cleared=true;
        }
        if(t==29'000*kMs) {
            recorder.reset(); journal.reset();
            journal=std::make_unique<diagnostics::FileJournal>((directory/"store").string());
            recorder=std::make_unique<diagnostics::Recorder>(*journal);
            ASSERT_TRUE(recorder->ledger().find(kKey)->cleared); EXPECT_EQ(recorder->ledger().find(kKey)->count,1U);
            EXPECT_EQ(recorder->ledger().find(kKey)->condition,diagnostics::Condition::Unknown);
            const auto duplicate=recorder->clear(clear); EXPECT_EQ(duplicate.result,diagnostics::Result::Duplicate); EXPECT_TRUE(duplicate.durable); restarted=true;
        }
        if(t%(10*kMs)==0) {
            record=recorder->ledger().find(kKey);
            checkpoints<<now<<','<<n.active_epoch<<','<<n.gate.allows(n.active_epoch)<<','<<d.normal_armed<<','<<d.stopping<<','<<static_cast<unsigned>(d.stop.state)<<','<<static_cast<unsigned>(d.fault)<<','<<static_cast<unsigned>(n.speed_control.fault())<<','
                <<(in.rear.drive_actual&&in.rear.drive_actual->wheel_speed?in.rear.drive_actual->wheel_speed->value_rad_s:-1)<<','
                <<(in.rear.drive_actual&&in.rear.drive_actual->torque_nm?*in.rear.drive_actual->torque_nm:0)<<','
                <<(in.front.brake_actual&&in.front.brake_actual->pressure_pa?*in.front.brake_actual->pressure_pa:0)<<','
                <<(record?static_cast<unsigned>(record->condition):0)<<','<<(record&&record->cleared)<<','<<(record?record->generation:0)<<','<<(record?record->count:0)<<','<<(record?record->revision:0)<<'\n';
        }
    }
    auto r=n.finish(); ASSERT_TRUE(r.passed)<<r.reason; ASSERT_TRUE(r.diagnostics_complete); ASSERT_TRUE(r.model_preserved);
    EXPECT_TRUE(restored&&passed&&cleared&&restarted&&qualification_checked); const auto* record=recorder->ledger().find(kKey); ASSERT_NE(record,nullptr);
    EXPECT_EQ(record->condition,diagnostics::Condition::Failed); EXPECT_FALSE(record->cleared); EXPECT_EQ(record->generation,2U); EXPECT_EQ(record->count,1U);
    EXPECT_EQ(record->state_session.epoch,3U); EXPECT_GT(record->first_detected.ns,before_clear.last_detected.ns);
    EXPECT_FALSE(n.gate.allows(3)); EXPECT_TRUE(recorder->ledger().complete());
    EXPECT_EQ(std::count_if(events.begin(),events.end(),[](const auto& e){return e.kind==diagnostics::Kind::Fault;}),2);
    EXPECT_EQ(std::count_if(events.begin(),events.end(),[](const auto& e){return e.kind==diagnostics::Kind::Passed;}),1);
    const auto proof=std::find_if(events.begin(),events.end(),[](const auto& e){return e.kind==diagnostics::Kind::Passed;});
    ASSERT_NE(proof,events.end()); EXPECT_EQ(proof->session.epoch,2U); EXPECT_EQ(proof->occurrence.epoch,1U);
    EXPECT_EQ(proof->proof,diagnostics::Proof::Input); EXPECT_NE(proof->proof_event.sequence,0U); EXPECT_EQ(proof->latch,diagnostics::Latch::Clear);
    EXPECT_EQ(r.trace.front().model_epoch,7U); EXPECT_EQ(r.trace.back().model_epoch,7U);
    EXPECT_GT(r.trace.back().distance_m,r.trace.front().distance_m);
    for(std::size_t i=1;i<r.trace.size();++i) {
        EXPECT_GT(r.trace[i].model_sequence,r.trace[i-1].model_sequence); EXPECT_GE(r.trace[i].distance_m,r.trace[i-1].distance_m);
        EXPECT_LE(std::abs(r.trace[i].vehicle_balance_j),1e-5);
    }
    const auto& battery=n.physical.electrical().battery_state();
    EXPECT_NEAR(battery.energy_j,battery.initial_energy_j-battery.drawn_dc_j+battery.received_dc_j-battery.auxiliary_j-battery.ohmic_loss_j,1e-5);
    EXPECT_GT(battery.received_dc_j,0); // Actual regeneration permits chemical energy to increase.
    for(const auto& row:n.physical.energy_trace) {
        EXPECT_EQ(row.state.model_epoch,7U); EXPECT_LE(std::abs(row.state.combined_balance_j),.001);
        EXPECT_LE(std::abs(row.state.coupling_balance_j),1e-6);
    }
    if(const auto* target=std::getenv("STRATADRIVE_M9_RECOVERY_EVIDENCE")) {
        const auto out=std::filesystem::path(target); ASSERT_FALSE(std::filesystem::exists(out)); std::filesystem::create_directories(out);
        simulation::write_m4_result(c,r,out.string());
        std::ofstream(out/"checkpoints.csv")<<checkpoints.str();
        std::ofstream physical(out/"physical.csv"); physical<<"source_ns,epoch,model_epoch,model_sequence,distance_m,energy_j,balance_j,run_gate\n"<<std::setprecision(17);
        for(const auto& row:r.trace) physical<<row.source_ns<<','<<row.epoch<<','<<row.model_epoch<<','<<row.model_sequence<<','<<row.distance_m<<','<<row.energy_j<<','<<row.vehicle_balance_j<<','<<row.run_gate<<'\n';
        std::ofstream control(out/"control.csv"); control<<"now_ns,epoch,sequence,source_ns,expiry_ns,speed_mps,acceleration_mps2\n"<<std::setprecision(17);
        for(const auto& row:r.speed_trace) control<<row.now_ns<<','<<row.epoch<<','<<row.sequence<<','<<row.speed_source_ns<<','<<row.request_expiry_ns<<','<<row.speed_mps<<','<<row.acceleration_mps2<<'\n';
        std::ofstream energy(out/"energy.csv"); energy<<"end_ns,model_epoch,sequence,battery_draw_j,received_dc_j,combined_balance_j,coupling_balance_j\n"<<std::setprecision(17);
        for(const auto& row:n.physical.energy_trace) energy<<row.state.end_ns<<','<<row.state.model_epoch<<','<<row.state.sequence<<','<<row.state.battery_draw_j<<','<<row.state.received_dc_j<<','<<row.state.combined_balance_j<<','<<row.state.coupling_balance_j<<'\n';
        std::filesystem::copy(directory/"store",out/"store",std::filesystem::copy_options::recursive);
    }
    recorder.reset(); journal.reset(); diagnostics::FileJournal replay((directory/"store").string()); diagnostics::Recorder replayed(replay);
    EXPECT_EQ(replayed.ledger().find(kKey)->generation,2U); EXPECT_EQ(replayed.ledger().find(kKey)->count,1U);
    EXPECT_FALSE(replayed.ledger().find(kKey)->cleared); EXPECT_EQ(replayed.ledger().find(kKey)->condition,diagnostics::Condition::Unknown);
    EXPECT_EQ(replayed.ledger().events().size(),events.size());
}
TEST_F(ControlRecoverySil, RestoringInputWithoutNewInitKeepsNativeProtectionAndFailedDtc) {
    auto c=config(); c.duration_ns=16'000*kMs; c.recovery_ns=0; c.speed_input_reinject_ns=0;
    const auto r=simulation::run_m4_async(c); ASSERT_TRUE(r.passed)<<r.reason;
    diagnostics::Ledger ledger;
    for(const auto& e:r.diagnostic_events) ASSERT_EQ(ledger.record(e),diagnostics::Result::Accepted);
    ASSERT_NE(ledger.find(kKey),nullptr); EXPECT_EQ(ledger.find(kKey)->condition,diagnostics::Condition::Failed);
    EXPECT_FALSE(ledger.find(kKey)->cleared);
    EXPECT_EQ(std::count_if(r.diagnostic_events.begin(),r.diagnostic_events.end(),[](const auto& e){return e.kind==diagnostics::Kind::Passed;}),0);
    EXPECT_EQ(r.trace.back().epoch,1U); EXPECT_FALSE(r.trace.back().run_gate); EXPECT_NE(r.speed_fault,0);
}
TEST_F(ControlRecoverySil, InvalidRecoveryWindowsAreRejectedBeforeExecution) {
    auto c=config(); c.speed_input_restore_ns=c.injection_ns; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
    c=config(); c.speed_input_reinject_ns=c.speed_input_restore_ns; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
    c=config(); c.wall_time=true; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
}
} // namespace
