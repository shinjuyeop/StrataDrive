#include "actual_boundary.hpp"
#include "steering_actuator.hpp"
#include "brake_actuator.hpp"
#include "drive_actuator.hpp"
#include "drive_controller.hpp"
#include <gtest/gtest.h>
#include <limits>
#include <functional>
#include <type_traits>

namespace {
using namespace stratadrive;
using namespace stratadrive::m7_test;
constexpr Time start=1000000000;
Time t(unsigned value) { return start+value*ms; }
struct Spy final : Backend {
    unsigned applies{0},ticks{0};
    ApplyResult result{ApplyResult::Applied};
    bool tick_ack{true}, throw_apply{false}, throw_tick{false};
    std::optional<ActualBundle> observed;
    std::function<void()> on_apply;
private:
    ApplyResult apply(const ActualBundle& a,const Interval&) override { ++applies; observed=a; if(on_apply)on_apply(); if(throw_apply)throw std::runtime_error("apply RPC lost"); return result; }
    bool tick(const Interval&) override { ++ticks; if(throw_tick)throw std::runtime_error("tick RPC lost"); return tick_ack; }
};
Provenance support(Time source=t(10)) {
    return {1,10,7,{{{Role::Steering,source,t(70)},{Role::Brake,source,t(70)},{Role::Drive,source,t(70)}}}};
}
Frames vector(std::uint32_t epoch=1, unsigned source=10, unsigned sequence=0, bool commands=false) {
    can::SteeringMessage s;
    s.kind=commands?can::SteeringFrameKind::Command:can::SteeringFrameKind::Actual;
    s.epoch=epoch; s.sequence=sequence; s.source_time_ns=t(source); s.causal_sequence=42;
    s.local_state=can::ActuatorLocalState::Normal; s.origin=can::ActuatorOrigin::NormalPath; s.angle_rad=.05;
    can::SteeringTxState st{s.kind}; st.protection.counter=static_cast<std::uint8_t>(sequence);
    can::BrakeMessage b; b.kind=commands?can::BrakeFrameKind::Command:can::BrakeFrameKind::Actual;
    b.epoch=epoch; b.sequence=sequence; b.source_time_ns=t(source); b.causal_sequence=43;
    b.local_state=can::ActuatorLocalState::Normal; b.origin=can::ActuatorOrigin::NormalPath; b.pressure_pa=200000;
    can::BrakeTxState bt{b.kind}; bt.protection.counter=static_cast<std::uint8_t>(sequence);
    can::DriveMessage d; d.kind=commands?can::DriveFrameKind::Command:can::DriveFrameKind::Actual;
    d.epoch=epoch; d.sequence=sequence; d.source_time_ns=t(source); d.causal_sequence=44;
    d.local_state=can::ActuatorLocalState::Normal; d.origin=can::ActuatorOrigin::NormalPath; d.torque_nm=25;
    can::DriveTxState dt{d.kind}; dt.protection.counter=static_cast<std::uint8_t>(sequence);
    return {can::encode_steering_frame(s,st),can::encode_brake_frame(b,bt),can::encode_drive_frame(d,dt)};
}
class Contract : public testing::Test {
protected:
    Spy spy;
    Boundary boundary{spy};
    std::unique_ptr<Boundary::Writer> writer=boundary.claim();
    std::uint64_t ticket{0};
    void SetUp() override { ASSERT_TRUE(writer); ASSERT_EQ(boundary.start(*writer,1,7,1,10,start),Code::Ok); }
    void receive() { ASSERT_EQ(boundary.receive(*writer,vector(),support(),t(10)),Code::Ok); }
    Code prepare(Time end=t(20),Mode mode=Mode::FakeProbe) {
        return boundary.prepare(*writer,mode,{1,t(10),end},t(10),ticket);
    }
};
TEST_F(Contract, ValidActualAppliesOnceAndPreservesBytesIdentityAndOriginalTimes) {
    const auto raw=vector();
    ASSERT_EQ(boundary.receive(*writer,raw,support(),t(12)),Code::Ok);
    ASSERT_EQ(boundary.prepare(*writer,Mode::FakeProbe,{1,t(12),t(20)},t(12),ticket),Code::Ok);
    EXPECT_EQ(spy.applies,0U); EXPECT_EQ(spy.ticks,0U);
    ASSERT_EQ(boundary.commit(*writer,ticket,t(12)),Code::Ok);
    ASSERT_TRUE(spy.observed);
    const auto& a=*spy.observed;
    EXPECT_DOUBLE_EQ(*a.steering.angle_rad,.05); EXPECT_DOUBLE_EQ(*a.brake.pressure_pa,200000);
    EXPECT_DOUBLE_EQ(*a.drive.torque_nm,25); EXPECT_EQ(a.drive.source_time_ns,t(10));
    EXPECT_EQ(a.drive.sequence,0U); EXPECT_EQ(a.drive.causal_sequence,44U); EXPECT_EQ(a.received_at,t(12));
    EXPECT_EQ(a.provenance.support[2].oldest,t(10)); EXPECT_EQ(a.provenance.support[2].exclusive_expiry,t(70));
    EXPECT_EQ(a.original_frames.drive->payload,raw.drive->payload);
    ASSERT_EQ(boundary.advance(*writer,ticket,1,t(12)),Code::Ok);
    EXPECT_EQ(spy.applies,1U); EXPECT_EQ(spy.ticks,1U);
    EXPECT_EQ(boundary.commit(*writer,ticket,t(12)),Code::Ticket);
    EXPECT_EQ(spy.applies,1U); EXPECT_EQ(spy.ticks,1U);
}
TEST_F(Contract, NativeLeafSoftwareReportsSensorsRatherThanCommandTargets) {
    vecu::SteeringActuator steering({-.5,.5,-.3,.3,0,1,50*ms});
    vecu::BrakeActuator brake({2000000,1500000,0,5000000,10000000,1000000,50*ms});
    vecu::DriveActuator drive({{-300,500},{-200,300,0,1000,2000,50*ms}});
    ASSERT_TRUE(steering.start_session({1,7,start})); ASSERT_TRUE(brake.start_session({1,7,start}));
    ASSERT_TRUE(drive.start_session({1,7,start}));
    auto command=vector(1,10,0,true);
    ASSERT_EQ(steering.receive(*command.steering,t(10)).decision,can::ActuatorReceiveDecision::Accepted);
    ASSERT_EQ(brake.receive(*command.brake,t(10)).decision,can::ActuatorReceiveDecision::Accepted);
    ASSERT_EQ(drive.receive(*command.drive,t(10)).decision,can::ActuatorReceiveDecision::Accepted);
    ASSERT_TRUE(steering.prepare(t(10))); ASSERT_TRUE(brake.prepare(t(10))); ASSERT_TRUE(drive.prepare(t(10)));
    // Intentionally different sensor values from the accepted demands (.05,200k,25).
    Frames actual{steering.complete(steering::AngleMeasurement{7,1,t(10),.02},t(10)),
        brake.complete(brake::PressureMeasurement{7,1,t(10),100000},t(10)),
        drive.complete(drive::TorqueMeasurement{7,1,t(10),5},t(10))};
    ASSERT_EQ(boundary.receive(*writer,actual,support(),t(10)),Code::Ok);
    ASSERT_EQ(prepare(),Code::Ok); ASSERT_EQ(boundary.commit(*writer,ticket,t(10)),Code::Ok);
    EXPECT_DOUBLE_EQ(*spy.observed->steering.angle_rad,.02);
    EXPECT_DOUBLE_EQ(*spy.observed->brake.pressure_pa,100000); EXPECT_DOUBLE_EQ(*spy.observed->drive.torque_nm,5);
}
TEST(M7Ingress, CommandCanNeverBeAcceptedAsActualForAnyActuator) {
    for (unsigned role=0;role<3;++role) {
        Spy spy; Boundary b(spy); auto w=b.claim(); ASSERT_EQ(b.start(*w,1,7,1,10,start),Code::Ok);
        auto actual=vector(), command=vector(1,10,0,true);
        if(role==0) actual.steering=command.steering;
        if(role==1) actual.brake=command.brake;
        if(role==2) actual.drive=command.drive;
        EXPECT_EQ(b.receive(*w,actual,support(),t(10)),Code::Receiver) << role;
        EXPECT_EQ(spy.applies,0U); EXPECT_EQ(spy.ticks,0U);
    }
    static_assert(!std::is_constructible_v<Frames,double,double,double>);
    static_assert(!std::is_copy_constructible_v<Boundary::Writer>);
    static_assert(!std::is_copy_constructible_v<Boundary>);
}
TEST(M7Ingress, WrongRoleRunPlantAndClockCannotAcquireTrustedIdentity) {
    for(unsigned fault=0;fault<4;++fault) {
        Spy spy; Boundary b(spy); auto w=b.claim(); ASSERT_EQ(b.start(*w,1,7,1,10,start),Code::Ok);
        auto p=support();
        if(fault==0)p.support[2].role=Role::Steering;
        if(fault==1)++p.run;
        if(fault==2)++p.plant;
        if(fault==3)++p.clock;
        EXPECT_EQ(b.receive(*w,vector(),p,t(10)),Code::Source);
        EXPECT_EQ(spy.applies,0U); EXPECT_EQ(spy.ticks,0U);
    }
}
TEST_F(Contract, OldEpochCannotStartSessionFromPayload) {
    EXPECT_EQ(boundary.receive(*writer,vector(2),support(),t(10)),Code::Receiver);
    EXPECT_EQ(boundary.fault(),Code::Receiver); EXPECT_EQ(spy.applies,0U);
}
TEST(M7Ingress, MissingInvalidCrcUnavailableAndOutOfRangeRemainUnavailable) {
    for(unsigned fault=0;fault<6;++fault) {
        Spy spy; Boundary b(spy); auto w=b.claim(); ASSERT_EQ(b.start(*w,1,7,1,10,start),Code::Ok);
        auto raw=vector();
        if(fault==0)raw.steering.reset();
        if(fault==1)raw.brake.reset();
        if(fault==2)raw.drive.reset();
        if(fault==3)raw.drive->payload[0]^=1;
        if(fault==4 || fault==5) {
            auto d=*can::decode_drive_frame(*raw.drive);
            if(fault==4)d.torque_nm.reset(); else d.torque_nm=400; // wire valid, outside this fixture
            can::DriveTxState tx{d.kind};raw.drive=can::encode_drive_frame(d,tx);
        }
        const auto code=b.receive(*w,raw,support(),t(10));
        EXPECT_EQ(code,fault<3?Code::Missing:Code::Receiver) << fault;
        std::uint64_t id=0; EXPECT_EQ(b.prepare(*w,Mode::FakeProbe,{1,t(10),t(20)},t(10),id),code);
        EXPECT_EQ(spy.applies,0U); EXPECT_EQ(spy.ticks,0U);
    }
}
TEST(M7Ingress, NonfiniteProducerValuesCannotBeEncodedIntoActual) {
    const auto raw=vector();
    auto s=*can::decode_steering_frame(*raw.steering);s.angle_rad=std::numeric_limits<double>::quiet_NaN();
    auto b=*can::decode_brake_frame(*raw.brake);b.pressure_pa=std::numeric_limits<double>::infinity();
    auto d=*can::decode_drive_frame(*raw.drive);d.torque_nm=std::numeric_limits<double>::quiet_NaN();
    can::SteeringTxState st{s.kind};can::BrakeTxState bt{b.kind};can::DriveTxState dt{d.kind};
    EXPECT_FALSE(can::encode_steering_frame(s,st));EXPECT_FALSE(can::encode_brake_frame(b,bt));
    EXPECT_FALSE(can::encode_drive_frame(d,dt));
}
TEST(M7Ingress, StaleFutureAndOldestDependencyChecksDoNotRestamp) {
    for(unsigned fault=0;fault<5;++fault) {
        Spy spy;Boundary b(spy);auto w=b.claim();ASSERT_EQ(b.start(*w,1,7,1,10,start),Code::Ok);
        auto p=support();auto raw=vector();Time now=t(10);Code expected=Code::Time;
        if(fault==0){now=t(41);expected=Code::Receiver;}
        if(fault==1){now=t(9);expected=Code::Receiver;}
        if(fault==2)p.support[2].oldest=t(11);
        if(fault==3)p.support[2].oldest=start-1;
        if(fault==4){p.support[2].oldest=t(0);raw=vector(1,20);now=t(20);expected=Code::Skew;}
        EXPECT_EQ(b.receive(*w,raw,p,now),expected) << fault;
        EXPECT_EQ(spy.applies,0U); EXPECT_EQ(spy.ticks,0U);
    }
}
TEST_F(Contract, CachedActualAndChangedCachedValueCannotRenewSource) {
    receive();
    auto changed=vector(1,10,1);
    auto d=*can::decode_drive_frame(*changed.drive);d.torque_nm=99;
    can::DriveTxState tx{d.kind};tx.protection.counter=1;changed.drive=can::encode_drive_frame(d,tx);
    EXPECT_EQ(boundary.receive(*writer,changed,support(),t(20)),Code::Receiver);
    EXPECT_EQ(spy.applies,0U); EXPECT_EQ(spy.ticks,0U);
}
TEST_F(Contract, PreparedSnapshotDoesNotFollowCallerMutation) {
    auto frames=vector();auto p=support();
    ASSERT_EQ(boundary.receive(*writer,frames,p,t(10)),Code::Ok);ASSERT_EQ(prepare(),Code::Ok);
    frames.drive->payload.fill(0);p.support[2].oldest=t(20);
    ASSERT_EQ(boundary.commit(*writer,ticket,t(10)),Code::Ok);
    EXPECT_EQ(spy.observed->drive.source_time_ns,t(10));
    EXPECT_DOUBLE_EQ(*spy.observed->drive.torque_nm,25);
    EXPECT_EQ(spy.observed->provenance.support[2].oldest,t(10));
}
TEST_F(Contract, SecondWriterForeignHandleAndForeignThreadHaveNoBackendAccess) {
    EXPECT_FALSE(boundary.claim());
    Spy other_spy;Boundary other(other_spy);auto other_writer=other.claim();
    EXPECT_EQ(boundary.receive(*other_writer,vector(),support(),t(10)),Code::Writer);
    Code foreign=Code::Ok;
    std::thread worker([&]{foreign=boundary.receive(*writer,vector(),support(),t(10));});worker.join();
    EXPECT_EQ(foreign,Code::Writer);EXPECT_EQ(boundary.fault(),Code::Ok);
    EXPECT_EQ(spy.applies,0U);EXPECT_EQ(spy.ticks,0U);
    receive();ASSERT_EQ(prepare(),Code::Ok);
    std::thread commit([&]{foreign=boundary.commit(*writer,ticket,t(10));});commit.join();
    EXPECT_EQ(foreign,Code::Writer);EXPECT_EQ(spy.applies,0U);
    ASSERT_EQ(boundary.commit(*writer,ticket,t(10)),Code::Ok);
    std::thread tick([&]{foreign=boundary.advance(*writer,ticket,1,t(10));});tick.join();
    EXPECT_EQ(foreign,Code::Writer);EXPECT_EQ(spy.ticks,0U);
    EXPECT_EQ(boundary.advance(*writer,ticket,1,t(10)),Code::Ok);
}
TEST_F(Contract, SameBackendCannotBeBoundByASecondAdapter) {
    Boundary other(spy); EXPECT_FALSE(other.claim());
    receive(); ASSERT_EQ(prepare(),Code::Ok);
    EXPECT_EQ(boundary.commit(*writer,ticket,t(10)),Code::Ok); EXPECT_EQ(spy.applies,1U);
}
TEST_F(Contract, ThrowingApplyIsAmbiguousAndCannotBeRetried) {
    receive(); ASSERT_EQ(prepare(),Code::Ok); spy.throw_apply=true;
    EXPECT_EQ(boundary.commit(*writer,ticket,t(10)),Code::ApplyAmbiguous);
    EXPECT_EQ(boundary.commit(*writer,ticket,t(10)),Code::ApplyAmbiguous);
    EXPECT_EQ(boundary.advance(*writer,ticket,1,t(10)),Code::ApplyAmbiguous);
    EXPECT_EQ(spy.applies,1U); EXPECT_EQ(spy.ticks,0U);
}
TEST_F(Contract, ThrowingTickIsAmbiguousAndCannotBeRetried) {
    receive(); ASSERT_EQ(prepare(),Code::Ok); ASSERT_EQ(boundary.commit(*writer,ticket,t(10)),Code::Ok);
    spy.throw_tick=true;
    EXPECT_EQ(boundary.advance(*writer,ticket,1,t(10)),Code::TickAmbiguous);
    EXPECT_EQ(boundary.advance(*writer,ticket,1,t(10)),Code::TickAmbiguous);
    EXPECT_EQ(spy.ticks,1U);
}
TEST(M7Writer, ConcurrentAdapterBindingCanCreateOnlyOneBackendOwner) {
    Spy spy; std::atomic<unsigned> owners{0};
    std::thread a([&]{Boundary b(spy);if(b.claim())++owners;});
    std::thread b([&]{Boundary c(spy);if(c.claim())++owners;});
    a.join();b.join();EXPECT_EQ(owners.load(),1U);EXPECT_EQ(spy.applies,0U);EXPECT_EQ(spy.ticks,0U);
}
TEST_F(Contract, WrongPreparedFrameIsRejectedWithoutApply) {
    receive();std::uint64_t id=0;
    EXPECT_EQ(boundary.prepare(*writer,Mode::FakeProbe,{2,t(10),t(20)},t(10),id),Code::Frame);
    EXPECT_EQ(spy.applies,0U);EXPECT_EQ(spy.ticks,0U);
}
TEST_F(Contract, WrongTickFrameCannotConsumeSuccessfulApplyAsAnotherFrame) {
    receive();ASSERT_EQ(prepare(),Code::Ok);ASSERT_EQ(boundary.commit(*writer,ticket,t(10)),Code::Ok);
    EXPECT_EQ(boundary.advance(*writer,ticket,2,t(10)),Code::Ticket);
    EXPECT_EQ(spy.applies,1U);EXPECT_EQ(spy.ticks,0U);
}
TEST_F(Contract, PendingSnapshotCannotBeReplacedByNewIngress) {
    receive();ASSERT_EQ(prepare(),Code::Ok);
    EXPECT_EQ(boundary.receive(*writer,vector(1,11,1),support(t(11)),t(11)),Code::Pending);
    EXPECT_EQ(boundary.commit(*writer,ticket,t(11)),Code::Pending);
    EXPECT_EQ(spy.applies,0U);EXPECT_EQ(spy.ticks,0U);
}
TEST_F(Contract, ReentrantBackendCannotReplaceOrResetAnInFlightApply) {
    receive();ASSERT_EQ(prepare(),Code::Ok);
    spy.on_apply=[&]{
        EXPECT_EQ(boundary.start(*writer,2,7,1,10,t(10)),Code::Pending);
        EXPECT_EQ(boundary.receive(*writer,vector(1,11,1),support(t(11)),t(11)),Code::Pending);
    };
    EXPECT_EQ(boundary.commit(*writer,ticket,t(10)),Code::Pending);
    EXPECT_EQ(boundary.advance(*writer,ticket,1,t(11)),Code::Pending);
    EXPECT_EQ(spy.applies,1U);EXPECT_EQ(spy.ticks,0U);
}
TEST_F(Contract, TickWithoutApplyAndWrongTicketCannotAdvance) {
    EXPECT_EQ(boundary.advance(*writer,999,1,t(10)),Code::Ticket);
    EXPECT_EQ(spy.applies,0U);EXPECT_EQ(spy.ticks,0U);
}
TEST_F(Contract, DuplicateTickCannotAdvanceTwice) {
    receive();ASSERT_EQ(prepare(),Code::Ok);ASSERT_EQ(boundary.commit(*writer,ticket,t(10)),Code::Ok);
    ASSERT_EQ(boundary.advance(*writer,ticket,1,t(10)),Code::Ok);
    EXPECT_EQ(boundary.advance(*writer,ticket,1,t(10)),Code::Ticket);
    EXPECT_EQ(spy.applies,1U);EXPECT_EQ(spy.ticks,1U);
}
TEST_F(Contract, NonDrivingAndCarlaDrivingAreDisabledEvenWithValidActual) {
    receive();EXPECT_EQ(prepare(t(20),Mode::CarlaDriving),Code::Disabled);
    EXPECT_EQ(spy.applies,0U);EXPECT_EQ(spy.ticks,0U);
}
TEST_F(Contract, NonDrivingModeDoesNotGrantProbeAuthority) {
    receive();EXPECT_EQ(prepare(t(20),Mode::NonDriving),Code::Disabled);
    EXPECT_EQ(spy.applies,0U);EXPECT_EQ(spy.ticks,0U);
}
TEST_F(Contract, FreshAtStartDoesNotAuthorizeFiftyMillisecondHold) {
    receive();EXPECT_EQ(prepare(t(60)),Code::Coverage);
    EXPECT_EQ(spy.applies,0U);EXPECT_EQ(spy.ticks,0U);
}
TEST_F(Contract, ExactSourceAgeBoundaryIsInclusiveButNotExtended) {
    receive();EXPECT_EQ(prepare(t(40)),Code::Ok); // source10 -> end40 is exactly30ms
    EXPECT_EQ(boundary.commit(*writer,ticket,t(10)),Code::Ok);
}
TEST_F(Contract, ExclusiveExpiryAndIntervalCoverageUseOriginalSupport) {
    auto p=support();p.support[2].exclusive_expiry=t(20);
    ASSERT_EQ(boundary.receive(*writer,vector(),p,t(10)),Code::Ok);ASSERT_EQ(prepare(t(20)),Code::Ok);
    EXPECT_EQ(boundary.commit(*writer,ticket,t(20)),Code::Expired);
    EXPECT_EQ(spy.applies,0U);EXPECT_EQ(spy.ticks,0U);
}
TEST_F(Contract, ExpiryInsideProposedIntervalRejectsBeforeApply) {
    auto p=support();p.support[1].exclusive_expiry=t(15);
    ASSERT_EQ(boundary.receive(*writer,vector(),p,t(10)),Code::Ok);
    EXPECT_EQ(prepare(t(20)),Code::Expired);EXPECT_EQ(spy.applies,0U);
}
TEST_F(Contract, ApplyAfterScheduledIntervalBeginIsNotBackdated) {
    receive();ASSERT_EQ(prepare(),Code::Ok);
    EXPECT_EQ(boundary.commit(*writer,ticket,t(11)),Code::Time);EXPECT_EQ(spy.applies,0U);
}
TEST_F(Contract, AmbiguousApplyConsumesTicketAndLatchesWithoutRetryOrTick) {
    receive();ASSERT_EQ(prepare(),Code::Ok);spy.result=ApplyResult::Ambiguous;
    EXPECT_EQ(boundary.commit(*writer,ticket,t(10)),Code::ApplyAmbiguous);
    EXPECT_EQ(boundary.commit(*writer,ticket,t(10)),Code::ApplyAmbiguous);
    EXPECT_EQ(boundary.advance(*writer,ticket,1,t(10)),Code::ApplyAmbiguous);
    EXPECT_EQ(spy.applies,1U);EXPECT_EQ(spy.ticks,0U);
}
TEST_F(Contract, RejectedApplyCannotBeReportedAsSuccessfulTick) {
    receive();ASSERT_EQ(prepare(),Code::Ok);spy.result=ApplyResult::Rejected;
    EXPECT_EQ(boundary.commit(*writer,ticket,t(10)),Code::ApplyRejected);
    EXPECT_EQ(boundary.advance(*writer,ticket,1,t(10)),Code::ApplyRejected);
    EXPECT_EQ(spy.applies,1U);EXPECT_EQ(spy.ticks,0U);
}
TEST_F(Contract, AmbiguousTickNeverIssuesASecondTick) {
    receive();ASSERT_EQ(prepare(),Code::Ok);ASSERT_EQ(boundary.commit(*writer,ticket,t(10)),Code::Ok);
    spy.tick_ack=false;EXPECT_EQ(boundary.advance(*writer,ticket,1,t(10)),Code::TickAmbiguous);
    EXPECT_EQ(boundary.advance(*writer,ticket,1,t(10)),Code::TickAmbiguous);EXPECT_EQ(spy.ticks,1U);
}
TEST_F(Contract, FaultLatchesUntilExplicitNewInitAndOldTicketCannotBindNewSession) {
    receive();ASSERT_EQ(prepare(),Code::Ok);const auto old=ticket;
    ASSERT_EQ(boundary.start(*writer,2,7,1,10,t(10)),Code::Ok);
    EXPECT_EQ(boundary.commit(*writer,old,t(10)),Code::Ticket);
    EXPECT_EQ(boundary.start(*writer,2,7,1,10,t(10)),Code::Init);
    EXPECT_EQ(boundary.fault(),Code::Ticket);
    ASSERT_EQ(boundary.start(*writer,3,7,1,10,t(10)),Code::Ok);
    ASSERT_EQ(boundary.receive(*writer,vector(3),support(),t(10)),Code::Ok);
    ASSERT_EQ(prepare(),Code::Ok);EXPECT_GT(ticket,old);
    EXPECT_EQ(boundary.commit(*writer,ticket,t(10)),Code::Ok);
}
TEST_F(Contract, ClockRollbackCannotHealOrApplyPendingSnapshot) {
    receive();ASSERT_EQ(prepare(),Code::Ok);
    EXPECT_EQ(boundary.commit(*writer,ticket,t(9)),Code::Clock);
    EXPECT_EQ(boundary.commit(*writer,ticket,t(10)),Code::Clock);EXPECT_EQ(spy.applies,0U);
}

TEST(M7Freshness, NativeDriveReceiverUsesOriginalSourceAtZeroTenTwentyThirtyFortyMs) {
    can::DriveReceiver rx{{can::DriveFrameKind::Actual,{-200,300},100,200}};
    ASSERT_TRUE(rx.start_session(1,start));auto raw=vector();
    ASSERT_EQ(rx.receive(*raw.drive,t(10)).decision,can::ActuatorReceiveDecision::Accepted);
    for(unsigned delta: {0U,10U,20U,30U,40U}) {
        const auto current=rx.current_sample(t(10+delta));
        EXPECT_EQ(current.has_value(),delta<=30) << delta;
        if(current) { EXPECT_EQ(current->source_time_ns,t(10)); }
    }
    RecordProperty("logical_age_ms","0,10,20,30=usable;40=unavailable;source=1010000000");
}
TEST(M7Freshness, NativeReceiverRejectsAtThirtyMillisecondsPlusOneNanosecond) {
    can::DriveReceiver rx{{can::DriveFrameKind::Actual,{-200,300},100,200}};
    ASSERT_TRUE(rx.start_session(1,start));ASSERT_EQ(rx.receive(*vector().drive,t(10)).decision,can::ActuatorReceiveDecision::Accepted);
    EXPECT_TRUE(rx.current_sample(t(40)));EXPECT_FALSE(rx.current_sample(t(40)+1));
}
TEST(M7Freshness, FreshTorqueAndEvSeventyMsDependencyCannotRefreshOldWheelSample) {
    can::DriveReceiver rx{{can::DriveFrameKind::Actual,{-200,300},100,200,30*ms,80*ms,30*ms,70*ms}};
    ASSERT_TRUE(rx.start_session(1,start));auto frame=vector();
    auto d=*can::decode_drive_frame(*frame.drive);d.wheel_speed=can::DriveWheelSpeed{20,t(10)};
    d.regen_capability=can::DriveRegenCapability{100,t(10),t(10)};
    d.regen_limit_reason=can::DriveRegenLimitReason::Nominal;
    can::DriveTxState tx{can::DriveFrameKind::Actual};
    ASSERT_EQ(rx.receive(*can::encode_drive_frame(d,tx),t(10)).decision,can::ActuatorReceiveDecision::Accepted);
    d.sequence=1;d.source_time_ns=t(50);d.regen_capability->source_time_ns=t(50);
    const auto next=rx.receive(*can::encode_drive_frame(d,tx),t(50));
    EXPECT_EQ(next.decision,can::ActuatorReceiveDecision::Accepted);
    EXPECT_EQ(next.wheel_speed,can::DriveFeedbackQuality::Stale);
    const auto current=rx.current_sample(t(50));ASSERT_TRUE(current);EXPECT_FALSE(current->wheel_speed);
    EXPECT_FALSE(current->regen_capability);EXPECT_EQ(current->source_time_ns,t(50));
    EXPECT_EQ(rx.last_accepted()->message.wheel_speed->source_time_ns,t(10));
}
TEST(M7Freshness, ReplayAndNewSequenceWithOldSourceCannotRenewAcceptedRxOrTimeout) {
    can::DriveReceiver rx{{can::DriveFrameKind::Actual,{-200,300},100,200}};
    ASSERT_TRUE(rx.start_session(1,start));const auto first=vector();
    ASSERT_EQ(rx.receive(*first.drive,t(10)).decision,can::ActuatorReceiveDecision::Accepted);
    EXPECT_EQ(rx.receive(*first.drive,t(20)).decision,can::ActuatorReceiveDecision::E2eRejected);
    const auto regenerated=vector(1,10,1);
    EXPECT_EQ(rx.receive(*regenerated.drive,t(30)).decision,can::ActuatorReceiveDecision::SourceNotIncreasing);
    ASSERT_TRUE(rx.last_accepted());EXPECT_EQ(rx.last_accepted()->received_time_ns,t(10));
    EXPECT_EQ(rx.last_accepted()->message.source_time_ns,t(10));
    EXPECT_EQ(rx.poll(t(90)),can::ActuatorReceiverHealth::Timeout);
    EXPECT_FALSE(rx.current_sample(t(90)));
}

drive::LocalSensors local(unsigned source,unsigned sequence=0) {
    const battery::ModelIdentity id{7,sequence,t(source)};
    return {battery::ModelMeasurement<double>{20,id,t(source)},
            battery::ModelMeasurement<drive::HvFeedback>{{400,true,false},id,t(source)}};
}
TEST(M7Freshness, NativeLocalValidationRejectsRestampOldDependencyBadIdentityAndNan) {
    for(unsigned fault=0;fault<5;++fault) {
        vecu::DriveController controller({});ASSERT_TRUE(controller.start_session({1,7,start}));
        auto sample=local(10);ASSERT_EQ(controller.observe_local(sample,t(10)).wheel_speed,drive::SensorDecision::Accepted);
        auto expected=drive::SensorDecision::Time;Time now=t(50);
        if(fault==0){sample.wheel_speed->identity.source_time_ns=t(20);now=t(20);expected=drive::SensorDecision::Identity;}
        if(fault==1){sample.wheel_speed->identity={7,1,t(50)};}
        if(fault==2){sample.wheel_speed->identity.epoch=8;expected=drive::SensorDecision::Identity;}
        if(fault==3){sample.wheel_speed->value=std::numeric_limits<double>::quiet_NaN();expected=drive::SensorDecision::Value;}
        if(fault==4){sample.wheel_speed->identity={7,1,t(60)};sample.wheel_speed->input_time_ns=t(60);now=t(50);}
        EXPECT_EQ(controller.observe_local(sample,now).wheel_speed,expected) << fault;
    }
}
TEST(M7Freshness, NativeDriveGateProtectsAtFortyMsAndFreshDataDoesNotUnlatch) {
    vecu::DriveController controller({});ASSERT_TRUE(controller.start_session({1,7,start}));
    can::DriveTxState command_tx{can::DriveFrameKind::Command};
    can::BmsTxState relay_tx{can::BmsFrameKind::DriveBatteryLimits},permission_tx{can::BmsFrameKind::DrivePermission};
    const auto held=local(10);
    for(unsigned i=0;i<6;++i) {
        const auto now=t(10+i*10);
        auto command=*can::decode_drive_frame(*vector(1,10+i*10,i,true).drive);
        command.torque_nm=100;
        ASSERT_EQ(controller.receive_command(*can::encode_drive_frame(command,command_tx),now).decision,
                  can::ActuatorReceiveDecision::Accepted);
        can::BmsMessage limits;limits.kind=can::BmsFrameKind::PowerLimits;
        limits.epoch=1;limits.sequence=i;limits.source_time_ns=now;limits.causal_sequence=i;
        limits.local_state=can::ActuatorLocalState::Normal;limits.origin=can::ActuatorOrigin::NormalPath;
        limits.content=can::BmsPowerLimits{30000,80000,can::BmsLimitReason::Nominal,can::BmsLimitReason::Nominal,now};
        ASSERT_EQ(controller.receive_limits(*can::forward_bms_limits(limits,relay_tx),now).decision,can::ActuatorReceiveDecision::Accepted);
        const can::BmsParentContext parent{1,1000+i,now,now+60*ms};
        can::BmsMessage permission;permission.kind=can::BmsFrameKind::DrivePermission;
        permission.epoch=1;permission.sequence=i;permission.source_time_ns=now;permission.causal_sequence=parent.sequence;
        permission.local_state=can::ActuatorLocalState::Normal;permission.origin=can::ActuatorOrigin::NormalPath;
        permission.content=can::BmsDriveGrant{can::BmsDrivePermission::AllowNormal,i,now,now,now+60*ms};
        ASSERT_EQ(controller.receive_permission(*can::encode_bms_frame(permission,permission_tx),now,&parent).decision,
                  can::ActuatorReceiveDecision::Accepted);
        const auto sensors=i==5?local(60,1):held;
        const auto observed=controller.observe_local(sensors,now);
        EXPECT_EQ(observed.wheel_speed,i==4?drive::SensorDecision::Time:drive::SensorDecision::Accepted) << i;
        ASSERT_TRUE(controller.prepare(now));
        const auto actual=controller.complete(drive::TorqueMeasurement{7,i,now,5},now);ASSERT_TRUE(actual);
        if(i<4) {
            EXPECT_TRUE(controller.decision().active) << i;
            EXPECT_EQ(controller.decision().fault,vecu::DriveGateFault::None) << i;
            EXPECT_EQ(can::decode_drive_frame(*actual)->wheel_speed->source_time_ns,t(10));
        } else {
            EXPECT_FALSE(controller.decision().active);
            EXPECT_EQ(controller.decision().fault,vecu::DriveGateFault::LocalInputsUnavailable);
            EXPECT_EQ(controller.output().mode,drive::ActuationMode::Zero);
            EXPECT_DOUBLE_EQ(controller.output().target_nm,0);
        }
    }
    RecordProperty("logical_age_ms","0,10,20,30=active;40=LocalInputsUnavailable/Zero;fresh50=still_latched");
}
} // namespace
