#include "normal_stop.hpp"
#include "control_diagnostics.hpp"

#include <gtest/gtest.h>
#include <algorithm>
#include <limits>

namespace {
using namespace stratadrive;
constexpr std::uint64_t kStart=1000000000,kMs=1000000;
std::uint64_t ns(std::uint32_t ms) { return kStart+static_cast<std::uint64_t>(ms)*kMs; }
template<class M> void metadata(M& m,std::uint32_t ms) {
    m.epoch=3; m.sequence=ms/10; m.source_time_ns=ns(ms); m.origin=can::ActuatorOrigin::NormalPath; m.local_state=can::ActuatorLocalState::Normal;
}
struct StopReadings { double speed{0},torque{0},pressure{100000}; };
central::NormalDriveReadinessInputs inputs(std::uint32_t ms,StopReadings readings = {}) {
    const auto speed=readings.speed, torque=readings.torque, pressure=readings.pressure;
    central::NormalDriveReadinessInputs in; in.epoch=3; in.session_enable_ns=kStart;
    in.front.health.emplace(); in.rear.health.emplace(); metadata(*in.front.health,ms); metadata(*in.rear.health,ms);
    in.front.health->phase=in.rear.health->phase=zone::ZonePhase::Ready;
    in.rear.health->scope=zone::ZoneScope::Rear;
    in.front.health->ready_for_normal=in.rear.health->ready_for_normal=true;
    in.front.steering_actual.emplace(); metadata(*in.front.steering_actual,ms); in.front.steering_actual->kind=can::SteeringFrameKind::Actual; in.front.steering_actual->angle_rad=0;
    in.front.brake_actual.emplace(); metadata(*in.front.brake_actual,ms); in.front.brake_actual->kind=can::BrakeFrameKind::Actual; in.front.brake_actual->pressure_pa=pressure;
    in.rear.drive_actual.emplace(); metadata(*in.rear.drive_actual,ms); in.rear.drive_actual->kind=can::DriveFrameKind::Actual;
    in.rear.drive_actual->torque_nm=torque; in.rear.drive_actual->wheel_speed=can::DriveWheelSpeed{speed,ns(ms)};
    can::BmsMessage limits,power; metadata(limits,ms); metadata(power,ms); limits.kind=can::BmsFrameKind::PowerLimits; power.kind=can::BmsFrameKind::PowerStatus;
    limits.content=can::BmsPowerLimits{30000,80000,can::BmsLimitReason::Nominal,can::BmsLimitReason::Nominal,ns(ms)};
    can::BmsPowerStatus p; p.state=can::BmsPowerState::HvReady; p.positive_contactor_closed=p.negative_contactor_closed=true;
    p.precharge_contactor_closed=false; p.hv_bus_voltage_v=400; p.condition_validity=31; p.condition_bits=7; p.input_time_ns=ns(ms); power.content=p;
    const can::BmsQualities q{can::BmsFieldQuality::Usable,can::BmsFieldQuality::Usable,can::BmsFieldQuality::NotApplicable};
    in.rear.power_status=can::BmsCurrentSample{power,q}; in.rear.power_limits=can::BmsCurrentSample{limits,q}; return in;
}
central::NormalStopRequest request(std::uint32_t ms) { return {{3,ms/10-1,ns(ms),ns(ms+60)},.02}; }
class NormalStopTest : public ::testing::Test {
protected:
    central::NormalStop stop;
    central::VehicleManagementDecision management;
    void SetUp() override {
        management.state=central::VehicleManagementState::Normal; management.normal_allowed=true;
        ASSERT_TRUE(stop.start_session(3,kStart)); ASSERT_TRUE(stop.begin(request(10),{4,9},ns(10)));
    }
    central::NormalStopPlan step(std::uint32_t ms,const central::NormalDriveReadinessInputs& in) {
        if(ms>10) { EXPECT_EQ(stop.receive_request(request(ms),ns(ms)),central::StopReceiveResult::Accepted); }
        auto out=stop.tick(in,management,ns(ms)); EXPECT_TRUE(out); return out.value();
    }
    central::NormalStopPlan confirm() { auto out=step(10,inputs(10)); for(std::uint32_t ms=20;ms<=70;ms+=10) out=step(ms,inputs(ms)); return out; }
};
TEST_F(NormalStopTest, BrakingKeepsEnableAndUsesBoundedChildrenFromContinuedIssuers) {
    const auto out=step(10,inputs(10,{20,50,0})); ASSERT_TRUE(out.vehicle);
    EXPECT_EQ(out.lifecycle.action,can::BmsPowerAction::Enable); EXPECT_EQ(out.lifecycle.identity.sequence,4U); EXPECT_EQ(out.vehicle->sequence,9U);
    EXPECT_LT(out.vehicle->acceleration_mps2,0); EXPECT_TRUE(out.vehicle->standstill_hold); EXPECT_FALSE(out.handoff_required);
    EXPECT_LE(out.lifecycle.identity.expires_at_ns,out.ancestor.identity.expires_at_ns); EXPECT_EQ(out.ancestor.identity.source_time_ns,ns(10));
}
TEST_F(NormalStopTest, FreshStoppedEvidenceAndTrustedExactAckPrecedeShutdownAndPhysicalOffPrecedesComplete) {
    const auto pending=confirm(); EXPECT_EQ(pending.state,central::NormalStopState::HandoffPending); EXPECT_EQ(pending.lifecycle.action,can::BmsPowerAction::Enable);
    auto wrong=pending.lease; ++wrong.sequence; EXPECT_FALSE(stop.acknowledge_handoff(wrong,ns(70)));
    ASSERT_TRUE(stop.acknowledge_handoff(pending.lease,ns(70))); management.state=central::VehicleManagementState::Stopping; management.normal_allowed=false;
    auto out=step(80,inputs(80)); EXPECT_EQ(out.lifecycle.action,can::BmsPowerAction::Shutdown); EXPECT_FALSE(out.vehicle);
    management.state=central::VehicleManagementState::Stopped; management.power_off_confirmed=true;
    EXPECT_EQ(step(90,inputs(90)).state,central::NormalStopState::PowerDown); // ACK alone, actual still READY
    auto off=inputs(100); auto& p=std::get<can::BmsPowerStatus>(off.rear.power_status->message.content);
    p.state=can::BmsPowerState::Off; p.hv_bus_voltage_v=0; p.positive_contactor_closed=p.negative_contactor_closed=false;
    EXPECT_EQ(step(100,off).state,central::NormalStopState::Complete);
}
TEST_F(NormalStopTest, CachedActualReadsCannotAdvanceConfirmationDwell) {
    central::NormalStopPlan out=step(10,inputs(10));
    for(std::uint32_t ms=20;ms<=90;ms+=10) {
        auto in=inputs(ms); const auto acquired=ms<=40?10:ms-30;
        in.rear.drive_actual->source_time_ns=ns(acquired); in.rear.drive_actual->wheel_speed->source_time_ns=ns(acquired);
        in.front.brake_actual->source_time_ns=ns(acquired); out=step(ms,in); EXPECT_EQ(out.state,central::NormalStopState::Braking);
    }
    auto in=inputs(100); in.rear.drive_actual->source_time_ns=in.rear.drive_actual->wheel_speed->source_time_ns=in.front.brake_actual->source_time_ns=ns(70);
    EXPECT_EQ(step(100,in).state,central::NormalStopState::HandoffPending);
}
TEST_F(NormalStopTest, SpeedTorqueAndPressureEachPreventHandoffWhilePacketsStayFresh) {
    for(std::uint32_t ms=10;ms<=200;ms+=10) {
        auto in=inputs(ms,{ms<90?.02:0,ms>=90 && ms<160?.2:0,ms>=160?99000.0:100000.0});
        EXPECT_EQ(step(ms,in).state,central::NormalStopState::Braking);
    }
}
TEST_F(NormalStopTest, FallingBrakePressureCannotStartTerminalHoldBeforeSettledDwell) {
    // M6 moving vehicle: zero speed/torque while friction is still releasing.
    // A terminal Hold at an old sensor pressure races the later physical hold.
    for(std::uint32_t ms=10;ms<=100;ms+=10) {
        const auto p=500000.0-ms*1000;
        EXPECT_EQ(step(ms,inputs(ms,{0,0,p})).state,central::NormalStopState::Braking);
    }
    for(std::uint32_t ms=110;ms<170;ms+=10)
        EXPECT_EQ(step(ms,inputs(ms,{0,0,100000})).state,central::NormalStopState::Braking);
    const auto p=step(170,inputs(170,{0,0,100000}));
    EXPECT_EQ(p.state,central::NormalStopState::HandoffPending);
    EXPECT_EQ(p.lease.source_time_ns,ns(170));EXPECT_LE(p.lease.expires_at_ns,p.ancestor.identity.expires_at_ns);
}
TEST_F(NormalStopTest, StableOldBrakingTargetIsNotSettledStandingHold) {
    for(std::uint32_t ms=10;ms<=100;ms+=10)
        EXPECT_EQ(step(ms,inputs(ms,{0,0,300000})).state,central::NormalStopState::Braking);
}
TEST_F(NormalStopTest, PriorAuthorityExpiryCannotBeRevivedByAFreshRequest) {
    ASSERT_TRUE(stop.tick(inputs(10),management,ns(10)));
    EXPECT_EQ(stop.receive_request(request(70),ns(70)),central::StopReceiveResult::Latched);
    EXPECT_EQ(stop.decision().fault,central::NormalStopFault::RequestLost);
}
TEST_F(NormalStopTest, RequestMutationAndWrongEpochAreRejectedWithoutExtendingLifetime) {
    auto mutated=request(10); ++mutated.identity.expires_at_ns; EXPECT_EQ(stop.receive_request(mutated,ns(10)),central::StopReceiveResult::Rejected);
    mutated=request(10); mutated.curvature_inv_m=.1; EXPECT_EQ(stop.receive_request(mutated,ns(10)),central::StopReceiveResult::Rejected);
    mutated=request(20); mutated.identity.epoch=4; EXPECT_EQ(stop.receive_request(mutated,ns(20)),central::StopReceiveResult::Rejected);
}
TEST_F(NormalStopTest, LossAfterConfirmedStopNeverFallsBackToDrivingOrShutdownSuccess) {
    confirm(); auto in=inputs(80,{1}); EXPECT_EQ(stop.receive_request(request(80),ns(80)),central::StopReceiveResult::Accepted);
    EXPECT_FALSE(stop.tick(in,management,ns(80))); EXPECT_EQ(stop.decision().fault,central::NormalStopFault::StopEvidenceLost);
}
TEST_F(NormalStopTest, MissingActualAndLocalProtectionFailClosed) {
    auto in=inputs(10); in.front.brake_actual.reset(); EXPECT_FALSE(stop.tick(in,management,ns(10)));
    EXPECT_EQ(stop.decision().fault,central::NormalStopFault::FeedbackUnavailable); EXPECT_TRUE(stop.decision().protection_required);
}
TEST_F(NormalStopTest, ClockRegressionAndFreshRequestCannotHealTheLatch) {
    ASSERT_TRUE(stop.tick(inputs(10),management,ns(10))); EXPECT_FALSE(stop.tick(inputs(9),management,ns(9)));
    EXPECT_EQ(stop.decision().fault,central::NormalStopFault::ClockError); EXPECT_FALSE(stop.start_session(4,ns(9)));
}
TEST(StopLease, DuplicateIdentityCannotExtendExpiryAndLateRenewalCannotHealLoss) {
    StopLeaseState state; const ActuatorStopLease lease{3,100,ns(10),ns(60)};
    ASSERT_TRUE(state.accept(lease,3,ns(10))); auto mutation=lease; ++mutation.expires_at_ns; EXPECT_FALSE(state.accept(mutation,3,ns(20)));
    EXPECT_TRUE(state.live(ns(59))); EXPECT_FALSE(state.live(ns(60))); EXPECT_FALSE(state.accept({3,101,ns(60),ns(100)},3,ns(60)));
}
TEST(StopLease, FirstTrustedIdentityMayBeLateInIndependentStopStreamButRenewalMustProgress) {
    StopLeaseState state; ASSERT_TRUE(state.accept({3,100,ns(10),ns(60)},3,ns(10)));
    EXPECT_FALSE(state.accept({3,111,ns(20),ns(70)},3,ns(20))); EXPECT_FALSE(state.accept({4,101,ns(20),ns(70)},3,ns(20)));
    EXPECT_TRUE(state.accept({3,101,ns(20),ns(70)},3,ns(20)));
}
TEST_F(NormalStopTest, PendingHandoffCannotBeExtendedByUnrelatedFreshStopRequests) {
    const auto out=confirm();
    for(std::uint32_t ms=80;ms<=120;ms+=10) {
        const auto pending=step(ms,inputs(ms)); EXPECT_EQ(pending.state,central::NormalStopState::HandoffPending);
        EXPECT_EQ(pending.ancestor.identity.source_time_ns,out.ancestor.identity.source_time_ns);
        EXPECT_EQ(pending.lifecycle.identity.expires_at_ns,out.lifecycle.identity.expires_at_ns);
    }
    EXPECT_EQ(stop.receive_request(request(130),ns(130)),central::StopReceiveResult::Latched);
    EXPECT_FALSE(stop.acknowledge_handoff(out.lease,ns(130))); EXPECT_EQ(stop.decision().fault,central::NormalStopFault::HandoffExpired);
}
TEST_F(NormalStopTest, ChildIssuersNeverWrapOrRestartAfterExhaustion) {
    central::NormalStop other; ASSERT_TRUE(other.start_session(3,kStart));
    ASSERT_TRUE(other.begin(request(10),{std::numeric_limits<std::uint32_t>::max(),0},ns(10)));
    ASSERT_TRUE(other.tick(inputs(10),management,ns(10))); ASSERT_EQ(other.receive_request(request(20),ns(20)),central::StopReceiveResult::Accepted);
    EXPECT_FALSE(other.tick(inputs(20),management,ns(20))); EXPECT_EQ(other.decision().fault,central::NormalStopFault::SequenceExhausted);
}
TEST_F(NormalStopTest, MovingAndPowerDownStagesHaveIndependentFiniteBudgets) {
    for(bool power_down:{false,true}) {
        central::NormalStopConfig config; config.braking_timeout_ns=80*kMs; config.shutdown_timeout_ns=40*kMs;
        central::NormalStop other{config}; ASSERT_TRUE(other.start_session(3,kStart)); ASSERT_TRUE(other.begin(request(10),{0,0},ns(10)));
        auto owner=management; bool failed=false;
        for(std::uint32_t ms=10;ms<=130;ms+=10) {
            if(ms>10) { ASSERT_EQ(other.receive_request(request(ms),ns(ms)),central::StopReceiveResult::Accepted); }
            const auto out=other.tick(inputs(ms,{power_down?0.0:20.0}),owner,ns(ms));
            if(!out) { failed=true; break; }
            if(out->state==central::NormalStopState::HandoffPending) { ASSERT_TRUE(other.acknowledge_handoff(out->lease,ns(ms))); owner.normal_allowed=false; owner.state=central::VehicleManagementState::Stopping; }
        }
        EXPECT_TRUE(failed); EXPECT_EQ(other.decision().fault,power_down?central::NormalStopFault::ShutdownTimeout:central::NormalStopFault::BrakingTimeout);
    }
}
TEST(StopLease, PreviousSessionSourceAndFutureSourceAreNotAuthorityForANewInit) {
    StopLeaseState state; state.reset(ns(20));
    EXPECT_FALSE(state.accept({3,100,ns(10),ns(60)},3,ns(20))); EXPECT_FALSE(state.accept({3,100,ns(21),ns(60)},3,ns(20)));
    EXPECT_TRUE(state.accept({3,100,ns(20),ns(60)},3,ns(20)));
}
TEST(NormalStopConfig, InvalidDecelerationOrConfirmationCannotOpenAStopPath) {
    central::NormalStopConfig c; c.deceleration_mps2=0; EXPECT_THROW(central::NormalStop{c},std::invalid_argument);
    c={}; c.confirmation_ns=kMs; EXPECT_THROW(central::NormalStop{c},std::invalid_argument);
}
TEST_F(NormalStopTest, DefaultBudgetAcceptsIdealTenKmhButTimesOutIdealThirtyKmh) {
    // Contract fixture, NOT a vehicle simulation: exact requested 1m/s^2 from
    // the first job, no lag/grade, and immediate standing pressure at zero.
    // Even this optimistic 30km/h trace cannot fit the existing 5s budget.
    for(double initial_kmh:{10.0,30.0}) {
        central::NormalStopConfig config;
        ASSERT_DOUBLE_EQ(config.deceleration_mps2,1.0);
        ASSERT_EQ(config.braking_timeout_ns,5000*kMs);
        central::NormalStop candidate(config);
        ASSERT_TRUE(candidate.start_session(3,kStart));
        ASSERT_TRUE(candidate.begin(request(10),{0,0},ns(10)));
        bool handoff=false;double last_speed=0;
        for(std::uint32_t ms=10;ms<=5010;ms+=10) {
            if(ms>10) { ASSERT_EQ(candidate.receive_request(request(ms),ns(ms)),central::StopReceiveResult::Accepted); }
            last_speed=std::max(0.0,initial_kmh/3.6-config.deceleration_mps2*(ms-10)/1000.0);
            auto plan=candidate.tick(inputs(ms,{last_speed/.355,0,last_speed>0?400000.0:100000.0}),management,ns(ms));
            if(!plan) { EXPECT_EQ(ms,5010U);break; }
            if(plan->handoff_required) {handoff=true;break;}
        }
        if(initial_kmh==10) {
            EXPECT_TRUE(handoff);EXPECT_EQ(candidate.decision().fault,central::NormalStopFault::None);
        } else {
            EXPECT_FALSE(handoff);EXPECT_NEAR(last_speed,30.0/3.6-5,1e-12);
            EXPECT_EQ(candidate.decision().fault,central::NormalStopFault::BrakingTimeout);
            EXPECT_TRUE(candidate.decision().protection_required);
            EXPECT_FALSE(candidate.tick(inputs(5020),management,ns(5020)));
        }
    }
}
TEST_F(NormalStopTest, ExplicitTenSecondBudgetAllowsIdealThirtyKmhHandoffWithoutChangingDefaults) {
    central::NormalStopConfig config;config.braking_timeout_ns=10000*kMs;
    central::NormalStop candidate(config);
    ASSERT_TRUE(candidate.start_session(3,kStart));
    ASSERT_TRUE(candidate.begin(request(10),{0,0},ns(10)));
    std::uint32_t handoff_ms=0;
    for(std::uint32_t ms=10;ms<=10010;ms+=10) {
        if(ms>10) {ASSERT_EQ(candidate.receive_request(request(ms),ns(ms)),central::StopReceiveResult::Accepted);}
        const auto speed=std::max(0.0,30.0/3.6-(ms-10)/1000.0);
        auto plan=candidate.tick(inputs(ms,{speed/.355,0,speed>0?400000.0:100000.0}),management,ns(ms));
        ASSERT_TRUE(plan);
        if(plan->handoff_required) {handoff_ms=ms;break;}
    }
    EXPECT_GT(handoff_ms,5010U);EXPECT_LT(handoff_ms,10010U);
    EXPECT_EQ(candidate.decision().fault,central::NormalStopFault::None);
    EXPECT_EQ(central::NormalStopConfig{}.braking_timeout_ns,5000*kMs);
}
diagnostics::Ledger diagnosed(diagnostics::EventQueue& queue) {
    diagnostics::Ledger ledger; diagnostics::Event e;
    while(queue.pop(e)) EXPECT_EQ(ledger.record(e),diagnostics::Result::Accepted);
    return ledger;
}
TEST_F(NormalStopTest, DiagnosticsRecordsNativeBrakingAndShutdownBudgetsAtTheirOwnOrigins) {
    for(bool shutdown:{false,true}) {
        diagnostics::EventQueue queue(10,20); diagnostics::ControlDiagnostics hook(queue,{10,20,diagnostics::Domain::Simulation,7,1});
        ASSERT_TRUE(hook.start_session(3,kStart));
        central::NormalStopConfig config; config.braking_timeout_ns=80*kMs; config.shutdown_timeout_ns=40*kMs;
        central::NormalStop c(config); ASSERT_TRUE(c.start_session(3,kStart)); ASSERT_TRUE(c.begin(request(10),{0,0},ns(10)));
        auto owner=management;
        for(std::uint32_t ms=10;ms<=130;ms+=10) {
            if(ms>10) { ASSERT_EQ(c.receive_request(request(ms),ns(ms)),central::StopReceiveResult::Accepted); }
            const auto out=c.tick(inputs(ms,{shutdown?0.:20.}),owner,ns(ms));
            if(!out) break;
            if(out->state==central::NormalStopState::HandoffPending) {
                ASSERT_TRUE(c.acknowledge_handoff(out->lease,ns(ms))); owner.normal_allowed=false; owner.state=central::VehicleManagementState::Stopping;
            }
        }
        hook.observe(c,ns(200)); hook.observe(c,ns(300)); const auto ledger=diagnosed(queue);
        ASSERT_EQ(ledger.records().size(),1U); const auto& r=ledger.records().front();
        EXPECT_EQ(r.key.code,shutdown?diagnostics::Code::ShutdownTimeout:diagnostics::Code::BrakingTimeout);
        EXPECT_EQ(r.first_detected.ns,ns(shutdown?110:90)); EXPECT_EQ(r.count,1U);
        const auto fault=std::find_if(ledger.events().begin(),ledger.events().end(),[](const auto& e){return e.kind==diagnostics::Kind::Fault;});
        ASSERT_NE(fault,ledger.events().end()); EXPECT_EQ(fault->times[1].ns,ns(shutdown?110:90));
        const auto& o=*c.fault_observations()[0]; EXPECT_EQ(o.phase_start_ns,ns(shutdown?70:10));
        EXPECT_EQ(o.config.braking_timeout_ns,80*kMs); EXPECT_EQ(o.config.shutdown_timeout_ns,40*kMs);
        EXPECT_TRUE(c.decision().protection_required);
    }
}
TEST_F(NormalStopTest, DiagnosticsSeparatesMissingFeedbackLostHoldRequestAndHandoffExpiry) {
    for(unsigned kind=0;kind<4;++kind) {
        diagnostics::EventQueue queue(10,20); diagnostics::ControlDiagnostics hook(queue,{10,20,diagnostics::Domain::Simulation,7,1});
        ASSERT_TRUE(hook.start_session(3,kStart)); central::NormalStop c;
        ASSERT_TRUE(c.start_session(3,kStart)); ASSERT_TRUE(c.begin(request(10),{0,0},ns(10)));
        if(kind==0) { auto in=inputs(10); in.front.brake_actual.reset(); EXPECT_FALSE(c.tick(in,management,ns(10))); }
        if(kind==1 || kind==3) {
            for(std::uint32_t ms=10;ms<=70;ms+=10) {
                if(ms>10) { ASSERT_EQ(c.receive_request(request(ms),ns(ms)),central::StopReceiveResult::Accepted); }
                ASSERT_TRUE(c.tick(inputs(ms),management,ns(ms)));
            }
            if(kind==1) { ASSERT_EQ(c.receive_request(request(80),ns(80)),central::StopReceiveResult::Accepted); EXPECT_FALSE(c.tick(inputs(80,{1}),management,ns(80))); }
            else for(std::uint32_t ms=80;ms<=130;ms+=10) { c.receive_request(request(ms),ns(ms)); c.tick(inputs(ms),management,ns(ms)); }
        }
        if(kind==2) { ASSERT_TRUE(c.tick(inputs(10),management,ns(10))); EXPECT_EQ(c.receive_request(request(70),ns(70)),central::StopReceiveResult::Latched); }
        hook.observe(c,ns(200)); const auto ledger=diagnosed(queue); ASSERT_EQ(ledger.records().size(),1U);
        const auto expected=kind<2?diagnostics::Code::StopEvidence:kind==2?diagnostics::Code::StopRequest:diagnostics::Code::Handoff;
        EXPECT_EQ(ledger.records().front().key.code,expected); EXPECT_TRUE(c.decision().protection_required);
        if(kind==3) {
            const auto fault=std::find_if(ledger.events().begin(),ledger.events().end(),[](const auto& e){return e.kind==diagnostics::Kind::Fault;});
            ASSERT_NE(fault,ledger.events().end()); EXPECT_EQ(fault->stop_lease.source.ns,ns(70)); EXPECT_EQ(fault->command.source.ns,ns(120));
        }
    }
}
TEST_F(NormalStopTest, DiagnosticsPreservesFirstFaultAndSeparateUntrustedClockFailure) {
    diagnostics::EventQueue queue(10,20); diagnostics::ControlDiagnostics hook(queue,{10,20,diagnostics::Domain::Simulation,7,1});
    ASSERT_TRUE(hook.start_session(3,kStart)); ASSERT_TRUE(stop.tick(inputs(10),management,ns(10)));
    EXPECT_EQ(stop.receive_request(request(70),ns(70)),central::StopReceiveResult::Latched);
    EXPECT_FALSE(stop.tick(inputs(9),management,ns(9))); hook.observe(stop,ns(200));
    const auto ledger=diagnosed(queue); ASSERT_EQ(ledger.records().size(),2U);
    EXPECT_EQ(ledger.records()[0].key.code,diagnostics::Code::StopRequest); EXPECT_EQ(ledger.records()[0].first_detected.ns,ns(70));
    EXPECT_EQ(ledger.records()[1].key.code,diagnostics::Code::Clock); EXPECT_EQ(ledger.records()[1].first_detected.ns,ns(9));
    EXPECT_FALSE(ledger.records()[1].first_detected.trusted);
}
TEST_F(NormalStopTest, DiagnosticsNeverTurnsRejectedRequestOrUpstreamProtectionIntoSpecificRoot) {
    diagnostics::EventQueue queue(10,20); diagnostics::ControlDiagnostics hook(queue,{10,20,diagnostics::Domain::Simulation,7,1});
    ASSERT_TRUE(hook.start_session(3,kStart)); auto wrong=request(20); wrong.identity.epoch=4;
    EXPECT_EQ(stop.receive_request(wrong,ns(20)),central::StopReceiveResult::Rejected);
    auto owner=management; owner.normal_allowed=false; EXPECT_FALSE(stop.tick(inputs(20),owner,ns(20)));
    hook.observe(stop,ns(30)); const auto ledger=diagnosed(queue);
    EXPECT_TRUE(ledger.records().empty()); EXPECT_EQ(ledger.events().back().kind,diagnostics::Kind::Observation);
    EXPECT_TRUE(ledger.events().back().cause_unknown);
}
} // namespace
