#include "speed_request.hpp"
#include "control_diagnostics.hpp"
#include <gtest/gtest.h>
#include <limits>
using namespace stratadrive;
namespace {
constexpr std::uint64_t ms=1000000;
can::DriveMessage sample(std::uint64_t source) {
    can::DriveMessage m;
    m.kind=can::DriveFrameKind::Actual; m.epoch=3; m.source_time_ns=source;
    m.torque_nm=0; m.wheel_speed=can::DriveWheelSpeed{10,source};
    return m;
}
TEST(SpeedRequestPropulsion, PreviousSelectionIdentityRequiredAndFaultLatches) {
    for(int fault=0;fault<8;++fault) {
        central::SpeedRequest c(.355,true);ASSERT_TRUE(c.start_session(3,100*ms));
        auto first=c.step_derived(120*ms,4,sample(118*ms),true);ASSERT_TRUE(first);
        central::PropulsionSelection f{3,0,130*ms,first->request.acceleration_mps2,24,12,true};
        if(fault==1)f.epoch=2;
        if(fault==2)f.request_sequence=1;
        if(fault==3)f.selection_ns=140*ms;
        if(fault==4)f.selection_ns=119*ms;
        if(fault==5)f.requested_acceleration_mps2=999;
        if(fault==6)f.limited=false;
        if(fault==7)f.selected_propulsion_nm=std::numeric_limits<double>::quiet_NaN();
        EXPECT_FALSE(c.step_derived(140*ms,4,sample(138*ms),true,fault?std::optional{f}:std::nullopt));
        EXPECT_EQ(c.fault(),central::SpeedRequestFault::PropulsionSelection);
        EXPECT_FALSE(c.step_derived(160*ms,4,sample(158*ms),true,f));
        ASSERT_TRUE(c.start_session(4,160*ms));auto fresh=sample(160*ms);fresh.epoch=4;
        EXPECT_TRUE(c.step_derived(160*ms,0,fresh,true));
    }
}
TEST(SpeedRequestPropulsion, AcceptedSelectionDoesNotRenewSensorAuthority) {
    central::SpeedRequest c(.355,true);ASSERT_TRUE(c.start_session(3,100*ms));
    auto first=c.step_derived(120*ms,4,sample(118*ms),true);ASSERT_TRUE(first);
    central::PropulsionSelection f{3,0,130*ms,first->request.acceleration_mps2,24,12,true};
    auto r=c.step_derived(140*ms,4,sample(138*ms),true,f);ASSERT_TRUE(r);
    EXPECT_EQ(r->input.source_time_ns,138*ms);EXPECT_EQ(r->request.source_time_ns,140*ms);
    EXPECT_EQ(r->input.expires_at_ns,198*ms+1);
    EXPECT_DOUBLE_EQ(c.state().integral,0);
}
TEST(SpeedRequest, PreservesAcquisitionAcrossUnitsAndChildAuthority) {
    central::SpeedRequest c; ASSERT_TRUE(c.start_session(3,100*ms));
    const auto r=c.step(120*ms,4,sample(118*ms),true); ASSERT_TRUE(r);
    EXPECT_DOUBLE_EQ(c.state().sample->speed_mps,3);
    EXPECT_EQ(r->source_time_ns,118*ms); EXPECT_EQ(r->expires_at_ns,148*ms+1);
    EXPECT_EQ(r->epoch,3); EXPECT_EQ(r->sequence,0); EXPECT_FALSE(r->standstill_hold);
    const auto next=c.step(140*ms,4,sample(138*ms),true); ASSERT_TRUE(next);
    EXPECT_EQ(next->sequence,1); EXPECT_DOUBLE_EQ(next->acceleration_mps2,.08);
}
TEST(SpeedRequest, NewEnvelopeCannotRefreshFrozenWheelAndNewSessionClearsLatch) {
    central::SpeedRequest c; ASSERT_TRUE(c.start_session(3,100*ms));
    ASSERT_TRUE(c.step(120*ms,4,sample(118*ms),true));
    auto renewed=sample(118*ms); renewed.sequence=20; renewed.source_time_ns=140*ms;
    EXPECT_FALSE(c.step(140*ms,4,renewed,true)); EXPECT_EQ(c.fault(),central::SpeedRequestFault::Source);
    EXPECT_FALSE(c.step(160*ms,4,sample(158*ms),true));
    EXPECT_FALSE(c.start_session(3,160*ms)); EXPECT_FALSE(c.start_session(4,119*ms));
    ASSERT_TRUE(c.start_session(4,160*ms));
    auto fresh=sample(162*ms); fresh.epoch=4;
    ASSERT_TRUE(c.step(164*ms,0,fresh,true)); EXPECT_DOUBLE_EQ(c.state().integral,0); // slew saturation freezes the integral
}
TEST(SpeedRequest, PermissionLossLatchesWithoutSuccessfulZero) {
    central::SpeedRequest c; ASSERT_TRUE(c.start_session(3,100*ms));
    EXPECT_FALSE(c.step(120*ms,0,sample(118*ms),false));
    EXPECT_EQ(c.fault(),central::SpeedRequestFault::Permission);
    EXPECT_FALSE(c.step(140*ms,0,sample(138*ms),true));
}
TEST(SpeedRequest, MissedOrDuplicateControlReleaseCannotCatchUp) {
    for(const auto gap:{0ULL,19ULL,21ULL,40ULL}) {
        central::SpeedRequest c; ASSERT_TRUE(c.start_session(3,100*ms));
        ASSERT_TRUE(c.step(120*ms,4,sample(118*ms),true));
        EXPECT_FALSE(c.step((120+gap)*ms,4,sample((120+gap)*ms),true));
        EXPECT_EQ(c.fault(),central::SpeedRequestFault::Controller);
    }
}
TEST(SpeedRequest, RejectsMissingWrongEpochAndNonfiniteWheel) {
    for(int kind=0;kind<5;++kind) {
        central::SpeedRequest c; ASSERT_TRUE(c.start_session(3,100*ms));
        auto m=sample(118*ms);
        if(kind==0)m.epoch=2;
        if(kind==1)m.wheel_speed.reset();
        if(kind==2)m.wheel_speed->value_rad_s=std::numeric_limits<double>::quiet_NaN();
        if(kind==3)m.wheel_speed->value_rad_s=-1;
        if(kind==4)m.kind=can::DriveFrameKind::Command;
        EXPECT_FALSE(c.step(120*ms,4,m,true)); EXPECT_EQ(c.fault(),central::SpeedRequestFault::Feedback);
    }
}
TEST(SpeedRequest, SourceAgeEnableFutureAndInclusiveBoundary) {
    for(const auto source:{99*ms,120*ms-30*ms-1,120*ms+1}) {
        central::SpeedRequest c; ASSERT_TRUE(c.start_session(3,100*ms));
        EXPECT_FALSE(c.step(120*ms,4,sample(source),true));
        EXPECT_EQ(c.fault(),central::SpeedRequestFault::Source);
    }
    central::SpeedRequest c; ASSERT_TRUE(c.start_session(3,100*ms));
    ASSERT_TRUE(c.step(130*ms,0,sample(100*ms),true));
}
TEST(SpeedRequest, ExplicitRadiusUsesPhysicalCalibrationAndRejectsInvalidConfiguration) {
    central::SpeedRequest c(.355); ASSERT_TRUE(c.start_session(3,100*ms));
    ASSERT_TRUE(c.step(120*ms,4,sample(118*ms),true));
    EXPECT_DOUBLE_EQ(c.state().sample->speed_mps,3.55);
    for(double bad:{0.,-1.,1.01,std::numeric_limits<double>::quiet_NaN()}) {
        EXPECT_THROW(central::SpeedRequest{bad},std::invalid_argument);
    }
}
TEST(SpeedRequest, UninitializedAndInvalidTargetFailClosed) {
    central::SpeedRequest c;
    EXPECT_FALSE(c.step(120*ms,0,sample(118*ms),true));
    EXPECT_EQ(c.fault(),central::SpeedRequestFault::Session);
    ASSERT_TRUE(c.start_session(3,100*ms));
    EXPECT_FALSE(c.step(120*ms,12,sample(118*ms),true));
    EXPECT_EQ(c.fault(),central::SpeedRequestFault::Controller);
}
TEST(SpeedRequest, DerivedRequestRetainsBothClocksAndThirtyMillisecondIngressLimit) {
    central::SpeedRequest c(.355);ASSERT_TRUE(c.start_session(3,100*ms));
    const auto r=c.step_derived(130*ms,4,sample(100*ms),true);ASSERT_TRUE(r);
    EXPECT_EQ(r->request.source_time_ns,130*ms);EXPECT_EQ(r->request.expires_at_ns,160*ms+1);
    EXPECT_EQ(r->input.source_time_ns,100*ms);EXPECT_EQ(r->input.expires_at_ns,160*ms+1);
    EXPECT_EQ(c.state().sample->source_ns,100*ms);
    EXPECT_FALSE(c.step_derived(150*ms,4,sample(120*ms-1),true));
    EXPECT_EQ(c.fault(),central::SpeedRequestFault::Source);
    EXPECT_FALSE(c.step_derived(170*ms,4,sample(170*ms),true));
}
TEST(SpeedDiagnostics, SuccessfulSnapshotRetainsNativeInputAndExactReturnedDerivedRoot) {
    central::SpeedRequest c; ASSERT_TRUE(c.start_session(3,100*ms));
    ASSERT_FALSE(c.success_observation()); const auto input=sample(118*ms);
    const auto request=c.step_derived(120*ms,4,input,true); ASSERT_TRUE(request); ASSERT_TRUE(c.success_observation());
    const auto original=*c.success_observation(); EXPECT_EQ(original.epoch,3U); EXPECT_EQ(original.enable_ns,100*ms);
    EXPECT_EQ(original.issued_ns,120*ms); EXPECT_EQ(original.input.wheel_speed->source_time_ns,118*ms);
    EXPECT_EQ(original.request.source_time_ns,request->request.source_time_ns); EXPECT_EQ(original.request.expires_at_ns,request->request.expires_at_ns);
    EXPECT_EQ(original.request.sequence,request->request.sequence); EXPECT_DOUBLE_EQ(original.request.acceleration_mps2,request->request.acceleration_mps2);
    EXPECT_FALSE(c.step(140*ms,4,std::nullopt,true)); EXPECT_EQ(c.success_observation()->issued_ns,original.issued_ns);
    ASSERT_TRUE(c.start_session(4,140*ms)); EXPECT_FALSE(c.success_observation());
}
TEST(SpeedDiagnostics, FailedDerivedExpiryNeverPublishesSuccessfulRoot) {
    central::SpeedRequest c; const auto end=std::numeric_limits<std::uint64_t>::max();
    ASSERT_TRUE(c.start_session(3,end-40*ms));
    EXPECT_FALSE(c.step_derived(end-10*ms,0,sample(end-11*ms),true));
    EXPECT_EQ(c.fault(),central::SpeedRequestFault::Source); EXPECT_FALSE(c.success_observation());
}
TEST(SpeedDiagnostics, FirstSourceFailureRetainsNativeTimeInputAndControllerDetail) {
    diagnostics::EventQueue queue(10,20); diagnostics::ControlDiagnostics hook(queue,{10,20,diagnostics::Domain::Simulation,7,1});
    central::SpeedRequest c; ASSERT_TRUE(c.start_session(3,100*ms)); ASSERT_TRUE(hook.start_session(3,100*ms));
    ASSERT_TRUE(c.step(120*ms,4,sample(118*ms),true));
    EXPECT_FALSE(c.step(140*ms,4,sample(118*ms),true));
    ASSERT_TRUE(c.fault_observation()); EXPECT_EQ(c.fault_observation()->detected_ns,140*ms);
    EXPECT_FALSE(c.step(160*ms,4,sample(158*ms),true)); hook.observe(c,200*ms); hook.observe(c,220*ms);
    diagnostics::Ledger ledger; diagnostics::Event event;
    while(queue.pop(event)) ASSERT_EQ(ledger.record(event),diagnostics::Result::Accepted);
    ASSERT_EQ(ledger.records().size(),1U); const auto& r=ledger.records().front();
    EXPECT_EQ(r.key.code,diagnostics::Code::SpeedInput); EXPECT_EQ(r.count,1U); EXPECT_EQ(r.first_detected.ns,140*ms);
    const auto& raw=ledger.events()[1]; EXPECT_EQ(raw.native_reason,4U<<8); EXPECT_EQ(raw.source.source.ns,118*ms);
    EXPECT_EQ(raw.times[static_cast<std::size_t>(diagnostics::Time::Observed)].ns,200*ms);
    ASSERT_TRUE(c.start_session(4,220*ms)); EXPECT_FALSE(c.fault_observation());
}
TEST(SpeedDiagnostics, MissingInputAndPiTargetFailureMapToDifferentCodesWithoutDebounce) {
    for(bool missing:{false,true}) {
        diagnostics::EventQueue queue(10,20); diagnostics::ControlDiagnostics hook(queue,{10,20,diagnostics::Domain::Simulation,7,1});
        central::SpeedRequest c; ASSERT_TRUE(c.start_session(3,100*ms)); ASSERT_TRUE(hook.start_session(3,100*ms));
        EXPECT_FALSE(c.step(120*ms,missing?4:12,missing?std::nullopt:std::optional{sample(118*ms)},true)); hook.observe(c,120*ms);
        diagnostics::Ledger ledger; diagnostics::Event e;
        while(queue.pop(e)) ASSERT_EQ(ledger.record(e),diagnostics::Result::Accepted);
        ASSERT_EQ(ledger.records().size(),1U);
        EXPECT_EQ(ledger.records().front().key.code,missing?diagnostics::Code::SpeedInput:diagnostics::Code::CentralControl);
        EXPECT_EQ(ledger.events().back().native_reason,missing?3U<<8:(5U<<8)|5U);
        EXPECT_EQ(c.fault_observation()->controller_reason,missing?central::SpeedPIReason::Normal:central::SpeedPIReason::Target);
    }
}
TEST(SpeedDiagnostics, SourceBoundaryAndPermissionPropagationNeverInventRootFaults) {
    diagnostics::EventQueue queue(10,20); diagnostics::ControlDiagnostics hook(queue,{10,20,diagnostics::Domain::Simulation,7,1});
    central::SpeedRequest c; ASSERT_TRUE(c.start_session(3,100*ms)); ASSERT_TRUE(hook.start_session(3,100*ms));
    ASSERT_TRUE(c.step(130*ms,4,sample(100*ms),true)); hook.observe(c,130*ms);
    EXPECT_FALSE(c.step(150*ms,4,sample(150*ms),false)); hook.observe(c,160*ms);
    diagnostics::Ledger ledger; diagnostics::Event e;
    while(queue.pop(e)) ASSERT_EQ(ledger.record(e),diagnostics::Result::Accepted);
    EXPECT_TRUE(ledger.records().empty()); EXPECT_TRUE(ledger.events().back().cause_unknown);
    EXPECT_EQ(ledger.events().back().native_reason,2U<<8);
}
} // namespace
