#include "remote_leaf_endpoint.hpp"
#include "m4_owner_network.hpp"
#include <gtest/gtest.h>

namespace {
using namespace stratadrive;
constexpr std::uint64_t kMs=1000000,kClock=99;
struct RemoteLeafTest : ::testing::Test {
    simulation::m4_detail::Clock clock{false};transport::RunGate gate;transport::LeafLink link;
    std::array<runtime::LatestSnapshot<simulation::OwnerSensors>,session::kRoleCount> sensors;
    std::array<runtime::LatestSnapshot<simulation::OwnerActuation>,transport::kLeaves> outputs;
    simulation::BmsGateChannel bms;std::vector<simulation::M4Event> events;transport::Protection observer;
    simulation::m4_detail::PhysicalOwner physical{clock,gate,sensors,outputs,clock.now_ns(),events,observer,42};
    simulation::AsyncLeafOwner actor{transport::Leaf::Steering,clock,gate,link,sensors[2],outputs[0],bms};
    simulation::RemoteLeafEndpoint endpoint{session::Role::Steering,actor,gate,link,{kClock,kClock,0,0,true}};
    session::Plan plan{};std::uint32_t sequence{0};can::SteeringTxState tx{can::SteeringFrameKind::Command};
    void SetUp() override { physical.step();clock.logical+=kMs;physical.step(); }
    std::optional<remote::OwnerMessage> send(remote::OwnerPayload payload,session::Role from=session::Role::CentralIngress) {
        const remote::OwnerMessage m{from,session::Role::Steering,kClock,std::move(payload)};
        const auto packet=remote::encode_owner_message(m);if(!packet) {ADD_FAILURE()<<"wire encode";return {};}
        const auto decoded=remote::decode_owner_message(packet->bytes.data(),packet->size);
        if(!decoded) {ADD_FAILURE()<<"wire decode";return {};}
        return endpoint.receive(*decoded);
    }
    void step(bool renew=false) {clock.logical+=kMs;physical.step();if(renew && clock.logical% (10*kMs)==0) credit();endpoint.poll();while(endpoint.take_report()){} }
    void ready(std::uint32_t epoch=42) {
        sequence=0;plan={epoch,clock.logical,clock.logical+2000*kMs,clock.logical+20*kMs,clock.logical+40*kMs};
        auto proposal=plan;proposal.enable_ns=proposal.commit_deadline_ns=0;
        auto ack=send(session::Control{session::Role::Steering,session::Phase::Prepare,proposal,clock.logical});ASSERT_TRUE(ack);ASSERT_TRUE(std::get<session::Ack>(ack->payload).accepted);
        EXPECT_FALSE(send(session::Control{session::Role::Steering,session::Phase::Initialize,plan,clock.logical}));
        while(clock.logical<plan.enable_ns) {clock.logical+=kMs;physical.step();const auto response=endpoint.poll();if(response) { EXPECT_TRUE(std::get<session::Ack>(response->payload).accepted); }}
        ack=send(session::Control{session::Role::Steering,session::Phase::Release,plan,clock.logical});ASSERT_TRUE(ack);ASSERT_TRUE(std::get<session::Ack>(ack->payload).accepted);
    }
    void credit() {send(remote::RunLease{plan,sequence++,clock.logical,clock.logical+60*kMs});}
    transport::LeafRequest request(transport::LeafOperation op) {
        transport::LeafRequest r;r.epoch=plan.epoch;r.token=123;r.sent_ns=clock.logical;r.deadline_ns=clock.logical+20*kMs;r.operation=op;return r;
    }
    void arm() {
        credit();for(unsigned i=0;i<10;++i) step(true);
        EXPECT_FALSE(send(request(transport::LeafOperation::Arm),session::Role::FrontZone));endpoint.poll();
        bool found=false;while(const auto report=endpoint.take_report()) {
            const auto& body=std::get<transport::LeafReport>(report->payload);if(const auto* r=std::get_if<transport::LeafResult>(&body)) {found=true;EXPECT_TRUE(r->accepted);}
        }EXPECT_TRUE(found);
    }
    transport::LeafRequest command() {
        auto r=request(transport::LeafOperation::Frame);central::VehicleRequest root{plan.epoch,0,clock.logical,clock.logical+60*kMs,.2,.02,0,false};
        r.command=central::CommandContext{root,clock.logical,clock.logical+30*kMs};
        can::SteeringMessage m;m.kind=can::SteeringFrameKind::Command;m.epoch=plan.epoch;m.sequence=0;m.source_time_ns=clock.logical;
        m.local_state=can::ActuatorLocalState::Normal;m.origin=can::ActuatorOrigin::NormalPath;m.angle_rad=.054;
        const auto frame=can::encode_steering_frame(m,tx);EXPECT_TRUE(frame);if(frame)r.frame=*frame;return r;
    }
};
TEST_F(RemoteLeafTest, LocalReleaseAndUnarmedCreditCannotApplyACommand) {
    ready();EXPECT_FALSE(endpoint.allowed());auto r=command();auto rejected=send(r,session::Role::FrontZone);ASSERT_TRUE(rejected);
    EXPECT_FALSE(std::get<transport::LeafResult>(std::get<transport::LeafReport>(rejected->payload)).accepted);
    credit();EXPECT_TRUE(endpoint.allowed());EXPECT_FALSE(send(r,session::Role::FrontZone));endpoint.poll();EXPECT_EQ(actor.received_commands(),0U);
    const auto out=outputs[0].read();if(out && out->steering) { EXPECT_EQ(out->steering->mode,steering::ActuationMode::Hold); }
}
TEST_F(RemoteLeafTest, ArmedOriginalFrameProducesOriginalActualAndCompositeExpiryProtects) {
    ready();arm();const auto r=command();EXPECT_FALSE(send(r,session::Role::FrontZone));endpoint.poll();EXPECT_EQ(actor.received_commands(),1U);
    for(unsigned i=0;i<10;++i) step(true);
    clock.logical+=kMs;physical.step();endpoint.poll();bool actual=false;
    // Advance to the next control publication and verify receiver sees raw
    // source metadata from the actuator, not an adapter-generated echo.
    for(unsigned i=0;i<10;++i) {
        clock.logical+=kMs;physical.step();endpoint.poll();
        while(const auto m=endpoint.take_report()) {const auto& report=std::get<transport::LeafReport>(m->payload);
            if(const auto* f=std::get_if<transport::Feedback>(&report)) if(const auto* raw=std::get_if<can::SteeringFrame>(f)) {
                const auto p=remote::encode_owner_message(*m);ASSERT_TRUE(p);const auto decoded=remote::decode_owner_message(p->bytes.data(),p->size);ASSERT_TRUE(decoded);
                const auto& kept=std::get<can::SteeringFrame>(std::get<transport::Feedback>(std::get<transport::LeafReport>(decoded->payload)));
                EXPECT_EQ(raw->payload,kept.payload);const auto sample=can::decode_steering_frame(kept);ASSERT_TRUE(sample);
                EXPECT_EQ(sample->epoch,42U);EXPECT_EQ(sample->source_time_ns,clock.logical);ASSERT_TRUE(sample->angle_rad);EXPECT_NEAR(*sample->angle_rad,.1,.02);actual=true;
            }
        }
    }
    EXPECT_TRUE(actual);
    // Command and global credit expire independently; no Central atomic bypass.
    while(endpoint.lease_fault()==remote::RunLeaseFault::None) step();
    EXPECT_TRUE(actor.faulted());EXPECT_FALSE(endpoint.allowed());credit();EXPECT_FALSE(endpoint.allowed());
    EXPECT_TRUE(link.protection.acknowledged(42));
}
TEST_F(RemoteLeafTest, CreditSourceAgeAloneProtectsAnUnarmedLiveActor) {
    ready();credit();const auto source=clock.logical;
    while(clock.logical<source+30*kMs) step();
    EXPECT_TRUE(endpoint.allowed());EXPECT_FALSE(actor.faulted());step();
    EXPECT_EQ(endpoint.lease_fault(),remote::RunLeaseFault::Expired);EXPECT_TRUE(actor.faulted());EXPECT_FALSE(endpoint.allowed());
    credit();EXPECT_EQ(endpoint.lease_fault(),remote::RunLeaseFault::Expired);EXPECT_FALSE(endpoint.allowed());
}
TEST_F(RemoteLeafTest, ExplicitProtectionAckIsLeafSelectionAndPreviousEpochCannotProtectNewSession) {
    ready();arm();const auto before=sensors[2].read();ASSERT_TRUE(before);const auto angle=before->angle;ASSERT_TRUE(angle);
    const remote::ProtectionRequest p{42,987,clock.logical,clock.logical+20*kMs};auto ack=send(p);ASSERT_TRUE(ack);
    EXPECT_TRUE(std::get<remote::ProtectionAck>(ack->payload).selected);EXPECT_EQ(ack->from,session::Role::Steering);EXPECT_TRUE(actor.faulted());
    const auto selected=std::get<remote::ProtectionAck>(ack->payload).selected_ns;step();ack=send(p);ASSERT_TRUE(ack);EXPECT_EQ(std::get<remote::ProtectionAck>(ack->payload).selected_ns,selected);
    for(unsigned i=0;i<10;++i) { step(); }
    ready(43);credit();EXPECT_TRUE(endpoint.allowed());EXPECT_FALSE(send(p));EXPECT_TRUE(endpoint.allowed());
    const auto after=sensors[2].read();ASSERT_TRUE(after);ASSERT_TRUE(after->angle);EXPECT_EQ(after->angle->model_epoch,angle->model_epoch);EXPECT_NEAR(after->angle->angle_rad,angle->angle_rad,1e-12);
    auto old=request(transport::LeafOperation::Arm);old.epoch=42;auto rejected=send(old,session::Role::FrontZone);ASSERT_TRUE(rejected);
    EXPECT_FALSE(std::get<transport::LeafResult>(std::get<transport::LeafReport>(rejected->payload)).accepted);EXPECT_TRUE(endpoint.allowed());
}
TEST_F(RemoteLeafTest, ExpiredStopLeaseCannotBeRestampedByTransport) {
    ready();arm();send(command(),session::Role::FrontZone);endpoint.poll();for(unsigned i=0;i<10;++i)step(true);
    auto stop=request(transport::LeafOperation::Stop);stop.lease=ActuatorStopLease{42,0,clock.logical,clock.logical+20*kMs};
    send(stop,session::Role::FrontZone);endpoint.poll();bool selected=false;while(const auto m=endpoint.take_report())if(const auto* r=std::get_if<transport::LeafResult>(&std::get<transport::LeafReport>(m->payload)))selected=r->accepted;
    EXPECT_TRUE(selected);for(unsigned i=0;i<25;++i)step(true);EXPECT_TRUE(actor.faulted());EXPECT_FALSE(endpoint.allowed());
}
TEST_F(RemoteLeafTest, NormalFifoOverflowLatchesSessionAndNewEpochCannotRepairFailedLink) {
    ready();credit();const auto r=request(transport::LeafOperation::Arm);
    for(std::size_t i=0;i<transport::kBudget+1;++i)send(r,session::Role::FrontZone);
    EXPECT_TRUE(link.failed());EXPECT_TRUE(actor.faulted());EXPECT_FALSE(endpoint.allowed());
    auto proposal=plan;proposal.epoch=43;proposal.requested_ns=clock.logical;proposal.enable_ns=proposal.commit_deadline_ns=0;
    auto ack=send(session::Control{session::Role::Steering,session::Phase::Prepare,proposal,clock.logical});ASSERT_TRUE(ack);EXPECT_FALSE(std::get<session::Ack>(ack->payload).accepted);
}
// Keep the existing negative-response compatibility, but never reclassify its session.
struct RemoteOldRequestTest : RemoteLeafTest, ::testing::WithParamInterface<transport::LeafOperation> {};
TEST_P(RemoteOldRequestTest, RejoinedLeafReplyCannotPoisonCurrentZonePendingArm) {
    ready();arm();send(remote::ProtectionRequest{42,9,clock.logical,clock.logical+20*kMs});
    for(unsigned i=0;i<10;++i)step();
    ready(43);credit();
    transport::RunGate zone_gate; transport::ZoneLink central;
    std::array<transport::LeafLink,transport::kLeaves> leaves;
    std::array<transport::LeafLink*,transport::kLeaves> ptrs{};
    for(std::size_t i=0;i<ptrs.size();++i)ptrs[i]=&leaves[i];
    zone::AsyncZoneOwner zone{zone::ZoneScope::Front,clock,zone_gate,central,ptrs};
    ASSERT_TRUE(zone.initialize(43,clock.logical));zone_gate.release(43);
    ASSERT_TRUE(central.work.push({43,123,clock.logical,clock.logical+20*kMs,transport::Arm{}}));zone.service();
    const auto steer=leaves[0].work.pop(),brake=leaves[1].work.pop();ASSERT_TRUE(steer);ASSERT_TRUE(brake);
    const auto history=zone.input_history();const auto commands=actor.received_commands();
    auto old=request(GetParam());old.epoch=42;
    auto response=send(old,session::Role::FrontZone);ASSERT_TRUE(response);
    const auto rejected=std::get<transport::LeafReport>(response->payload);
    const auto result=std::get<transport::LeafResult>(rejected);
    EXPECT_EQ(result.epoch,42U);EXPECT_EQ(result.token,old.token);EXPECT_EQ(result.operation,old.operation);EXPECT_FALSE(result.accepted);
    for(unsigned i=0;i<2;++i) { // delayed/duplicated negative reply must not consume the pending arm
        ASSERT_TRUE(leaves[0].reports.push(rejected));zone.service();
        EXPECT_FALSE(zone.faulted());EXPECT_TRUE(zone_gate.allows(43));EXPECT_FALSE(central.results.pop());
    }
    EXPECT_TRUE(endpoint.allowed());EXPECT_FALSE(actor.faulted());EXPECT_EQ(actor.received_commands(),commands);
    const auto after=zone.input_history();for(std::size_t i=0;i<history.size();++i) {
        EXPECT_EQ(history[i].epoch,after[i].epoch);EXPECT_EQ(history[i].source_ns,after[i].source_ns);EXPECT_EQ(history[i].received_ns,after[i].received_ns);
    }
    ASSERT_TRUE(leaves[0].reports.push(transport::LeafResult{43,123,clock.logical,transport::LeafOperation::Arm,true}));
    ASSERT_TRUE(leaves[1].reports.push(transport::LeafResult{43,123,clock.logical,transport::LeafOperation::Arm,true}));zone.service();
    const auto armed=central.results.pop();ASSERT_TRUE(armed);EXPECT_TRUE(armed->accepted);EXPECT_TRUE(zone_gate.allows(43));
    // A genuine current-session negative Frame still selects protection.
    ASSERT_TRUE(leaves[0].reports.push(transport::LeafResult{43,124,clock.logical,transport::LeafOperation::Frame,false}));zone.service();
    EXPECT_TRUE(zone.faulted());EXPECT_FALSE(zone_gate.allows(43));
}
INSTANTIATE_TEST_SUITE_P(FrameArmStop,RemoteOldRequestTest,::testing::Values(
    transport::LeafOperation::Frame,transport::LeafOperation::Arm,transport::LeafOperation::Stop));
} // namespace
