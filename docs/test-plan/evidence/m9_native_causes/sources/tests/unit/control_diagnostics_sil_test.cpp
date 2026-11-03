#include "m4_async_runtime.hpp"
#include "diagnostics_journal.hpp"
#include "control_diagnostics.hpp"
#include <gtest/gtest.h>
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>

namespace {
using namespace stratadrive;
constexpr std::uint64_t kMs=1000000,kStart=1000000000;
class ControlDiagnosticsSil : public ::testing::Test {
protected:
    std::filesystem::path directory;
    void SetUp() override {
        std::array<char,48> name{}; const std::string pattern="/tmp/stratadrive-control-diag-XXXXXX";
        std::copy(pattern.begin(),pattern.end(),name.begin()); const auto* p=mkdtemp(name.data()); ASSERT_NE(p,nullptr); directory=p;
    }
    void TearDown() override { std::filesystem::remove_all(directory); }
    simulation::M4Config config(bool loss) {
        simulation::M4Config c; c.speed_loop=true; c.renewal=central::CommandRenewal::Host10ms;
        c.scenario=loss?simulation::M4Scenario::SpeedInputLoss:simulation::M4Scenario::Normal;
        c.duration_ns=loss?13000000000ULL:92000000000ULL; c.injection_ns=10000000000ULL; return c;
    }
    void save(const char* mode,const simulation::M4Config& c,const simulation::M4Result& r,const diagnostics::Ledger& ledger) {
        const auto* target=std::getenv("STRATADRIVE_M9_CONTROL_EVIDENCE"); if(!target) return;
        const auto out=std::filesystem::path(target)/mode;
        ASSERT_FALSE(std::filesystem::exists(out)); std::filesystem::create_directories(out);
        simulation::write_m4_result(c,r,out.string());
        std::ofstream events(out/"diagnostics.csv");
        events<<"event_sequence,kind,code,component,monitor,subject,native_reason,epoch,occurrence_sequence,related_sequence,detected_ns,selected_ns,actual_source_ns,observed_ns,source_ns,command_source_ns,command_expiry_ns,measured,acknowledged_ns,source_producer,source_sequence,received_roles\n"<<std::setprecision(17);
        for(const auto& e:r.diagnostic_events) events<<e.id.sequence<<','<<static_cast<unsigned>(e.kind)<<','<<static_cast<unsigned>(e.key.code)<<','<<e.key.component<<','<<e.key.monitor<<','<<e.key.subject<<','<<e.native_reason<<','<<e.session.epoch<<','<<e.occurrence.sequence<<','<<e.related.sequence<<','<<e.times[2].ns<<','<<e.times[3].ns<<','<<e.times[5].ns<<','<<e.times[6].ns<<','<<e.source.source.ns<<','<<e.command.source.ns<<','<<e.command.expiry.ns<<','<<e.measured<<','<<e.times[4].ns<<','<<e.source.producer<<','<<e.source.sequence<<','<<e.received_roles<<'\n';
        std::ofstream summary(out/"diagnostics.json");
        summary<<"{\"run\":"<<c.diagnostics_run<<",\"clock\":\"simulation\",\"clock_instance\":"<<c.diagnostics_run<<",\"profile\":1,\"diagnostic_events\":"<<r.diagnostic_events.size()<<",\"dtc_records\":"<<ledger.records().size()<<",\"complete\":"<<std::boolalpha<<ledger.complete()<<",\"monitor_hooks_complete\":"<<r.diagnostics_complete<<",\"physical_samples\":"<<r.trace.size()<<",\"controller_samples\":"<<r.speed_trace.size()<<"}\n";
        std::ofstream physical(out/"physical.csv"); physical<<"source_ns,speed_mps,distance_m,torque_nm,pressure_pa,energy_j,balance_j,model_epoch,model_sequence,run_gate\n"<<std::setprecision(17);
        for(const auto& v:r.trace) physical<<v.source_ns<<','<<v.speed_mps<<','<<v.distance_m<<','<<v.torque_nm<<','<<v.pressure_pa<<','<<v.energy_j<<','<<v.vehicle_balance_j<<','<<v.model_epoch<<','<<v.model_sequence<<','<<v.run_gate<<'\n';
        std::ofstream control(out/"control.csv"); control<<"now_ns,profile_ns,source_ns,expiry_ns,target_mps,speed_mps,acceleration_mps2\n"<<std::setprecision(17);
        for(const auto& v:r.speed_trace) control<<v.now_ns<<','<<v.profile_ns<<','<<v.speed_source_ns<<','<<v.request_expiry_ns<<','<<v.target_mps<<','<<v.speed_mps<<','<<v.acceleration_mps2<<'\n';
        std::filesystem::copy(directory/"store",out/"store",std::filesystem::copy_options::recursive);
    }
};
TEST_F(ControlDiagnosticsSil, NormalFullSpeedLoopStopsAndPowersOffWithZeroFalseDtc) {
    auto c=config(false); c.diagnostics_run=1001; const auto r=simulation::run_m4_async(c);
    ASSERT_TRUE(r.passed)<<r.reason; ASSERT_TRUE(r.diagnostics_complete); ASSERT_EQ(r.speed_trace.size(),4350U);
    diagnostics::FileJournal::initialize((directory/"store").string(),1001);
    diagnostics::FileJournal journal((directory/"store").string()); diagnostics::Recorder recorder(journal);
    for(const auto& e:r.diagnostic_events) ASSERT_TRUE(recorder.record(e).durable);
    EXPECT_TRUE(recorder.ledger().complete()); EXPECT_TRUE(recorder.ledger().records().empty());
    bool handoff=false,off=false; unsigned actual=0;
    for(const auto& e:r.diagnostic_events) {
        if(e.key.component==2 && e.state_after==static_cast<unsigned>(central::NormalStopState::HandoffPending)) handoff=true;
        if(e.kind==diagnostics::Kind::Actual) { ++actual; EXPECT_TRUE(e.source.present); EXPECT_EQ(e.times[5].ns,e.source.source.ns); }
        if(e.kind==diagnostics::Kind::Actual && e.source.producer==6) { off=true; EXPECT_LE(e.measured,30); }
    }
    EXPECT_TRUE(handoff); EXPECT_TRUE(off); EXPECT_GE(actual,7U); EXPECT_EQ(r.trace.back().contacts,0U);
    save("normal",c,r,recorder.ledger());
}
TEST_F(ControlDiagnosticsSil, RealInputLossConnectsDetectionProtectionPhysicalResponseAndDurableDtc) {
    auto c=config(true); c.diagnostics_run=1002; const auto r=simulation::run_m4_async(c);
    ASSERT_TRUE(r.passed)<<r.reason; ASSERT_TRUE(r.diagnostics_complete);
    diagnostics::FileJournal::initialize((directory/"store").string(),1002);
    const auto key=diagnostics::Key{diagnostics::Code::SpeedInput,1,1,1};
    {
        diagnostics::FileJournal journal((directory/"store").string()); diagnostics::Recorder recorder(journal);
        for(const auto& e:r.diagnostic_events) ASSERT_TRUE(recorder.record(e).durable);
        ASSERT_EQ(recorder.ledger().records().size(),1U); const auto* dtc=recorder.ledger().find(key); ASSERT_NE(dtc,nullptr);
        EXPECT_EQ(dtc->count,1U); EXPECT_EQ(dtc->condition,diagnostics::Condition::Failed);
        EXPECT_GE(dtc->first_detected.ns,kStart+c.injection_ns); EXPECT_LT(dtc->first_detected.ns,kStart+c.injection_ns+20*kMs);
        EXPECT_EQ(dtc->first_detected.ns,kStart+r.first_fault_ns);
        const auto ack=std::find_if(r.diagnostic_events.begin(),r.diagnostic_events.end(),[](const auto& e){return e.kind==diagnostics::Kind::ProtectionAck && e.source.producer==3;});
        ASSERT_NE(ack,r.diagnostic_events.end()); EXPECT_TRUE(ack->related==dtc->first_event);
        EXPECT_GE(ack->times[4].ns,kStart+r.all_protected_ns); EXPECT_FALSE(ack->times[3].present);
        EXPECT_TRUE(ack->command.present); EXPECT_LT(ack->command.source.ns,dtc->first_detected.ns);
        unsigned selected_roles=0;
        for(const auto& e:r.diagnostic_events) if(e.kind==diagnostics::Kind::ProtectionSelected) {
            EXPECT_TRUE(e.related==dtc->first_event); EXPECT_EQ(e.times[3].ns,e.source.source.ns);
            EXPECT_GE(e.times[3].ns,dtc->first_detected.ns); EXPECT_LE(e.times[3].ns,kStart+r.all_protected_ns);
            selected_roles|=e.received_roles;
        }
        EXPECT_EQ(selected_roles,124U); // Steering/Brake/Drive/BMS/Power, not a fabricated aggregate ACK
        unsigned actuals=0;
        for(const auto& e:r.diagnostic_events) if(e.kind==diagnostics::Kind::Actual) {
            ++actuals; EXPECT_TRUE(e.related==dtc->first_event); EXPECT_EQ(e.times[5].ns,e.source.source.ns);
            EXPECT_GE(e.times[5].ns,dtc->first_detected.ns); EXPECT_LE(e.times[5].ns,kStart+r.all_protected_ns+230*kMs);
            if(e.source.producer==4) { EXPECT_LE(std::abs(e.measured),1); }
            if(e.source.producer==5) { EXPECT_GE(e.measured,1000000); }
        }
        EXPECT_EQ(actuals,3U);
        EXPECT_GE(r.all_protected_ns,r.first_fault_ns); EXPECT_LE(r.all_protected_ns,c.injection_ns+100*kMs);
        const auto after=kStart+r.all_protected_ns+230*kMs;
        unsigned responses=0;
        for(const auto& row:r.trace) if(row.source_ns>=after) {
            ++responses; EXPECT_LE(std::abs(row.torque_nm),1); EXPECT_GE(row.pressure_pa,1000000); EXPECT_FALSE(row.run_gate);
            EXPECT_EQ(row.model_epoch,7U); EXPECT_LE(std::abs(row.vehicle_balance_j),1e-5);
        }
        EXPECT_GT(responses,100U); save("input-loss",c,r,recorder.ledger());
    }
    diagnostics::FileJournal journal((directory/"store").string()); diagnostics::Recorder restarted(journal);
    ASSERT_NE(restarted.ledger().find(key),nullptr); EXPECT_EQ(restarted.ledger().find(key)->count,1U);
    EXPECT_EQ(restarted.ledger().find(key)->condition,diagnostics::Condition::Unknown);
}
TEST_F(ControlDiagnosticsSil, HookOnAndOffHaveIdenticalControllerAuthorityPhysicsAndEnergy) {
    auto c=config(true); const auto original=simulation::run_m4_async(c); c.diagnostics_run=1003;
    const auto connected=simulation::run_m4_async(c); ASSERT_TRUE(original.passed)<<original.reason; ASSERT_TRUE(connected.passed)<<connected.reason;
    ASSERT_EQ(original.trace.size(),connected.trace.size()); ASSERT_EQ(original.speed_trace.size(),connected.speed_trace.size());
    EXPECT_EQ(original.first_fault_ns,connected.first_fault_ns); EXPECT_EQ(original.all_protected_ns,connected.all_protected_ns);
    for(std::size_t i=0;i<original.speed_trace.size();++i) {
        const auto& a=original.speed_trace[i]; const auto& b=connected.speed_trace[i];
        EXPECT_EQ(a.now_ns,b.now_ns); EXPECT_EQ(a.profile_ns,b.profile_ns); EXPECT_EQ(a.speed_source_ns,b.speed_source_ns);
        EXPECT_EQ(a.request_expiry_ns,b.request_expiry_ns); EXPECT_EQ(a.epoch,b.epoch); EXPECT_EQ(a.sequence,b.sequence);
        EXPECT_DOUBLE_EQ(a.target_mps,b.target_mps); EXPECT_DOUBLE_EQ(a.speed_mps,b.speed_mps);
        EXPECT_DOUBLE_EQ(a.acceleration_mps2,b.acceleration_mps2); EXPECT_DOUBLE_EQ(a.integral,b.integral);
    }
    for(std::size_t i=0;i<original.trace.size();++i) {
        const auto& a=original.trace[i]; const auto& b=connected.trace[i];
        EXPECT_EQ(a.run_gate,b.run_gate); EXPECT_EQ(a.coordinator_fault,b.coordinator_fault); EXPECT_EQ(a.model_sequence,b.model_sequence);
        EXPECT_EQ(a.command_source_ns,b.command_source_ns); EXPECT_EQ(a.command_root_sequence,b.command_root_sequence);
        EXPECT_DOUBLE_EQ(a.speed_mps,b.speed_mps); EXPECT_DOUBLE_EQ(a.torque_nm,b.torque_nm); EXPECT_DOUBLE_EQ(a.pressure_pa,b.pressure_pa);
        EXPECT_DOUBLE_EQ(a.bus_v,b.bus_v); EXPECT_DOUBLE_EQ(a.soc,b.soc); EXPECT_DOUBLE_EQ(a.energy_j,b.energy_j); EXPECT_DOUBLE_EQ(a.vehicle_balance_j,b.vehicle_balance_j);
    }
    EXPECT_TRUE(original.diagnostic_events.empty()); EXPECT_FALSE(connected.diagnostic_events.empty());
}
TEST_F(ControlDiagnosticsSil, OptInRejectsWallAndUnscopedInputLossBeforeExecution) {
    auto c=config(true); c.diagnostics_run=1004; c.wall_time=true; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
    c=config(true); c.speed_loop=false; EXPECT_THROW(simulation::run_m4_async(c),std::invalid_argument);
}
} // namespace
