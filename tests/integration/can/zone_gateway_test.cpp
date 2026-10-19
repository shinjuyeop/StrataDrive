#include "zone_gateway_port.hpp"
#include "steering_receiver.hpp"
#include "brake_receiver.hpp"
#include "drive_receiver.hpp"

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
}  // namespace
