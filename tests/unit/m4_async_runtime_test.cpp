#include "m4_async_runtime.hpp"

#include <gtest/gtest.h>
#include <cstdlib>
#include <cmath>

namespace {
using namespace stratadrive::simulation;
M4Result run(M4Scenario scenario,bool wall=false) {
    M4Config c; c.scenario=scenario; c.wall_time=wall;
    c.transport_trace=std::getenv("STRATADRIVE_M4_TRANSPORT_TRACE")!=nullptr;
    if(scenario==M4Scenario::NormalStop) c.duration_ns=3000000000;
    if(scenario==M4Scenario::Rejoin) c.duration_ns=4200000000;
    if(scenario==M4Scenario::OldEpoch) c.first_epoch=3;
    const auto result=run_m4_async(c);
    if(const auto* directory=std::getenv("STRATADRIVE_M4_RESULTS")) write_m4_result(c,result,directory);
    EXPECT_TRUE(result.passed)<<result.reason;
    for(const auto& row:result.trace) {
        if(row.protected_all) { EXPECT_FALSE(row.run_gate)<<"elapsed="<<row.elapsed_ns<<" epoch="<<row.epoch; }
    }
    return result;
}
TEST(M4AsyncRuntime, NormalUsesRealBmsAndFeedbackBeforeActuation) {
    const auto r=run(M4Scenario::Normal); ASSERT_FALSE(r.trace.empty());
    const auto& end=r.trace.back(); EXPECT_TRUE(end.run_gate); EXPECT_TRUE(end.normal_armed); EXPECT_EQ(end.coordinator_fault,0);
    EXPECT_NEAR(end.angle_rad,std::atan(2.7*.02),.001); EXPECT_LT(end.pressure_pa,1); EXPECT_GT(end.torque_nm,50);
    EXPECT_GT(end.bus_v,395); EXPECT_LT(end.soc,.63); EXPECT_GT(end.soc,.6299);
    for(const auto& row:r.trace) if(!row.normal_armed && row.elapsed_ns<r.first_active_ns) {
        EXPECT_DOUBLE_EQ(row.angle_rad,.1); EXPECT_DOUBLE_EQ(row.pressure_pa,200000); EXPECT_DOUBLE_EQ(row.torque_nm,0);
    }
}
TEST(M4AsyncRuntime, NormalStopWaitsForLeafHandoffThenActualHvOff) {
    const auto r=run(M4Scenario::NormalStop); ASSERT_FALSE(r.trace.empty());
    EXPECT_LT(r.trace.back().bus_v,30); EXPECT_LT(std::abs(r.trace.back().torque_nm),.1); EXPECT_GE(r.trace.back().pressure_pa,100000);
}
TEST(M4AsyncRuntime, PartialFrontWritePreventsRearBatchAndProtectsAllDomains) {
    const auto r=run(M4Scenario::PartialFront);
    EXPECT_EQ(r.front_frames,2*r.rear_frames+1); EXPECT_EQ(r.completed_batches,r.rear_frames);
}
TEST(M4AsyncRuntime, FeedbackLossCannotBeHiddenByLiveZoneHeartbeat) {
    const auto r=run(M4Scenario::FeedbackLoss); ASSERT_FALSE(r.trace.empty());
    EXPECT_LT(std::abs(r.trace.back().torque_nm),.1); EXPECT_GE(r.trace.back().pressure_pa,1000000);
    for(const auto& row:r.trace) {
        if(row.elapsed_ns>=r.first_fault_ns) { EXPECT_FALSE(row.run_gate); }
    }
}
TEST(M4AsyncRuntime, LostVehicleRootDoesNotGetRenewedByPowerTraffic) { run(M4Scenario::CommandLoss); }
TEST(M4AsyncRuntime, PartialArmNeverEmitsNormalActuatorFrames) { run(M4Scenario::PartialArm); }
TEST(M4AsyncRuntime, ExplicitNewEpochRejoinKeepsPhysicalStateAndRestoresReadiness) {
    const auto r=run(M4Scenario::Rejoin); EXPECT_GT(r.rejoin_active_ns,2300000000U); ASSERT_FALSE(r.trace.empty());
    EXPECT_EQ(r.trace.back().epoch,2U); EXPECT_TRUE(r.trace.back().normal_armed); EXPECT_LT(r.trace.back().soc,.63);
}
TEST(M4AsyncRuntime, PreviousEpochWorkCannotDisturbCurrentNormalSession) { run(M4Scenario::OldEpoch); }
TEST(M4AsyncRuntime, PersistedGrantValueDoesNotChangePartialWriteProtection) {
    M4Config config; config.scenario=M4Scenario::PartialFront; config.first_epoch=17; config.rejoin_epoch=18;
    const auto result=run_m4_async(config); EXPECT_TRUE(result.passed)<<result.reason;
    EXPECT_GE(result.first_fault_ns,config.injection_ns); EXPECT_LE(result.all_protected_ns,config.injection_ns+100000000);
}
TEST(M4AsyncWall, IndependentOwnersRunActualNormalPath) {
    const auto r=run(M4Scenario::Normal,true); ASSERT_FALSE(r.trace.empty());
    EXPECT_NEAR(r.trace.back().angle_rad,std::atan(2.7*.02),.001); EXPECT_LT(r.trace.back().pressure_pa,1); EXPECT_GT(r.trace.back().torque_nm,50);
}
TEST(M4AsyncWall, IndependentFeedbackLossHasMeasuredProtectionResponse) { run(M4Scenario::FeedbackLoss,true); }
TEST(M4AsyncRuntime, TransportTraceCorrelatesOriginalAuthorityWithoutChangingPhysicalResponse) {
    M4Config c;const auto original=run_m4_async(c);c.transport_trace=true;const auto traced=run_m4_async(c);
    ASSERT_TRUE(original.passed);ASSERT_TRUE(traced.passed)<<traced.reason;EXPECT_FALSE(traced.event_overflow);
    ASSERT_EQ(original.trace.size(),traced.trace.size());
    for(std::size_t i=0;i<original.trace.size();++i) {
        const auto& a=original.trace[i];const auto& b=traced.trace[i];
        EXPECT_EQ(a.run_gate,b.run_gate);EXPECT_EQ(a.normal_armed,b.normal_armed);EXPECT_EQ(a.coordinator_fault,b.coordinator_fault);
        EXPECT_DOUBLE_EQ(a.angle_rad,b.angle_rad);EXPECT_DOUBLE_EQ(a.pressure_pa,b.pressure_pa);EXPECT_DOUBLE_EQ(a.torque_nm,b.torque_nm);
        EXPECT_DOUBLE_EQ(a.bus_v,b.bus_v);EXPECT_DOUBLE_EQ(a.soc,b.soc);EXPECT_EQ(a.model_sequence,b.model_sequence);
    }
    std::size_t checked=0;
    for(const auto& sent:traced.transport_events) {
        if(std::string(sent.stage)!="central-enqueued" || sent.operation!=3)continue;
        bool received=false,dispatched=false,completed=false,returned=false;
        for(const auto& e:traced.transport_events)if(e.epoch==sent.epoch && e.token==sent.token) {
            EXPECT_EQ(e.sent_ns,sent.sent_ns);EXPECT_EQ(e.original_source_ns,sent.original_source_ns);
            EXPECT_EQ(e.inner_deadline_ns,sent.inner_deadline_ns);EXPECT_EQ(e.deadline_ns,sent.deadline_ns);
            if(std::string(e.stage)=="zone-received")received=true;
            if(std::string(e.stage)=="zone-leaf-enqueued")dispatched=true;
            if(std::string(e.stage)=="leaf-completed") {completed=true;EXPECT_EQ(e.outcome,1);EXPECT_GT(e.payload_source_ns,0U);}
            if(std::string(e.stage)=="central-result-accepted") {returned=true;EXPECT_LT(e.time_ns,e.deadline_ns);EXPECT_LE(e.result_source_ns,e.time_ns);}
        }
        EXPECT_TRUE(received);EXPECT_TRUE(dispatched);EXPECT_TRUE(completed);EXPECT_TRUE(returned);++checked;
    }
    EXPECT_GT(checked,20U);
}
}  // namespace
