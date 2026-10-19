#include "rear_power_gateway.hpp"
#include "rear_power_control.hpp"
#include "control_allocation.hpp"
#include "command_gateway.hpp"
#include "power_model.hpp"
#include "drive_sil_plant.hpp"
#include "front_startup_control.hpp"
#include "normal_stop_control.hpp"
#include "zone_feedback_monitor.hpp"
#include "vehicle_coordinator_port.hpp"
#include "steering_response.hpp"
#include "brake_pressure_response.hpp"
#include "vehicle_session_init.hpp"
#include "session_loop.hpp"
#include "multirate_fixture.hpp"

#include <gtest/gtest.h>
#include <vector>
#include <memory>

namespace {
using namespace stratadrive;
using zone::RearPowerResult;
constexpr std::uint64_t kStart=1000000000,kMs=1000000;
std::uint64_t ns(std::uint32_t ms) { return kStart+static_cast<std::uint64_t>(ms)*kMs; }
struct TestStamp { std::uint32_t milliseconds,sequence; };
template<class M> void meta(M& m,TestStamp stamp) {
    m.epoch=3; m.sequence=stamp.sequence; m.source_time_ns=ns(stamp.milliseconds); m.origin=can::ActuatorOrigin::NormalPath; m.local_state=can::ActuatorLocalState::Normal;
}
can::BmsMessage limits(std::uint32_t ms,std::uint32_t seq) {
    can::BmsMessage m; meta(m,{ms,seq}); m.kind=can::BmsFrameKind::PowerLimits; m.causal_sequence=seq;
    m.content=can::BmsPowerLimits{30000,80000,can::BmsLimitReason::Nominal,can::BmsLimitReason::Nominal,ns(ms)}; return m;
}
can::BmsMessage status(std::uint32_t ms,std::uint32_t seq,bool ready) {
    can::BmsMessage m; meta(m,{ms,seq}); m.kind=can::BmsFrameKind::PowerStatus;
    can::BmsPowerStatus s; s.state=ready?can::BmsPowerState::HvReady:can::BmsPowerState::Off;
    s.positive_contactor_closed=s.negative_contactor_closed=ready; s.precharge_contactor_closed=false;
    s.hv_bus_voltage_v=ready?400:0; s.condition_bits=7; s.condition_validity=31; s.input_time_ns=ns(ms); s.input_sequence=seq;
    s.accepted_request_source_time_ns=ready?ns(10):0; m.content=s; return m;
}
can::BmsMessage request(std::uint32_t ms,std::uint32_t seq) {
    can::BmsMessage m; meta(m,{ms,seq}); m.kind=can::BmsFrameKind::PowerRequest; m.causal_sequence=seq;
    m.content=can::BmsPowerRequest{can::BmsPowerAction::Enable,ns(ms+40),ns(ms)}; return m;
}
can::BmsMessage permission(std::uint32_t ms,std::uint32_t seq,bool allow=false) {
    can::BmsMessage m; meta(m,{ms,seq}); m.kind=can::BmsFrameKind::DrivePermission; m.causal_sequence=allow?seq:0;
    m.content=can::BmsDriveGrant{allow?can::BmsDrivePermission::AllowNormal:can::BmsDrivePermission::Inhibit,
        allow?1U:0U,allow?ns(20):0,allow?ns(10):0,ns(ms+30)}; return m;
}
class Port : public zone::RearPowerPort {
public:
    struct Sent { can::BmsFrame frame; zone::RearPowerDelivery delivery; };
    std::uint64_t now{kStart},delay{0}; std::size_t calls{0},fail_call{0},protections{0},arms{0}; bool arm_ok{true},ack{true};
    std::vector<Sent> sent;
    simulation::RearPowerControl* control{nullptr}; vecu::PowerController* power{nullptr}; vecu::DriveController* drive{nullptr};
    zone::CommandGateway* commands{nullptr}; can::BmsReceiver* observed_permission{nullptr};
    std::uint64_t clock_delay_ns{0};
    std::uint64_t now_ns() noexcept override { now+=clock_delay_ns; return now; }
    bool arm_normal_commands(std::uint32_t epoch,std::uint64_t time) noexcept override {
        ++arms;
        return arm_ok && (!control || control->arm_normal_commands(epoch,time)) && (!commands || commands->arm());
    }
    bool protect(zone::ZoneScope scope,zone::ProtectionCause cause,std::uint64_t time) noexcept override {
        ++protections; return control?control->protect(scope,cause,time):ack;
    }
    bool send(const can::BmsFrame& frame,const zone::RearPowerDelivery& delivery) noexcept override {
        try {
            now+=delay; ++calls; if(calls==fail_call || now>=delivery.expires_at_ns) return false;
            if(control && !control->stage_context(frame,delivery)) return false;
            const auto kind=delivery.message.kind;
            if(kind==can::BmsFrameKind::PowerRequest && power && power->receive(frame,now,delivery.parent?&*delivery.parent:nullptr).decision!=can::ActuatorReceiveDecision::Accepted) return false;
            if(kind==can::BmsFrameKind::PowerLimits && drive && drive->receive_limits(frame,now).decision!=can::ActuatorReceiveDecision::Accepted) return false;
            if(kind==can::BmsFrameKind::DrivePermission) {
                if(drive && drive->receive_permission(frame,now,delivery.parent?&*delivery.parent:nullptr).decision!=can::ActuatorReceiveDecision::Accepted) return false;
                if(observed_permission && observed_permission->receive(frame,now,delivery.parent?&*delivery.parent:nullptr).decision!=can::ActuatorReceiveDecision::Accepted) return false;
            }
            sent.push_back({frame,delivery}); return true;
        } catch(...) { return false; }
    }
};
class RearPowerGatewayTest : public ::testing::Test {
protected:
    Port port; zone::RearPowerGateway gateway{port};
    can::BmsTxState limits_tx{can::BmsFrameKind::PowerLimits},status_tx{can::BmsFrameKind::PowerStatus};
    void SetUp() override { ASSERT_TRUE(gateway.start_session(3,kStart)); }
    void observe(std::uint32_t ms,std::uint32_t seq,bool ready=false) {
        port.now=ns(ms); const auto l=can::encode_bms_frame(limits(ms,seq),limits_tx), s=can::encode_bms_frame(status(ms,seq,ready),status_tx);
        ASSERT_TRUE(l); ASSERT_TRUE(s); ASSERT_EQ(gateway.receive_limits(*l),RearPowerResult::Accepted); ASSERT_EQ(gateway.receive_status(*s),RearPowerResult::Accepted);
    }
    void root(std::uint32_t ms,std::uint32_t seq=0) { ASSERT_EQ(gateway.authorize_request({{3,seq,ns(ms),ns(ms+60)},can::BmsPowerAction::Enable}),RearPowerResult::Accepted); }
    void seed() {
        observe(10,0); root(10); ASSERT_EQ(gateway.enqueue_power(request(10,0)),RearPowerResult::Accepted);
        ASSERT_EQ(gateway.enqueue_permission(permission(10,0)),RearPowerResult::Accepted); ASSERT_EQ(gateway.dispatch(),3U);
    }
    void ready() { seed(); observe(20,1,true); root(20,1); ASSERT_TRUE(gateway.arm_normal_commands()); }
};
TEST_F(RearPowerGatewayTest, EnableCannotSupplyItsOwnParentAndActionMustMatchTrustedRoot) {
    port.now=ns(10); EXPECT_EQ(gateway.enqueue_power(request(10,0)),RearPowerResult::ParentRejected); root(10);
    auto bad=request(10,0); std::get<can::BmsPowerRequest>(bad.content).action=can::BmsPowerAction::Shutdown;
    EXPECT_EQ(gateway.enqueue_power(bad),RearPowerResult::ParentRejected);
    bad=request(10,0); bad.causal_sequence=1; EXPECT_EQ(gateway.enqueue_power(bad),RearPowerResult::Rejected);
    EXPECT_EQ(gateway.enqueue_power(request(10,0)),RearPowerResult::Accepted);
}
TEST_F(RearPowerGatewayTest, ImmutableLifecycleRootCannotChangeActionOrDeadline) {
    port.now=ns(10); root(10);
    EXPECT_EQ(gateway.authorize_request({{3,0,ns(10),ns(69)},can::BmsPowerAction::Enable}),RearPowerResult::ParentRejected);
    EXPECT_EQ(gateway.authorize_request({{3,0,ns(10),ns(70)},can::BmsPowerAction::Shutdown}),RearPowerResult::ParentRejected);
    EXPECT_EQ(gateway.authorize_request({{2,1,ns(10),ns(70)},can::BmsPowerAction::Enable}),RearPowerResult::ParentRejected);
}
TEST_F(RearPowerGatewayTest, DispatchesInhibitBeforeLimitsAndEnablePreservingSourceAndRoot) {
    seed(); ASSERT_EQ(port.sent.size(),3U);
    EXPECT_EQ(port.sent[0].delivery.message.kind,can::BmsFrameKind::DrivePermission);
    EXPECT_EQ(can::decode_bms_frame(port.sent[1].frame)->kind,can::BmsFrameKind::DriveBatteryLimits);
    EXPECT_EQ(port.sent[2].delivery.message.kind,can::BmsFrameKind::PowerRequest);
    ASSERT_TRUE(port.sent[2].delivery.parent); EXPECT_EQ(port.sent[2].delivery.parent->source_time_ns,ns(10));
    EXPECT_EQ(can::decode_bms_frame(port.sent[1].frame)->source_time_ns,ns(10)); EXPECT_EQ(gateway.dispatch(),0U);
}
TEST_F(RearPowerGatewayTest, CachedStatusAndLimitsNeverAcquireTheQueryTime) {
    seed(); port.now=ns(30); const auto s=gateway.power_status(),l=gateway.power_limits(); ASSERT_TRUE(s); ASSERT_TRUE(l);
    EXPECT_EQ(s->message.source_time_ns,ns(10)); EXPECT_EQ(std::get<can::BmsPowerLimits>(l->message.content).input_time_ns,ns(10));
}
TEST_F(RearPowerGatewayTest, AllowRequiresExplicitArmAndAnActuallySentEnableAcknowledgement) {
    seed(); port.now=ns(20); root(20,1);
    EXPECT_EQ(gateway.enqueue_permission(permission(20,1,true)),RearPowerResult::NotReady); EXPECT_FALSE(gateway.arm_normal_commands());
    auto s=status(20,1,true); std::get<can::BmsPowerStatus>(s.content).accepted_request_source_time_ns=ns(11);
    const auto f=can::encode_bms_frame(s,status_tx); ASSERT_TRUE(f); ASSERT_EQ(gateway.receive_status(*f),RearPowerResult::Accepted);
    EXPECT_FALSE(gateway.arm_normal_commands()); EXPECT_EQ(port.arms,0U);
}
TEST_F(RearPowerGatewayTest, ReadyAcknowledgementAllowsOneTrustedArmAndBoundedGrant) {
    ready(); EXPECT_EQ(port.arms,1U); EXPECT_FALSE(gateway.arm_normal_commands());
    EXPECT_EQ(gateway.enqueue_power(request(20,1)),RearPowerResult::Accepted);
    EXPECT_EQ(gateway.enqueue_permission(permission(20,1,true)),RearPowerResult::Accepted);
    EXPECT_EQ(gateway.dispatch(),3U); EXPECT_EQ(port.sent.back().delivery.message.kind,can::BmsFrameKind::DrivePermission);
    EXPECT_EQ(port.sent.back().delivery.parent->sequence,1U); EXPECT_EQ(port.sent.back().delivery.expires_at_ns,ns(50));
}
TEST_F(RearPowerGatewayTest, ReadyBitsCannotArmWithDegradedStatusOrInitLimits) {
    seed(); port.now=ns(20); root(20,1);
    auto s=status(20,1,true); s.local_state=can::ActuatorLocalState::Degraded;
    auto f=can::encode_bms_frame(s,status_tx); ASSERT_TRUE(f);
    ASSERT_EQ(gateway.receive_status(*f),RearPowerResult::Accepted); EXPECT_FALSE(gateway.arm_normal_commands());
    s=status(21,2,true); port.now=ns(21); f=can::encode_bms_frame(s,status_tx); ASSERT_TRUE(f);
    ASSERT_EQ(gateway.receive_status(*f),RearPowerResult::Accepted);
    auto l=limits(21,1); l.local_state=can::ActuatorLocalState::Init;
    f=can::encode_bms_frame(l,limits_tx); ASSERT_TRUE(f);
    ASSERT_EQ(gateway.receive_limits(*f),RearPowerResult::Accepted); EXPECT_FALSE(gateway.arm_normal_commands());
    EXPECT_EQ(port.arms,0U);
}
TEST_F(RearPowerGatewayTest, GrantCannotOutliveAcknowledgedPowerRequestOrUseAnUnknownStatus) {
    ready(); auto grant=permission(20,1,true); std::get<can::BmsDriveGrant>(grant.content).power_status_sequence=7;
    EXPECT_EQ(gateway.enqueue_permission(grant),RearPowerResult::NotReady);
    grant=permission(20,1,true); std::get<can::BmsDriveGrant>(grant.content).expires_at_ns=ns(61);
    EXPECT_EQ(gateway.enqueue_permission(grant),RearPowerResult::NotReady);
}
TEST_F(RearPowerGatewayTest, FailedLeafArmLatchesInsteadOfForwardingAllow) {
    seed(); observe(20,1,true); root(20,1); port.arm_ok=false;
    EXPECT_FALSE(gateway.arm_normal_commands()); EXPECT_EQ(gateway.poll().safety.cause,zone::ProtectionCause::UpstreamLost);
    EXPECT_EQ(gateway.enqueue_permission(permission(20,1,true)),RearPowerResult::Latched);
}
TEST_F(RearPowerGatewayTest, MissingAnyCriticalStreamLatchesBeforeLateFreshData) {
    seed(); port.now=ns(50); EXPECT_EQ(gateway.poll().safety.cause,zone::ProtectionCause::CommandExpired);
    EXPECT_EQ(gateway.enqueue_permission(permission(50,1)),RearPowerResult::Latched); EXPECT_EQ(port.protections,1U);
}
TEST_F(RearPowerGatewayTest, StartupTimeoutAndClockRollbackCannotBeHiddenByOtherInputs) {
    port.now=ns(80); EXPECT_EQ(gateway.poll().safety.cause,zone::ProtectionCause::UpstreamLost);
    EXPECT_FALSE(gateway.start_session(4,kStart)); ASSERT_TRUE(gateway.start_session(4,ns(80)));
    port.now=ns(79); EXPECT_EQ(gateway.poll().safety.cause,zone::ProtectionCause::ClockError);
}
TEST_F(RearPowerGatewayTest, OverflowDiscardsBacklogAndPendingProtectionRetriesOncePerPoll) {
    seed(); port.ack=false;
    for(std::uint32_t i=0;i<=zone::RearPowerGateway::kCapacity;++i) {
        port.now=ns(20+i); const auto r=gateway.enqueue_permission(permission(20+i,1+i));
        EXPECT_EQ(r,i<zone::RearPowerGateway::kCapacity?RearPowerResult::Accepted:RearPowerResult::Latched);
    }
    EXPECT_EQ(port.protections,1U); EXPECT_FALSE(gateway.poll().safety.handoff_accepted); EXPECT_EQ(port.protections,2U);
    port.ack=true; EXPECT_TRUE(gateway.poll().safety.handoff_accepted); EXPECT_EQ(gateway.dispatch(),0U);
}
TEST_F(RearPowerGatewayTest, SendFailureAndFinalEnqueueExpiryNeverContinueTheBatch) {
    seed(); port.now=ns(20); ASSERT_EQ(gateway.enqueue_permission(permission(20,1)),RearPowerResult::Accepted); port.fail_call=4;
    EXPECT_EQ(gateway.dispatch(),0U); EXPECT_EQ(gateway.poll().safety.cause,zone::ProtectionCause::SendFailure); EXPECT_EQ(port.calls,4U);
}
TEST_F(RearPowerGatewayTest, TimeConsumedByThePortCannotEnqueueAnExpiredDelivery) {
    seed(); port.now=ns(20); ASSERT_EQ(gateway.enqueue_permission(permission(20,1)),RearPowerResult::Accepted); port.delay=30*kMs;
    EXPECT_EQ(gateway.dispatch(),0U); EXPECT_EQ(gateway.poll().safety.cause,zone::ProtectionCause::CommandExpired); EXPECT_EQ(port.sent.size(),3U);
}
TEST(RearPowerSources, EachMissingSourceLatchesWhileTheOtherThreeKeepUpdating) {
    for(int missing=0;missing<4;++missing) {
        SCOPED_TRACE(missing); Port port; zone::RearPowerGateway g{port}; ASSERT_TRUE(g.start_session(3,kStart));
        can::BmsTxState lt{can::BmsFrameKind::PowerLimits},st{can::BmsFrameKind::PowerStatus};
        bool lost=false;
        for(std::uint32_t ms=10;ms<=90;ms+=10) {
            port.now=ns(ms); const auto seq=ms/10-1;
            if(g.poll().safety.cause!=zone::ProtectionCause::None) { lost=true; break; }
            ASSERT_EQ(g.authorize_request({{3,seq,port.now,ns(ms+60)},can::BmsPowerAction::Enable}),RearPowerResult::Accepted);
            if(ms==10 || missing!=0) { ASSERT_EQ(g.enqueue_power(request(ms,seq)),RearPowerResult::Accepted); }
            if(ms==10 || missing!=1) { ASSERT_EQ(g.enqueue_permission(permission(ms,seq)),RearPowerResult::Accepted); }
            if(ms==10 || missing!=2) { const auto f=can::encode_bms_frame(limits(ms,seq),lt); ASSERT_TRUE(f); ASSERT_EQ(g.receive_limits(*f),RearPowerResult::Accepted); }
            if(ms==10 || missing!=3) { const auto f=can::encode_bms_frame(status(ms,seq,false),st); ASSERT_TRUE(f); ASSERT_EQ(g.receive_status(*f),RearPowerResult::Accepted); }
            g.dispatch();
        }
        EXPECT_TRUE(lost); EXPECT_EQ(port.protections,1U);
    }
}
TEST_F(RearPowerGatewayTest, LossOfActualReadyRevokesNormalEvenWhilePacketsRemainFresh) {
    ready(); port.now=ns(21); auto s=status(21,2,false); const auto frame=can::encode_bms_frame(s,status_tx); ASSERT_TRUE(frame);
    EXPECT_EQ(gateway.receive_status(*frame),RearPowerResult::Accepted); EXPECT_EQ(gateway.poll().safety.cause,zone::ProtectionCause::UpstreamLost);
}
TEST_F(RearPowerGatewayTest, ValidZeroAndNonProtectionDeratingAreRelayedWithoutNormalization) {
    seed(); port.now=ns(20); auto m=limits(20,1); m.local_state=can::ActuatorLocalState::Degraded;
    auto& l=std::get<can::BmsPowerLimits>(m.content); l.charge_power_w=0; l.charge_reason=can::BmsLimitReason::SocLimited;
    const auto frame=can::encode_bms_frame(m,limits_tx); ASSERT_TRUE(frame); ASSERT_EQ(gateway.receive_limits(*frame),RearPowerResult::Accepted);
    ASSERT_EQ(gateway.dispatch(),1U); const auto out=can::decode_bms_frame(port.sent.back().frame); ASSERT_TRUE(out);
    EXPECT_EQ(out->local_state,can::ActuatorLocalState::Degraded); EXPECT_EQ(std::get<can::BmsPowerLimits>(out->content).charge_power_w,0);
}
TEST_F(RearPowerGatewayTest, TerminalStopClearsQueuedNormalTrafficAndOnlyAcceptsShutdownAuthority) {
    ready(); ASSERT_GT(gateway.poll().pending,0U);
    ASSERT_TRUE(gateway.select_normal_stop({3,100,ns(20),ns(60)})); EXPECT_EQ(gateway.poll().pending,0U);
    EXPECT_EQ(gateway.enqueue_power(request(20,1)),RearPowerResult::NotReady);
    EXPECT_EQ(gateway.enqueue_permission(permission(20,1,true)),RearPowerResult::NotReady);
    port.now=ns(21);
    const can::BmsParentContext parent{3,2,ns(21),ns(81)};
    EXPECT_EQ(gateway.authorize_request({parent,can::BmsPowerAction::Enable}),RearPowerResult::ParentRejected);
    ASSERT_EQ(gateway.authorize_request({parent,can::BmsPowerAction::Shutdown}),RearPowerResult::Accepted);
    auto m=request(21,1); m.causal_sequence=2; std::get<can::BmsPowerRequest>(m.content).action=can::BmsPowerAction::Shutdown;
    ASSERT_EQ(gateway.enqueue_power(m),RearPowerResult::Accepted); EXPECT_EQ(gateway.dispatch(),1U);
}
TEST(RearPowerControl, OnlyExactUnexpiredIssuedFramesRecoverTheIndependentContext) {
    vecu::DriveController drive{{}}; vecu::PowerController power{{}}; simulation::RearPowerControl control{drive,power};
    ASSERT_TRUE(drive.start_session({3,7,kStart},vecu::DriveCommandStartup::NonDriving)); ASSERT_TRUE(power.start_session(3,7,kStart)); ASSERT_TRUE(control.start_session(3));
    const zone::RearPowerDelivery delivery{request(10,0),can::BmsParentContext{3,0,ns(10),ns(70)},ns(50)};
    can::BmsTxState tx{can::BmsFrameKind::PowerRequest}; const auto frame=can::encode_bms_frame(delivery.message,tx); ASSERT_TRUE(frame);
    EXPECT_FALSE(control.context_for(*frame,ns(10))); ASSERT_TRUE(control.stage_context(*frame,delivery));
    EXPECT_TRUE(control.context_for(*frame,ns(49))); EXPECT_FALSE(control.context_for(*frame,ns(50)));
    auto fdf=*frame; fdf.fd_flags=4; EXPECT_TRUE(control.context_for(fdf,ns(10))); // optional FDF presentation marker only
    fdf.fd_flags=1; EXPECT_FALSE(control.context_for(fdf,ns(10))); // BRS/ESI remain part of the envelope
    auto changed=*frame; changed.payload[1]^=1; EXPECT_FALSE(control.context_for(changed,ns(10)));
    ASSERT_TRUE(control.start_session(4)); EXPECT_FALSE(control.context_for(*frame,ns(10))); EXPECT_FALSE(control.arm_normal_commands(4,ns(10)));
}
class DrivePort : public zone::GatewayPort {
public:
    Port& port; vecu::DriveController& drive; std::vector<can::DriveMessage> sent;
    DrivePort(Port& p,vecu::DriveController& d):port(p),drive(d) {}
    std::uint64_t now_ns() noexcept override { return port.now; }
    bool send(const zone::CommandFrame& f,const central::CommandContext& context) noexcept override {
        try {
            const auto* frame=std::get_if<can::DriveFrame>(&f); if(!frame || port.now>=context.expires_at_ns) return false;
            const auto result=drive.receive_command(*frame,port.now);
            if(result.decision!=can::ActuatorReceiveDecision::Accepted) return false;
            sent.push_back(*can::decode_drive_frame(*frame)); return true;
        } catch(...) { return false; }
    }
    bool protect(zone::ZoneScope s,zone::ProtectionCause c,std::uint64_t n) noexcept override { return port.protect(s,c,n); }
};
class FrontPort : public zone::GatewayPort {
public:
    Port& clock; vecu::SteeringActuator& steering; vecu::BrakeActuator& brake;
    simulation::FrontStartupControl control;
    std::vector<can::SteeringMessage> steering_sent; std::vector<can::BrakeMessage> brake_sent; bool fail_brake{false};
    FrontPort(Port& p,vecu::SteeringActuator& s,vecu::BrakeActuator& b):clock(p),steering(s),brake(b),control(s,b) {}
    std::uint64_t now_ns() noexcept override { return clock.now; }
    bool send(const zone::CommandFrame& f,const central::CommandContext& context) noexcept override {
        try {
            if(clock.now>=context.expires_at_ns) return false;
            if(const auto* sf=std::get_if<can::SteeringFrame>(&f)) {
                if(steering.receive(*sf,clock.now).decision!=can::ActuatorReceiveDecision::Accepted) return false;
                steering_sent.push_back(*can::decode_steering_frame(*sf)); return true;
            }
            if(const auto* bf=std::get_if<can::BrakeFrame>(&f)) {
                if(fail_brake) return false;
                if(brake.receive(*bf,clock.now).decision!=can::ActuatorReceiveDecision::Accepted) return false;
                brake_sent.push_back(*can::decode_brake_frame(*bf)); return true;
            }
            return false;
        } catch(...) { return false; }
    }
    bool protect(zone::ZoneScope scope,zone::ProtectionCause cause,std::uint64_t now) noexcept override { return control.protect(scope,cause,now); }
};
enum class StopInjection { None, LeaseLoss, PressureLoss, SpeedLoss, PartialHandoff,
    FrontActualLoss, RearActualLoss, FrontPartition, RearPartition, FrontContinuity, RearContinuity,
    PartialArm, PowerTxFailure, FrontPartialTx, PermissionIngressLoss, PartialRejoin };
// Fault wrapper around the production same-host binding; never a fake normal
// health/permission path. Lost renewal lies only about a stop handoff ACK so the
// independent gateway/Leaf lease monitor must still catch it.
class CoordinatorPort : public central::CoordinatorPort {
public:
    simulation::VehicleCoordinatorPort& real; Port& clock; StopInjection injection; bool selected{false};
    CoordinatorPort(simulation::VehicleCoordinatorPort& r,Port& p,StopInjection i):real(r),clock(p),injection(i) {}
    std::uint64_t now_ns() noexcept override { return real.now_ns(); }
    bool session_ready(central::CoordinatorSession s) noexcept override { return real.session_ready(s); }
    bool healthy(std::uint32_t e) noexcept override { return real.healthy(e); }
    bool authorize_lifecycle(const central::LifecycleRequest& r) noexcept override { return real.authorize_lifecycle(r); }
    bool authorize_vehicle(const central::VehicleRequest& r) noexcept override { return real.authorize_vehicle(r); }
    bool arm(std::uint32_t e) noexcept override { return real.arm(e); }
    bool deliver_power(const central::VehicleManagementOutput& o) noexcept override { return real.deliver_power(o); }
    std::optional<can::BmsCurrentSample> current_permission() noexcept override { return real.current_permission(); }
    bool deliver_commands(const central::AllocatedCommands& c) noexcept override { return real.deliver_commands(c); }
    bool select_stop(const central::NormalStopPlan& plan) noexcept override {
        if(selected && injection==StopInjection::LeaseLoss) return true;
        if(!selected && injection==StopInjection::PartialHandoff) clock.clock_delay_ns=60*kMs;
        const bool ok=real.select_stop(plan); selected=selected||ok; return ok;
    }
    bool protect() noexcept override { return real.protect(); }
};
void run_vehicle_fixture(bool shutdown,StopInjection injection) {
    vecu::PowerController power{{}}; vecu::DriveController drive{{}};
    simulation::PowerModel plant{{.002,50,.02,100,1000,500}}; simulation::DriveSilPlant motor{vecu::DriveControllerConfig{}.response};
    Port port; simulation::RearPowerControl control{drive,power}; port.control=&control; port.power=&power; port.drive=&drive;
    vecu::SteeringActuator steering{{-.5,.5,-.3,.3,.1,1,50*kMs}};
    vecu::BrakeActuator brake{{2000000,1500000,200000,5000000,10000000,1000000,50*kMs}};
    simulation::SteeringResponse angles{{-.3,.3,.1,1,50*kMs,7}};
    simulation::BrakePressureResponse pressure{{1500000,200000,5000000,10000000,50*kMs,7}};
    FrontPort front_port{port,steering,brake}; zone::CommandGateway front{zone::ZoneScope::Front,front_port};
    can::SteeringReceiver steering_rx{{can::SteeringFrameKind::Actual,-.3,.3}};
    can::BrakeReceiver brake_rx{{can::BrakeFrameKind::Actual,0,1500000}};
    zone::RearPowerGateway rear{port}; DrivePort command_port{port,drive}; zone::CommandGateway normal{zone::ZoneScope::Rear,command_port}; port.commands=&normal;
    zone::ZoneFeedbackMonitor front_health{front},rear_health{normal,&rear};
    zone::ZoneStatusReceiver front_status{zone::ZoneScope::Front},rear_status{zone::ZoneScope::Rear};
    const can::BmsPhysicalRanges ranges{{0,1000},{-3000,3000},{-50,150},100000};
    can::BmsReceiver grant_rx{{can::BmsFrameKind::DrivePermission,ranges}}; port.observed_permission=&grant_rx;
    can::DriveReceiver drive_rx{{can::DriveFrameKind::Actual,{-300,500},100,300,30000000,80000000,30000000,70000000}};
    can::BmsTxState status_tx{can::BmsFrameKind::PowerStatus},limits_tx{can::BmsFrameKind::PowerLimits};
    simulation::VehicleCoordinatorPort real_coordinator_port{{steering,brake,drive,power,front,normal,rear,grant_rx,front_port}};
    CoordinatorPort coordinator_port{real_coordinator_port,port,injection}; central::VehicleCoordinator coordinator{coordinator_port};
    ASSERT_TRUE(power.start_session(3,7,kStart));
    ASSERT_TRUE(drive.start_session({3,7,kStart},vecu::DriveCommandStartup::NonDriving)); ASSERT_TRUE(control.start_session(3));
    ASSERT_TRUE(rear.start_session(3,kStart)); ASSERT_TRUE(normal.start_session(3,kStart)); ASSERT_TRUE(grant_rx.start_session(3,kStart)); ASSERT_TRUE(drive_rx.start_session(3,kStart));
    ASSERT_TRUE(plant.initialize({7,0,kStart},0)); motor.begin(7,kStart);
    ASSERT_TRUE(steering.start_session({3,7,kStart},ActuatorCommandStartup::NonDriving));
    ASSERT_TRUE(brake.start_session({3,7,kStart},ActuatorCommandStartup::NonDriving));
    ASSERT_TRUE(angles.begin(kStart)); ASSERT_TRUE(pressure.begin(kStart)); ASSERT_TRUE(front.start_session(3,kStart));
    ASSERT_TRUE(steering_rx.start_session(3,kStart)); ASSERT_TRUE(brake_rx.start_session(3,kStart));
    ASSERT_TRUE(front_health.start_session(3,kStart)); ASSERT_TRUE(rear_health.start_session(3,kStart));
    ASSERT_TRUE(front_status.start_session(3,kStart)); ASSERT_TRUE(rear_status.start_session(3,kStart));
    ASSERT_TRUE(coordinator.start_session({3,kStart}));
    if(injection==StopInjection::PartialArm) port.arm_ok=false;
    bool stopping=false,handed=false,loss_seen=false; std::uint32_t stop_seq=0; std::size_t drive_count=0,front_count=0;
    std::uint32_t root_seq=0,vehicle_seq=0; bool precharge=false,active=false; std::uint32_t first_normal=0;
    const auto collect_feedback=[&](std::uint32_t ms) {
        central::NormalDriveReadinessInputs in; in.epoch=3; in.session_enable_ns=kStart;
        in.front.steering_actual=steering_rx.current_sample(port.now); in.front.brake_actual=brake_rx.current_sample(port.now);
        in.rear.drive_actual=drive_rx.current_sample(port.now); in.rear.power_status=rear.power_status(); in.rear.power_limits=rear.power_limits();
        const auto fh=front_health.tick({in.front.steering_actual,in.front.brake_actual,{},{},{}},port.now);
        const auto rh=rear_health.tick({{},{},in.rear.drive_actual,in.rear.power_status,in.rear.power_limits},port.now);
        EXPECT_TRUE(fh); EXPECT_TRUE(rh);
        if(ms==1000 && injection==StopInjection::FrontContinuity) front_status.mark_continuity_lost(port.now);
        if(ms==1000 && injection==StopInjection::RearContinuity) rear_status.mark_continuity_lost(port.now);
        const bool front_partition=(ms>=1010 && injection==StopInjection::FrontPartition) || (ms>=1000 && injection==StopInjection::FrontContinuity);
        const bool rear_partition=(ms>=1010 && injection==StopInjection::RearPartition) || (ms>=1000 && injection==StopInjection::RearContinuity);
        if(!front_partition) { EXPECT_EQ(front_status.receive(*fh,port.now),can::ActuatorReceiveDecision::Accepted); }
        if(!rear_partition) { EXPECT_EQ(rear_status.receive(*rh,port.now),can::ActuatorReceiveDecision::Accepted); }
        in.front.health=front_status.current_sample(port.now); in.rear.health=rear_status.current_sample(port.now);
        return in;
    };
    const auto verify_loss=[&](const central::NormalDriveReadinessInputs& in) {
        coordinator.tick(in,port.now); EXPECT_NE(coordinator.decision().fault,central::CoordinatorFault::None);
        EXPECT_FALSE(coordinator.decision().management.normal_allowed); EXPECT_TRUE(coordinator.decision().protection_selected);
        loss_seen=true;
        EXPECT_EQ(drive.output().mode,drive::ActuationMode::Zero); EXPECT_EQ(brake.output().mode,brake::ActuationMode::Protect);
        EXPECT_NE(steering.fault(),vecu::SteeringFault::None); EXPECT_TRUE(power.output().inhibit_drive);
        port.now+=10*kMs;
        if(injection==StopInjection::FrontPartition || injection==StopInjection::FrontContinuity) { EXPECT_NE(front_status.receive(*front_health.tick({},port.now),port.now),can::ActuatorReceiveDecision::Accepted); }
        if(injection==StopInjection::RearPartition || injection==StopInjection::RearContinuity) { EXPECT_NE(rear_status.receive(*rear_health.tick({},port.now),port.now),can::ActuatorReceiveDecision::Accepted); }
        EXPECT_FALSE(coordinator.start_session({3,port.now})); EXPECT_FALSE(coordinator.decision().management.normal_allowed);
    };
    for(std::uint32_t ms=10;ms<=(shutdown?3200U:1600U);ms+=10) {
        port.now=ns(ms);
        // Expiring permission/gateway support may protect locally before the
        // next normal CAN ingress. Observe that state before sending again.
        if(ms==1040 && injection>=StopInjection::FrontActualLoss && injection<=StopInjection::RearPartition) {
            const auto lost=collect_feedback(ms); EXPECT_FALSE(central::evaluate_vehicle_input_health(lost,port.now).ready()); verify_loss(lost); break;
        }
        if(handed && rear.poll().safety.cause!=zone::ProtectionCause::None) {
            verify_loss(collect_feedback(ms)); EXPECT_NE(coordinator.decision().stop.state,central::NormalStopState::Complete); break;
        }
        const battery::ModelIdentity id{7,ms/10,port.now};
        const auto coils=power.output().coils.value_or(power::CoilCommand{});
        const auto begin=ns(ms-10);
        ASSERT_EQ(plant.step({begin,port.now,{{400,0,true,true,true,false,false},{7,ms/10-1,begin},begin},coils}),simulation::PowerModelFault::None);
        const auto s=power.tick(plant.observation(),power::BmsSafetyGate{3,ms/10-1,port.now,begin,false},port.now); ASSERT_TRUE(s);
        const auto sf=can::encode_bms_frame(*s,status_tx); ASSERT_TRUE(sf); ASSERT_EQ(rear.receive_status(*sf),RearPowerResult::Accepted);
        auto limit=limits(ms,ms/10-1); const bool hv=std::get<can::BmsPowerStatus>(s->content).state==can::BmsPowerState::HvReady;
        if(!hv) { limit.local_state=can::ActuatorLocalState::Init; limit.origin=can::ActuatorOrigin::NoAcceptedInput; limit.content=can::BmsPowerLimits{0,0,can::BmsLimitReason::Disabled,can::BmsLimitReason::Disabled,port.now}; }
        const auto lf=can::encode_bms_frame(limit,limits_tx); ASSERT_TRUE(lf); ASSERT_EQ(rear.receive_limits(*lf),RearPowerResult::Accepted);
        const double speed=(handed && injection==StopInjection::SpeedLoss)?.02:shutdown?(ms<=1200?20:std::max(0.0,20-.04*(ms-1200))):0;
        drive.observe_local({battery::ModelMeasurement<double>{speed,id,port.now},battery::ModelMeasurement<drive::HvFeedback>{{plant.diagnostic_state().bus_voltage_v,hv,false},id,port.now}},port.now);
        ASSERT_TRUE(motor.advance(port.now,false)); ASSERT_TRUE(drive.prepare(port.now)); const auto df=drive.complete(motor.capture(port.now),port.now); ASSERT_TRUE(df); ASSERT_TRUE(motor.apply(drive.output()));
        if(injection!=StopInjection::RearActualLoss || ms<1010) { ASSERT_EQ(drive_rx.receive(*df,port.now).decision,can::ActuatorReceiveDecision::Accepted); }
        if(handed && injection==StopInjection::SpeedLoss && drive.decision().fault!=vecu::DriveGateFault::None) {
            verify_loss(collect_feedback(ms)); EXPECT_EQ(drive.decision().fault,vecu::DriveGateFault::NormalStopInvalid); break;
        }
        ASSERT_TRUE(angles.advance(port.now)); ASSERT_TRUE(pressure.advance(port.now));
        ASSERT_TRUE(steering.prepare(port.now)); ASSERT_TRUE(brake.prepare(port.now));
        const auto af=steering.complete(angles.capture(),port.now);
        const auto bf=brake.complete(pressure.capture(simulation::BrakeSensorAction::Acquire,
            handed && injection==StopInjection::PressureLoss?std::optional<double>{0}:std::nullopt),port.now);
        if(handed && injection==StopInjection::PressureLoss && brake.fault()!=vecu::BrakeFault::None) {
            verify_loss(collect_feedback(ms)); EXPECT_EQ(brake.fault(),vecu::BrakeFault::NormalStopInvalid);
            EXPECT_GE(pressure.actual_pressure_pa(),kStopPressurePa); break;
        }
        ASSERT_TRUE(af); ASSERT_TRUE(bf);
        if(injection!=StopInjection::FrontActualLoss || ms<1010) { ASSERT_EQ(steering_rx.receive(*af,port.now).decision,can::ActuatorReceiveDecision::Accepted); }
        ASSERT_EQ(brake_rx.receive(*bf,port.now).decision,can::ActuatorReceiveDecision::Accepted);
        if(steering.output().mode==steering::ActuationMode::Hold) { ASSERT_TRUE(angles.hold(port.now)); }
        else { ASSERT_TRUE(angles.set_target(steering.output().target_rad,port.now)); }
        if(brake.output().mode==brake::ActuationMode::Target) { ASSERT_TRUE(pressure.set_target(brake.output().target_pa,port.now)); }
        if(handed && brake.output().mode==brake::ActuationMode::Hold) { ASSERT_TRUE(pressure.hold(port.now)); }
        EXPECT_EQ(front.poll().safety.cause,zone::ProtectionCause::None);
        auto in=collect_feedback(ms);
        if(injection>=StopInjection::FrontActualLoss && !central::evaluate_vehicle_input_health(in,port.now).ready()) { verify_loss(in); break; }
        if(handed) {
            ASSERT_TRUE(in.front.health); ASSERT_TRUE(in.rear.health);
            EXPECT_EQ(in.front.health->phase,zone::ZonePhase::Terminal); EXPECT_EQ(in.rear.health->phase,zone::ZonePhase::Terminal);
            EXPECT_TRUE(central::evaluate_vehicle_input_health(in,port.now).ready());
            EXPECT_FALSE(central::evaluate_normal_drive_readiness(in,port.now).ready());
        }
        if(shutdown && ms>=1200) {
            if(!stopping || ms%20==0) {
                const central::NormalStopRequest intent{{3,stop_seq++,port.now,ns(ms+60)},.02};
                ASSERT_EQ(coordinator.receive_stop(intent,port.now),central::CoordinatorReceive::Accepted); stopping=true;
            }
        }
        if(!stopping && ms%20==10) {
            const central::LifecycleRequest root{{3,root_seq++,port.now,ns(ms+60)},can::BmsPowerAction::Enable};
            ASSERT_EQ(coordinator.receive_lifecycle(root,port.now),central::CoordinatorReceive::Accepted);
        }
        if(active && !stopping && ms%20==0) {
            ASSERT_EQ(coordinator.receive_vehicle({3,vehicle_seq++,port.now,ns(ms+60),.2,.02,0,false},port.now),central::CoordinatorReceive::Accepted);
        }
        if(ms==1000) {
            if(injection==StopInjection::PowerTxFailure) port.fail_call=port.calls+1;
            if(injection==StopInjection::FrontPartialTx) front_port.fail_brake=true;
            if(injection==StopInjection::PermissionIngressLoss) port.observed_permission=nullptr;
            if(injection==StopInjection::PartialRejoin) { ASSERT_TRUE(front.start_session(4,port.now)); EXPECT_FALSE(coordinator.start_session({4,port.now})); }
        }
        ASSERT_TRUE(coordinator.tick(in,port.now));
        const auto state=coordinator.decision();
        if(state.fault!=central::CoordinatorFault::None) {
            verify_loss(in);
            if(injection==StopInjection::PartialArm) { EXPECT_EQ(state.fault,central::CoordinatorFault::Arm); EXPECT_TRUE(command_port.sent.empty()); }
            else if(injection==StopInjection::PowerTxFailure) { EXPECT_EQ(state.fault,central::CoordinatorFault::PowerDelivery); }
            else if(injection==StopInjection::FrontPartialTx) { EXPECT_EQ(state.fault,central::CoordinatorFault::CommandDelivery); EXPECT_EQ(front_port.steering_sent.size(),front_port.brake_sent.size()+1); }
            else if(injection==StopInjection::PermissionIngressLoss) { EXPECT_EQ(state.fault,central::CoordinatorFault::Allocation); }
            else if(injection==StopInjection::PartialRejoin) { EXPECT_EQ(state.fault,central::CoordinatorFault::LocalProtection); }
            else { EXPECT_EQ(injection,StopInjection::PartialHandoff); EXPECT_EQ(state.stop.state,central::NormalStopState::HandoffPending); }
            break;
        }
        if(state.normal_armed && !active) { active=true; first_normal=ms; }
        if(!handed && (state.stop.state==central::NormalStopState::PowerDown || state.stop.state==central::NormalStopState::Complete)) {
            handed=true; drive_count=command_port.sent.size(); front_count=front_port.brake_sent.size();
            ASSERT_TRUE(angles.hold(port.now)); ASSERT_TRUE(pressure.hold(port.now)); ASSERT_TRUE(motor.apply(drive.output()));
        }
        if(power.output().phase==vecu::PowerPhase::Precharging) { precharge=true; EXPECT_FALSE(active); EXPECT_FALSE(drive.decision().active); EXPECT_DOUBLE_EQ(motor.actual_nm(),0); }
        if(!active) {
            EXPECT_TRUE(command_port.sent.empty()); EXPECT_TRUE(front_port.steering_sent.empty()); EXPECT_TRUE(front_port.brake_sent.empty());
            EXPECT_DOUBLE_EQ(angles.actual_angle_rad(),.1); EXPECT_DOUBLE_EQ(pressure.actual_pressure_pa(),200000);
        }
        EXPECT_EQ(steering.fault(),vecu::SteeringFault::None); EXPECT_EQ(brake.fault(),vecu::BrakeFault::None);
        EXPECT_EQ(drive.decision().fault,vecu::DriveGateFault::None);
    }
    EXPECT_TRUE(precharge);
    if(injection==StopInjection::PartialArm) { EXPECT_TRUE(loss_seen); EXPECT_FALSE(active); return; }
    ASSERT_TRUE(active); EXPECT_GT(first_normal,80U); ASSERT_FALSE(command_port.sent.empty());
    EXPECT_EQ(command_port.sent.front().sequence,0U); EXPECT_GE(command_port.sent.front().source_time_ns,ns(first_normal));
    if(shutdown) {
        if(injection==StopInjection::PartialHandoff) { EXPECT_TRUE(loss_seen); EXPECT_FALSE(handed); return; }
        ASSERT_TRUE(handed);
        if(injection!=StopInjection::None) { EXPECT_TRUE(loss_seen); return; }
        EXPECT_EQ(coordinator.decision().stop.state,central::NormalStopState::Complete); EXPECT_EQ(coordinator.decision().stop.fault,central::NormalStopFault::None);
        EXPECT_EQ(coordinator.decision().management.state,central::VehicleManagementState::Stopped); EXPECT_TRUE(coordinator.decision().management.power_off_confirmed);
        EXPECT_EQ(power.output().fault,vecu::PowerControlFault::None); EXPECT_EQ(drive.decision().fault,vecu::DriveGateFault::None);
        EXPECT_EQ(brake.fault(),vecu::BrakeFault::None); EXPECT_EQ(steering.fault(),vecu::SteeringFault::None);
        EXPECT_LE(plant.diagnostic_state().bus_voltage_v,30); EXPECT_GE(pressure.actual_pressure_pa(),kStopPressurePa);
        EXPECT_LE(std::abs(motor.actual_nm()),kStopTorqueNm); EXPECT_EQ(command_port.sent.size(),drive_count); EXPECT_EQ(front_port.brake_sent.size(),front_count);
        EXPECT_FALSE(front.arm()); EXPECT_FALSE(drive.arm_normal_commands(port.now));
        can::DriveMessage forbidden; meta(forbidden,{3200,0}); forbidden.torque_nm=100;
        can::DriveTxState dt{can::DriveFrameKind::Command}; const auto forbidden_frame=can::encode_drive_frame(forbidden,dt); ASSERT_TRUE(forbidden_frame);
        EXPECT_EQ(drive.receive_command(*forbidden_frame,port.now).decision,can::ActuatorReceiveDecision::ModeRejected);
        auto release=can::BrakeMessage{}; meta(release,{3200,0}); release.pressure_pa=0;
        can::BrakeTxState bt{can::BrakeFrameKind::Command}; const auto release_frame=can::encode_brake_frame(release,bt); ASSERT_TRUE(release_frame);
        EXPECT_EQ(brake.receive(*release_frame,port.now).decision,can::ActuatorReceiveDecision::ModeRejected);
        return;
    }
    if(injection>=StopInjection::FrontActualLoss) { EXPECT_TRUE(loss_seen); return; }
    EXPECT_GT(motor.actual_nm(),0); EXPECT_EQ(port.protections,0U);
    ASSERT_FALSE(front_port.steering_sent.empty()); ASSERT_FALSE(front_port.brake_sent.empty());
    EXPECT_EQ(front_port.steering_sent.front().sequence,0U); EXPECT_EQ(front_port.brake_sent.front().sequence,0U);
    EXPECT_NE(angles.actual_angle_rad(),.1); EXPECT_DOUBLE_EQ(pressure.actual_pressure_pa(),0);
    // Real Rear handoff selects both protections; ACK cannot erase physical residuals.
    EXPECT_FALSE(control.protect(zone::ZoneScope::Front,zone::ProtectionCause::UpstreamLost,port.now));
    rear.mark_continuity_lost(); EXPECT_TRUE(rear.poll().safety.handoff_accepted);
    EXPECT_EQ(drive.decision().fault,vecu::DriveGateFault::UpstreamProtection);
    EXPECT_EQ(drive.output().mode,drive::ActuationMode::Zero); EXPECT_GT(motor.actual_nm(),0);
    EXPECT_EQ(power.output().fault,vecu::PowerControlFault::ContinuityLost); EXPECT_TRUE(power.output().inhibit_drive);
    ASSERT_TRUE(power.output().coils); EXPECT_TRUE(power.output().coils->close.positive); EXPECT_TRUE(power.output().coils->close.negative);
    port.now=ns(1610);
    ASSERT_EQ(plant.step({ns(1600),port.now,{{400,0,true,true,true,false,false},{7,160,ns(1600)},ns(1600)},*power.output().coils}),simulation::PowerModelFault::None);
    ASSERT_TRUE(power.tick(plant.observation(),power::BmsSafetyGate{3,160,port.now,ns(1600),false},port.now));
    EXPECT_EQ(power.output().phase,vecu::PowerPhase::WaitCurrent); ASSERT_TRUE(power.output().coils);
    EXPECT_TRUE(power.output().coils->close.positive); EXPECT_TRUE(power.output().coils->close.negative);
}
TEST(RearPowerIntegration, BothZonesUseRealLeafActualsAndExplicitStartupThenProtectWithoutFabricatingPhysicalCompletion) { run_vehicle_fixture(false,StopInjection::None); }
TEST(NormalStopIntegration, ActualStopHandoffThenInhibitAndContactorDischargeCompleteWithoutFaultReset) { run_vehicle_fixture(true,StopInjection::None); }
TEST(NormalStopIntegration, IndependentHandoffLeaseLossProtectsBothZonesWhilePowerTrafficContinues) { run_vehicle_fixture(true,StopInjection::LeaseLoss); }
TEST(NormalStopIntegration, LocalPressureLossAfterHandoffCannotBeHiddenByFreshLeaseAndPowerFrames) { run_vehicle_fixture(true,StopInjection::PressureLoss); }
TEST(NormalStopIntegration, LocalSpeedRiseAfterHandoffClosesTheDriveGateEvenBeforeCentralReacts) { run_vehicle_fixture(true,StopInjection::SpeedLoss); }
TEST(NormalStopIntegration, ExpiryDuringPartialHandoffProtectsBothZonesWithoutAcknowledgingCompletion) { run_vehicle_fixture(true,StopInjection::PartialHandoff); }
TEST(ZoneFeedbackIntegration, FrontLeafActualLossPropagatesThroughRealStatusAndProtectsBothZones) { run_vehicle_fixture(false,StopInjection::FrontActualLoss); }
TEST(ZoneFeedbackIntegration, RearLeafActualLossPropagatesThroughRealStatusAndProtectsBothZones) { run_vehicle_fixture(false,StopInjection::RearActualLoss); }
TEST(ZoneFeedbackIntegration, RearHeartbeatCannotHideFrontStatusPartition) { run_vehicle_fixture(false,StopInjection::FrontPartition); }
TEST(ZoneFeedbackIntegration, FrontHeartbeatCannotHideRearStatusPartition) { run_vehicle_fixture(false,StopInjection::RearPartition); }
TEST(ZoneFeedbackIntegration, FrontStatusContinuityLossRequiresNewInit) { run_vehicle_fixture(false,StopInjection::FrontContinuity); }
TEST(ZoneFeedbackIntegration, RearStatusContinuityLossRequiresNewInit) { run_vehicle_fixture(false,StopInjection::RearContinuity); }
TEST(CoordinatorIntegration, PartialArmProtectsBothZonesBeforeAnyNormalCommand) { run_vehicle_fixture(false,StopInjection::PartialArm); }
TEST(CoordinatorIntegration, PowerWriteFailureStopsTheUnifiedCycleAndSelectsBothProtections) { run_vehicle_fixture(false,StopInjection::PowerTxFailure); }
TEST(CoordinatorIntegration, PartialFrontWriteProtectsBothZonesWithoutSendingTheRearBatch) { run_vehicle_fixture(false,StopInjection::FrontPartialTx); }
TEST(CoordinatorIntegration, MissingActualPermissionIngressCannotBeReplacedByTheNewIssuedGrant) { run_vehicle_fixture(false,StopInjection::PermissionIngressLoss); }
TEST(CoordinatorIntegration, OneGatewayNewEpochCannotReinitializeOrHealTheCentralSession) { run_vehicle_fixture(false,StopInjection::PartialRejoin); }

class InitRecovery : public simulation::SessionRecoveryPort {
public:
    Port& clock; simulation::SessionInitParticipants& p; simulation::SessionResetEvidence samples;
    std::size_t closed{0},services{0};
    InitRecovery(Port& c,simulation::SessionInitParticipants& participants):clock(c),p(participants) {}
    std::uint64_t now_ns() noexcept override { return clock.now; }
    bool quiesce(session::Role) noexcept override { ++closed; return true; } // no normal producer in this startup fixture
    simulation::SessionResetEvidence evidence() noexcept override { return samples; }
    void service(session::Role) noexcept override { ++services; }
    void protect(session::Role role) noexcept override {
        switch(role) {
        case session::Role::FrontZone: p.actors.front.request_protection(); break;
        case session::Role::RearZone: p.actors.rear.request_protection(); p.actors.rear_power.mark_continuity_lost(); break;
        case session::Role::Steering: p.actors.steering.request_local_protection(clock.now); break;
        case session::Role::Brake: p.actors.brake.request_local_protection(clock.now); break;
        case session::Role::Drive: p.actors.drive.request_local_protection(clock.now); break;
        case session::Role::Power: p.actors.power.request_local_protection(clock.now); break;
        case session::Role::CentralIngress: p.front_status.mark_continuity_lost(clock.now); p.rear_status.mark_continuity_lost(clock.now); break;
        case session::Role::Bms: case session::Role::Count: break; // external run gate stays shut; no BMS bypass
        }
    }
};
class InitCentralPort : public session::CoordinatorPort {
public:
    central::VehicleCoordinator& core; Port& clock; std::size_t commits{0};
    InitCentralPort(central::VehicleCoordinator& c,Port& p):core(c),clock(p) {}
    std::uint64_t now_ns() noexcept override { return clock.now; }
    bool quiesce_central() noexcept override { core.request_protection(clock.now); return true; }
    bool send(const session::Control&) noexcept override { return false; } // SessionCentralLoop owns transport
    bool commit_central(central::CoordinatorSession s) noexcept override { ++commits; return core.start_session(s); }
    void protect_central() noexcept override { core.request_protection(clock.now); }
};
class InitFailurePort : public session::ParticipantPort {
public:
    simulation::VehicleSessionInit& real; bool reject{false};
    explicit InitFailurePort(simulation::VehicleSessionInit& p):real(p) {}
    std::uint64_t now_ns() noexcept override { return real.now_ns(); }
    session::Preparation prepare(const session::Plan& p) noexcept override { return real.prepare(p); }
    bool initialize(const session::Plan& p) noexcept override { return !reject && real.initialize(p); }
    void protect() noexcept override { real.protect(); }
    void service() noexcept override { real.service(); }
};
void run_session_bootstrap(bool unsafe_at_enable) {
    vecu::PowerController power{{}}; vecu::DriveController drive{{}};
    vecu::BmsController bms{simulation::multirate_fixture::bms_config()};
    vecu::SteeringActuator steering{{-.5,.5,-.3,.3,.1,1,50*kMs}};
    vecu::BrakeActuator brake{{2000000,1500000,200000,5000000,10000000,1000000,50*kMs}};
    simulation::SteeringResponse angles{{-.3,.3,.1,1,50*kMs,7}};
    simulation::BrakePressureResponse pressure{{1500000,200000,5000000,10000000,50*kMs,7}};
    simulation::DriveSilPlant motor{vecu::DriveControllerConfig{}.response};
    simulation::PowerModel plant{{.002,50,.02,100,1000,500}};
    simulation::BatteryModel battery{{180000000,400,.05,200000,20,25,100,.01,1,100000}};
    ASSERT_TRUE(angles.begin(kStart)); ASSERT_TRUE(pressure.begin(kStart)); motor.begin(7,kStart);
    ASSERT_TRUE(plant.initialize({7,0,kStart},0)); ASSERT_TRUE(battery.initialize({7,kStart,.63,25}));
    Port clock; simulation::RearPowerControl rear_control{drive,power}; clock.control=&rear_control; clock.drive=&drive; clock.power=&power;
    FrontPort front_port{clock,steering,brake}; DrivePort rear_port{clock,drive};
    zone::CommandGateway front{zone::ZoneScope::Front,front_port},rear{zone::ZoneScope::Rear,rear_port};
    zone::RearPowerGateway rear_power{clock}; clock.commands=&rear;
    zone::ZoneFeedbackMonitor front_monitor{front},rear_monitor{rear,&rear_power};
    zone::ZoneStatusReceiver front_status{zone::ZoneScope::Front},rear_status{zone::ZoneScope::Rear};
    const can::BmsPhysicalRanges ranges{{0,1000},{-3000,3000},{-50,150},100000};
    can::BmsReceiver permission_rx{{can::BmsFrameKind::DrivePermission,ranges}};
    can::SteeringReceiver steering_rx{{can::SteeringFrameKind::Actual,-.3,.3}};
    can::BrakeReceiver brake_rx{{can::BrakeFrameKind::Actual,0,1500000}};
    can::DriveReceiver drive_rx{{can::DriveFrameKind::Actual,{-300,500},100,300}};
    simulation::CoordinatorSilParticipants actors{steering,brake,drive,power,front,rear,rear_power,permission_rx,front_port};
    simulation::VehicleCoordinatorPort core_port{actors}; central::VehicleCoordinator core{core_port};
    simulation::SessionInitParticipants participants{actors,bms,rear_control,front_monitor,rear_monitor,steering_rx,brake_rx,drive_rx,front_status,rear_status};
    InitRecovery recovery{clock,participants}; InitCentralPort startup{core,clock}; session::SessionLinks links;
    simulation::SessionCentralLoop central{startup,links};
    std::vector<std::unique_ptr<simulation::VehicleSessionInit>> initializers;
    std::vector<std::unique_ptr<InitFailurePort>> bindings;
    std::vector<std::unique_ptr<simulation::SessionOwnerLoop>> owners;
    for(std::size_t i=0;i<session::kRoleCount;++i) {
        const auto role=static_cast<session::Role>(i);
        initializers.push_back(std::make_unique<simulation::VehicleSessionInit>(role,7,participants,recovery));
        bindings.push_back(std::make_unique<InitFailurePort>(*initializers.back()));
        owners.push_back(std::make_unique<simulation::SessionOwnerLoop>(role,*bindings.back(),links[i]));
    }
    std::uint32_t physical_sequence=0;
    const auto advance_physics=[&] {
        const auto begin=clock.now; clock.now+=kMs;
        ASSERT_EQ(plant.step({begin,clock.now,{{400,0,true,true,true,false,false},{7,physical_sequence++,begin},begin},{}}),simulation::PowerModelFault::None);
        ASSERT_TRUE(angles.advance(clock.now)); ASSERT_TRUE(pressure.advance(clock.now)); ASSERT_TRUE(motor.advance(clock.now,false));
        recovery.samples={battery::ModelMeasurement<double>{0,{7,physical_sequence,clock.now},clock.now},motor.capture(clock.now),plant.observation()};
    };
    const auto finish=[&] {
        for(unsigned i=0;i<60 && central.state()!=session::State::Running && central.state()!=session::State::Failed;++i) {
            advance_physics();
            if(unsafe_at_enable && central.state()==session::State::Initializing && clock.now>=central.plan().enable_ns) {
                recovery.samples.power->bus_voltage_v=100; // independent sensor change after Prepared
            }
            for(auto& owner:owners) owner->step();
            central.step();
        }
    };
    advance_physics(); ASSERT_TRUE(central.begin(1,clock.now)); finish();
    if(unsafe_at_enable) {
        EXPECT_FALSE(central.run_enabled()); EXPECT_EQ(central.fault(),session::Fault::Participant);
        EXPECT_GT(central.plan().enable_ns,central.plan().requested_ns); EXPECT_EQ(startup.commits,0U);
        EXPECT_EQ(steering.application_epoch(),0U); EXPECT_EQ(power.application_epoch(),0U);
        EXPECT_DOUBLE_EQ(plant.diagnostic_state().bus_voltage_v,0); // sensor fault does not reset plant
        EXPECT_TRUE(clock.sent.empty()); return;
    }
    ASSERT_TRUE(central.run_enabled());
    EXPECT_EQ(startup.commits,1U); EXPECT_EQ(steering.application_epoch(),1U); EXPECT_EQ(power.application_epoch(),1U);
    EXPECT_EQ(bms.decision().state,vecu::BmsControlState::InitialChecks); EXPECT_FALSE(core.decision().normal_armed);
    EXPECT_TRUE(clock.sent.empty()); EXPECT_TRUE(front_port.steering_sent.empty()); EXPECT_TRUE(rear_port.sent.empty());
    // Rejoin cannot skip one owner or reuse an abandoned Epoch. The startup
    // fixture continues physical acquisition; it never applies normal actuation.
    central.cancel(clock.now); bindings[static_cast<std::size_t>(session::Role::Brake)]->reject=true;
    ASSERT_TRUE(central.begin(2,clock.now)); finish(); EXPECT_FALSE(central.run_enabled());
    EXPECT_EQ(central.fault(),session::Fault::Participant); EXPECT_EQ(startup.commits,1U);
    EXPECT_FALSE(central.begin(2,clock.now)); EXPECT_FALSE(core.decision().management.normal_allowed);
    bindings[static_cast<std::size_t>(session::Role::Brake)]->reject=false;
    ASSERT_TRUE(central.begin(3,clock.now)); finish(); ASSERT_TRUE(central.run_enabled());
    EXPECT_EQ(startup.commits,2U); EXPECT_EQ(steering.application_epoch(),3U); EXPECT_EQ(brake.application_epoch(),3U);
    EXPECT_EQ(drive.application_epoch(),3U); EXPECT_EQ(power.application_epoch(),3U); EXPECT_EQ(permission_rx.application_epoch(),3U);
    EXPECT_DOUBLE_EQ(angles.actual_angle_rad(),.1); EXPECT_DOUBLE_EQ(pressure.actual_pressure_pa(),200000);
    EXPECT_DOUBLE_EQ(motor.actual_nm(),0); EXPECT_DOUBLE_EQ(plant.diagnostic_state().bus_voltage_v,0);
    EXPECT_FALSE(plant.diagnostic_state().contactors.positive); EXPECT_EQ(plant.diagnostic_state().identity.epoch,7U);
    EXPECT_DOUBLE_EQ(battery.diagnostic_state().soc,.63); EXPECT_EQ(battery.diagnostic_state().identity.epoch,7U);
    EXPECT_FALSE(core.decision().normal_armed); EXPECT_TRUE(clock.sent.empty()); EXPECT_GT(recovery.services,0U);
}
TEST(SessionBootstrapIntegration, AllOwnersCommitAndExplicitRejoinPreservesContinuingPhysicalModels) { run_session_bootstrap(false); }
TEST(SessionBootstrapIntegration, PreparedAckCannotBypassChangedPhysicalEvidenceAtActualInit) { run_session_bootstrap(true); }
} // namespace
