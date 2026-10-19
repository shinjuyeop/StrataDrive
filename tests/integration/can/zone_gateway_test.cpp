#include "zone_gateway_port.hpp"
#include "steering_receiver.hpp"
#include "brake_receiver.hpp"
#include "drive_receiver.hpp"
#include "rear_power_control.hpp"
#include "front_startup_control.hpp"

#include <gtest/gtest.h>
#include <chrono>
#include <thread>

namespace {
using namespace stratadrive;
constexpr std::uint64_t kMs=1000000;
struct Protection : zone::ProtectionPort {
    std::size_t calls{0};
    bool protect(zone::ZoneScope,zone::ProtectionCause,std::uint64_t) noexcept override { ++calls; return true; }
};
central::AllocatedCommands commands(std::uint64_t now) {
    central::AllocatedCommands c; c.parent={3,0,now,now+60*kMs,0,0.1,0.2,false};
    c.oldest_input_time_ns=now; c.expires_at_ns=now+30*kMs;
    const can::ActuatorMetadata m{0,3,now,0,can::ActuatorLocalState::Normal,can::ActuatorOrigin::NormalPath};
    static_cast<can::ActuatorMetadata&>(c.brake)=m; static_cast<can::ActuatorMetadata&>(c.drive)=m;
    c.steering.epoch=3; c.steering.source_time_ns=now; c.steering.local_state=m.local_state; c.steering.origin=m.origin;
    c.steering.angle_rad=.2; c.brake.pressure_pa=500000; c.drive.torque_nm=-50; return c;
}
std::optional<socketcan::ReceivedFrame> receive(socketcan::Endpoint& endpoint) {
    const auto until=socketcan::monotonic_time_ns()+20*kMs;
    do {
        if(auto frame=endpoint.receive()) return frame;
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    } while(socketcan::monotonic_time_ns()<until);
    return std::nullopt;
}
TEST(ZoneGatewayVcan, FrontCanFdFramesReachIndependentReceiversWithOriginalMetadata) {
    socketcan::Endpoint tx{"vcan_front"}, steering_rx{"vcan_front",can::kSteeringCommandId}, brake_rx{"vcan_front",can::kBrakeCommandId};
    Protection protection; socketcan::ZoneGatewayPort port{tx,protection}; zone::CommandGateway gateway{zone::ZoneScope::Front,port};
    const auto now=port.now_ns(); const auto c=commands(now);
    can::SteeringReceiver steering{{can::SteeringFrameKind::Command,-.3,.3}};
    can::BrakeReceiver brake{{can::BrakeFrameKind::Command,0,1500000}};
    ASSERT_TRUE(steering.start_session(3,now)); ASSERT_TRUE(brake.start_session(3,now));
    ASSERT_TRUE(gateway.start_session(3,now)); ASSERT_TRUE(gateway.arm());
    ASSERT_EQ(gateway.authorize_request(c.parent),zone::AdmissionResult::Accepted);
    ASSERT_EQ(gateway.enqueue(central::front_commands(c)),zone::AdmissionResult::Accepted);
    ASSERT_EQ(gateway.dispatch().frames_enqueued,2U);
    const auto s=receive(steering_rx), b=receive(brake_rx); ASSERT_TRUE(s); ASSERT_TRUE(b);
    ASSERT_EQ(steering.receive(socketcan::to_steering(s->frame),port.now_ns()).decision,can::ActuatorReceiveDecision::Accepted);
    ASSERT_EQ(brake.receive(socketcan::to_brake(b->frame),port.now_ns()).decision,can::ActuatorReceiveDecision::Accepted);
    EXPECT_EQ(steering.last_accepted()->message.source_time_ns,now); EXPECT_EQ(brake.last_accepted()->message.source_time_ns,now);
    EXPECT_EQ(brake.last_accepted()->message.causal_sequence,c.parent.sequence); EXPECT_EQ(protection.calls,0U);
}
TEST(ZoneGatewayVcan, ExpiredEnqueueDeadlineWritesNoKernelFrameAndInvokesLocalProtection) {
    socketcan::Endpoint tx{"vcan_front"}, rx{"vcan_front",can::kSteeringCommandId};
    Protection protection; socketcan::ZoneGatewayPort port{tx,protection}; zone::CommandGateway gateway{zone::ZoneScope::Front,port};
    const auto now=port.now_ns(); auto c=commands(now); c.expires_at_ns=now+5*kMs;
    ASSERT_TRUE(gateway.start_session(3,now)); ASSERT_TRUE(gateway.arm());
    ASSERT_EQ(gateway.authorize_request(c.parent),zone::AdmissionResult::Accepted);
    ASSERT_EQ(gateway.enqueue(central::front_commands(c)),zone::AdmissionResult::Accepted);
    std::this_thread::sleep_for(std::chrono::milliseconds(6));
    EXPECT_EQ(gateway.dispatch().frames_enqueued,0U); EXPECT_FALSE(rx.receive()); EXPECT_EQ(protection.calls,1U);
    can::SteeringTxState state{can::SteeringFrameKind::Command}; const auto frame=can::encode_steering_frame(c.steering,state); ASSERT_TRUE(frame);
    EXPECT_FALSE(tx.send_before(socketcan::to_socketcan(*frame),port.now_ns())); EXPECT_FALSE(rx.receive());
}
TEST(ZoneGatewayVcan, SeparateZoneInterfacesRouteRearDriveAndKeepFrontProtectionIndependent) {
    socketcan::Endpoint tx{"vcan_rear"}, rx{"vcan_rear",can::kDriveCommandId}, wrong_bus{"vcan_front",can::kDriveCommandId};
    socketcan::Endpoint front_tx{"vcan_front"}; Protection front_safety,rear_safety;
    socketcan::ZoneGatewayPort fp{front_tx,front_safety}, rp{tx,rear_safety};
    zone::CommandGateway front{zone::ZoneScope::Front,fp}, rear{zone::ZoneScope::Rear,rp};
    const auto now=rp.now_ns(); const auto c=commands(now);
    can::DriveReceiver drive{{can::DriveFrameKind::Command,{-200,300},100,200}}; ASSERT_TRUE(drive.start_session(3,now));
    ASSERT_TRUE(front.start_session(3,now)); ASSERT_TRUE(rear.start_session(3,now)); ASSERT_TRUE(rear.arm());
    ASSERT_EQ(rear.authorize_request(c.parent),zone::AdmissionResult::Accepted);
    ASSERT_EQ(rear.enqueue(central::rear_commands(c)),zone::AdmissionResult::Accepted);
    front.request_protection(); ASSERT_EQ(rear.dispatch().frames_enqueued,1U);
    const auto frame=receive(rx); ASSERT_TRUE(frame);
    ASSERT_EQ(drive.receive(socketcan::to_drive(frame->frame),rp.now_ns()).decision,can::ActuatorReceiveDecision::Accepted);
    const auto current=drive.current_sample(rp.now_ns()); ASSERT_TRUE(current);
    EXPECT_DOUBLE_EQ(*current->torque_nm,-50); EXPECT_FALSE(wrong_bus.receive());
    EXPECT_EQ(front_safety.calls,1U); EXPECT_EQ(rear_safety.calls,0U);
}
TEST(RearPowerVcan, RoutesThreeBmsStreamsWithOriginalTimesAndSeparateTrustedPowerParent) {
    socketcan::Endpoint tx{"vcan_rear"},pr{"vcan_rear",static_cast<std::uint16_t>(can::BmsFrameKind::PowerRequest)},
        lr{"vcan_rear",static_cast<std::uint16_t>(can::BmsFrameKind::DriveBatteryLimits)},gr{"vcan_rear",static_cast<std::uint16_t>(can::BmsFrameKind::DrivePermission)};
    vecu::DriveController drive{{}}; vecu::PowerController power{{}}; simulation::RearPowerControl control{drive,power};
    socketcan::RearPowerGatewayPort port{tx,control}; zone::RearPowerGateway gateway{port}; const auto now=port.now_ns();
    ASSERT_TRUE(drive.start_session({3,7,now},vecu::DriveCommandStartup::NonDriving)); ASSERT_TRUE(power.start_session(3,7,now));
    ASSERT_TRUE(control.start_session(3)); ASSERT_TRUE(gateway.start_session(3,now));
    can::BmsMessage l; l.kind=can::BmsFrameKind::PowerLimits; l.epoch=3; l.source_time_ns=now;
    l.local_state=can::ActuatorLocalState::Init; l.origin=can::ActuatorOrigin::NoAcceptedInput;
    l.content=can::BmsPowerLimits{0,0,can::BmsLimitReason::Disabled,can::BmsLimitReason::Disabled,now};
    auto s=l; s.kind=can::BmsFrameKind::PowerStatus; can::BmsPowerStatus actual;
    actual.state=can::BmsPowerState::Off; actual.positive_contactor_closed=actual.negative_contactor_closed=actual.precharge_contactor_closed=false;
    actual.hv_bus_voltage_v=0; actual.condition_bits=7; actual.condition_validity=31; actual.input_time_ns=now; s.content=actual;
    can::BmsTxState lt{l.kind},st{s.kind}; const auto lf=can::encode_bms_frame(l,lt),sf=can::encode_bms_frame(s,st); ASSERT_TRUE(lf); ASSERT_TRUE(sf);
    ASSERT_EQ(gateway.receive_limits(*lf),zone::RearPowerResult::Accepted); ASSERT_EQ(gateway.receive_status(*sf),zone::RearPowerResult::Accepted);
    ASSERT_EQ(gateway.authorize_request({{3,0,now,now+60*kMs},can::BmsPowerAction::Enable}),zone::RearPowerResult::Accepted);
    auto p=l; p.kind=can::BmsFrameKind::PowerRequest; p.origin=can::ActuatorOrigin::NormalPath; p.content=can::BmsPowerRequest{can::BmsPowerAction::Enable,now+40*kMs,now};
    auto g=l; g.kind=can::BmsFrameKind::DrivePermission; g.content=can::BmsDriveGrant{can::BmsDrivePermission::Inhibit,0,0,0,now+40*kMs};
    ASSERT_EQ(gateway.enqueue_power(p),zone::RearPowerResult::Accepted); ASSERT_EQ(gateway.enqueue_permission(g),zone::RearPowerResult::Accepted); ASSERT_EQ(gateway.dispatch(),3U);
    const auto power_frame=receive(pr),limit_frame=receive(lr),grant_frame=receive(gr); ASSERT_TRUE(power_frame); ASSERT_TRUE(limit_frame); ASSERT_TRUE(grant_frame);
    const auto native_power=socketcan::to_bms(power_frame->frame); const auto context=control.context_for(native_power,port.now_ns()); ASSERT_TRUE(context); ASSERT_TRUE(context->parent);
    EXPECT_EQ(context->parent->source_time_ns,now); EXPECT_EQ(power.receive(native_power,port.now_ns(),&*context->parent).decision,can::ActuatorReceiveDecision::Accepted);
    EXPECT_EQ(drive.receive_limits(socketcan::to_bms(limit_frame->frame),port.now_ns()).decision,can::ActuatorReceiveDecision::Accepted);
    const auto native_grant=socketcan::to_bms(grant_frame->frame); const auto gc=control.context_for(native_grant,port.now_ns()); ASSERT_TRUE(gc);
    EXPECT_EQ(drive.receive_permission(native_grant,port.now_ns(),nullptr).decision,can::ActuatorReceiveDecision::Accepted);
    EXPECT_EQ(can::decode_bms_frame(native_grant)->source_time_ns,now); EXPECT_FALSE(gc->parent);
}
TEST(FrontStartupVcan, EarlyPacketsCannotArmAndFirstNormalPairReachesActualLeafReceivers) {
    socketcan::Endpoint tx{"vcan_front"},sr{"vcan_front",can::kSteeringCommandId},br{"vcan_front",can::kBrakeCommandId};
    vecu::SteeringActuator steering{{-.5,.5,-.3,.3,.1,1,50*kMs}};
    vecu::BrakeActuator brake{{2000000,1500000,200000,5000000,10000000,1000000,50*kMs}};
    simulation::FrontStartupControl control{steering,brake}; socketcan::ZoneGatewayPort port{tx,control};
    zone::CommandGateway gateway{zone::ZoneScope::Front,port}; const auto acquired=port.now_ns(),enable=acquired-10*kMs;
    ASSERT_TRUE(steering.start_session({3,7,enable},ActuatorCommandStartup::NonDriving));
    ASSERT_TRUE(brake.start_session({3,7,enable},ActuatorCommandStartup::NonDriving)); ASSERT_TRUE(gateway.start_session(3,enable));
    ASSERT_TRUE(steering.prepare(acquired)); ASSERT_TRUE(brake.prepare(acquired));
    ASSERT_TRUE(steering.complete(steering::AngleMeasurement{7,0,acquired,.1},acquired));
    ASSERT_TRUE(brake.complete(brake::PressureMeasurement{7,0,acquired,200000},acquired));
    auto early=commands(port.now_ns()); early.steering.sequence=9; early.brake.sequence=9;
    can::SteeringTxState st{can::SteeringFrameKind::Command}; can::BrakeTxState bt{can::BrakeFrameKind::Command};
    ASSERT_NO_THROW(tx.send(socketcan::to_socketcan(*can::encode_steering_frame(early.steering,st))));
    ASSERT_NO_THROW(tx.send(socketcan::to_socketcan(*can::encode_brake_frame(early.brake,bt))));
    const auto sf=receive(sr),bf=receive(br); ASSERT_TRUE(sf); ASSERT_TRUE(bf);
    EXPECT_EQ(steering.receive(socketcan::to_steering(sf->frame),port.now_ns()).decision,can::ActuatorReceiveDecision::NotInitialized);
    EXPECT_EQ(brake.receive(socketcan::to_brake(bf->frame),port.now_ns()).decision,can::ActuatorReceiveDecision::NotInitialized);
    ASSERT_TRUE(control.arm_commands(gateway,{3,port.now_ns()})); const auto c=commands(port.now_ns());
    ASSERT_EQ(gateway.authorize_request(c.parent),zone::AdmissionResult::Accepted);
    ASSERT_EQ(gateway.enqueue(central::front_commands(c)),zone::AdmissionResult::Accepted); ASSERT_EQ(gateway.dispatch().frames_enqueued,2U);
    const auto normal_s=receive(sr),normal_b=receive(br); ASSERT_TRUE(normal_s); ASSERT_TRUE(normal_b);
    ASSERT_EQ(steering.receive(socketcan::to_steering(normal_s->frame),port.now_ns()).decision,can::ActuatorReceiveDecision::Accepted);
    ASSERT_EQ(brake.receive(socketcan::to_brake(normal_b->frame),port.now_ns()).decision,can::ActuatorReceiveDecision::Accepted);
    EXPECT_EQ(steering.receiver().last_accepted()->message.sequence,0U); EXPECT_EQ(brake.receiver().last_accepted()->message.sequence,0U);
    EXPECT_EQ(steering.receiver().last_accepted()->message.source_time_ns,c.steering.source_time_ns);
    EXPECT_EQ(brake.receiver().last_accepted()->message.source_time_ns,c.brake.source_time_ns);
    const auto handoff=port.now_ns(); const ActuatorStopLease lease{3,0,handoff,handoff+40*kMs};
    ASSERT_TRUE(steering.select_normal_stop(lease,handoff)); ASSERT_TRUE(brake.select_normal_stop(lease,handoff));
    ASSERT_TRUE(gateway.select_normal_stop(lease)); EXPECT_FALSE(gateway.arm());
    auto late=commands(port.now_ns()); late.steering.sequence=late.brake.sequence=1; late.brake.pressure_pa=0;
    ASSERT_NO_THROW(tx.send(socketcan::to_socketcan(*can::encode_steering_frame(late.steering,st))));
    ASSERT_NO_THROW(tx.send(socketcan::to_socketcan(*can::encode_brake_frame(late.brake,bt))));
    const auto late_s=receive(sr),late_b=receive(br); ASSERT_TRUE(late_s); ASSERT_TRUE(late_b);
    EXPECT_EQ(steering.receive(socketcan::to_steering(late_s->frame),port.now_ns()).decision,can::ActuatorReceiveDecision::ModeRejected);
    EXPECT_EQ(brake.receive(socketcan::to_brake(late_b->frame),port.now_ns()).decision,can::ActuatorReceiveDecision::ModeRejected);
    EXPECT_EQ(steering.receiver().last_accepted()->message.sequence,0U); EXPECT_EQ(brake.receiver().last_accepted()->message.sequence,0U);
}
}  // namespace
