#include "remote_leaf_endpoint.hpp"
#include "remote_zone_endpoint.hpp"
#include "../../interfaces/someip/owner_message_binding.hpp"
#include "m4_owner_network.hpp"
#include <gtest/gtest.h>
#include <limits>

namespace {
using namespace stratadrive;
constexpr std::uint64_t kMs=1000000,kDomain=99;
// Logical component wiring only: actual Central/Zone/Leaf controllers and plant.
// Separate Leaf gates/queues; all boundary traffic takes the canonical codec.
struct RemoteZoneIntegration : ::testing::Test {
    simulation::M4Config config;
    std::unique_ptr<simulation::m4_detail::Network> net;
    std::array<transport::RunGate,5> gates;
    std::array<transport::LeafLink,5> links;
    std::array<std::unique_ptr<simulation::AsyncLeafOwner>,5> actors;
    std::array<std::unique_ptr<simulation::RemoteLeafEndpoint>,5> endpoints;
    std::array<std::vector<transport::LeafRequest>,5> requests;
    std::array<std::vector<transport::LeafResult>,5> results;
    std::array<std::size_t,5> actuals{},arms{},stops{};
    bool inject_old_stop{false};std::size_t old_stop_replies{0};
    std::uint32_t credit_sequence{0};std::uint64_t last_credit{0};
    void start(bool stop=false) {
        config.first_epoch=42;config.scenario=stop?simulation::M4Scenario::NormalStop:simulation::M4Scenario::Normal;
        net=std::make_unique<simulation::m4_detail::Network>(config);
        for(std::size_t i=0;i<5;++i) {
            actors[i]=std::make_unique<simulation::AsyncLeafOwner>(static_cast<transport::Leaf>(i),net->clock,gates[i],links[i],net->sensors[i+2],net->outputs[i],net->bms_gate);
            endpoints[i]=std::make_unique<simulation::RemoteLeafEndpoint>(static_cast<session::Role>(i+2),*actors[i],gates[i],links[i],remote::ClockAgreement{kDomain,kDomain,0,0,true});
        }
    }
    remote::OwnerMessage wire(remote::OwnerMessage m) {
        const auto packet=remote::encode_owner_message(m);EXPECT_TRUE(packet);if(!packet)return m;
        const auto decoded=remote::decode_owner_message(packet->bytes.data(),packet->size);EXPECT_TRUE(decoded);if(!decoded)return m;
        const auto again=remote::encode_owner_message(*decoded);EXPECT_TRUE(again);
        if(again) {EXPECT_EQ(packet->size,again->size);EXPECT_EQ(packet->bytes,again->bytes);} // every inner byte/context is retained
        return *decoded;
    }
    session::Role zone(std::size_t i) {return i<2?session::Role::FrontZone:session::Role::RearZone;}
    void returned(std::size_t i,const std::optional<remote::OwnerMessage>& m) {
        if(!m)return;
        const auto decoded=wire(*m);
        if(const auto* a=std::get_if<session::Ack>(&decoded.payload)) {EXPECT_TRUE(net->session_links[i+2].acks.push(*a));return;}
        if(const auto* report=std::get_if<transport::LeafReport>(&decoded.payload)) {
            if(const auto* r=std::get_if<transport::LeafResult>(report)) {
                results[i].push_back(*r);
                if(r->accepted && r->operation==transport::LeafOperation::Arm)++arms[i];
                if(r->accepted && r->operation==transport::LeafOperation::Stop)++stops[i];
            } else ++actuals[i];
            EXPECT_TRUE(net->leaves[i].reports.push(*report));
        }
    }
    std::optional<remote::OwnerMessage> deliver(std::size_t i,transport::LeafRequest r) {
        return endpoints[i]->receive(wire({zone(i),static_cast<session::Role>(i+2),kDomain,r}));
    }
    void cycle() {
        const auto now=net->clock.logical;
        if((now-net->start)%kMs==0)net->step(8);
        net->step(0);net->step(1);
        const bool renew=net->startup.run_enabled() && net->gate.allows(42) && (!last_credit || now-last_credit>=10*kMs);
        for(std::size_t i=0;i<5;++i) {
            const auto role=static_cast<session::Role>(i+2);
            while(const auto c=net->session_links[i+2].controls.pop())returned(i,endpoints[i]->receive(wire({session::Role::CentralIngress,role,kDomain,*c})));
            if(renew)endpoints[i]->receive(wire({session::Role::CentralIngress,role,kDomain,remote::RunLease{net->startup.plan(),credit_sequence,now,now+60*kMs}}));
            while(const auto r=net->leaves[i].work.pop()) {
                requests[i].push_back(*r);
                EXPECT_LE(r->deadline_ns-r->sent_ns,transport::kResultBudgetNs)<<"leaf="<<i;
                EXPECT_LT(r->sent_ns,now); // Central's first enqueue time survives the Zone hop.
                if(inject_old_stop && r->operation==transport::LeafOperation::Stop) {
                    for(const auto op:{transport::LeafOperation::Frame,transport::LeafOperation::Arm,transport::LeafOperation::Stop}) {
                        auto old=*r;old.epoch=41;old.operation=op;
                        const auto rejected=deliver(i,old);ASSERT_TRUE(rejected);
                        EXPECT_EQ(std::get<transport::LeafResult>(std::get<transport::LeafReport>(rejected->payload)).epoch,41U);
                        returned(i,rejected);++old_stop_replies;
                    }
                }
                returned(i,deliver(i,*r));
            }
            returned(i,endpoints[i]->poll());
            while(const auto m=endpoints[i]->take_report())returned(i,m);
        }
        if(renew) {last_credit=now;++credit_sequence;}
        net->step(7);net->clock.logical+=200000;
    }
    void until(std::uint64_t elapsed) {while(net->clock.logical<=net->start+elapsed)cycle();}
};
TEST_F(RemoteZoneIntegration, RealZoneFramesArmApplyActualAndPowerAuthoritySurviveWire) {
    start();until(1100*kMs);
    EXPECT_TRUE(net->gate.allows(42));EXPECT_TRUE(net->core.decision().normal_armed);EXPECT_EQ(net->core.decision().fault,central::CoordinatorFault::None);
    for(const auto i:{0U,1U,2U}) {EXPECT_EQ(arms[i],1U);EXPECT_GT(actors[i]->received_commands(),10U);EXPECT_GT(actuals[i],20U);}
    std::size_t power=0,permission=0,limits=0;
    for(std::size_t i=0;i<5;++i)for(const auto& r:requests[i])if(const auto* f=std::get_if<can::BmsFrame>(&r.frame)) {
        const auto m=can::decode_bms_frame(*f);ASSERT_TRUE(m);
        if(m->kind==can::BmsFrameKind::PowerRequest) {++power;if(m->origin==can::ActuatorOrigin::NormalPath){EXPECT_TRUE(r.parent);}}
        if(m->kind==can::BmsFrameKind::DrivePermission) {++permission;if(std::get<can::BmsDriveGrant>(m->content).permission==can::BmsDrivePermission::AllowNormal){EXPECT_TRUE(r.parent);}}
        if(m->kind==can::BmsFrameKind::DriveBatteryLimits)++limits;
    }
    EXPECT_GT(power,20U);EXPECT_GT(permission,20U);EXPECT_GT(limits,20U);
    ASSERT_FALSE(net->physical.trace.empty());const auto& end=net->physical.trace.back();
    EXPECT_NEAR(end.angle_rad,std::atan(2.7*.02),.002);EXPECT_LT(end.pressure_pa,1);EXPECT_GT(end.torque_nm,50);EXPECT_GT(end.bus_v,395);
}
TEST_F(RemoteZoneIntegration, RealZoneNormalStopPreservesTerminalLeaseAndCompletesHvOff) {
    start(true);until(3000*kMs);
    for(const auto i:{0U,1U,2U}) {EXPECT_GT(stops[i],0U);for(const auto& r:requests[i])if(r.operation==transport::LeafOperation::Stop) {
        ASSERT_TRUE(r.lease);EXPECT_LE(r.deadline_ns,r.lease->expires_at_ns);EXPECT_EQ(r.lease->epoch,r.epoch);
    }}
    EXPECT_EQ(net->core.decision().fault,central::CoordinatorFault::None);
    ASSERT_FALSE(net->physical.trace.empty());EXPECT_LT(net->physical.trace.back().bus_v,30);EXPECT_LT(std::abs(net->physical.trace.back().torque_nm),.1);
}
TEST_F(RemoteZoneIntegration, ActualProducedEnvelopeExpiresExclusivelyWithoutRestamping) {
    start();until(1000*kMs);ASSERT_TRUE(net->core.decision().normal_armed);
    const auto found=std::find_if(requests[0].rbegin(),requests[0].rend(),[](const auto& r){return r.operation==transport::LeafOperation::Frame;});
    ASSERT_NE(found,requests[0].rend());const auto original=*found;const auto count=actors[0]->received_commands();
    // Network delay, no fresh timestamp/CRC/context creation. Gate/credit stay within their original windows.
    net->clock.logical=original.deadline_ns;
    const auto response=deliver(0,original);ASSERT_TRUE(response);
    const auto result=std::get<transport::LeafResult>(std::get<transport::LeafReport>(response->payload));
    EXPECT_FALSE(result.accepted);EXPECT_EQ(result.epoch,original.epoch);EXPECT_EQ(result.token,original.token);EXPECT_EQ(actors[0]->received_commands(),count);
}
TEST_F(RemoteZoneIntegration, OldFrameArmStopRepliesCannotConsumeCurrentPendingStop) {
    start(true);inject_old_stop=true;until(3000*kMs);
    EXPECT_GE(old_stop_replies,9U);EXPECT_EQ(net->core.decision().fault,central::CoordinatorFault::None);
    EXPECT_EQ(net->core.decision().stop.state,central::NormalStopState::Complete);
    for(const auto i:{0U,1U,2U})EXPECT_GT(stops[i],0U);
}
TEST(RemoteDeliveryDeadline, OverflowAndOriginalExclusiveBoundary) {
    constexpr auto maximum=std::numeric_limits<std::uint64_t>::max();
    EXPECT_EQ(transport::delivery_deadline(maximum-5,maximum),maximum);
    EXPECT_EQ(transport::delivery_deadline(100,100),100U);
    EXPECT_EQ(transport::delivery_deadline(101,100),100U);
    EXPECT_EQ(transport::delivery_deadline(100,maximum),100+transport::kResultBudgetNs);
    EXPECT_EQ(transport::delivery_deadline(100,120),120U);
}
TEST_F(RemoteZoneIntegration, DelayedPowerAndPermissionKeepOriginalExpiryAndCannotReachActor) {
    start();until(1100*kMs);ASSERT_TRUE(net->core.decision().normal_armed);
    std::array<transport::LeafRequest,2> selected{};
    for(std::size_t j=0;j<2;++j) {
        const auto leaf=j==0?4U:2U;const auto kind=j==0?can::BmsFrameKind::PowerRequest:can::BmsFrameKind::DrivePermission;
        const auto it=std::find_if(requests[leaf].rbegin(),requests[leaf].rend(),[&](const auto& r){
            const auto* f=std::get_if<can::BmsFrame>(&r.frame);const auto m=f?can::decode_bms_frame(*f):std::nullopt;return m && m->kind==kind;
        });ASSERT_NE(it,requests[leaf].rend());selected[j]=*it;
    }
    net->clock.logical=std::max(selected[0].deadline_ns,selected[1].deadline_ns);
    for(std::size_t j=0;j<2;++j) {
        const auto leaf=j==0?4U:2U;const auto response=deliver(leaf,selected[j]);ASSERT_TRUE(response);
        const auto rejected=std::get<transport::LeafResult>(std::get<transport::LeafReport>(response->payload));
        EXPECT_FALSE(rejected.accepted);EXPECT_EQ(rejected.token,selected[j].token);EXPECT_FALSE(links[leaf].work.pop());
    }
}
TEST_F(RemoteZoneIntegration, ExpiredArmAndStopResponsesRemainBoundToTheOriginalOperation) {
    start(true);until(3000*kMs);
    for(const auto op:{transport::LeafOperation::Arm,transport::LeafOperation::Stop}) {
        const auto it=std::find_if(requests[0].begin(),requests[0].end(),[&](const auto& r){return r.operation==op;});ASSERT_NE(it,requests[0].end());
        ASSERT_GE(net->clock.logical,it->deadline_ns);const auto reply=deliver(0,*it);ASSERT_TRUE(reply);
        const auto r=std::get<transport::LeafResult>(std::get<transport::LeafReport>(reply->payload));
        EXPECT_FALSE(r.accepted);EXPECT_EQ(r.operation,op);EXPECT_EQ(r.token,it->token);EXPECT_FALSE(links[0].work.pop());
    }
}
} // namespace

TEST(SomeipRearBinding, ServicesRolesAndPayloadAreBoundToOneEcu) {
    using namespace stratadrive;using someip::Ecu;using session::Role;
    for(const auto ecu:{Ecu::Front,Ecu::Rear}) {
        const bool rear=ecu==Ecu::Rear;const auto zone=rear?Role::RearZone:Role::FrontZone;
        for(unsigned i=0;i<8;++i) {
            const auto role=static_cast<Role>(i);
            remote::OwnerMessage m{Role::CentralIngress,role,someip::kDomain,session::Control{role,session::Phase::Prepare,{},0}};
            EXPECT_EQ(someip::binding(ecu,rear?0x5349:0x5345,1,0x40,1,1,m),someip::owns_role(ecu,role));
            EXPECT_FALSE(someip::binding(ecu,rear?0x5345:0x5349,1,0x40,1,1,m));
            if(someip::owns_role(ecu,role)) {
                EXPECT_FALSE(someip::binding(ecu,rear?0x5349:0x5345,1,0x20,1,1,m));
                EXPECT_FALSE(someip::binding(ecu,rear?0x5349:0x5345,1,0x40,0,1,m));
                EXPECT_FALSE(someip::binding(ecu,rear?0x5349:0x5345,1,0x40,1,2,m));
            }
            m={role,Role::CentralIngress,someip::kDomain,session::Ack{role,session::Phase::Release,{},0,true}};
            EXPECT_EQ(someip::binding(Ecu::Central,rear?0x534b:0x5347,1,0x40,1,1,m),someip::owns_role(ecu,role));
        }
        remote::OwnerMessage m{zone,Role::CentralIngress,someip::kDomain,transport::TxResult{}};
        EXPECT_TRUE(someip::binding(Ecu::Central,rear?0x534a:0x5346,1,0x80,1,1,m));
        m.from=rear?Role::Drive:Role::Steering;
        EXPECT_FALSE(someip::binding(Ecu::Central,rear?0x534a:0x5346,1,0x80,1,1,m));
        m={Role::CentralIngress,zone,someip::kDomain,transport::ZoneRequest{}};
        EXPECT_TRUE(someip::binding(ecu,rear?0x5348:0x5344,1,0x20,1,1,m));
        if(rear){EXPECT_FALSE(someip::binding(true,0x5348,1,0x20,1,1,m));} // opt-in only
    }
}

TEST(SomeipRearBinding, ZoneEndpointCannotAcquirePeerOwnershipOrAuthorityFromWrongRoute) {
    using namespace stratadrive;
    auto n=std::make_unique<simulation::m4_detail::Network>(simulation::M4Config{});
    constexpr remote::ClockAgreement clock{99,99,0,0,true};
    for(unsigned z=0;z<2;++z) {
        const auto role=static_cast<session::Role>(z);
        simulation::RemoteZoneEndpoint endpoint(role,*n->zone_sessions[z],*n->zone_owners[z],n->gate,n->zones[z],clock);
        const auto before=n->gate.epoch();
        EXPECT_FALSE(endpoint.receive({session::Role::CentralIngress,static_cast<session::Role>(1-z),99,transport::ZoneRequest{}}));
        EXPECT_EQ(n->gate.epoch(),before);EXPECT_FALSE(n->zones[z].work.pop());
        EXPECT_THROW((simulation::RemoteZoneEndpoint(session::Role::Drive,*n->zone_sessions[z],*n->zone_owners[z],n->gate,n->zones[z],clock)),std::invalid_argument);
        auto wrong=clock;wrong.established=false;
        EXPECT_THROW((simulation::RemoteZoneEndpoint(role,*n->zone_sessions[z],*n->zone_owners[z],n->gate,n->zones[z],wrong)),std::invalid_argument);
    }
}
