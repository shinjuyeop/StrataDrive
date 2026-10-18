#include "vehicle_management.hpp"
#include "power_controller.hpp"
#include "power_model.hpp"

#include <gtest/gtest.h>
#include <limits>
#include <stdexcept>

namespace {
using namespace stratadrive;
using central::VehicleManagementState;
using central::VehicleManagementFault;
using central::LifecycleReceiveDecision;
constexpr std::uint64_t kStart = 1000000000, kMs = 1000000;
std::uint64_t ns(std::uint32_t ms) { return kStart + static_cast<std::uint64_t>(ms)*kMs; }
template <typename Message>
void metadata(Message& m, std::uint32_t ms) {
    m.epoch = 3; m.sequence = ms/10; m.source_time_ns = ns(ms);
    m.local_state = can::ActuatorLocalState::Normal; m.origin = can::ActuatorOrigin::NormalPath;
}
central::NormalDriveReadinessInputs inputs(std::uint32_t ms, can::BmsPowerState phase) {
    central::NormalDriveReadinessInputs in; in.epoch = 3; in.session_enable_ns = kStart;
    in.front.health.emplace(); in.rear.health.emplace(); metadata(*in.front.health, ms); metadata(*in.rear.health, ms);
    in.front.health->ready_for_normal = in.rear.health->ready_for_normal = true;
    in.front.steering_actual.emplace(); metadata(*in.front.steering_actual, ms);
    in.front.steering_actual->kind = can::SteeringFrameKind::Actual; in.front.steering_actual->angle_rad = 0;
    in.front.brake_actual.emplace(); metadata(*in.front.brake_actual, ms);
    in.front.brake_actual->kind = can::BrakeFrameKind::Actual; in.front.brake_actual->pressure_pa = 0;
    in.rear.drive_actual.emplace(); metadata(*in.rear.drive_actual, ms);
    in.rear.drive_actual->kind = can::DriveFrameKind::Actual; in.rear.drive_actual->torque_nm = 0;
    const can::BmsQualities usable{can::BmsFieldQuality::Usable, can::BmsFieldQuality::Usable, can::BmsFieldQuality::NotApplicable};
    in.rear.power_status = can::BmsCurrentSample{can::BmsMessage{}, usable};
    auto& power = in.rear.power_status->message; metadata(power, ms); power.kind = can::BmsFrameKind::PowerStatus;
    can::BmsPowerStatus status; status.state = phase; status.input_time_ns = ns(ms); status.input_sequence = ms/10;
    status.positive_contactor_closed = phase == can::BmsPowerState::HvReady;
    status.negative_contactor_closed = phase == can::BmsPowerState::HvReady || phase == can::BmsPowerState::Precharge;
    status.precharge_contactor_closed = phase == can::BmsPowerState::Precharge;
    status.hv_bus_voltage_v = phase == can::BmsPowerState::Off || phase == can::BmsPowerState::Checks ? 0 : 400;
    status.condition_bits = 7; status.condition_validity = 31; power.content = status;
    in.rear.power_limits = can::BmsCurrentSample{can::BmsMessage{}, usable};
    auto& limits = in.rear.power_limits->message; metadata(limits, ms); limits.kind = can::BmsFrameKind::PowerLimits;
    limits.content = can::BmsPowerLimits{30000, 80000, can::BmsLimitReason::Nominal, can::BmsLimitReason::Nominal, ns(ms)};
    return in;
}
void acknowledge(central::NormalDriveReadinessInputs& in, const central::VehicleManagementOutput& previous) {
    in.rear.power_status->message.causal_sequence = previous.power_request.sequence;
    std::get<can::BmsPowerStatus>(in.rear.power_status->message.content).accepted_request_source_time_ns = previous.power_request.source_time_ns;
}
class VehicleManagementTest : public ::testing::Test {
protected:
    central::VehicleManagement owner;
    std::optional<central::VehicleManagementOutput> output;
    std::uint32_t root_sequence{0};
    void SetUp() override { ASSERT_TRUE(owner.start_session(3, kStart)); }
    central::LifecycleRequest root(std::uint32_t ms, can::BmsPowerAction action = can::BmsPowerAction::Enable) {
        return {{3, root_sequence++, ns(ms), ns(ms + 60)}, action};
    }
    void submit(std::uint32_t ms, can::BmsPowerAction action = can::BmsPowerAction::Enable) {
        EXPECT_EQ(owner.receive_request(root(ms, action), ns(ms)), LifecycleReceiveDecision::Accepted);
    }
    central::NormalDriveReadinessInputs snapshot(std::uint32_t ms, can::BmsPowerState phase) const {
        auto in = inputs(ms, phase); if (output) acknowledge(in, *output); return in;
    }
    void step(std::uint32_t ms, can::BmsPowerState phase = can::BmsPowerState::HvReady) {
        output = owner.tick(snapshot(ms, phase), ns(ms)); ASSERT_TRUE(output);
    }
    void normal() {
        submit(10); step(10, can::BmsPowerState::Off); step(20);
        ASSERT_EQ(owner.decision().state, VehicleManagementState::Normal);
        ASSERT_TRUE(owner.decision().normal_allowed);
    }
    const can::BmsPowerRequest& power() const { return std::get<can::BmsPowerRequest>(output->power_request.content); }
    const can::BmsDriveGrant& grant() const { return std::get<can::BmsDriveGrant>(output->drive_permission.content); }
    void expect_fault(VehicleManagementFault fault) const {
        EXPECT_EQ(owner.decision().state, VehicleManagementState::FailSafe);
        EXPECT_EQ(owner.decision().fault, fault); EXPECT_FALSE(owner.decision().normal_allowed);
        if (output) { EXPECT_EQ(grant().permission, can::BmsDrivePermission::Inhibit); }
    }
};
TEST(VehicleManagementConfig, RejectsPermissiveOrInvalidTiming) {
    central::VehicleManagementConfig c; c.max_tick_gap_ns = 30000001;
    EXPECT_THROW(central::VehicleManagement{c}, std::invalid_argument);
    c = {}; c.output_lifetime_ns = 80000001; EXPECT_THROW(central::VehicleManagement{c}, std::invalid_argument);
    c = {}; c.request_source_age_ns = 50000001; EXPECT_THROW(central::VehicleManagement{c}, std::invalid_argument);
    c = {}; c.readiness.bms_dependency_age_ns = 70000001; EXPECT_THROW(central::VehicleManagement{c}, std::invalid_argument);
    c = {}; c.initial_input_timeout_ns = 0; EXPECT_THROW(central::VehicleManagement{c}, std::invalid_argument);
    c = {}; c.acknowledgement_timeout_ns = 0; EXPECT_THROW(central::VehicleManagement{c}, std::invalid_argument);
    c = {}; c.startup_timeout_ns = 1; EXPECT_THROW(central::VehicleManagement{c}, std::invalid_argument);
    c = {}; c.shutdown_timeout_ns = 0; EXPECT_THROW(central::VehicleManagement{c}, std::invalid_argument);
    c = {}; c.off_bus_max_v = std::numeric_limits<double>::quiet_NaN(); EXPECT_THROW(central::VehicleManagement{c}, std::invalid_argument);
}
TEST(VehicleManagementSession, NoOutputBeforeInitAndOnlyNewerTrustedEpochRecovers) {
    central::VehicleManagement owner;
    EXPECT_FALSE(owner.tick(inputs(10, can::BmsPowerState::Off), ns(10)));
    EXPECT_EQ(owner.receive_request({{3, 0, ns(10), ns(60)}, can::BmsPowerAction::Enable}, ns(10)), LifecycleReceiveDecision::NotInitialized);
    EXPECT_FALSE(owner.start_session(0, kStart)); ASSERT_TRUE(owner.start_session(3, kStart));
    owner.mark_continuity_lost(ns(10)); EXPECT_FALSE(owner.start_session(3, ns(20)));
    EXPECT_FALSE(owner.start_session(2, ns(20))); EXPECT_FALSE(owner.start_session(4, kStart));
    ASSERT_TRUE(owner.start_session(4, ns(20))); EXPECT_EQ(owner.decision().state, VehicleManagementState::Init);
    EXPECT_EQ(owner.decision().fault, VehicleManagementFault::None); EXPECT_FALSE(owner.decision().normal_allowed);
}
TEST_F(VehicleManagementTest, WaitsForInitialInputsAndEmitsNonDrivingKeepOff) {
    central::NormalDriveReadinessInputs in; in.epoch = 3; in.session_enable_ns = kStart;
    for (std::uint32_t ms = 10; ms < 80; ms += 10) {
        output = owner.tick(in, ns(ms)); ASSERT_TRUE(output);
        EXPECT_EQ(owner.decision().state, VehicleManagementState::Init);
        EXPECT_EQ(power().action, can::BmsPowerAction::KeepOff); EXPECT_FALSE(output->power_parent);
        EXPECT_EQ(grant().permission, can::BmsDrivePermission::Inhibit);
    }
    output = owner.tick(in, ns(80)); expect_fault(VehicleManagementFault::InputsUnavailable);
}
TEST_F(VehicleManagementTest, InitialKnownZeroBmsAndOffActualAreHealthyWithoutNormalPermission) {
    auto in = inputs(10, can::BmsPowerState::Off);
    for (auto* sample : {&*in.rear.power_status, &*in.rear.power_limits}) {
        sample->message.local_state = can::ActuatorLocalState::Init;
        sample->message.origin = can::ActuatorOrigin::NoAcceptedInput;
    }
    in.rear.power_limits->message.content = can::BmsPowerLimits{0, 0, can::BmsLimitReason::Disabled, can::BmsLimitReason::Disabled, ns(10)};
    EXPECT_TRUE(central::evaluate_vehicle_input_health(in, ns(10)).ready());
    EXPECT_FALSE(central::evaluate_normal_drive_readiness(in, ns(10)).ready());
    auto wrong_kind = in; wrong_kind.rear.power_status->message.kind = can::BmsFrameKind::PowerLimits;
    EXPECT_FALSE(central::evaluate_vehicle_input_health(wrong_kind, ns(10)).ready());
    submit(10); output = owner.tick(in, ns(10)); ASSERT_TRUE(output);
    EXPECT_EQ(owner.decision().state, VehicleManagementState::Starting);
    EXPECT_EQ(power().action, can::BmsPowerAction::Enable); EXPECT_EQ(grant().permission, can::BmsDrivePermission::Inhibit);
}
TEST_F(VehicleManagementTest, EnableCanStartPrechargeButNormalRequiresAcknowledgedActualHv) {
    submit(10); step(10, can::BmsPowerState::Off);
    EXPECT_EQ(owner.decision().state, VehicleManagementState::Starting); EXPECT_EQ(power().action, can::BmsPowerAction::Enable);
    step(20, can::BmsPowerState::Precharge); EXPECT_FALSE(owner.decision().normal_allowed);
    submit(30); step(30);
    EXPECT_TRUE(owner.decision().normal_allowed); EXPECT_EQ(grant().permission, can::BmsDrivePermission::AllowNormal);
    EXPECT_EQ(grant().power_status_sequence, 3); EXPECT_EQ(grant().power_status_source_time_ns, ns(30));
    ASSERT_TRUE(output->permission_parent); EXPECT_EQ(output->drive_permission.causal_sequence, output->permission_parent->sequence);
    EXPECT_LE(grant().input_time_ns, grant().power_status_source_time_ns);
}
TEST_F(VehicleManagementTest, EnergizedStartupNeverTrustsHvReadyAsAnInitShortcut) {
    submit(10); step(10); expect_fault(VehicleManagementFault::StartupEnergized);
    EXPECT_EQ(power().action, can::BmsPowerAction::Shutdown);
    EXPECT_EQ(output->power_request.origin, can::ActuatorOrigin::LocalProtection); EXPECT_FALSE(output->power_parent);
}
TEST_F(VehicleManagementTest, OpenContactsWithResidualBusWaitForActualDischargeBeforeEnable) {
    submit(10); auto in = snapshot(10, can::BmsPowerState::Shutdown);
    output = owner.tick(in, ns(10)); ASSERT_TRUE(output);
    EXPECT_EQ(owner.decision().state, VehicleManagementState::Init); EXPECT_EQ(power().action, can::BmsPowerAction::KeepOff);
    step(20, can::BmsPowerState::Off); EXPECT_EQ(owner.decision().state, VehicleManagementState::Starting);
}
TEST_F(VehicleManagementTest, ChargingConnectionAndUnknownActualCannotAuthorizeEnable) {
    submit(10); auto in = snapshot(10, can::BmsPowerState::Off);
    std::get<can::BmsPowerStatus>(in.rear.power_status->message.content).condition_bits = 15;
    output = owner.tick(in, ns(10)); expect_fault(VehicleManagementFault::UnsafePowerConditions);
}
TEST_F(VehicleManagementTest, ImmutableRootCannotBeReplayedChangedOrExtended) {
    const auto request = root(10); ASSERT_EQ(owner.receive_request(request, ns(10)), LifecycleReceiveDecision::Accepted);
    EXPECT_EQ(owner.receive_request(request, ns(10)), LifecycleReceiveDecision::Unchanged);
    auto changed = request; ++changed.identity.expires_at_ns;
    EXPECT_EQ(owner.receive_request(changed, ns(10)), LifecycleReceiveDecision::MutationRejected);
    changed = request; changed.action = can::BmsPowerAction::Shutdown;
    EXPECT_EQ(owner.receive_request(changed, ns(10)), LifecycleReceiveDecision::MutationRejected);
    changed = request; ++changed.identity.source_time_ns;
    EXPECT_EQ(owner.receive_request(changed, ns(11)), LifecycleReceiveDecision::MutationRejected);
    changed = root(10); EXPECT_EQ(owner.receive_request(changed, ns(11)), LifecycleReceiveDecision::SequenceRejected);
    changed = root(20); changed.identity.sequence = 100;
    EXPECT_EQ(owner.receive_request(changed, ns(20)), LifecycleReceiveDecision::SequenceRejected);
}
TEST_F(VehicleManagementTest, RejectsWrongEpochFutureOldExpiredAndOverlongRoots) {
    auto request = root(10); request.identity.epoch = 2;
    EXPECT_EQ(owner.receive_request(request, ns(10)), LifecycleReceiveDecision::EpochMismatch);
    request = root(20); EXPECT_EQ(owner.receive_request(request, ns(10)), LifecycleReceiveDecision::Invalid);
    request = root(10); request.identity.source_time_ns = kStart - 1;
    EXPECT_EQ(owner.receive_request(request, ns(10)), LifecycleReceiveDecision::Invalid);
    request = root(10); request.identity.expires_at_ns = ns(10);
    EXPECT_EQ(owner.receive_request(request, ns(10)), LifecycleReceiveDecision::Invalid);
    request = root(10); request.identity.expires_at_ns = ns(91);
    EXPECT_EQ(owner.receive_request(request, ns(10)), LifecycleReceiveDecision::Invalid);
    request = root(0); request.identity.expires_at_ns = ns(10);
    EXPECT_EQ(owner.receive_request(request, ns(10)), LifecycleReceiveDecision::Expired);
}
TEST_F(VehicleManagementTest, RootSourceAgeIsCheckedSeparatelyFromItsDeadline) {
    for (std::uint32_t ms = 10; ms <= 50; ms += 10) step(ms, can::BmsPowerState::Off);
    central::LifecycleRequest request{{3, 0, kStart, ns(80)}, can::BmsPowerAction::Enable};
    EXPECT_EQ(owner.receive_request(request, ns(51)), LifecycleReceiveDecision::Expired);
    EXPECT_EQ(owner.decision().state, VehicleManagementState::Off);
}
TEST_F(VehicleManagementTest, PermissionIsBoundedByRootAcknowledgementAndEachOriginalSource) {
    normal();
    EXPECT_LE(grant().expires_at_ns, output->permission_parent->expires_at_ns);
    EXPECT_LE(grant().expires_at_ns, ns(10) + 50*kMs + 1);
    EXPECT_LE(grant().expires_at_ns, ns(20) + 30*kMs + 1);
    auto in = snapshot(30, can::BmsPowerState::HvReady); in.front.steering_actual->source_time_ns = ns(1);
    output = owner.tick(in, ns(30)); ASSERT_TRUE(output); ASSERT_TRUE(owner.decision().normal_allowed);
    EXPECT_EQ(grant().expires_at_ns, ns(31) + 1); EXPECT_EQ(grant().input_time_ns, ns(1));
}
TEST_F(VehicleManagementTest, LateNewRootCannotHideAnExpiredActiveRequest) {
    auto request = root(10); request.identity.expires_at_ns = ns(30);
    ASSERT_EQ(owner.receive_request(request, ns(10)), LifecycleReceiveDecision::Accepted);
    step(10, can::BmsPowerState::Off); step(20);
    EXPECT_EQ(owner.receive_request(root(30), ns(30)), LifecycleReceiveDecision::Latched);
    step(30); expect_fault(VehicleManagementFault::RequestLost);
}
TEST_F(VehicleManagementTest, LateFreshFeedbackCannotHideExpiredGrantSupport) {
    normal(); auto in = snapshot(30, can::BmsPowerState::HvReady); in.front.health->source_time_ns = ns(1);
    output = owner.tick(in, ns(30)); ASSERT_TRUE(output); EXPECT_TRUE(owner.decision().normal_allowed);
    step(40); expect_fault(VehicleManagementFault::GrantExpired);
}
TEST_F(VehicleManagementTest, CachedRootSourceAgeExpiresEvenWithALongerOriginalDeadline) {
    auto request = root(10); request.identity.expires_at_ns = ns(90);
    ASSERT_EQ(owner.receive_request(request, ns(10)), LifecycleReceiveDecision::Accepted);
    step(10, can::BmsPowerState::Off);
    for (std::uint32_t ms = 20; ms <= 60; ms += 10) step(ms);
    step(70); expect_fault(VehicleManagementFault::RequestLost);
}
TEST_F(VehicleManagementTest, MismatchedPowerResponseCannotStartNormal) {
    submit(10); step(10, can::BmsPowerState::Off);
    auto in = snapshot(20, can::BmsPowerState::HvReady); ++in.rear.power_status->message.causal_sequence;
    output = owner.tick(in, ns(20)); ASSERT_TRUE(output); EXPECT_FALSE(owner.decision().normal_allowed);
    in = snapshot(30, can::BmsPowerState::HvReady);
    ++std::get<can::BmsPowerStatus>(in.rear.power_status->message.content).accepted_request_source_time_ns;
    output = owner.tick(in, ns(30)); ASSERT_TRUE(output); EXPECT_FALSE(owner.decision().normal_allowed);
}
TEST_F(VehicleManagementTest, MissingPowerAcknowledgementsTimeoutDespiteFreshStatusAndRenewals) {
    submit(10); step(10, can::BmsPowerState::Off);
    for (std::uint32_t ms = 20; ms <= 90; ms += 10) {
        if (ms%20 == 10) submit(ms);
        auto in = inputs(ms, can::BmsPowerState::Precharge);
        in.rear.power_status->message.causal_sequence = 999;
        output = owner.tick(in, ns(ms)); ASSERT_TRUE(output);
    }
    expect_fault(VehicleManagementFault::PowerAcknowledgement);
}
TEST_F(VehicleManagementTest, NormalPowerAcknowledgementLossImmediatelyLatches) {
    normal(); auto in = snapshot(30, can::BmsPowerState::HvReady);
    in.rear.power_status->message.causal_sequence = 999;
    output = owner.tick(in, ns(30)); expect_fault(VehicleManagementFault::PowerAcknowledgement);
}
TEST_F(VehicleManagementTest, LostLeafAndThenFreshDataCannotAutomaticallyRecover) {
    normal(); auto in = snapshot(30, can::BmsPowerState::HvReady); in.front.brake_actual.reset();
    output = owner.tick(in, ns(30)); expect_fault(VehicleManagementFault::InputsUnavailable);
    step(40); expect_fault(VehicleManagementFault::InputsUnavailable);
    EXPECT_EQ(owner.receive_request(root(40), ns(40)), LifecycleReceiveDecision::Latched);
    EXPECT_FALSE(owner.start_session(3, ns(40)));
    ASSERT_TRUE(owner.start_session(4, ns(40))); EXPECT_EQ(owner.decision().state, VehicleManagementState::Init);
    EXPECT_FALSE(owner.decision().normal_allowed);
}
TEST(VehicleManagementLoss, EachCriticalSourceLatchesWithoutTheOtherZoneMaskingIt) {
    for (int source = 0; source < 7; ++source) {
        SCOPED_TRACE(source); central::VehicleManagement owner; ASSERT_TRUE(owner.start_session(3, kStart));
        ASSERT_EQ(owner.receive_request({{3, 0, ns(10), ns(70)}, can::BmsPowerAction::Enable}, ns(10)), LifecycleReceiveDecision::Accepted);
        auto out = owner.tick(inputs(10, can::BmsPowerState::Off), ns(10)); ASSERT_TRUE(out);
        auto in = inputs(20, can::BmsPowerState::HvReady); acknowledge(in, *out);
        out = owner.tick(in, ns(20)); ASSERT_TRUE(out); ASSERT_TRUE(owner.decision().normal_allowed);
        in = inputs(30, can::BmsPowerState::HvReady); acknowledge(in, *out);
        switch (source) {
        case 0: in.front.health.reset(); break;
        case 1: in.rear.health.reset(); break;
        case 2: in.front.steering_actual.reset(); break;
        case 3: in.front.brake_actual.reset(); break;
        case 4: in.rear.drive_actual.reset(); break;
        case 5: in.rear.power_status.reset(); break;
        case 6: in.rear.power_limits.reset(); break;
        }
        out = owner.tick(in, ns(30)); ASSERT_TRUE(out);
        EXPECT_EQ(owner.decision().fault, VehicleManagementFault::InputsUnavailable);
        EXPECT_FALSE(owner.decision().normal_allowed);
        in = inputs(40, can::BmsPowerState::HvReady); acknowledge(in, *out);
        ASSERT_TRUE(owner.tick(in, ns(40))); EXPECT_EQ(owner.decision().state, VehicleManagementState::FailSafe);
    }
}
TEST_F(VehicleManagementTest, FailedPowerOrActualReadyRegressionInNormalStopsNewGrants) {
    normal(); auto in = snapshot(30, can::BmsPowerState::Precharge);
    output = owner.tick(in, ns(30)); expect_fault(VehicleManagementFault::PowerNotReady);
}
TEST_F(VehicleManagementTest, ConfirmedActualOffSurvivesPeerFaultWithoutClearingTheVehicleLatch) {
    normal(); auto in = snapshot(30, can::BmsPowerState::HvReady); in.front.brake_actual.reset();
    output = owner.tick(in, ns(30)); ASSERT_TRUE(output); expect_fault(VehicleManagementFault::InputsUnavailable);
    in = snapshot(40, can::BmsPowerState::Off); in.front.brake_actual.reset();
    in.rear.power_status->message.local_state = can::ActuatorLocalState::FailSafe;
    in.rear.power_status->message.origin = can::ActuatorOrigin::LocalProtection;
    std::get<can::BmsPowerStatus>(in.rear.power_status->message.content).condition_bits = 23;
    output = owner.tick(in, ns(40)); ASSERT_TRUE(output);
    EXPECT_TRUE(owner.decision().power_off_confirmed); expect_fault(VehicleManagementFault::InputsUnavailable);
    in = snapshot(50, can::BmsPowerState::Off);
    std::get<can::BmsPowerStatus>(in.rear.power_status->message.content).hv_bus_voltage_v.reset();
    output = owner.tick(in, ns(50)); EXPECT_FALSE(owner.decision().power_off_confirmed);
    expect_fault(VehicleManagementFault::InputsUnavailable);
}
TEST_F(VehicleManagementTest, SourceProtectionAndWrongSessionContextLatchWithoutAdoptingEpoch) {
    auto in = inputs(10, can::BmsPowerState::Off);
    in.rear.power_limits->message.local_state = can::ActuatorLocalState::FailSafe;
    output = owner.tick(in, ns(10)); expect_fault(VehicleManagementFault::SourceProtection);
    ASSERT_TRUE(owner.start_session(4, ns(20)));
    output = owner.tick(inputs(20, can::BmsPowerState::Off), ns(20));
    expect_fault(VehicleManagementFault::SessionMismatch); ASSERT_TRUE(output); EXPECT_EQ(output->power_request.epoch, 4);
}
TEST_F(VehicleManagementTest, StopWaitsForShutdownAckActualOpenContactsAndLowBus) {
    normal(); submit(30, can::BmsPowerAction::Shutdown); step(30);
    EXPECT_EQ(owner.decision().state, VehicleManagementState::Stopping); EXPECT_EQ(power().action, can::BmsPowerAction::Shutdown);
    EXPECT_FALSE(owner.decision().power_off_confirmed); EXPECT_FALSE(owner.decision().normal_allowed);
    step(40, can::BmsPowerState::Shutdown); EXPECT_EQ(owner.decision().state, VehicleManagementState::Stopping);
    auto in = snapshot(50, can::BmsPowerState::Off); ++in.rear.power_status->message.causal_sequence;
    output = owner.tick(in, ns(50)); EXPECT_EQ(owner.decision().state, VehicleManagementState::Stopping);
    step(60, can::BmsPowerState::Off); EXPECT_EQ(owner.decision().state, VehicleManagementState::Stopped);
    EXPECT_TRUE(owner.decision().power_off_confirmed); EXPECT_EQ(power().action, can::BmsPowerAction::KeepOff);
    EXPECT_EQ(owner.receive_request(root(60), ns(60)), LifecycleReceiveDecision::RestartRequired);
    step(70, can::BmsPowerState::Off); EXPECT_FALSE(owner.decision().normal_allowed); EXPECT_TRUE(owner.decision().power_off_confirmed);
}
TEST_F(VehicleManagementTest, KeepOffDuringOperationRequestsControlledShutdownAndCannotBeCancelledByEnable) {
    normal(); submit(30, can::BmsPowerAction::KeepOff); step(30);
    EXPECT_EQ(power().action, can::BmsPowerAction::Shutdown);
    EXPECT_EQ(owner.receive_request(root(40), ns(40)), LifecycleReceiveDecision::RestartRequired);
    step(40, can::BmsPowerState::Shutdown); EXPECT_FALSE(owner.decision().normal_allowed);
}
TEST_F(VehicleManagementTest, ExpiredStopRootContinuesOnlyLocalRestrictiveShutdown) {
    normal(); auto request = root(30, can::BmsPowerAction::Shutdown); request.identity.expires_at_ns = ns(45);
    ASSERT_EQ(owner.receive_request(request, ns(30)), LifecycleReceiveDecision::Accepted);
    step(30); step(40, can::BmsPowerState::Shutdown); step(50, can::BmsPowerState::Shutdown);
    EXPECT_EQ(owner.decision().state, VehicleManagementState::Stopping); EXPECT_EQ(power().action, can::BmsPowerAction::Shutdown);
    EXPECT_EQ(output->power_request.origin, can::ActuatorOrigin::LocalProtection); EXPECT_FALSE(output->power_parent);
    EXPECT_EQ(grant().permission, can::BmsDrivePermission::Inhibit);
}
TEST_F(VehicleManagementTest, ClockRollbackAndOwnerDeadlineCannotBeConcealedByNewRequests) {
    normal();
    EXPECT_EQ(owner.receive_request(root(60), ns(60)), LifecycleReceiveDecision::Latched);
    output = owner.tick(snapshot(60, can::BmsPowerState::HvReady), ns(60)); expect_fault(VehicleManagementFault::ControlDeadline);
    EXPECT_FALSE(owner.tick(snapshot(50, can::BmsPowerState::HvReady), ns(50)));
    EXPECT_EQ(owner.decision().fault, VehicleManagementFault::ClockError); EXPECT_FALSE(owner.decision().normal_allowed);
}
TEST_F(VehicleManagementTest, DuplicateEarlyTicksHaveNoNewDecisionAndContinuityLossLatches) {
    step(10, can::BmsPowerState::Off);
    EXPECT_FALSE(owner.tick(snapshot(10, can::BmsPowerState::Off), ns(10)));
    EXPECT_FALSE(owner.tick(snapshot(15, can::BmsPowerState::Off), ns(15)));
    owner.mark_continuity_lost(ns(20)); step(20, can::BmsPowerState::Off);
    expect_fault(VehicleManagementFault::ContinuityLost);
}
TEST(VehicleManagementClock, TimestampRangeExhaustionCannotEmitAnExpiredWireMessage) {
    central::VehicleManagement owner;
    const auto maximum = std::numeric_limits<std::uint64_t>::max();
    ASSERT_TRUE(owner.start_session(3, maximum - 10*kMs));
    EXPECT_FALSE(owner.tick({}, maximum));
    EXPECT_EQ(owner.decision().fault, VehicleManagementFault::ClockError);
    EXPECT_FALSE(owner.decision().normal_allowed);
}
TEST(VehicleManagementTimeouts, StartupAndShutdownDoNotWaitIndefinitelyForActuals) {
    for (const bool stopping : {false, true}) {
        central::VehicleManagementConfig config; config.startup_timeout_ns = 100*kMs; config.shutdown_timeout_ns = 40*kMs;
        central::VehicleManagement owner(config); ASSERT_TRUE(owner.start_session(3, kStart));
        std::optional<central::VehicleManagementOutput> previous; std::uint32_t root = 0;
        for (std::uint32_t ms = 10; ms <= (stopping ? 70U : 110U); ms += 10) {
            if (ms%20 == 10 && owner.decision().state != VehicleManagementState::Stopping) {
                const auto action = stopping && ms >= 30 ? can::BmsPowerAction::Shutdown : can::BmsPowerAction::Enable;
                ASSERT_EQ(owner.receive_request({{3, root++, ns(ms), ns(ms+60)}, action}, ns(ms)), LifecycleReceiveDecision::Accepted);
            }
            const auto phase = ms == 10 ? can::BmsPowerState::Off : stopping ? can::BmsPowerState::HvReady : can::BmsPowerState::Precharge;
            auto in = inputs(ms, phase); if (previous) acknowledge(in, *previous);
            previous = owner.tick(in, ns(ms)); ASSERT_TRUE(previous);
        }
        EXPECT_EQ(owner.decision().fault, stopping ? VehicleManagementFault::ShutdownTimeout : VehicleManagementFault::StartupTimeout);
        EXPECT_FALSE(owner.decision().normal_allowed);
    }
}
TEST(VehicleManagementPowerCircuit, RealPrechargeAndDischargeViaExistingCanReceivers) {
    central::VehicleManagement owner; vecu::PowerController power({});
    simulation::PowerModel plant({0.002, 50, 0.02, 100, 1000, 500});
    const can::BmsPhysicalRanges ranges{{0,1000},{-3000,3000},{-50,100},100000};
    can::BmsReceiver status_rx({can::BmsFrameKind::PowerStatus, ranges});
    can::BmsReceiver grant_rx({can::BmsFrameKind::DrivePermission, ranges});
    can::BmsTxState request_tx{can::BmsFrameKind::PowerRequest}, status_tx{can::BmsFrameKind::PowerStatus}, grant_tx{can::BmsFrameKind::DrivePermission};
    ASSERT_TRUE(owner.start_session(3, kStart)); ASSERT_TRUE(power.start_session(3, 7, kStart));
    ASSERT_TRUE(plant.initialize({7, 0, kStart}, 0)); ASSERT_TRUE(status_rx.start_session(3, kStart)); ASSERT_TRUE(grant_rx.start_session(3, kStart));
    bool saw_normal = false, saw_precharge_without_permission = false, saw_stopped = false;
    std::uint32_t root = 0;
    for (std::uint32_t i = 0; i < 220; ++i) {
        const auto ms = (i+1)*10;
        const auto now = ns(ms), begin = ns(i*10);
        const simulation::PowerEnvironment environment{400, 0, true, true, true, false, false};
        ASSERT_EQ(plant.step({begin, now, {environment, {7, i, begin}, begin}, power.output().coils.value_or(power::CoilCommand{})}), simulation::PowerModelFault::None);
        const power::BmsSafetyGate gate{3, i, now, begin, false}; // explicit healthy local BMS fixture
        const auto status = power.tick(plant.observation(), gate, now); ASSERT_TRUE(status);
        const auto status_frame = can::encode_bms_frame(*status, status_tx); ASSERT_TRUE(status_frame);
        ASSERT_EQ(status_rx.receive(*status_frame, now).decision, can::ActuatorReceiveDecision::Accepted);
        auto in = inputs(ms, can::BmsPowerState::Off); in.rear.power_status = status_rx.current_sample(now);
        if (i%2 == 0 && owner.decision().state != VehicleManagementState::Stopping && owner.decision().state != VehicleManagementState::Stopped) {
            const auto action = ms < 1000 ? can::BmsPowerAction::Enable : can::BmsPowerAction::Shutdown;
            ASSERT_EQ(owner.receive_request({{3, root++, now, now+60*kMs}, action}, now), LifecycleReceiveDecision::Accepted);
        }
        const auto out = owner.tick(in, now); ASSERT_TRUE(out);
        const auto request = can::encode_bms_frame(out->power_request, request_tx); ASSERT_TRUE(request);
        ASSERT_EQ(power.receive(*request, now, out->power_parent ? &*out->power_parent : nullptr).decision, can::ActuatorReceiveDecision::Accepted);
        const auto grant = can::encode_bms_frame(out->drive_permission, grant_tx); ASSERT_TRUE(grant);
        ASSERT_EQ(grant_rx.receive(*grant, now, out->permission_parent ? &*out->permission_parent : nullptr).decision, can::ActuatorReceiveDecision::Accepted);
        EXPECT_EQ(owner.decision().fault, VehicleManagementFault::None);
        if (owner.decision().normal_allowed) {
            saw_normal = true; ASSERT_TRUE(in.rear.power_status); EXPECT_TRUE(can::bms_power_is_ready(*in.rear.power_status));
            ASSERT_TRUE(grant_rx.current_sample(now)); EXPECT_TRUE(can::bms_permission_allows_normal(*grant_rx.current_sample(now)));
            EXPECT_TRUE(plant.diagnostic_state().contactors.positive); EXPECT_TRUE(plant.diagnostic_state().contactors.negative);
        }
        if (power.output().phase == vecu::PowerPhase::Precharging) {
            saw_precharge_without_permission = true; EXPECT_FALSE(owner.decision().normal_allowed);
        }
        if (owner.decision().state == VehicleManagementState::Stopped) {
            saw_stopped = true; EXPECT_TRUE(owner.decision().power_off_confirmed);
            EXPECT_FALSE(plant.diagnostic_state().contactors.positive); EXPECT_FALSE(plant.diagnostic_state().contactors.negative);
            EXPECT_LE(plant.diagnostic_state().bus_voltage_v, 30);
        }
    }
    EXPECT_TRUE(saw_normal); EXPECT_TRUE(saw_precharge_without_permission); EXPECT_TRUE(saw_stopped);
}
}  // namespace
