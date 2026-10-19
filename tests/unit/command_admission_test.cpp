#include "command_admission.hpp"

#include <gtest/gtest.h>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace {
using namespace stratadrive;
using zone::AdmissionResult;
using zone::AdmissionState;
using zone::AdmissionFault;
constexpr std::uint64_t kStart = 1000000000, kMs = 1000000;
std::uint64_t ns(std::uint32_t ms) { return kStart+static_cast<std::uint64_t>(ms)*kMs; }
central::AllocatedCommands allocation(std::uint32_t ms, std::uint32_t sequence = 0) {
    central::AllocatedCommands c;
    c.parent = {3, sequence, ns(ms), ns(ms+60), 0, 0.1, 0.2, false};
    c.oldest_input_time_ns = ns(ms); c.expires_at_ns = ns(ms+30);
    const can::ActuatorMetadata m{sequence, 3, ns(ms), sequence, can::ActuatorLocalState::Normal, can::ActuatorOrigin::NormalPath};
    static_cast<can::ActuatorMetadata&>(c.brake) = m; static_cast<can::ActuatorMetadata&>(c.drive) = m;
    c.steering.sequence = m.sequence; c.steering.epoch = m.epoch; c.steering.source_time_ns = m.source_time_ns;
    c.steering.causal_sequence = m.causal_sequence; c.steering.local_state = m.local_state; c.steering.origin = m.origin;
    c.steering.angle_rad = 0.1; c.brake.pressure_pa = 100000; c.drive.torque_nm = -50;
    return c;
}
class CommandAdmissionTest : public ::testing::TestWithParam<zone::ZoneScope> {
protected:
    zone::CommandAdmission gate{GetParam()};
    void SetUp() override { ASSERT_TRUE(gate.start_session(3, kStart)); ASSERT_TRUE(gate.arm(kStart)); }
    central::ScopedCommands scoped(const central::AllocatedCommands& c) const {
        if (GetParam() == zone::ZoneScope::Front) return central::front_commands(c);
        return central::rear_commands(c);
    }
    void authorize(const central::AllocatedCommands& c, std::uint32_t ms) {
        ASSERT_EQ(gate.authorize_request(c.parent, ns(ms)), AdmissionResult::Accepted);
    }
    void accept(const central::AllocatedCommands& c, std::uint32_t ms) {
        authorize(c, ms); ASSERT_EQ(gate.receive(scoped(c), ns(ms)), AdmissionResult::Accepted);
    }
    void sequence(central::AllocatedCommands& c, std::uint32_t seq) const {
        c.steering.sequence = c.brake.sequence = c.drive.sequence = seq;
    }
    void source(central::AllocatedCommands& c, std::uint64_t time) const {
        c.steering.source_time_ns = c.brake.source_time_ns = c.drive.source_time_ns = time;
    }
    void latched(AdmissionFault fault, std::uint32_t ms) {
        EXPECT_FALSE(gate.current_command(ns(ms))); EXPECT_EQ(gate.decision().state, AdmissionState::FailSafe);
        EXPECT_EQ(gate.decision().fault, fault); EXPECT_TRUE(gate.decision().protection_required);
    }
};
TEST(CommandAdmissionConfig, RejectsInvalidPhysicalAndTimingEnvelopes) {
    zone::AdmissionConfig c; c.max_angle_rad = 0; EXPECT_THROW((zone::CommandAdmission{zone::ZoneScope::Front, c}), std::invalid_argument);
    c = {}; c.max_pressure_pa = std::numeric_limits<double>::infinity(); EXPECT_THROW((zone::CommandAdmission{zone::ZoneScope::Front, c}), std::invalid_argument);
    c = {}; c.max_regen_nm = 4000; EXPECT_THROW((zone::CommandAdmission{zone::ZoneScope::Rear, c}), std::invalid_argument);
    c = {}; c.parent_source_age_ns = 30000001; EXPECT_THROW((zone::CommandAdmission{zone::ZoneScope::Rear, c}), std::invalid_argument);
    c = {}; c.dependency_age_ns = 0; EXPECT_THROW((zone::CommandAdmission{zone::ZoneScope::Rear, c}), std::invalid_argument);
    c = {}; c.command_timeout_ns = 80000001; EXPECT_THROW((zone::CommandAdmission{zone::ZoneScope::Rear, c}), std::invalid_argument);
    c = {}; c.command_timeout_ns = c.command_source_age_ns; EXPECT_THROW((zone::CommandAdmission{zone::ZoneScope::Rear, c}), std::invalid_argument);
}
TEST(CommandAdmissionSession, ExplicitArmingAllowsLongNonDrivingStartup) {
    zone::CommandAdmission gate{zone::ZoneScope::Front}; auto c = allocation(3000);
    EXPECT_FALSE(gate.arm(kStart)); EXPECT_FALSE(gate.start_session(0, kStart));
    EXPECT_EQ(gate.receive(central::front_commands(c), kStart), AdmissionResult::NotInitialized);
    ASSERT_TRUE(gate.start_session(3, kStart));
    EXPECT_EQ(gate.poll(ns(3000)).state, AdmissionState::Idle); EXPECT_FALSE(gate.decision().protection_required);
    ASSERT_EQ(gate.authorize_request(c.parent, ns(3000)), AdmissionResult::Accepted);
    EXPECT_EQ(gate.receive(central::front_commands(c), ns(3000)), AdmissionResult::NotArmed);
    EXPECT_FALSE(gate.current_command(ns(3000))); ASSERT_TRUE(gate.arm(ns(3000))); EXPECT_FALSE(gate.arm(ns(3000)));
    EXPECT_EQ(gate.receive(central::front_commands(c), ns(3000)), AdmissionResult::Accepted);
}
TEST_P(CommandAdmissionTest, PreservesRootSourceAndLeaseWithoutRestamping) {
    const auto c = allocation(20); accept(c, 20);
    const auto out = gate.current_command(ns(30)); ASSERT_TRUE(out);
    std::visit([&](const auto& x) {
        EXPECT_TRUE(central::same_vehicle_request(x.parent, c.parent));
        EXPECT_EQ(x.oldest_input_time_ns, ns(20)); EXPECT_EQ(x.expires_at_ns, ns(50));
    }, *out);
    EXPECT_EQ(gate.last_valid_receive_time_ns(), ns(20)); EXPECT_EQ(gate.decision().state, AdmissionState::Active);
}
TEST_P(CommandAdmissionTest, AttachedParentCannotAuthorizeItself) {
    auto c = allocation(20);
    EXPECT_EQ(gate.receive(scoped(c), ns(20)), AdmissionResult::ParentUnavailable);
    EXPECT_FALSE(gate.current_command(ns(20))); EXPECT_FALSE(gate.last_valid_receive_time_ns());
    accept(c, 20);
}
TEST_P(CommandAdmissionTest, WrongZoneNeverUpdatesTheCommandCursor) {
    auto c = allocation(20); authorize(c, 20);
    const central::ScopedCommands wrong = GetParam() == zone::ZoneScope::Front ?
        central::ScopedCommands{central::rear_commands(c)} : central::ScopedCommands{central::front_commands(c)};
    EXPECT_EQ(gate.receive(wrong, ns(20)), AdmissionResult::WrongScope);
    EXPECT_EQ(gate.receive(scoped(c), ns(20)), AdmissionResult::Accepted);
}
TEST_P(CommandAdmissionTest, WrongEpochDoesNotPoisonNewSessionStream) {
    auto c = allocation(20); authorize(c, 20);
    auto old = c; old.steering.epoch = old.brake.epoch = old.drive.epoch = 2;
    sequence(old, 200); EXPECT_EQ(gate.receive(scoped(old), ns(20)), AdmissionResult::EpochMismatch);
    old = c; old.parent.epoch = 2; EXPECT_EQ(gate.authorize_request(old.parent, ns(20)), AdmissionResult::EpochMismatch);
    EXPECT_EQ(gate.receive(scoped(c), ns(20)), AdmissionResult::Accepted);
}
TEST_P(CommandAdmissionTest, RejectsParentContentSourceExpiryAndCausalMismatch) {
    const auto c = allocation(20); authorize(c, 20);
    for (int field = 0; field < 5; ++field) {
        auto bad = c;
        if (field == 0) bad.parent.acceleration_mps2 = 1;
        if (field == 1) ++bad.parent.source_time_ns;
        if (field == 2) ++bad.parent.expires_at_ns;
        if (field == 3) bad.parent.standstill_hold = true;
        if (field == 4) ++bad.steering.causal_sequence, ++bad.brake.causal_sequence, ++bad.drive.causal_sequence;
        EXPECT_EQ(gate.receive(scoped(bad), ns(20)), AdmissionResult::ParentMismatch) << field;
    }
    EXPECT_EQ(gate.receive(scoped(c), ns(20)), AdmissionResult::Accepted);
}
TEST_P(CommandAdmissionTest, RootMutationAndReplayDoNotAdvanceAuthorization) {
    const auto c = allocation(20); authorize(c, 20);
    auto bad = c.parent; --bad.expires_at_ns;
    EXPECT_EQ(gate.authorize_request(bad, ns(20)), AdmissionResult::MutationRejected);
    EXPECT_EQ(gate.authorize_request(c.parent, ns(21)), AdmissionResult::Unchanged);
    auto next = allocation(22, 1); authorize(next, 22);
    EXPECT_EQ(gate.authorize_request(c.parent, ns(22)), AdmissionResult::SequenceRejected);
    EXPECT_EQ(gate.receive(scoped(c), ns(22)), AdmissionResult::ParentMismatch);
    EXPECT_EQ(gate.receive(scoped(next), ns(22)), AdmissionResult::Accepted);
}
TEST_P(CommandAdmissionTest, RootRejectsInvalidAgeLifetimeAndValue) {
    auto c = allocation(20);
    auto p = c.parent; p.source_time_ns = ns(21); EXPECT_EQ(gate.authorize_request(p, ns(20)), AdmissionResult::InvalidContext);
    p = c.parent; p.source_time_ns = kStart-1; EXPECT_EQ(gate.authorize_request(p, ns(20)), AdmissionResult::InvalidContext);
    p = c.parent; p.expires_at_ns = ns(81); EXPECT_EQ(gate.authorize_request(p, ns(20)), AdmissionResult::InvalidContext);
    p = c.parent; p.braking_demand = std::numeric_limits<double>::quiet_NaN(); EXPECT_EQ(gate.authorize_request(p, ns(20)), AdmissionResult::InvalidContext);
    p = c.parent; p.acceleration_mps2 = 2.1; EXPECT_EQ(gate.authorize_request(p, ns(20)), AdmissionResult::InvalidContext);
    EXPECT_EQ(gate.authorize_request(c.parent, ns(51)), AdmissionResult::InvalidContext);
    EXPECT_EQ(gate.authorize_request(c.parent, ns(80)), AdmissionResult::Latched); // initial command monitor also expires
}
TEST_P(CommandAdmissionTest, RootIsExpiredAtItsDeadlineAndCannotArmOrRefreshTheMonitor) {
    auto c = allocation(20); c.parent.expires_at_ns = ns(20);
    EXPECT_EQ(gate.authorize_request(c.parent, ns(20)), AdmissionResult::Expired);
    EXPECT_FALSE(gate.last_valid_receive_time_ns()); EXPECT_FALSE(gate.current_command(ns(20)));
    EXPECT_EQ(gate.poll(ns(79)).state, AdmissionState::Waiting); latched(AdmissionFault::CommandTimeout, 80);
}
TEST_P(CommandAdmissionTest, UnknownValuesAreRejectedButKnownZeroIsValid) {
    auto c = allocation(20); authorize(c, 20); auto bad = c;
    bad.steering.angle_rad.reset(); bad.brake.pressure_pa.reset(); bad.drive.torque_nm.reset();
    EXPECT_EQ(gate.receive(scoped(bad), ns(20)), AdmissionResult::InvalidPayload);
    c.steering.angle_rad = 0; c.brake.pressure_pa = 0; c.drive.torque_nm = 0;
    EXPECT_EQ(gate.receive(scoped(c), ns(20)), AdmissionResult::Accepted);
}
TEST_P(CommandAdmissionTest, PhysicalEnvelopeRejectsNonfiniteAndNextWireStep) {
    const auto c = allocation(20); authorize(c, 20);
    for (const double invalid : {std::numeric_limits<double>::quiet_NaN(), std::numeric_limits<double>::infinity(), 100000000.0}) {
        auto bad = c; bad.steering.angle_rad = bad.brake.pressure_pa = bad.drive.torque_nm = invalid;
        EXPECT_EQ(gate.receive(scoped(bad), ns(20)), AdmissionResult::ValueOutOfRange);
    }
    auto bad = c; bad.steering.angle_rad = 0.3001; bad.drive.torque_nm = 300.1;
    EXPECT_EQ(gate.receive(scoped(bad), ns(20)), AdmissionResult::ValueOutOfRange);
    bad = c; bad.brake.pressure_pa = 1501000; bad.drive.torque_nm = -200.1;
    EXPECT_EQ(gate.receive(scoped(bad), ns(20)), AdmissionResult::ValueOutOfRange);
    EXPECT_EQ(gate.receive(scoped(c), ns(20)), AdmissionResult::Accepted);
}
TEST_P(CommandAdmissionTest, ProtectionAndInitCannotEnterTheNormalPath) {
    const auto c = allocation(20); authorize(c, 20);
    for (const auto state : {can::ActuatorLocalState::Init, can::ActuatorLocalState::Degraded, can::ActuatorLocalState::FailSafe}) {
        auto bad = c; bad.steering.local_state = bad.brake.local_state = bad.drive.local_state = state;
        EXPECT_EQ(gate.receive(scoped(bad), ns(20)), AdmissionResult::ModeRejected);
    }
    auto bad = c; bad.steering.origin = bad.brake.origin = bad.drive.origin = can::ActuatorOrigin::LocalProtection;
    EXPECT_EQ(gate.receive(scoped(bad), ns(20)), AdmissionResult::ModeRejected);
    EXPECT_EQ(gate.receive(scoped(c), ns(20)), AdmissionResult::Accepted);
}
TEST_P(CommandAdmissionTest, RejectsWrongFrameKind) {
    auto c = allocation(20); authorize(c, 20);
    c.steering.kind = can::SteeringFrameKind::Actual; c.brake.kind = can::BrakeFrameKind::Actual; c.drive.kind = can::DriveFrameKind::Actual;
    EXPECT_EQ(gate.receive(scoped(c), ns(20)), AdmissionResult::InvalidPayload);
}
TEST_P(CommandAdmissionTest, ValidatesCommandAndDependencyTimeDomain) {
    const auto c = allocation(20); authorize(c, 20);
    for (const auto time : {kStart-1, ns(19), ns(21)}) {
        auto bad = c; source(bad, time);
        EXPECT_EQ(gate.receive(scoped(bad), ns(20)), AdmissionResult::InvalidContext);
    }
    for (const auto time : {kStart-1, ns(21)}) {
        auto bad = c; bad.oldest_input_time_ns = time;
        EXPECT_EQ(gate.receive(scoped(bad), ns(20)), AdmissionResult::InvalidContext);
    }
    EXPECT_EQ(gate.receive(scoped(c), ns(20)), AdmissionResult::Accepted);
}
TEST_P(CommandAdmissionTest, RejectsExpiryBeyondLocalSourceAndParentBounds) {
    auto c = allocation(20); authorize(c, 20);
    c.expires_at_ns = ns(51)+1; EXPECT_EQ(gate.receive(scoped(c), ns(20)), AdmissionResult::InvalidContext);
    auto next = allocation(21, 1); next.parent.expires_at_ns = ns(25); authorize(next, 21);
    EXPECT_EQ(gate.receive(scoped(next), ns(21)), AdmissionResult::InvalidContext);
    next.expires_at_ns = ns(25); EXPECT_EQ(gate.receive(scoped(next), ns(21)), AdmissionResult::Accepted);
    EXPECT_TRUE(gate.current_command(ns(25)-1)); latched(AdmissionFault::CommandExpired, 25);
}
TEST_P(CommandAdmissionTest, OldestDependencyBoundsLeaseAndCannotBeRenewedByNewSource) {
    auto c = allocation(60); c.oldest_input_time_ns = kStart; authorize(c, 60);
    EXPECT_EQ(gate.receive(scoped(c), ns(60)), AdmissionResult::InvalidContext);
    c.expires_at_ns = ns(70)+1; EXPECT_EQ(gate.receive(scoped(c), ns(60)), AdmissionResult::Accepted);
    EXPECT_TRUE(gate.current_command(ns(70))); EXPECT_FALSE(gate.current_command(ns(70)+1));
    EXPECT_EQ(gate.decision().fault, AdmissionFault::CommandExpired);
}
TEST_P(CommandAdmissionTest, ParentAgeThirtyMsIsInclusiveButExpiryIsExclusive) {
    auto c = allocation(0); authorize(c, 0); source(c, ns(30)); c.expires_at_ns = ns(30)+1;
    EXPECT_EQ(gate.receive(scoped(c), ns(30)), AdmissionResult::Accepted);
    EXPECT_TRUE(gate.current_command(ns(30))); EXPECT_FALSE(gate.current_command(ns(30)+1));
}
TEST_P(CommandAdmissionTest, ExpiredIncomingCommandCannotRefreshTheWaitingMonitor) {
    auto c = allocation(20); authorize(c, 20); c.expires_at_ns = ns(20);
    EXPECT_EQ(gate.receive(scoped(c), ns(20)), AdmissionResult::Expired);
    EXPECT_FALSE(gate.last_valid_receive_time_ns()); EXPECT_EQ(gate.poll(ns(79)).state, AdmissionState::Waiting);
    latched(AdmissionFault::CommandTimeout, 80);
}
TEST_P(CommandAdmissionTest, DuplicatesAndInvalidFloodDoNotRefreshLastValidOrExpiry) {
    const auto c = allocation(20); accept(c, 20);
    EXPECT_EQ(gate.receive(scoped(c), ns(21)), AdmissionResult::Unchanged);
    auto bad = c; sequence(bad, 11);
    for (std::uint32_t ms = 22; ms < 50; ++ms) EXPECT_EQ(gate.receive(scoped(bad), ns(ms)), AdmissionResult::SequenceRejected);
    EXPECT_EQ(gate.last_valid_receive_time_ns(), ns(20)); latched(AdmissionFault::CommandExpired, 50);
}
TEST_P(CommandAdmissionTest, SameIdentityCannotChangeValueOrSideband) {
    const auto c = allocation(20); accept(c, 20);
    auto bad = c; bad.steering.angle_rad = 0.2; bad.brake.pressure_pa = 200000; bad.drive.torque_nm = -40;
    EXPECT_EQ(gate.receive(scoped(bad), ns(21)), AdmissionResult::MutationRejected);
    bad = c; --bad.expires_at_ns; EXPECT_EQ(gate.receive(scoped(bad), ns(21)), AdmissionResult::MutationRejected);
    bad = c; --bad.oldest_input_time_ns; EXPECT_EQ(gate.receive(scoped(bad), ns(21)), AdmissionResult::MutationRejected);
    EXPECT_EQ(gate.last_valid_receive_time_ns(), ns(20)); EXPECT_TRUE(gate.current_command(ns(21)));
}
TEST_P(CommandAdmissionTest, CommandSequenceAndSourceMustBothProgress) {
    auto c = allocation(20); sequence(c, 10); authorize(c, 20);
    EXPECT_EQ(gate.receive(scoped(c), ns(20)), AdmissionResult::SequenceRejected);
    sequence(c, 0); EXPECT_EQ(gate.receive(scoped(c), ns(20)), AdmissionResult::Accepted);
    sequence(c, 1); EXPECT_EQ(gate.receive(scoped(c), ns(21)), AdmissionResult::SourceNotIncreasing);
    auto next = allocation(40, 1); authorize(next, 40); sequence(next, 11);
    EXPECT_EQ(gate.receive(scoped(next), ns(40)), AdmissionResult::SequenceRejected);
    sequence(next, 10); EXPECT_EQ(gate.receive(scoped(next), ns(40)), AdmissionResult::Accepted); // max delta
}
TEST_P(CommandAdmissionTest, RootSequenceAndSourceHaveIndependentContinuity) {
    auto c = allocation(20); c.parent.sequence = 10;
    EXPECT_EQ(gate.authorize_request(c.parent, ns(20)), AdmissionResult::SequenceRejected);
    c = allocation(20); authorize(c, 20); auto next = allocation(20, 1);
    EXPECT_EQ(gate.authorize_request(next.parent, ns(21)), AdmissionResult::SourceNotIncreasing);
    next = allocation(22, 11); EXPECT_EQ(gate.authorize_request(next.parent, ns(22)), AdmissionResult::SequenceRejected);
    next = allocation(22, 10); EXPECT_EQ(gate.authorize_request(next.parent, ns(22)), AdmissionResult::Accepted);
}
TEST_P(CommandAdmissionTest, NewRootCannotRefreshThePreviouslyAcceptedCommand) {
    const auto c = allocation(20); accept(c, 20); const auto next = allocation(40, 1); authorize(next, 40);
    EXPECT_EQ(gate.last_valid_receive_time_ns(), ns(20)); EXPECT_TRUE(gate.current_command(ns(49)));
    EXPECT_EQ(gate.receive(scoped(next), ns(50)), AdmissionResult::Latched); latched(AdmissionFault::CommandExpired, 50);
}
TEST_P(CommandAdmissionTest, LateFreshDataCannotHideAnExpiredLease) {
    const auto c = allocation(20); accept(c, 20); const auto next = allocation(50, 1);
    EXPECT_EQ(gate.authorize_request(next.parent, ns(50)), AdmissionResult::Latched);
    EXPECT_EQ(gate.receive(scoped(next), ns(50)), AdmissionResult::Latched); latched(AdmissionFault::CommandExpired, 50);
}
TEST_P(CommandAdmissionTest, ClockRollbackLatchesAndRequiresNewTrustedInit) {
    const auto c = allocation(20); accept(c, 20); gate.poll(ns(21)); latched(AdmissionFault::ClockError, 20);
    EXPECT_FALSE(gate.arm(ns(22))); EXPECT_FALSE(gate.start_session(3, ns(22))); EXPECT_FALSE(gate.start_session(4, ns(20)));
    ASSERT_TRUE(gate.start_session(4, ns(22))); EXPECT_EQ(gate.decision().state, AdmissionState::Idle);
    EXPECT_FALSE(gate.decision().protection_required); EXPECT_FALSE(gate.current_command(ns(22)));
}
TEST_P(CommandAdmissionTest, ContinuityLossRevokesNormalDispatchUntilExplicitInit) {
    const auto c = allocation(20); accept(c, 20); gate.mark_continuity_lost(ns(21));
    latched(AdmissionFault::ContinuityLost, 21); EXPECT_EQ(gate.receive(scoped(c), ns(22)), AdmissionResult::Latched);
    EXPECT_FALSE(gate.arm(ns(22))); ASSERT_TRUE(gate.start_session(4, ns(22))); EXPECT_FALSE(gate.current_command(ns(22)));
}
TEST(CommandAdmissionFront, RejectsTornSteeringBrakePairAtomically) {
    zone::CommandAdmission gate{zone::ZoneScope::Front}; ASSERT_TRUE(gate.start_session(3, kStart)); ASSERT_TRUE(gate.arm(kStart));
    const auto c = allocation(20); ASSERT_EQ(gate.authorize_request(c.parent, ns(20)), AdmissionResult::Accepted);
    for (int field = 0; field < 6; ++field) {
        auto torn = central::front_commands(c);
        if (field == 0) ++torn.brake.sequence;
        if (field == 1) ++torn.brake.epoch;
        if (field == 2) ++torn.brake.source_time_ns;
        if (field == 3) ++torn.brake.causal_sequence;
        if (field == 4) torn.brake.local_state = can::ActuatorLocalState::Degraded;
        if (field == 5) torn.brake.origin = can::ActuatorOrigin::LocalProtection;
        EXPECT_EQ(gate.receive(torn, ns(20)), AdmissionResult::InvalidPayload) << field;
        EXPECT_FALSE(gate.current_command(ns(20)));
    }
    EXPECT_EQ(gate.receive(central::front_commands(c), ns(20)), AdmissionResult::Accepted);
}
TEST(CommandAdmissionRear, RejectsActualAuxiliaryFieldsInDriveCommands) {
    zone::CommandAdmission gate{zone::ZoneScope::Rear}; ASSERT_TRUE(gate.start_session(3, kStart)); ASSERT_TRUE(gate.arm(kStart));
    const auto c = allocation(20); ASSERT_EQ(gate.authorize_request(c.parent, ns(20)), AdmissionResult::Accepted);
    auto bad = central::rear_commands(c); bad.drive.wheel_speed = can::DriveWheelSpeed{20, ns(20)};
    EXPECT_EQ(gate.receive(bad, ns(20)), AdmissionResult::InvalidPayload);
    bad = central::rear_commands(c); bad.drive.regen_capability = can::DriveRegenCapability{100, ns(20), ns(20)};
    EXPECT_EQ(gate.receive(bad, ns(20)), AdmissionResult::InvalidPayload);
    bad = central::rear_commands(c); bad.drive.regen_limit_reason = can::DriveRegenLimitReason::Nominal;
    EXPECT_EQ(gate.receive(bad, ns(20)), AdmissionResult::InvalidPayload);
}
TEST(CommandAdmissionZones, RearTrafficAndRejoinCannotRecoverFrontLoss) {
    zone::CommandAdmission front{zone::ZoneScope::Front}, rear{zone::ZoneScope::Rear};
    ASSERT_TRUE(front.start_session(3, kStart)); ASSERT_TRUE(rear.start_session(3, kStart));
    ASSERT_TRUE(front.arm(kStart)); ASSERT_TRUE(rear.arm(kStart));
    auto c = allocation(20);
    ASSERT_EQ(front.authorize_request(c.parent, ns(20)), AdmissionResult::Accepted);
    ASSERT_EQ(rear.authorize_request(c.parent, ns(20)), AdmissionResult::Accepted);
    ASSERT_EQ(front.receive(central::front_commands(c), ns(20)), AdmissionResult::Accepted);
    ASSERT_EQ(rear.receive(central::rear_commands(c), ns(20)), AdmissionResult::Accepted);
    for (std::uint32_t ms : {40, 60}) {
        c = allocation(ms, ms/20-1); ASSERT_EQ(rear.authorize_request(c.parent, ns(ms)), AdmissionResult::Accepted);
        ASSERT_EQ(rear.receive(central::rear_commands(c), ns(ms)), AdmissionResult::Accepted);
    }
    EXPECT_FALSE(front.current_command(ns(60))); EXPECT_EQ(front.decision().fault, AdmissionFault::CommandExpired);
    EXPECT_TRUE(rear.current_command(ns(60))); EXPECT_EQ(front.receive(central::front_commands(c), ns(60)), AdmissionResult::Latched);
    ASSERT_TRUE(front.start_session(4, ns(60))); EXPECT_FALSE(front.current_command(ns(60)));
    EXPECT_EQ(front.receive(central::front_commands(c), ns(60)), AdmissionResult::NotArmed);
    EXPECT_TRUE(rear.current_command(ns(60))); // no cross-Zone reset
}
TEST(CommandAdmissionBounds, EnforcesTighterLocalEnvelopeAndLeaseWithoutClamping) {
    zone::AdmissionConfig config; config.max_angle_rad = 0.05; config.command_source_age_ns = 10000000;
    zone::CommandAdmission gate{zone::ZoneScope::Front, config};
    ASSERT_TRUE(gate.start_session(3, kStart)); ASSERT_TRUE(gate.arm(kStart));
    auto c = allocation(20); ASSERT_EQ(gate.authorize_request(c.parent, ns(20)), AdmissionResult::Accepted);
    EXPECT_EQ(gate.receive(central::front_commands(c), ns(20)), AdmissionResult::ValueOutOfRange);
    c.steering.angle_rad = 0.05; EXPECT_EQ(gate.receive(central::front_commands(c), ns(20)), AdmissionResult::InvalidContext);
    c.expires_at_ns = ns(30)+1; EXPECT_EQ(gate.receive(central::front_commands(c), ns(20)), AdmissionResult::Accepted);
    EXPECT_TRUE(gate.current_command(ns(30))); EXPECT_FALSE(gate.current_command(ns(30)+1));
}
TEST(CommandAdmissionBounds, WireQuantizationCannotRoundOutsideTheLocalEnvelope) {
    zone::AdmissionConfig config; config.max_angle_rad = 0.05006; config.max_pressure_pa = 100600;
    config.max_propulsion_nm = 100.06; config.max_regen_nm = 100.06;
    zone::CommandAdmission front{zone::ZoneScope::Front, config}, rear{zone::ZoneScope::Rear, config};
    ASSERT_TRUE(front.start_session(3, kStart)); ASSERT_TRUE(rear.start_session(3, kStart));
    ASSERT_TRUE(front.arm(kStart)); ASSERT_TRUE(rear.arm(kStart));
    auto c = allocation(20); c.steering.angle_rad = 0.05;
    ASSERT_EQ(front.authorize_request(c.parent, ns(20)), AdmissionResult::Accepted);
    ASSERT_EQ(rear.authorize_request(c.parent, ns(20)), AdmissionResult::Accepted);
    c.steering.angle_rad = 0.05006; EXPECT_EQ(front.receive(central::front_commands(c), ns(20)), AdmissionResult::ValueOutOfRange);
    c.steering.angle_rad = 0.05; c.brake.pressure_pa = 100600;
    EXPECT_EQ(front.receive(central::front_commands(c), ns(20)), AdmissionResult::ValueOutOfRange);
    c.drive.torque_nm = 100.06; EXPECT_EQ(rear.receive(central::rear_commands(c), ns(20)), AdmissionResult::ValueOutOfRange);
    c.drive.torque_nm = -100.06; EXPECT_EQ(rear.receive(central::rear_commands(c), ns(20)), AdmissionResult::ValueOutOfRange);
    c.brake.pressure_pa = 100000; c.drive.torque_nm = -100;
    EXPECT_EQ(front.receive(central::front_commands(c), ns(20)), AdmissionResult::Accepted);
    EXPECT_EQ(rear.receive(central::rear_commands(c), ns(20)), AdmissionResult::Accepted);
}
TEST(CommandAdmissionBounds, SaturatingLeaseBoundCannotWrapNearUint64End) {
    const auto end = std::numeric_limits<std::uint64_t>::max();
    zone::CommandAdmission gate{zone::ZoneScope::Rear};
    ASSERT_TRUE(gate.start_session(3, end-30*kMs)); ASSERT_TRUE(gate.arm(end-30*kMs));
    auto c = allocation(0); c.parent.source_time_ns = end-20*kMs; c.parent.expires_at_ns = end;
    c.oldest_input_time_ns = c.drive.source_time_ns = c.parent.source_time_ns; c.expires_at_ns = end;
    ASSERT_EQ(gate.authorize_request(c.parent, end-20*kMs), AdmissionResult::Accepted);
    ASSERT_EQ(gate.receive(central::rear_commands(c), end-20*kMs), AdmissionResult::Accepted);
    EXPECT_TRUE(gate.current_command(end-1)); EXPECT_FALSE(gate.current_command(end));
    EXPECT_EQ(gate.decision().fault, AdmissionFault::CommandExpired);
}
INSTANTIATE_TEST_SUITE_P(BothZones, CommandAdmissionTest, ::testing::Values(zone::ZoneScope::Front, zone::ZoneScope::Rear),
    [](const ::testing::TestParamInfo<zone::ZoneScope>& info) { return info.param == zone::ZoneScope::Front ? "Front" : "Rear"; });
}  // namespace
