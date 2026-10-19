#include "rear_power_gateway.hpp"
#include "rear_power_control.hpp"
#include "control_allocation.hpp"
#include "command_gateway.hpp"
#include "power_model.hpp"
#include "drive_sil_plant.hpp"

#include <gtest/gtest.h>
#include <vector>

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
    std::uint64_t now_ns() noexcept override { return now; }
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
central::NormalDriveReadinessInputs front_fixture(std::uint32_t ms) {
    central::NormalDriveReadinessInputs in; in.epoch=3; in.session_enable_ns=kStart;
    in.front.health.emplace(); in.rear.health.emplace(); meta(*in.front.health,{ms,ms/10}); meta(*in.rear.health,{ms,ms/10});
    in.front.health->ready_for_normal=in.rear.health->ready_for_normal=true;
    in.front.steering_actual.emplace(); meta(*in.front.steering_actual,{ms,ms/10}); in.front.steering_actual->kind=can::SteeringFrameKind::Actual; in.front.steering_actual->angle_rad=0;
    in.front.brake_actual.emplace(); meta(*in.front.brake_actual,{ms,ms/10}); in.front.brake_actual->kind=can::BrakeFrameKind::Actual; in.front.brake_actual->pressure_pa=0;
    return in;
}
TEST(RearPowerIntegration, RealCentralAndPowerPrechargeKeepDriveZeroUntilExplicitArmThenAllocateWithoutBootstrapPackets) {
    central::VehicleManagement owner; central::ControlAllocation allocation; vecu::PowerController power{{}}; vecu::DriveController drive{{}};
    simulation::PowerModel plant{{.002,50,.02,100,1000,500}}; simulation::DriveSilPlant motor{vecu::DriveControllerConfig{}.response};
    Port port; simulation::RearPowerControl control{drive,power}; port.control=&control; port.power=&power; port.drive=&drive;
    zone::RearPowerGateway rear{port}; DrivePort command_port{port,drive}; zone::CommandGateway normal{zone::ZoneScope::Rear,command_port}; port.commands=&normal;
    const can::BmsPhysicalRanges ranges{{0,1000},{-3000,3000},{-50,150},100000};
    can::BmsReceiver grant_rx{{can::BmsFrameKind::DrivePermission,ranges}}; port.observed_permission=&grant_rx;
    can::DriveReceiver drive_rx{{can::DriveFrameKind::Actual,{-300,500},100,300,30000000,80000000,30000000,70000000}};
    can::BmsTxState status_tx{can::BmsFrameKind::PowerStatus},limits_tx{can::BmsFrameKind::PowerLimits};
    ASSERT_TRUE(owner.start_session(3,kStart)); ASSERT_TRUE(allocation.start_session(3,kStart)); ASSERT_TRUE(power.start_session(3,7,kStart));
    ASSERT_TRUE(drive.start_session({3,7,kStart},vecu::DriveCommandStartup::NonDriving)); ASSERT_TRUE(control.start_session(3));
    ASSERT_TRUE(rear.start_session(3,kStart)); ASSERT_TRUE(normal.start_session(3,kStart)); ASSERT_TRUE(grant_rx.start_session(3,kStart)); ASSERT_TRUE(drive_rx.start_session(3,kStart));
    ASSERT_TRUE(plant.initialize({7,0,kStart},0)); motor.begin(7,kStart);
    std::uint32_t root_seq=0,vehicle_seq=0; bool precharge=false,active=false; std::uint32_t first_normal=0;
    for(std::uint32_t ms=10;ms<=1600;ms+=10) {
        port.now=ns(ms); const battery::ModelIdentity id{7,ms/10,port.now};
        const auto coils=power.output().coils.value_or(power::CoilCommand{});
        const auto begin=ns(ms-10);
        ASSERT_EQ(plant.step({begin,port.now,{{400,0,true,true,true,false,false},{7,ms/10-1,begin},begin},coils}),simulation::PowerModelFault::None);
        const auto s=power.tick(plant.observation(),power::BmsSafetyGate{3,ms/10-1,port.now,begin,false},port.now); ASSERT_TRUE(s);
        const auto sf=can::encode_bms_frame(*s,status_tx); ASSERT_TRUE(sf); ASSERT_EQ(rear.receive_status(*sf),RearPowerResult::Accepted);
        auto limit=limits(ms,ms/10-1); const bool hv=std::get<can::BmsPowerStatus>(s->content).state==can::BmsPowerState::HvReady;
        if(!hv) { limit.local_state=can::ActuatorLocalState::Init; limit.origin=can::ActuatorOrigin::NoAcceptedInput; limit.content=can::BmsPowerLimits{0,0,can::BmsLimitReason::Disabled,can::BmsLimitReason::Disabled,port.now}; }
        const auto lf=can::encode_bms_frame(limit,limits_tx); ASSERT_TRUE(lf); ASSERT_EQ(rear.receive_limits(*lf),RearPowerResult::Accepted);
        drive.observe_local({battery::ModelMeasurement<double>{0,id,port.now},battery::ModelMeasurement<drive::HvFeedback>{{plant.diagnostic_state().bus_voltage_v,hv,false},id,port.now}},port.now);
        ASSERT_TRUE(motor.advance(port.now,false)); ASSERT_TRUE(drive.prepare(port.now)); const auto df=drive.complete(motor.capture(port.now),port.now); ASSERT_TRUE(df); ASSERT_TRUE(motor.apply(drive.output()));
        ASSERT_EQ(drive_rx.receive(*df,port.now).decision,can::ActuatorReceiveDecision::Accepted);
        auto in=front_fixture(ms); in.rear.drive_actual=drive_rx.current_sample(port.now); in.rear.power_status=rear.power_status(); in.rear.power_limits=rear.power_limits();
        if(ms%20==10) {
            const central::LifecycleRequest root{{3,root_seq++,port.now,ns(ms+60)},can::BmsPowerAction::Enable};
            ASSERT_EQ(owner.receive_request(root,port.now),central::LifecycleReceiveDecision::Accepted); ASSERT_EQ(rear.authorize_request(root),RearPowerResult::Accepted);
        }
        const auto out=owner.tick(in,port.now); ASSERT_TRUE(out); ASSERT_EQ(owner.decision().fault,central::VehicleManagementFault::None);
        if(owner.decision().normal_allowed && !active) { ASSERT_TRUE(rear.arm_normal_commands()); active=true; first_normal=ms; }
        ASSERT_EQ(rear.enqueue_power(out->power_request),RearPowerResult::Accepted); ASSERT_EQ(rear.enqueue_permission(out->drive_permission),RearPowerResult::Accepted);
        ASSERT_EQ(rear.dispatch(),3U); ASSERT_EQ(rear.poll().safety.cause,zone::ProtectionCause::None);
        central::AllocationInputs ai; ai.feedback=in; ai.management=owner.decision(); ai.permission=grant_rx.current_sample(port.now); ai.permission_parent=out->permission_parent;
        if(ms%20==0) {
            if(active) {
                const central::VehicleRequest r{3,vehicle_seq++,port.now,ns(ms+60),.2,0,0,false};
                ASSERT_EQ(allocation.receive_request(r,port.now),central::AllocationReceiveDecision::Accepted); ASSERT_EQ(normal.authorize_request(r),zone::AdmissionResult::Accepted);
            }
            const auto a=allocation.tick(ai,port.now);
            if(active) { ASSERT_TRUE(a); ASSERT_EQ(normal.enqueue(central::rear_commands(*a)),zone::AdmissionResult::Accepted); ASSERT_EQ(normal.dispatch().frames_enqueued,1U); }
            else EXPECT_FALSE(a);
        }
        if(power.output().phase==vecu::PowerPhase::Precharging) { precharge=true; EXPECT_FALSE(active); EXPECT_FALSE(drive.decision().active); EXPECT_DOUBLE_EQ(motor.actual_nm(),0); }
        if(!active) { EXPECT_TRUE(command_port.sent.empty()); }
        EXPECT_EQ(drive.decision().fault,vecu::DriveGateFault::None);
    }
    EXPECT_TRUE(precharge); ASSERT_TRUE(active); EXPECT_GT(first_normal,80U); ASSERT_FALSE(command_port.sent.empty());
    EXPECT_EQ(command_port.sent.front().sequence,0U); EXPECT_GE(command_port.sent.front().source_time_ns,ns(first_normal));
    EXPECT_GT(motor.actual_nm(),0); EXPECT_EQ(port.protections,0U);
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
} // namespace
