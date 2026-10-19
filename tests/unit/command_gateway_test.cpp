#include "command_gateway.hpp"
#include "zone_leaf_protection.hpp"
#include "front_startup_control.hpp"
#include "steering_response.hpp"
#include "brake_pressure_response.hpp"
#include "drive_sil_plant.hpp"

#include <gtest/gtest.h>
#include <type_traits>
#include <vector>

namespace {
using namespace stratadrive;
using zone::AdmissionResult;
using zone::ProtectionCause;
constexpr std::uint64_t kStart = 1000000000, kMs = 1000000;
std::uint64_t ns(std::uint32_t ms) { return kStart+static_cast<std::uint64_t>(ms)*kMs; }
central::AllocatedCommands commands(std::uint32_t ms, std::uint32_t seq = 0) {
    central::AllocatedCommands c; c.parent = {3, seq, ns(ms), ns(ms+60), 0, 0.1, 0.2, false};
    c.oldest_input_time_ns = ns(ms); c.expires_at_ns = ns(ms+30);
    const can::ActuatorMetadata m{seq, 3, ns(ms), seq, can::ActuatorLocalState::Normal, can::ActuatorOrigin::NormalPath};
    static_cast<can::ActuatorMetadata&>(c.brake) = m; static_cast<can::ActuatorMetadata&>(c.drive) = m;
    c.steering.sequence = seq; c.steering.epoch = 3; c.steering.source_time_ns = ns(ms); c.steering.causal_sequence = seq;
    c.steering.local_state = m.local_state; c.steering.origin = m.origin;
    c.steering.angle_rad = 0.2; c.brake.pressure_pa = 100000; c.drive.torque_nm = 200; return c;
}
class Port : public zone::GatewayPort {
public:
    struct Sent { zone::CommandFrame frame; central::CommandContext context; };
    std::uint64_t now{kStart}, before_write_ns{0}, after_write_ns{0}, protection_time{0};
    std::size_t attempts{0}, fail_attempt{0}, protection_calls{0};
    bool acknowledge{true};
    std::vector<Sent> sent;
    zone::ProtectionPort* protection{nullptr};
    vecu::SteeringActuator* steering{nullptr}; vecu::BrakeActuator* brake{nullptr}; vecu::DriveController* drive{nullptr};
    std::size_t clock_reads{0}, rollback_read{0}; std::uint64_t clock_step_ns{0};
    std::uint64_t now_ns() noexcept override {
        const auto observed = ++clock_reads == rollback_read ? now-1 : now;
        now += clock_step_ns; return observed;
    }
    bool send(const zone::CommandFrame& frame, const central::CommandContext& ctx) noexcept override {
        try {
        ++attempts; now += before_write_ns;
        if (now >= ctx.expires_at_ns || attempts == fail_attempt) return false;
        const bool accepted = std::visit([&](const auto& f) {
            using F = std::decay_t<decltype(f)>;
            if constexpr (std::is_same_v<F, can::SteeringFrame>) return !steering || steering->receive(f, now).decision == can::ActuatorReceiveDecision::Accepted;
            else if constexpr (std::is_same_v<F, can::BrakeFrame>) return !brake || brake->receive(f, now).decision == can::ActuatorReceiveDecision::Accepted;
            else return !drive || drive->receive_command(f, now).decision == can::ActuatorReceiveDecision::Accepted;
        }, frame);
        if (accepted) sent.push_back({frame, ctx});
        now += after_write_ns; return accepted;
        } catch (...) {
            return false;
        }
    }
    bool protect(zone::ZoneScope scope, ProtectionCause cause, std::uint64_t time) noexcept override {
        ++protection_calls; protection_time = time;
        return protection ? protection->protect(scope, cause, time) : acknowledge;
    }
};
class CommandGatewayTest : public ::testing::TestWithParam<zone::ZoneScope> {
protected:
    Port port; zone::CommandGateway gateway{GetParam(), port};
    void SetUp() override { ASSERT_TRUE(gateway.start_session(3, kStart)); ASSERT_TRUE(gateway.arm()); }
    central::ScopedCommands scoped(const central::AllocatedCommands& c) const {
        if (GetParam() == zone::ZoneScope::Front) return central::front_commands(c);
        return central::rear_commands(c);
    }
    void submit(const central::AllocatedCommands& c) {
        ASSERT_EQ(gateway.authorize_request(c.parent), AdmissionResult::Accepted);
        ASSERT_EQ(gateway.enqueue(scoped(c)), AdmissionResult::Accepted);
    }
    std::size_t frames() const { return GetParam() == zone::ZoneScope::Front ? 2 : 1; }
};
TEST_P(CommandGatewayTest, SendsOriginalIdentityAndLeaseOnlyOnceWithIndependentP05Counters) {
    for (std::uint32_t i = 0; i < 2; ++i) {
        port.now = ns(20+20*i); const auto c = commands(20+20*i, i); submit(c);
        EXPECT_EQ(gateway.dispatch().frames_enqueued, frames());
        for (std::size_t j = port.sent.size()-frames(); j < port.sent.size(); ++j) {
            const auto& item = port.sent[j]; EXPECT_EQ(item.context.expires_at_ns, c.expires_at_ns);
            EXPECT_TRUE(central::same_vehicle_request(item.context.parent, c.parent));
            std::visit([&](const auto& f) { EXPECT_EQ(f.payload[31], i); }, item.frame);
        }
        EXPECT_EQ(gateway.dispatch().frames_enqueued, 0U);
    }
    EXPECT_EQ(port.protection_calls, 0U);
}
TEST_P(CommandGatewayTest, ExpiredQueuedCommandNeverEntersCanAndTriggersProtection) {
    port.now = ns(20); submit(commands(20)); port.now = ns(50);
    EXPECT_EQ(gateway.dispatch().frames_enqueued, 0U); EXPECT_TRUE(port.sent.empty());
    EXPECT_EQ(gateway.poll().safety.cause, ProtectionCause::CommandExpired);
    EXPECT_TRUE(gateway.poll().safety.handoff_accepted); EXPECT_EQ(port.protection_calls, 1U);
    EXPECT_EQ(gateway.poll().pending, 0U);
}
TEST_P(CommandGatewayTest, SkipsSupersededExpiredItemsWhileLatestLeaseRemainsLive) {
    port.now = ns(20); auto first = commands(20); first.expires_at_ns = ns(30); submit(first);
    port.now = ns(25); submit(commands(25, 1)); port.now = ns(31);
    const auto result = gateway.dispatch(); EXPECT_EQ(result.superseded, 1U); EXPECT_EQ(result.frames_enqueued, frames());
    EXPECT_EQ(port.sent.back().context.parent.sequence, 1U); EXPECT_EQ(port.protection_calls, 0U);
}
TEST_P(CommandGatewayTest, DuplicatesAndInvalidPacketsDoNotOccupyTheFifo) {
    port.now = ns(20); const auto c = commands(20); submit(c);
    for (int i = 0; i < 20; ++i) EXPECT_EQ(gateway.enqueue(scoped(c)), AdmissionResult::Unchanged);
    auto wrong = c; ++wrong.parent.expires_at_ns;
    EXPECT_EQ(gateway.enqueue(scoped(wrong)), AdmissionResult::ParentMismatch);
    EXPECT_EQ(gateway.poll().pending, 1U); EXPECT_EQ(gateway.dispatch().frames_enqueued, frames());
}
TEST_P(CommandGatewayTest, OverflowClearsAllBacklogAndLatchesBeforeAnyWrite) {
    for (std::uint32_t i = 0; i <= zone::CommandGateway::kCapacity; ++i) {
        port.now = ns(20+i); const auto c = commands(20+i, i);
        ASSERT_EQ(gateway.authorize_request(c.parent), AdmissionResult::Accepted);
        const auto r = gateway.enqueue(scoped(c));
        EXPECT_EQ(r, i < zone::CommandGateway::kCapacity ? AdmissionResult::Accepted : AdmissionResult::Latched);
    }
    EXPECT_EQ(gateway.poll().safety.cause, ProtectionCause::QueueOverflow);
    EXPECT_EQ(gateway.poll().pending, 0U); EXPECT_EQ(gateway.dispatch().frames_enqueued, 0U); EXPECT_TRUE(port.sent.empty());
}
TEST_P(CommandGatewayTest, FinalPortDeadlineGuardRejectsDelayBeforeWrite) {
    port.now = ns(20); submit(commands(20)); port.before_write_ns = 30*kMs;
    EXPECT_EQ(gateway.dispatch().frames_enqueued, 0U); EXPECT_EQ(port.attempts, 1U); EXPECT_TRUE(port.sent.empty());
    EXPECT_EQ(gateway.poll().safety.cause, ProtectionCause::CommandExpired);
}
TEST_P(CommandGatewayTest, DetectsExpiryAfterAWriteAndStopsRemainingFrontFrame) {
    port.now = ns(20); submit(commands(20)); port.after_write_ns = 30*kMs;
    const auto result = gateway.dispatch(); EXPECT_EQ(result.frames_enqueued, 1U);
    EXPECT_EQ(result.partial_front, GetParam() == zone::ZoneScope::Front);
    EXPECT_EQ(gateway.poll().safety.cause, ProtectionCause::CommandExpired); EXPECT_EQ(port.protection_calls, 1U);
}
TEST_P(CommandGatewayTest, FailedSendRequestsProtectionWithoutRetryingNormalFrames) {
    port.now = ns(20); submit(commands(20)); port.fail_attempt = 1;
    EXPECT_EQ(gateway.dispatch().frames_enqueued, 0U); EXPECT_EQ(gateway.poll().safety.cause, ProtectionCause::SendFailure);
    port.fail_attempt = 0; EXPECT_EQ(gateway.dispatch().frames_enqueued, 0U); EXPECT_EQ(port.attempts, 1U);
    EXPECT_EQ(gateway.enqueue(scoped(commands(21, 1))), AdmissionResult::Latched);
}
TEST_P(CommandGatewayTest, ClockRollbackBlocksNormalOutputAndHandsOffAtLastOrderedTime) {
    port.now = ns(20); submit(commands(20)); port.now = ns(19);
    EXPECT_EQ(gateway.dispatch().frames_enqueued, 0U); EXPECT_EQ(gateway.poll().safety.cause, ProtectionCause::ClockError);
    EXPECT_EQ(gateway.poll().admission.fault, zone::AdmissionFault::ClockError); EXPECT_EQ(port.protection_time, ns(20));
}
TEST_P(CommandGatewayTest, PendingProtectionIsRetriedOncePerPollAndAcceptanceDoesNotClearLatch) {
    port.acknowledge = false; gateway.request_protection(); EXPECT_EQ(port.protection_calls, 1U);
    auto state = gateway.poll(); EXPECT_FALSE(state.safety.handoff_accepted); EXPECT_EQ(port.protection_calls, 2U);
    port.acknowledge = true; state = gateway.poll(); EXPECT_TRUE(state.safety.handoff_accepted); EXPECT_EQ(port.protection_calls, 3U);
    EXPECT_EQ(gateway.poll().safety.cause, ProtectionCause::CoordinatorRequest); EXPECT_EQ(port.protection_calls, 3U);
    EXPECT_FALSE(gateway.arm()); EXPECT_FALSE(gateway.start_session(3, kStart));
}
TEST_P(CommandGatewayTest, NewInitDropsOldQueueAndResetsLinkProtectionCountersWithoutAutoArming) {
    port.now = ns(20); submit(commands(20)); gateway.mark_continuity_lost();
    EXPECT_FALSE(gateway.start_session(4, ns(21))); EXPECT_FALSE(gateway.start_session(4, kStart));
    ASSERT_TRUE(gateway.start_session(4, ns(20))); EXPECT_EQ(gateway.dispatch().frames_enqueued, 0U);
    ASSERT_TRUE(gateway.arm()); auto c = commands(20); c.parent.epoch = c.steering.epoch = c.brake.epoch = c.drive.epoch = 4;
    submit(c); EXPECT_EQ(gateway.dispatch().frames_enqueued, frames());
    std::visit([&](const auto& f) { EXPECT_EQ(f.payload[31], 0); }, port.sent.back().frame);
}
TEST_P(CommandGatewayTest, WaitingTimeoutUsesIndependentProtectionEvenWithNoQueuedCommand) {
    port.now = ns(79); EXPECT_EQ(gateway.poll().safety.cause, ProtectionCause::None);
    port.now = ns(80); EXPECT_EQ(gateway.poll().safety.cause, ProtectionCause::UpstreamLost); EXPECT_EQ(port.protection_calls, 1U);
}
TEST(CommandGateway, UninitializedAndIdleCannotSendOrSelfArm) {
    Port p; zone::CommandGateway g{zone::ZoneScope::Front, p};
    EXPECT_FALSE(g.arm()); EXPECT_EQ(g.enqueue(central::front_commands(commands(0))), AdmissionResult::NotInitialized);
    EXPECT_FALSE(g.start_session(3, ns(1))); ASSERT_TRUE(g.start_session(3, kStart));
    p.now = ns(3000); EXPECT_EQ(g.poll().admission.state, zone::AdmissionState::Idle);
    EXPECT_EQ(g.enqueue(central::front_commands(commands(3000))), AdmissionResult::NotArmed);
    EXPECT_EQ(g.dispatch().frames_enqueued, 0U); EXPECT_EQ(p.protection_calls, 0U);
    g.request_protection(); EXPECT_EQ(p.protection_calls, 1U);
}
TEST(CommandGateway, PartialFrontWriteProtectsBothLeavesAndDoesNotClaimAtomicCanDelivery) {
    Port p; zone::CommandGateway g{zone::ZoneScope::Front, p}; ASSERT_TRUE(g.start_session(3, kStart)); ASSERT_TRUE(g.arm());
    p.now = ns(20); const auto c = commands(20); ASSERT_EQ(g.authorize_request(c.parent), AdmissionResult::Accepted);
    ASSERT_EQ(g.enqueue(central::front_commands(c)), AdmissionResult::Accepted); p.fail_attempt = 2;
    const auto result = g.dispatch(); EXPECT_EQ(result.frames_enqueued, 1U); EXPECT_TRUE(result.partial_front);
    EXPECT_EQ(g.poll().safety.cause, ProtectionCause::SendFailure); EXPECT_TRUE(g.poll().safety.handoff_accepted);
}
TEST(CommandGateway, FrontLossAndLocalReinitDoNotResetRear) {
    Port f, r; zone::CommandGateway front{zone::ZoneScope::Front, f}, rear{zone::ZoneScope::Rear, r};
    ASSERT_TRUE(front.start_session(3, kStart)); ASSERT_TRUE(rear.start_session(3, kStart)); ASSERT_TRUE(front.arm()); ASSERT_TRUE(rear.arm());
    for (std::uint32_t ms : {20, 40, 60}) {
        r.now = ns(ms); const auto c = commands(ms, ms/20-1);
        ASSERT_EQ(rear.authorize_request(c.parent), AdmissionResult::Accepted);
        ASSERT_EQ(rear.enqueue(central::rear_commands(c)), AdmissionResult::Accepted); EXPECT_EQ(rear.dispatch().frames_enqueued, 1U);
    }
    f.now = ns(80); EXPECT_EQ(front.poll().safety.cause, ProtectionCause::UpstreamLost); EXPECT_EQ(r.protection_calls, 0U);
    ASSERT_TRUE(front.start_session(4, ns(80))); EXPECT_EQ(rear.poll().safety.cause, ProtectionCause::None);
}
TEST(ZoneLeafProtection, FrontExpiryCancelsPendingMotionAndReleaseWithoutFabricatingFloorAchievement) {
    for (const double initial : {0.0, 1200000.0}) {
        vecu::SteeringActuator s{{-.5,.5,-.3,.3,0,1,50*kMs}};
        vecu::BrakeActuator b{{2000000,1500000,initial,5000000,10000000,1000000,50*kMs}};
        simulation::SteeringResponse sp{{-.3,.3,0,1,50*kMs,7}};
        simulation::BrakePressureResponse bp{{1500000,initial,5000000,10000000,50*kMs,7}};
        ASSERT_TRUE(s.start_session({3,7,kStart})); ASSERT_TRUE(b.start_session({3,7,kStart})); ASSERT_TRUE(sp.begin(kStart)); ASSERT_TRUE(bp.begin(kStart));
        simulation::ZoneLeafProtection safety{s,b}; Port p; p.protection = &safety; p.steering = &s; p.brake = &b;
        zone::CommandGateway g{zone::ZoneScope::Front,p}; ASSERT_TRUE(g.start_session(3,kStart)); ASSERT_TRUE(g.arm());
        p.now = ns(20); auto c = commands(20); c.brake.pressure_pa = 0;
        ASSERT_EQ(g.authorize_request(c.parent),AdmissionResult::Accepted); ASSERT_EQ(g.enqueue(central::front_commands(c)),AdmissionResult::Accepted);
        ASSERT_EQ(g.dispatch().frames_enqueued,2U);
        for (std::uint32_t ms=20; ms<=260; ms+=10) {
            p.now=ns(ms); ASSERT_TRUE(sp.advance(p.now)); ASSERT_TRUE(bp.advance(p.now)); g.poll();
            if (ms==50) { EXPECT_EQ(s.output().mode,steering::ActuationMode::Hold); EXPECT_EQ(b.output().mode,brake::ActuationMode::Protect); EXPECT_FALSE(b.protection_floor_observed()); }
            ASSERT_TRUE(s.prepare(p.now)); ASSERT_TRUE(b.prepare(p.now));
            const auto sf=s.complete(sp.capture(),p.now); const auto bf=b.complete(bp.capture(),p.now); ASSERT_TRUE(sf); ASSERT_TRUE(bf);
            if(s.output().mode==steering::ActuationMode::Hold) ASSERT_TRUE(sp.hold(p.now)); else ASSERT_TRUE(sp.set_target(s.output().target_rad,p.now));
            if(b.output().mode==brake::ActuationMode::Protect) ASSERT_TRUE(bp.request_protection(b.output().target_pa,p.now)); else ASSERT_TRUE(bp.set_target(b.output().target_pa,p.now));
            if(ms==50) { EXPECT_DOUBLE_EQ(*can::decode_brake_frame(*bf)->pressure_pa,initial); EXPECT_EQ(b.protection_floor_observed(),initial>=1000000); }
        }
        EXPECT_DOUBLE_EQ(sp.actual_angle_rad(),0); EXPECT_DOUBLE_EQ(bp.actual_pressure_pa(),initial>0?initial:1000000);
        EXPECT_EQ(s.fault(),vecu::SteeringFault::UpstreamProtection); EXPECT_EQ(b.fault(),vecu::BrakeFault::UpstreamProtection);
        EXPECT_EQ(b.protection_floor_observed(),true); EXPECT_EQ(p.protection_calls,1U);
        ASSERT_TRUE(g.start_session(4,p.now)); ASSERT_TRUE(g.arm()); EXPECT_EQ(b.fault(),vecu::BrakeFault::UpstreamProtection); // Leaf requires its own INIT
    }
}
TEST(ZoneLeafProtection, MissingRecipientsKeepHandoffPendingAndWrongScopeCannotProtectOtherLeaves) {
    vecu::SteeringActuator s{{-.5,.5,-.3,.3,0,1,50*kMs}}; vecu::BrakeActuator b{{2000000,1500000,0,5000000,10000000,1000000,50*kMs}};
    simulation::ZoneLeafProtection safety{s,b};
    EXPECT_FALSE(safety.protect(zone::ZoneScope::Front,ProtectionCause::UpstreamLost,ns(20)));
    ASSERT_TRUE(s.start_session({3,7,kStart})); ASSERT_TRUE(b.start_session({3,7,kStart}));
    EXPECT_FALSE(safety.protect(zone::ZoneScope::Rear,ProtectionCause::UpstreamLost,ns(20)));
    EXPECT_EQ(s.fault(),vecu::SteeringFault::None); EXPECT_EQ(b.fault(),vecu::BrakeFault::None);
    EXPECT_TRUE(safety.protect(zone::ZoneScope::Front,ProtectionCause::UpstreamLost,ns(20)));
}
TEST(ZoneLeafProtection, RearProtectionSelectsZeroWithResidualActualAndClockFaultStillLatched) {
    vecu::DriveControllerConfig config; config.response.initial_nm=150;
    vecu::DriveController d{config}; simulation::DriveSilPlant plant{config.response};
    ASSERT_TRUE(d.start_session({3,7,kStart})); plant.begin(7,kStart);
    simulation::ZoneLeafProtection safety{d}; Port p; p.protection=&safety;
    zone::CommandGateway g{zone::ZoneScope::Rear,p}; ASSERT_TRUE(g.start_session(3,kStart)); ASSERT_TRUE(g.arm());
    p.now=ns(20); g.request_protection(); ASSERT_TRUE(g.poll().safety.handoff_accepted);
    EXPECT_EQ(d.decision().fault,vecu::DriveGateFault::UpstreamProtection); EXPECT_EQ(d.output().mode,drive::ActuationMode::Zero);
    ASSERT_TRUE(plant.advance(p.now,false)); const auto residual=plant.actual_nm(); EXPECT_GT(residual,0); ASSERT_TRUE(plant.apply(d.output()));
    ASSERT_TRUE(d.prepare(p.now)); const auto actual=d.complete(plant.capture(p.now),p.now); ASSERT_TRUE(actual);
    EXPECT_DOUBLE_EQ(*can::decode_drive_frame(*actual)->torque_nm,residual); EXPECT_EQ(can::decode_drive_frame(*actual)->origin,can::ActuatorOrigin::LocalProtection);
    ASSERT_TRUE(plant.advance(ns(30),false)); EXPECT_DOUBLE_EQ(plant.actual_nm(),residual-20);
    EXPECT_FALSE(d.prepare(ns(19))); EXPECT_EQ(d.decision().fault,vecu::DriveGateFault::ClockError);
    EXPECT_TRUE(safety.protect(zone::ZoneScope::Rear,ProtectionCause::ClockError,ns(19)));
    EXPECT_EQ(d.decision().fault,vecu::DriveGateFault::ClockError); EXPECT_EQ(d.output().mode,drive::ActuationMode::Zero);
}
TEST(ZoneLeafProtection, StuckBrakeKeepsObservedFloorFalseAfterAcceptedProtectionHandoff) {
    vecu::SteeringActuator s{{-.5,.5,-.3,.3,0,1,50*kMs}}; vecu::BrakeActuator b{{2000000,1500000,0,5000000,10000000,1000000,50*kMs}};
    simulation::BrakePressureResponse plant{{1500000,0,5000000,10000000,50*kMs,7}};
    ASSERT_TRUE(s.start_session({3,7,kStart})); ASSERT_TRUE(b.start_session({3,7,kStart})); ASSERT_TRUE(plant.begin(kStart));
    simulation::ZoneLeafProtection safety{s,b}; Port p; p.protection=&safety;
    zone::CommandGateway g{zone::ZoneScope::Front,p}; ASSERT_TRUE(g.start_session(3,kStart));
    p.now=ns(20); ASSERT_TRUE(plant.advance(p.now)); g.request_protection();
    ASSERT_TRUE(g.poll().safety.handoff_accepted); ASSERT_TRUE(plant.request_protection(b.output().target_pa,p.now));
    for(std::uint32_t ms=20;ms<=260;ms+=10) {
        ASSERT_TRUE(plant.advance(ns(ms),{true,1,1})); ASSERT_TRUE(b.prepare(ns(ms)));
        const auto frame=b.complete(plant.capture(),ns(ms)); ASSERT_TRUE(frame);
        EXPECT_DOUBLE_EQ(*can::decode_brake_frame(*frame)->pressure_pa,0); EXPECT_EQ(b.protection_floor_observed(),false);
    }
}
TEST(ZoneLeafProtection, GatewayReachesRealEvGateAndLeaseLossRevokesBothMotorTorqueSigns) {
    for(const double sign : {-1.0,1.0}) {
        vecu::DriveControllerConfig config; config.response.initial_nm=sign*150;
        vecu::DriveController d{config}; simulation::DriveSilPlant plant{config.response};
        ASSERT_TRUE(d.start_session({3,7,kStart})); plant.begin(7,kStart);
        simulation::ZoneLeafProtection safety{d}; Port p; p.protection=&safety; p.drive=&d;
        zone::CommandGateway g{zone::ZoneScope::Rear,p}; ASSERT_TRUE(g.start_session(3,kStart)); ASSERT_TRUE(g.arm());
        can::BmsTxState limits_tx{can::BmsFrameKind::DriveBatteryLimits}, grant_tx{can::BmsFrameKind::DrivePermission};
        p.now=ns(20); auto c=commands(20); c.drive.torque_nm=sign*100;
        ASSERT_EQ(g.authorize_request(c.parent),AdmissionResult::Accepted); ASSERT_EQ(g.enqueue(central::rear_commands(c)),AdmissionResult::Accepted);
        ASSERT_EQ(g.dispatch().frames_enqueued,1U);
        for(std::uint32_t ms=20;ms<=140;ms+=10) {
            p.now=ns(ms); ASSERT_TRUE(plant.advance(p.now,false));
            if(ms<50) {
                const auto seq=ms/10-2;
                can::BmsMessage limit; limit.kind=can::BmsFrameKind::PowerLimits;
                limit.epoch=3; limit.sequence=seq; limit.causal_sequence=seq; limit.source_time_ns=p.now;
                limit.local_state=can::ActuatorLocalState::Normal; limit.origin=can::ActuatorOrigin::NormalPath;
                limit.content=can::BmsPowerLimits{30000,80000,can::BmsLimitReason::Nominal,can::BmsLimitReason::Nominal,p.now};
                const auto lf=can::forward_bms_limits(limit,limits_tx); ASSERT_TRUE(lf);
                const auto limits_result=d.receive_limits(*lf,p.now);
                ASSERT_EQ(limits_result.decision,can::ActuatorReceiveDecision::Accepted);
                ASSERT_EQ(limits_result.quality[0],can::BmsFieldQuality::Usable);
                const can::BmsParentContext parent{3,100+seq,p.now,p.now+60*kMs};
                auto grant=limit; grant.kind=can::BmsFrameKind::DrivePermission; grant.causal_sequence=parent.sequence;
                grant.content=can::BmsDriveGrant{can::BmsDrivePermission::AllowNormal,seq,p.now,p.now,p.now+60*kMs};
                const auto gf=can::encode_bms_frame(grant,grant_tx); ASSERT_TRUE(gf);
                ASSERT_EQ(d.receive_permission(*gf,p.now,&parent).decision,can::ActuatorReceiveDecision::Accepted);
                const battery::ModelIdentity id{7,seq,p.now};
                d.observe_local({battery::ModelMeasurement<double>{20,id,p.now},battery::ModelMeasurement<drive::HvFeedback>{{400,true,false},id,p.now}},p.now);
            }
            g.poll(); ASSERT_TRUE(d.prepare(p.now));
            const auto frame=d.complete(plant.capture(p.now),p.now); ASSERT_TRUE(frame); ASSERT_TRUE(plant.apply(d.output()));
            if(ms<50) { EXPECT_TRUE(d.decision().active); EXPECT_DOUBLE_EQ(d.output().target_nm,sign*100); }
            else { EXPECT_FALSE(d.decision().active); EXPECT_EQ(d.output().mode,drive::ActuationMode::Zero); }
            if(ms==50) { EXPECT_GT(sign * *can::decode_drive_frame(*frame)->torque_nm,0); } // observed residual, not commanded zero
        }
        EXPECT_EQ(g.poll().safety.cause,ProtectionCause::CommandExpired); EXPECT_EQ(d.decision().fault,vecu::DriveGateFault::UpstreamProtection);
        EXPECT_DOUBLE_EQ(plant.actual_nm(),0);
    }
}
class FrontStartupTest : public ::testing::Test {
protected:
    vecu::SteeringActuator steering{{-.5,.5,-.3,.3,.1,1,50*kMs}};
    vecu::BrakeActuator brake{{2000000,1500000,400000,5000000,10000000,1000000,50*kMs}};
    simulation::FrontStartupControl control{steering,brake};
    Port port; zone::CommandGateway gateway{zone::ZoneScope::Front,port};
    void SetUp() override {
        ASSERT_TRUE(steering.start_session({3,7,kStart},ActuatorCommandStartup::NonDriving));
        ASSERT_TRUE(brake.start_session({3,7,kStart},ActuatorCommandStartup::NonDriving));
        port.protection=&control; port.steering=&steering; port.brake=&brake;
        ASSERT_TRUE(gateway.start_session(3,kStart));
    }
    void observe(std::uint32_t ms) {
        port.now=ns(ms); ASSERT_TRUE(steering.prepare(port.now)); ASSERT_TRUE(brake.prepare(port.now));
        ASSERT_TRUE(steering.complete(steering::AngleMeasurement{7,ms/10-1,port.now,.1},port.now));
        ASSERT_TRUE(brake.complete(brake::PressureMeasurement{7,ms/10-1,port.now,400000},port.now));
    }
};
TEST_F(FrontStartupTest, LongIdleThenOneTrustedArmOpensBothLeavesAndGatewayWithoutBootstrapCommands) {
    for(std::uint32_t ms=10;ms<=1000;ms+=10) { observe(ms); EXPECT_EQ(gateway.poll().admission.state,zone::AdmissionState::Idle); }
    const auto c=commands(1000); EXPECT_EQ(gateway.enqueue(central::front_commands(c)),AdmissionResult::NotArmed);
    EXPECT_TRUE(port.sent.empty()); ASSERT_TRUE(control.arm_commands(gateway,{3,port.now}));
    EXPECT_FALSE(control.arm_commands(gateway,{3,port.now}));
    ASSERT_EQ(gateway.authorize_request(c.parent),AdmissionResult::Accepted);
    ASSERT_EQ(gateway.enqueue(central::front_commands(c)),AdmissionResult::Accepted); EXPECT_EQ(gateway.dispatch().frames_enqueued,2U);
    ASSERT_TRUE(steering.receiver().last_accepted()); ASSERT_TRUE(brake.receiver().last_accepted());
    EXPECT_EQ(steering.receiver().last_accepted()->message.sequence,0U); EXPECT_EQ(brake.receiver().last_accepted()->message.sequence,0U);
    EXPECT_EQ(port.protection_calls,0U); EXPECT_EQ(steering.fault(),vecu::SteeringFault::None); EXPECT_EQ(brake.fault(),vecu::BrakeFault::None);
}
TEST_F(FrontStartupTest, OneMissingAcquisitionCannotPartiallyArmTheFront) {
    port.now=ns(10); ASSERT_TRUE(steering.prepare(port.now));
    ASSERT_TRUE(steering.complete(steering::AngleMeasurement{7,0,port.now,.1},port.now));
    EXPECT_FALSE(control.arm_commands(gateway,{3,port.now})); EXPECT_TRUE(steering.can_arm_normal_commands(port.now));
    EXPECT_EQ(gateway.poll().admission.state,zone::AdmissionState::Idle); observe(20);
    EXPECT_TRUE(control.arm_commands(gateway,{3,port.now}));
}
TEST_F(FrontStartupTest, StaleSensorProtectsBothAndLateFreshDataCannotHealTheLatch) {
    observe(10); port.now=ns(31); EXPECT_FALSE(control.arm_commands(gateway,{3,port.now}));
    EXPECT_EQ(steering.fault(),vecu::SteeringFault::SensorUnavailable); EXPECT_EQ(brake.output().mode,brake::ActuationMode::Protect);
    EXPECT_TRUE(gateway.poll().safety.handoff_accepted); observe(40);
    EXPECT_FALSE(control.arm_commands(gateway,{3,port.now})); EXPECT_EQ(gateway.poll().admission.state,zone::AdmissionState::FailSafe);
}
TEST_F(FrontStartupTest, WrongScopeAndMismatchedInitCannotArmOrResetAnyRecipient) {
    observe(10); zone::CommandGateway rear{zone::ZoneScope::Rear,port}; ASSERT_TRUE(rear.start_session(3,kStart));
    EXPECT_FALSE(control.arm_commands(rear,{3,port.now})); EXPECT_FALSE(control.arm_commands(gateway,{4,port.now}));
    ASSERT_TRUE(gateway.start_session(4,port.now)); EXPECT_FALSE(control.arm_commands(gateway,{4,port.now}));
    EXPECT_EQ(steering.fault(),vecu::SteeringFault::None); EXPECT_EQ(brake.fault(),vecu::BrakeFault::None);
    EXPECT_EQ(steering.application_epoch(),3U); EXPECT_EQ(brake.application_epoch(),3U);
}
TEST_F(FrontStartupTest, GatewayCommitFailureProtectsBothLeavesRatherThanLeavingAPartialNormalPath) {
    observe(10); port.rollback_read=port.clock_reads+2;
    EXPECT_FALSE(control.arm_commands(gateway,{3,port.now}));
    EXPECT_EQ(gateway.poll().admission.state,zone::AdmissionState::FailSafe);
    EXPECT_EQ(steering.output().mode,steering::ActuationMode::Hold); EXPECT_EQ(brake.output().mode,brake::ActuationMode::Protect);
    EXPECT_NE(steering.fault(),vecu::SteeringFault::None); EXPECT_NE(brake.fault(),vecu::BrakeFault::None); EXPECT_TRUE(port.sent.empty());
}
TEST_F(FrontStartupTest, AdvancingGatewayClockDoesNotTurnSensorLossIntoAnArtificialClockFault) {
    observe(10); port.now=ns(31); port.clock_step_ns=kMs;
    EXPECT_FALSE(control.arm_commands(gateway,{3,port.now}));
    EXPECT_EQ(steering.fault(),vecu::SteeringFault::SensorUnavailable);
    EXPECT_EQ(brake.fault(),vecu::BrakeFault::SensorUnavailable);
    EXPECT_TRUE(gateway.poll().safety.handoff_accepted);
}
INSTANTIATE_TEST_SUITE_P(BothZones,CommandGatewayTest,::testing::Values(zone::ZoneScope::Front,zone::ZoneScope::Rear),
    [](const ::testing::TestParamInfo<zone::ZoneScope>& info){return info.param==zone::ZoneScope::Front?"Front":"Rear";});
}  // namespace
