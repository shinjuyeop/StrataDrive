#include "owner_wire.hpp"
#include "run_lease_gate.hpp"
#include "run_lease_issuer.hpp"
#include "command_admission.hpp"
#include <gtest/gtest.h>
#include <cstring>
#include <limits>
#include <string>
#include <vector>

namespace {
using namespace stratadrive;
constexpr std::uint64_t kStart=1000000000,kMs=1000000,kClock=0x1122334455667788ULL;
const remote::ClockAgreement kCommon{kClock,kClock,0,0,true};
session::Plan plan(std::uint32_t epoch=42) { return {epoch,kStart,kStart+2000*kMs,kStart+20*kMs,kStart+40*kMs}; }
central::VehicleRequest root() { return {42,3,kStart,kStart+60*kMs,.2,.02,0,false}; }
central::FrontCommands front() {
    central::FrontCommands v;v.parent=root();v.oldest_input_time_ns=kStart;v.expires_at_ns=kStart+30*kMs;
    v.steering.epoch=v.brake.epoch=42;v.steering.source_time_ns=v.brake.source_time_ns=kStart;
    v.steering.local_state=v.brake.local_state=can::ActuatorLocalState::Normal;
    v.steering.origin=v.brake.origin=can::ActuatorOrigin::NormalPath;
    v.steering.angle_rad=.0539476501;v.brake.pressure_pa=0;return v;
}
remote::OwnerMessage sample(std::size_t kind) {
    remote::OwnerMessage m; m.clock_domain=kClock;
    switch(kind) {
    case 0:m.payload=session::Control{session::Role::FrontZone,session::Phase::Initialize,plan(),kStart};break;
    case 1:m.from=session::Role::FrontZone;m.to=session::Role::CentralIngress;m.payload=session::Ack{session::Role::FrontZone,session::Phase::Release,plan(),kStart+20*kMs,true};break;
    case 2:m.payload=remote::RunLease{plan(),0,kStart+20*kMs,kStart+80*kMs};break;
    case 3:m.payload=transport::ZoneRequest{42,0x0102030405060708ULL,kStart,kStart+20*kMs,root()};break;
    case 4:m.from=session::Role::FrontZone;m.to=session::Role::CentralIngress;m.payload=transport::TxResult{42,55,kStart,transport::Operation::Commands,true,2};break;
    case 5:{
        m.from=session::Role::FrontZone;m.to=session::Role::Steering;
        transport::LeafRequest r; r.epoch=42;r.token=55;r.sent_ns=kStart;r.deadline_ns=kStart+20*kMs;
        r.command=static_cast<const central::CommandContext&>(front());r.parent=can::BmsParentContext{42,7,kStart,kStart+60*kMs};r.lease=ActuatorStopLease{42,8,kStart,kStart+40*kMs};
        can::SteeringFrame f;f.can_id=can::kSteeringCommandId;
        for(std::size_t i=0;i<f.payload.size();++i) f.payload[i]=static_cast<std::uint8_t>(i*7);
        r.frame=f;m.payload=r;break;
    }
    case 6:m.from=session::Role::Steering;m.to=session::Role::FrontZone;m.payload=transport::LeafReport{transport::LeafResult{42,55,kStart,transport::LeafOperation::Stop,true}};break;
    case 7:m.payload=remote::ProtectionRequest{42,55,kStart,kStart+20*kMs};break;
    case 8:m.from=session::Role::FrontZone;m.to=session::Role::CentralIngress;m.payload=remote::ProtectionAck{{42,55,kStart,kStart+20*kMs},kStart+3*kMs,true};break;
    case 9:{m.from=session::Role::FrontZone;m.to=session::Role::CentralIngress;zone::ZoneHealthSnapshot h;h.epoch=42;h.source_time_ns=kStart;h.phase=zone::ZonePhase::Active;h.local_state=can::ActuatorLocalState::Normal;h.origin=can::ActuatorOrigin::NormalPath;h.ready_for_normal=true;m.payload=transport::Feedback{h};break;}
    default:throw std::invalid_argument("sample kind");
    }
    return m;
}
std::string hex(const remote::OwnerPacket& p) { std::string out;const char* digits="0123456789abcdef";for(std::size_t i=0;i<p.size;++i){out+=digits[p.bytes[i]>>4];out+=digits[p.bytes[i]&15];}return out; }
void repair_crc(remote::OwnerPacket& p) {const auto crc=remote::owner_crc32c(p.bytes.data(),p.size-4);for(unsigned i=0;i<4;++i)p.bytes[p.size-4+i]=static_cast<std::uint8_t>(crc>>(8*i));}
TEST(RemoteWire, Crc32cMatchesPublishedCheckVector) {const char* text="123456789";EXPECT_EQ(remote::owner_crc32c(reinterpret_cast<const std::uint8_t*>(text),9),0xe3069283U);}
TEST(RemoteWire, IndependentLittleEndianGoldenKeepsOriginalIdentityAndBinary64) {
    const auto p=remote::encode_owner_message(sample(3));ASSERT_TRUE(p);
    EXPECT_EQ(hex(*p),"534452560100000007000000000000008877665544332211032a000000080706050403020100ca9a3b0000000000f7cb3c00000000012a0000000300000000ca9a3b0000000000512e3f000000009a9999999999c93f7b14ae47e17a943f00000000000000000026d5dfa9");
}
class RemoteWireBodies : public ::testing::TestWithParam<std::size_t> {};
TEST_P(RemoteWireBodies, RoundTripPreservesExactCanonicalMessage) {
    const auto p=remote::encode_owner_message(sample(GetParam()));ASSERT_TRUE(p);
    const auto m=remote::decode_owner_message(p->bytes.data(),p->size);ASSERT_TRUE(m);
    const auto back=remote::encode_owner_message(*m);ASSERT_TRUE(back);EXPECT_EQ(p->size,back->size);EXPECT_EQ(p->bytes,back->bytes);
}
INSTANTIATE_TEST_SUITE_P(AllContracts,RemoteWireBodies,::testing::Range(std::size_t{0},std::size_t{10}));
TEST(RemoteWire, EverySingleBitCorruptionAndEveryTruncationIsRejected) {
    const auto p=remote::encode_owner_message(sample(5));ASSERT_TRUE(p);
    for(std::size_t i=0;i<p->size;++i) for(unsigned bit=0;bit<8;++bit) {auto bad=*p;bad.bytes[i]^=static_cast<std::uint8_t>(1U<<bit);EXPECT_FALSE(remote::decode_owner_message(bad.bytes.data(),bad.size));}
    for(std::size_t n=0;n<p->size;++n) EXPECT_FALSE(remote::decode_owner_message(p->bytes.data(),n));
    EXPECT_FALSE(remote::decode_owner_message(nullptr,p->size));
    EXPECT_FALSE(remote::decode_owner_message(p->bytes.data(),remote::kOwnerWireCapacity+1));
}
TEST(RemoteWire, ValidCrcCannotHideUnknownVersionReservedBooleanOrTruncatedEnum) {
    const auto p=remote::encode_owner_message(sample(9));ASSERT_TRUE(p);auto bad=*p;
    bad.bytes[4]=2;repair_crc(bad);EXPECT_FALSE(remote::decode_owner_message(bad.bytes.data(),bad.size));
    bad=*p;bad.bytes[6]=1;repair_crc(bad);EXPECT_FALSE(remote::decode_owner_message(bad.bytes.data(),bad.size));
    bad=*p;bad.bytes[p->size-5]=2;repair_crc(bad);EXPECT_FALSE(remote::decode_owner_message(bad.bytes.data(),bad.size));
    bad=*p;bad.bytes[51]=1;repair_crc(bad);EXPECT_FALSE(remote::decode_owner_message(bad.bytes.data(),bad.size));
}
TEST(RemoteWire, UnknownAndKnownZeroRemainDistinctAcrossAllBmsContents) {
    auto m=sample(3);auto& request=std::get<transport::ZoneRequest>(m.payload);m.to=session::Role::RearZone;
    for(std::size_t kind=0;kind<5;++kind) {
        central::VehicleManagementOutput out;out.power_request.epoch=out.drive_permission.epoch=42;
        switch(kind) {
        case 0:out.power_request.content=can::BmsPowerRequest{can::BmsPowerAction::Enable,kStart+40*kMs,kStart};break;
        case 1:out.power_request.content=can::BmsPowerLimits{0,std::nullopt,can::BmsLimitReason::Disabled,can::BmsLimitReason::InputsInvalid,kStart};break;
        case 2:out.power_request.content=can::BmsBatteryState{can::BmsSocSample{.63,kStart},can::BmsElectricalSample{400,-12.25,kStart-1},can::BmsTemperatureSample{25,kStart-2}};break;
        case 3:out.power_request.content=can::BmsPowerStatus{can::BmsPowerState::HvReady,true,true,false,7,31,400,kStart,kStart-10*kMs,123};break;
        case 4:out.power_request.content=can::BmsDriveGrant{can::BmsDrivePermission::AllowNormal,12,kStart,kStart-1,kStart+40*kMs};break;
        }
        out.power_parent=can::BmsParentContext{42,12,kStart,kStart+60*kMs};request.work=out;
        const auto p=remote::encode_owner_message(m);ASSERT_TRUE(p);const auto decoded=remote::decode_owner_message(p->bytes.data(),p->size);ASSERT_TRUE(decoded);
        const auto& recovered=std::get<central::VehicleManagementOutput>(std::get<transport::ZoneRequest>(decoded->payload).work);
        EXPECT_EQ(recovered.power_request.content.index(),kind);
        if(kind==1) { const auto& limits=std::get<can::BmsPowerLimits>(recovered.power_request.content);ASSERT_TRUE(limits.charge_power_w);EXPECT_EQ(*limits.charge_power_w,0);EXPECT_FALSE(limits.discharge_power_w); }
        EXPECT_EQ(remote::encode_owner_message(*decoded)->bytes,p->bytes);
    }
}
TEST(RemoteWire, EveryZoneOperationAndRawFrameAlternativeKeepsSideband) {
    auto m=sample(3);auto& r=std::get<transport::ZoneRequest>(m.payload);
    for(std::size_t kind=0;kind<6;++kind) {
        m.to=session::Role::RearZone;
        switch(kind) {
        case 0:r.work=central::LifecycleRequest{{42,3,kStart,kStart+60*kMs},can::BmsPowerAction::Enable};break;
        case 1:r.work=root();break;
        case 2:r.work=central::VehicleManagementOutput{};break;
        case 3:{central::RearCommands rear;rear.parent=root();rear.drive.regen_capability=can::DriveRegenCapability{10,kStart,kStart-1};rear.drive.wheel_speed=can::DriveWheelSpeed{0,kStart};r.work=central::ScopedCommands{rear};break;}
        case 4:r.work=transport::Arm{};break;
        case 5:r.work=central::NormalStopPlan{central::NormalStopState::HandoffPending,{{42,7,kStart,kStart+60*kMs},.02},{{42,8,kStart,kStart+60*kMs},can::BmsPowerAction::Shutdown},root(),{42,9,kStart,kStart+30*kMs},true};break;
        }
        const auto p=remote::encode_owner_message(m);ASSERT_TRUE(p);const auto v=remote::decode_owner_message(p->bytes.data(),p->size);ASSERT_TRUE(v);EXPECT_EQ(std::get<transport::ZoneRequest>(v->payload).work.index(),kind);
    }
    m=sample(5);auto& q=std::get<transport::LeafRequest>(m.payload);
    for(std::size_t kind=0;kind<4;++kind) {
        if(kind==0) q.frame=can::SteeringFrame{};
        if(kind==1) q.frame=can::BrakeFrame{};
        if(kind==2) q.frame=can::DriveFrame{};
        if(kind==3) q.frame=can::BmsFrame{};
        const auto p=remote::encode_owner_message(m);ASSERT_TRUE(p);const auto v=remote::decode_owner_message(p->bytes.data(),p->size);ASSERT_TRUE(v);
        EXPECT_EQ(std::get<transport::LeafRequest>(v->payload).frame.index(),kind);
        EXPECT_EQ(remote::encode_owner_message(*v)->bytes,p->bytes);
    }
}
TEST(RemoteWire, NoInnerCanCounterSourceOrCrcIsRegenerated) {
    can::SteeringMessage original;original.epoch=42;original.sequence=12;original.source_time_ns=UINT64_MAX-7;original.angle_rad=.0539;
    can::SteeringTxState tx{can::SteeringFrameKind::Command};const auto frame=can::encode_steering_frame(original,tx);ASSERT_TRUE(frame);
    auto m=sample(5);std::get<transport::LeafRequest>(m.payload).frame=*frame;
    const auto p=remote::encode_owner_message(m);ASSERT_TRUE(p);const auto decoded=remote::decode_owner_message(p->bytes.data(),p->size);ASSERT_TRUE(decoded);
    const auto& q=std::get<transport::LeafRequest>(decoded->payload);const auto& kept=std::get<can::SteeringFrame>(q.frame);
    EXPECT_EQ(kept.payload,frame->payload);EXPECT_EQ(can::decode_steering_frame(kept)->source_time_ns,UINT64_MAX-7);
    ASSERT_TRUE(q.command);EXPECT_EQ(q.command->expires_at_ns,kStart+30*kMs);ASSERT_TRUE(q.parent);EXPECT_EQ(q.parent->source_time_ns,kStart);
}
TEST(RemoteWire, NonFiniteTypedDemandAndWrongPeerRouteAreRejected) {
    auto m=sample(3);std::get<central::VehicleRequest>(std::get<transport::ZoneRequest>(m.payload).work).curvature_inv_m=std::numeric_limits<double>::quiet_NaN();EXPECT_FALSE(remote::encode_owner_message(m));
    m=sample(5);m.from=session::Role::RearZone;EXPECT_FALSE(remote::encode_owner_message(m));
}
TEST(RemoteWire, DelayedDecodedCommandKeepsOriginalExclusiveExpiryAtZone) {
    zone::CommandAdmission admission{zone::ZoneScope::Front};ASSERT_TRUE(admission.start_session(42,kStart));ASSERT_TRUE(admission.arm(kStart));
    ASSERT_EQ(admission.authorize_request(root(),kStart),zone::AdmissionResult::Accepted);
    auto m=sample(3);std::get<transport::ZoneRequest>(m.payload).work=central::ScopedCommands{front()};
    const auto p=remote::encode_owner_message(m);ASSERT_TRUE(p);const auto decoded=remote::decode_owner_message(p->bytes.data(),p->size);ASSERT_TRUE(decoded);
    const auto& scope=std::get<central::ScopedCommands>(std::get<transport::ZoneRequest>(decoded->payload).work);
    EXPECT_NE(admission.receive(scope,kStart+40*kMs),zone::AdmissionResult::Accepted);EXPECT_FALSE(admission.last_valid_receive_time_ns());
}
TEST(RemoteClock, WorstCaseAgeAndExclusiveExpiryIncludeUncertaintyWithoutRewritingSource) {
    const remote::ClockAgreement a{11,22,100,10,true};
    const auto bound=remote::mapped_time(1000,a);ASSERT_TRUE(bound);EXPECT_EQ(bound->earliest,1090U);EXPECT_EQ(bound->latest,1110U);
    EXPECT_FALSE(remote::source_and_expiry_current(1000,2000,1100,500,a)); // possible future
    EXPECT_TRUE(remote::source_and_expiry_current(1000,2000,1200,110,a));
    EXPECT_FALSE(remote::source_and_expiry_current(1000,2000,1200,109,a));
    EXPECT_FALSE(remote::source_and_expiry_current(1000,2000,2090,2000,a)); // earliest expiry
}
TEST(RemoteClock, UnknownDomainSignedOffsetAndArithmeticBoundsFailClosed) {
    EXPECT_FALSE(remote::mapped_time(1000,{}));
    EXPECT_FALSE(remote::mapped_time(UINT64_MAX,{1,2,1,0,true}));
    EXPECT_FALSE(remote::mapped_time(0,{1,2,-1,0,true}));
    EXPECT_FALSE(remote::mapped_time(0,{1,2,INT64_MIN,0,true}));
    EXPECT_FALSE(remote::mapped_time(5,{1,2,0,6,true}));
    EXPECT_EQ(remote::mapped_time(1000,{1,2,-100,10,true})->earliest,890U);
}
struct PeerPort final:session::ParticipantPort {
    std::uint64_t now{kStart};bool physical_safe{true};remote::RunLeaseGate gate;
    std::uint64_t now_ns() noexcept override {return now;}
    session::Preparation prepare(const session::Plan&) noexcept override {return physical_safe?session::Preparation::Ready:session::Preparation::Pending;}
    bool initialize(const session::Plan& p) noexcept override {return physical_safe && gate.bind(p,kCommon,now);}
    void protect() noexcept override {}
    void service() noexcept override {}
};
struct PeerFixture: ::testing::Test {
    PeerPort port;session::SessionParticipant local{session::Role::FrontZone,port};session::Plan current=plan();
    void ready(std::uint32_t epoch=42) {
        current=plan(epoch);current.requested_ns=port.now;current.prepare_deadline_ns=port.now+2000*kMs;current.enable_ns=port.now+20*kMs;current.commit_deadline_ns=port.now+40*kMs;
        auto prepare=current;prepare.enable_ns=prepare.commit_deadline_ns=0;
        ASSERT_TRUE(local.receive({session::Role::FrontZone,session::Phase::Prepare,prepare,port.now},port.now));
        ASSERT_FALSE(local.receive({session::Role::FrontZone,session::Phase::Initialize,current,port.now},port.now));
        port.now=current.enable_ns;ASSERT_TRUE(local.poll(port.now));ASSERT_TRUE(local.receive({session::Role::FrontZone,session::Phase::Release,current,port.now},port.now));
    }
    remote::RunLease lease(std::uint32_t seq=0) {return {current,seq,port.now,port.now+60*kMs};}
};
TEST_F(PeerFixture, LocalReleaseAloneCannotAuthorizeNormalCommands) {
    ready();EXPECT_TRUE(local.run_enabled());EXPECT_FALSE(port.gate.allows(local,port.now));
    EXPECT_TRUE(port.gate.receive(lease(),kClock,local,port.now));EXPECT_TRUE(port.gate.allows(local,port.now));
}
TEST_F(PeerFixture, SourceLossExpiresAndFreshSameEpochRenewalCannotHeal) {
    ready();ASSERT_TRUE(port.gate.receive(lease(),kClock,local,port.now));
    port.now+=30*kMs;EXPECT_TRUE(port.gate.allows(local,port.now));
    ++port.now;EXPECT_FALSE(port.gate.allows(local,port.now));EXPECT_EQ(port.gate.fault(),remote::RunLeaseFault::Expired);
    EXPECT_FALSE(port.gate.receive(lease(1),kClock,local,port.now));
    ++port.now;ready(43);ASSERT_TRUE(port.gate.receive(lease(),kClock,local,port.now));EXPECT_TRUE(port.gate.allows(local,port.now));
}
TEST_F(PeerFixture, ExactExpiryWrongClockOldPlanAndReplayNeverRefreshLease) {
    ready();auto first=lease();first.expires_at_ns=port.now+10*kMs;ASSERT_TRUE(port.gate.receive(first,kClock,local,port.now));
    EXPECT_FALSE(port.gate.receive(lease(1),kClock+1,local,port.now));
    auto wrong=lease(1);++wrong.plan.epoch;EXPECT_FALSE(port.gate.receive(wrong,kClock,local,port.now));
    EXPECT_FALSE(port.gate.receive(first,kClock,local,port.now));
    port.now=first.expires_at_ns;EXPECT_FALSE(port.gate.receive(lease(1),kClock,local,port.now));EXPECT_EQ(port.gate.fault(),remote::RunLeaseFault::Expired);
}
TEST_F(PeerFixture, ProtectionClockRollbackAndUnsafePreparationCannotAutoRecover) {
    ready();ASSERT_TRUE(port.gate.receive(lease(),kClock,local,port.now));port.gate.protect(42);
    EXPECT_FALSE(port.gate.allows(local,port.now));EXPECT_FALSE(port.gate.receive(lease(1),kClock,local,port.now));
    EXPECT_FALSE(port.gate.bind(plan(43),{1,2,100,0,true},port.now)); // mapped inner CAN not supported in Host profile
    PeerPort unsafe;unsafe.physical_safe=false;session::SessionParticipant waiting{session::Role::FrontZone,unsafe};auto proposal=plan();proposal.enable_ns=proposal.commit_deadline_ns=0;
    EXPECT_FALSE(waiting.receive({session::Role::FrontZone,session::Phase::Prepare,proposal,kStart},kStart));EXPECT_FALSE(unsafe.gate.receive(lease(),kClock,waiting,kStart));
    EXPECT_FALSE(port.gate.allows(local,port.now-1));EXPECT_EQ(port.gate.fault(),remote::RunLeaseFault::Clock);
}
TEST_F(PeerFixture, MissingFirstCreditHasItsOwnBoundedAcquisitionDeadline) {
    ready();port.now=current.commit_deadline_ns+session::kMessageAgeNs;
    EXPECT_FALSE(port.gate.receive(lease(),kClock,local,port.now));EXPECT_EQ(port.gate.fault(),remote::RunLeaseFault::AcquisitionTimeout);
}
struct CentralPort final:session::CoordinatorPort {
    std::uint64_t now{kStart};
    std::uint64_t now_ns() noexcept override{return now;}
    bool quiesce_central() noexcept override{return true;}
    bool send(const session::Control&) noexcept override{return true;}
    bool commit_central(central::CoordinatorSession) noexcept override{return true;}
    void protect_central() noexcept override{}
};
TEST(RemoteIssuer, NoGlobalCreditUntilEveryReleaseAckAndNoCreditAfterCancel) {
    CentralPort port;session::SessionCoordinator owner{port};central::RunLeaseIssuer issuer{owner};
    ASSERT_TRUE(owner.begin(42,port.now));EXPECT_FALSE(issuer.issue(port.now));
    for(const auto phase:{session::Phase::Prepare,session::Phase::Initialize,session::Phase::Release}) {
        if(phase==session::Phase::Initialize)port.now=owner.plan().enable_ns;
        for(std::size_t i=0;i<session::kRoleCount;++i) {
            if(phase==session::Phase::Release && i==session::kRoleCount-1) { EXPECT_FALSE(issuer.issue(port.now)); }
            ASSERT_EQ(owner.receive({static_cast<session::Role>(i),phase,owner.plan(),port.now,true},port.now),session::AckResult::Accepted);
        }
    }
    const auto permit=issuer.issue(port.now);ASSERT_TRUE(permit);EXPECT_EQ(permit->plan.epoch,42U);EXPECT_EQ(permit->source_time_ns,port.now);
    owner.cancel(port.now);EXPECT_FALSE(issuer.issue(port.now+1));ASSERT_TRUE(owner.begin(43,++port.now));
    auto late=session::Ack{session::Role::FrontZone,session::Phase::Release,permit->plan,port.now,true};
    remote::OwnerMessage message{session::Role::FrontZone,session::Role::CentralIngress,kClock,late};const auto encoded=remote::encode_owner_message(message);ASSERT_TRUE(encoded);
    const auto decoded=remote::decode_owner_message(encoded->bytes.data(),encoded->size);ASSERT_TRUE(decoded);
    EXPECT_EQ(owner.receive(std::get<session::Ack>(decoded->payload),port.now),session::AckResult::Rejected);EXPECT_FALSE(issuer.issue(port.now));
}
TEST(RemoteProtection, LateAckWrongRoleAndOldEpochCannotCompleteNewRequest) {
    remote::ProtectionReceipt receipt;remote::ProtectionRequest old{42,5,kStart,kStart+20*kMs};
    ASSERT_TRUE(receipt.expect(old,session::Role::FrontZone,kClock,kStart));
    remote::OwnerMessage ack{session::Role::FrontZone,session::Role::CentralIngress,kClock,remote::ProtectionAck{old,kStart+2*kMs,true}};
    EXPECT_FALSE(receipt.receive(ack,kStart+20*kMs));EXPECT_FALSE(receipt.acknowledged());
    remote::ProtectionRequest next{43,6,kStart+21*kMs,kStart+41*kMs};ASSERT_TRUE(receipt.expect(next,session::Role::FrontZone,kClock,kStart+21*kMs));
    EXPECT_FALSE(receipt.receive(ack,kStart+22*kMs));EXPECT_FALSE(receipt.acknowledged());
    ack.payload=remote::ProtectionAck{next,kStart+22*kMs,true};ack.from=session::Role::RearZone;EXPECT_FALSE(receipt.receive(ack,kStart+23*kMs));
    ack.from=session::Role::FrontZone;EXPECT_TRUE(receipt.receive(ack,kStart+23*kMs));EXPECT_TRUE(receipt.acknowledged());
    std::get<remote::ProtectionAck>(ack.payload).selected_ns++;EXPECT_FALSE(receipt.receive(ack,kStart+24*kMs));
}
TEST(RemoteProtection, SelectionRequestCannotExtendOriginalTwentyMillisecondBudget) {
    remote::ProtectionReceipt receipt;
    EXPECT_FALSE(receipt.expect({42,1,kStart,kStart+20*kMs+1},session::Role::Drive,kClock,kStart));
    EXPECT_FALSE(receipt.expect({42,1,kStart,kStart},session::Role::Drive,kClock,kStart));
}
TEST(RemoteProtection, MissingOrNegativeAckIsNotASelectionAndCannotOpenRunGate) {
    remote::ProtectionReceipt receipt;remote::ProtectionRequest r{42,1,kStart,kStart+20*kMs};ASSERT_TRUE(receipt.expect(r,session::Role::Drive,kClock,kStart));
    EXPECT_FALSE(receipt.acknowledged());
    remote::OwnerMessage ack{session::Role::Drive,session::Role::CentralIngress,kClock,remote::ProtectionAck{r,kStart+1*kMs,false}};
    EXPECT_FALSE(receipt.receive(ack,kStart+2*kMs));EXPECT_FALSE(receipt.acknowledged());
}
} // namespace
