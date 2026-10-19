#include "zone_feedback_monitor.hpp"

#include <gtest/gtest.h>
#include <stdexcept>

namespace {
using namespace stratadrive;
constexpr std::uint64_t kStart=1000000000,kMs=1000000;
std::uint64_t ns(std::uint32_t ms) { return kStart+ms*kMs; }
zone::ZoneHealthSnapshot status(std::uint32_t ms,zone::ZoneScope scope=zone::ZoneScope::Front) {
    zone::ZoneHealthSnapshot s; s.epoch=3; s.sequence=ms/10-1; s.source_time_ns=ns(ms);
    s.scope=scope; s.phase=zone::ZonePhase::Ready; s.ready_for_normal=true;
    s.local_state=can::ActuatorLocalState::Normal; s.origin=can::ActuatorOrigin::NormalPath; return s;
}
class Port : public zone::GatewayPort {
public:
    std::uint64_t now{kStart}, clock_step_ns{0}; std::size_t protections{0};
    std::uint64_t now_ns() noexcept override { now+=clock_step_ns; return now; }
    bool send(const zone::CommandFrame&,const central::CommandContext&) noexcept override { return true; }
    bool protect(zone::ZoneScope,zone::ProtectionCause,std::uint64_t) noexcept override { ++protections; return true; }
};
zone::ZoneFeedbackInputs inputs(std::uint32_t ms) {
    zone::ZoneFeedbackInputs in; in.steering.emplace(); in.brake.emplace();
    const auto copy=[&](auto& m) { const auto s=status(ms); m.epoch=s.epoch; m.sequence=s.sequence; m.source_time_ns=s.source_time_ns; m.local_state=s.local_state; m.origin=s.origin; };
    copy(*in.steering); copy(*in.brake);
    in.steering->kind=can::SteeringFrameKind::Actual; in.steering->angle_rad=0;
    in.brake->kind=can::BrakeFrameKind::Actual; in.brake->pressure_pa=100000; return in;
}
class ZoneFeedbackTest : public ::testing::Test {
protected:
    Port port; zone::CommandGateway commands{zone::ZoneScope::Front,port}; zone::ZoneFeedbackMonitor monitor{commands};
    void SetUp() override { ASSERT_TRUE(commands.start_session(3,kStart)); ASSERT_TRUE(monitor.start_session(3,kStart)); }
    zone::ZoneHealthSnapshot tick(std::uint32_t ms,const zone::ZoneFeedbackInputs& in) {
        port.now=ns(ms); const auto s=monitor.tick(in,port.now); EXPECT_TRUE(s); return s.value();
    }
};
TEST_F(ZoneFeedbackTest, WaitingDoesNotInventReadinessAndInitialInputDeadlineIsInclusive) {
    for(std::uint32_t ms=10;ms<80;ms+=10) EXPECT_EQ(tick(ms,{}).phase,zone::ZonePhase::Waiting);
    EXPECT_EQ(tick(80,{}).phase,zone::ZonePhase::FailSafe); EXPECT_EQ(monitor.fault(),zone::ZoneFeedbackFault::InputsUnavailable);
    EXPECT_EQ(port.protections,1U); EXPECT_EQ(tick(90,inputs(90)).phase,zone::ZonePhase::FailSafe);
}
TEST_F(ZoneFeedbackTest, FreshStatusCannotRefreshCachedLeafSourceAndLateInputCannotHeal) {
    const auto cached=inputs(10);
    for(std::uint32_t ms=10;ms<=40;ms+=10) { const auto s=tick(ms,cached); EXPECT_EQ(s.phase,zone::ZonePhase::Ready); EXPECT_EQ(cached.steering->source_time_ns,ns(10)); }
    EXPECT_EQ(tick(50,cached).phase,zone::ZonePhase::FailSafe); EXPECT_EQ(monitor.fault(),zone::ZoneFeedbackFault::InputsUnavailable);
    EXPECT_EQ(tick(60,inputs(60)).phase,zone::ZonePhase::FailSafe); EXPECT_EQ(port.protections,1U);
}
TEST_F(ZoneFeedbackTest, IndividualSeenStreamLossFailsEvenBeforeOtherLeafFirstArrives) {
    auto first=inputs(10); first.brake.reset(); EXPECT_EQ(tick(10,first).phase,zone::ZonePhase::Waiting);
    first.steering.reset(); EXPECT_EQ(tick(20,first).phase,zone::ZonePhase::FailSafe);
}
TEST_F(ZoneFeedbackTest, ExplicitLeafProtectionIsImmediateAndSeparateFromPhysicalValue) {
    auto in=inputs(10); in.brake->local_state=can::ActuatorLocalState::FailSafe; in.brake->origin=can::ActuatorOrigin::LocalProtection;
    EXPECT_EQ(tick(10,in).phase,zone::ZonePhase::FailSafe); EXPECT_EQ(monitor.fault(),zone::ZoneFeedbackFault::SourceProtection);
    EXPECT_EQ(in.brake->pressure_pa,100000); EXPECT_EQ(port.protections,1U);
}
TEST_F(ZoneFeedbackTest, ActualGatewayProtectionCannotBeHiddenByHealthyFeedback) {
    tick(10,inputs(10)); commands.mark_continuity_lost();
    EXPECT_EQ(tick(20,inputs(20)).phase,zone::ZonePhase::FailSafe); EXPECT_EQ(monitor.fault(),zone::ZoneFeedbackFault::GatewayProtection);
}
TEST_F(ZoneFeedbackTest, EarlyCallsDoNotPublishAndOverdueOrBackwardsClockProtect) {
    tick(10,inputs(10)); port.now=ns(11); EXPECT_FALSE(monitor.tick(inputs(11),port.now));
    EXPECT_EQ(tick(50,inputs(50)).phase,zone::ZonePhase::FailSafe); EXPECT_EQ(monitor.fault(),zone::ZoneFeedbackFault::ControlDeadline);
    port.now=ns(49); EXPECT_FALSE(monitor.tick(inputs(49),port.now)); EXPECT_EQ(monitor.fault(),zone::ZoneFeedbackFault::ClockError);
}
TEST_F(ZoneFeedbackTest, RejoinRequiresExplicitNewerInitAtGatewayAndMonitorWithoutChangingChildEpoch) {
    tick(10,inputs(10)); auto absent=inputs(20); absent.steering.reset(); tick(20,absent);
    EXPECT_FALSE(monitor.start_session(3,ns(20))); EXPECT_FALSE(monitor.start_session(4,ns(20)));
    EXPECT_TRUE(commands.start_session(4,ns(20))); EXPECT_TRUE(monitor.start_session(4,ns(20)));
    EXPECT_EQ(tick(30,inputs(30)).phase,zone::ZonePhase::Waiting); // old Epoch children cannot join
    auto joined=inputs(40); joined.steering->epoch=joined.brake->epoch=4;
    EXPECT_EQ(tick(40,joined).phase,zone::ZonePhase::Ready);
}
TEST_F(ZoneFeedbackTest, BindingCannotMixFrontAndRearAndInvalidSharedContextFailsClosed) {
    zone::CommandGateway rear{zone::ZoneScope::Rear,port};
    EXPECT_THROW(zone::ZoneFeedbackMonitor{rear},std::invalid_argument);
    const auto in=inputs(10); feedback::SourceContext c{0,kStart,ns(10)};
    EXPECT_FALSE(feedback::steering_available(in.steering,c));
    c.epoch=3; c.timing.actual_source_age_ns=30000001; EXPECT_FALSE(feedback::steering_available(in.steering,c));
}
TEST_F(ZoneFeedbackTest, AdvancingCallbackClockUsesCompletionTimeAndRechecksChildFreshness) {
    port.clock_step_ns=kMs;
    auto s=tick(10,inputs(10)); EXPECT_EQ(s.phase,zone::ZonePhase::Ready); EXPECT_EQ(s.source_time_ns,ns(11));
    // At invocation age30 ms, the cached child expires during the callback.
    s=tick(40,inputs(10)); EXPECT_EQ(s.phase,zone::ZonePhase::FailSafe); EXPECT_EQ(s.source_time_ns,ns(41));
    EXPECT_EQ(monitor.fault(),zone::ZoneFeedbackFault::InputsUnavailable);
}
TEST_F(ZoneFeedbackTest, GatewayInitCallbackMayCompleteAfterSharedSessionEnableBoundary) {
    port.now=ns(11); ASSERT_TRUE(commands.start_session(4,ns(10))); ASSERT_TRUE(monitor.start_session(4,ns(10)));
    auto in=inputs(20); in.steering->epoch=in.brake->epoch=4; EXPECT_EQ(tick(20,in).phase,zone::ZonePhase::Ready);
}
TEST(ZoneStatusIngress, ScopeMalformedModeAndRejectedPacketsNeverRenewSourceDeadline) {
    zone::ZoneStatusReceiver rx{zone::ZoneScope::Front}; ASSERT_TRUE(rx.start_session(3,kStart));
    ASSERT_EQ(rx.receive(status(10),ns(10)),can::ActuatorReceiveDecision::Accepted);
    EXPECT_EQ(rx.receive(status(20,zone::ZoneScope::Rear),ns(20)),can::ActuatorReceiveDecision::MalformedPayload);
    auto bad=status(30); bad.phase=zone::ZonePhase::Terminal; // flag contradicts phase
    EXPECT_EQ(rx.receive(bad,ns(30)),can::ActuatorReceiveDecision::MalformedPayload);
    EXPECT_EQ(rx.receive(status(10),ns(40)),can::ActuatorReceiveDecision::SequenceRejected);
    EXPECT_TRUE(rx.current_sample(ns(40))); EXPECT_FALSE(rx.current_sample(ns(41)));
    EXPECT_EQ(rx.receive(status(50),ns(50)),can::ActuatorReceiveDecision::ContinuityLost);
}
TEST(ZoneStatusIngress, LateReplacementChecksOldDeadlineBeforeCommitting) {
    zone::ZoneStatusReceiver rx{zone::ZoneScope::Front}; ASSERT_TRUE(rx.start_session(3,kStart));
    ASSERT_EQ(rx.receive(status(10),ns(10)),can::ActuatorReceiveDecision::Accepted);
    EXPECT_EQ(rx.receive(status(50),ns(50)),can::ActuatorReceiveDecision::ContinuityLost);
}
TEST(ZoneStatusIngress, TimeoutBeforeFirstStatusAndOldEpochReplayCannotRecoverAfterExplicitRejoin) {
    zone::ZoneStatusReceiver rx{zone::ZoneScope::Rear}; ASSERT_TRUE(rx.start_session(3,kStart));
    EXPECT_EQ(rx.receive(status(80,zone::ZoneScope::Rear),ns(80)),can::ActuatorReceiveDecision::Timeout);
    EXPECT_FALSE(rx.start_session(3,ns(80))); EXPECT_FALSE(rx.start_session(4,ns(79))); ASSERT_TRUE(rx.start_session(4,ns(80)));
    auto s=status(90,zone::ZoneScope::Rear); EXPECT_EQ(rx.receive(s,ns(90)),can::ActuatorReceiveDecision::EpochMismatch);
    s.epoch=4; s.sequence=0; EXPECT_EQ(rx.receive(s,ns(90)),can::ActuatorReceiveDecision::Accepted);
}
TEST(ZoneStatusIngress, TerminalAndProtectionCannotRegressToNormalInTheSameEpoch) {
    zone::ZoneStatusReceiver rx{zone::ZoneScope::Front}; ASSERT_TRUE(rx.start_session(3,kStart));
    auto s=status(10); s.phase=zone::ZonePhase::Terminal; s.ready_for_normal=false;
    ASSERT_EQ(rx.receive(s,ns(10)),can::ActuatorReceiveDecision::Accepted); EXPECT_TRUE(zone::zone_inputs_healthy(*rx.current_sample(ns(10))));
    EXPECT_EQ(rx.receive(status(20),ns(20)),can::ActuatorReceiveDecision::ModeRejected);
    s=status(30); s.phase=zone::ZonePhase::FailSafe; s.ready_for_normal=false; s.local_state=can::ActuatorLocalState::FailSafe; s.origin=can::ActuatorOrigin::LocalProtection;
    ASSERT_EQ(rx.receive(s,ns(30)),can::ActuatorReceiveDecision::Accepted); EXPECT_FALSE(zone::zone_inputs_healthy(s));
    EXPECT_EQ(rx.receive(status(40),ns(40)),can::ActuatorReceiveDecision::ModeRejected);
}
TEST(ZoneStatusIngress, ContinuityAndClockFaultsAreIndependentAcrossZones) {
    zone::ZoneStatusReceiver front{zone::ZoneScope::Front},rear{zone::ZoneScope::Rear};
    ASSERT_TRUE(front.start_session(3,kStart)); ASSERT_TRUE(rear.start_session(3,kStart));
    ASSERT_EQ(front.receive(status(10),ns(10)),can::ActuatorReceiveDecision::Accepted);
    ASSERT_EQ(rear.receive(status(10,zone::ZoneScope::Rear),ns(10)),can::ActuatorReceiveDecision::Accepted);
    front.mark_continuity_lost(ns(20)); EXPECT_FALSE(front.current_sample(ns(20))); EXPECT_TRUE(rear.current_sample(ns(20)));
    EXPECT_FALSE(rear.current_sample(ns(19))); EXPECT_EQ(rear.receive(status(30,zone::ZoneScope::Rear),ns(30)),can::ActuatorReceiveDecision::ClockError);
}
}  // namespace
