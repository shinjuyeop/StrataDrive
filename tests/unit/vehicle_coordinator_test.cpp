#include "vehicle_coordinator.hpp"

#include <gtest/gtest.h>
#include <string>
#include <vector>

namespace {
using namespace stratadrive;
constexpr std::uint64_t kStart=1000000000,kMs=1000000;
std::uint64_t ns(std::uint32_t ms) { return kStart+ms*kMs; }
class Port : public central::CoordinatorPort {
public:
    std::uint64_t now{kStart}, power_delay_ns{0}, health_delay_ns{0}; std::uint32_t epoch{3};
    bool ready{true},health{true},arm_ok{true},power_ok{true},commands_ok{true},root_ok{true},stop_ok{true},protect_ok{true};
    std::size_t protections{0},arms{0},handoffs{0};
    std::vector<std::string> events;
    std::optional<central::VehicleManagementOutput> sent_power;
    std::vector<central::AllocatedCommands> commands;
    std::vector<central::LifecycleRequest> lifecycles; std::vector<central::VehicleRequest> vehicles;
    std::uint64_t now_ns() noexcept override { return now; }
    bool session_ready(central::CoordinatorSession s) noexcept override { return ready && s.epoch==epoch; }
    bool healthy(std::uint32_t e) noexcept override { events.emplace_back("health"); now+=health_delay_ns; return health && e==epoch; }
    bool authorize_lifecycle(const central::LifecycleRequest& r) noexcept override { events.emplace_back("lifecycle"); lifecycles.push_back(r); return root_ok; }
    bool authorize_vehicle(const central::VehicleRequest& r) noexcept override { events.emplace_back("vehicle"); vehicles.push_back(r); return root_ok; }
    bool arm(std::uint32_t) noexcept override { events.emplace_back("arm"); ++arms; return arm_ok; }
    bool deliver_power(const central::VehicleManagementOutput& p) noexcept override { events.emplace_back("power"); sent_power=p; now+=power_delay_ns; return power_ok; }
    std::optional<can::BmsCurrentSample> current_permission() noexcept override {
        events.emplace_back("permission");
        if(!sent_power) return std::nullopt;
        return can::BmsCurrentSample{sent_power->drive_permission,{can::BmsFieldQuality::Usable,can::BmsFieldQuality::NotApplicable,can::BmsFieldQuality::NotApplicable}};
    }
    bool deliver_commands(const central::AllocatedCommands& c) noexcept override { events.emplace_back("commands"); commands.push_back(c); return commands_ok; }
    bool select_stop(const central::NormalStopPlan&) noexcept override { events.emplace_back("stop"); ++handoffs; return stop_ok; }
    bool protect() noexcept override { events.emplace_back("protect"); ++protections; return protect_ok; }
};
template<class M> void meta(M& m,std::uint32_t ms) {
    m.epoch=3; m.sequence=ms/10; m.source_time_ns=ns(ms); m.origin=can::ActuatorOrigin::NormalPath; m.local_state=can::ActuatorLocalState::Normal;
}
central::NormalDriveReadinessInputs feedback(std::uint32_t ms,bool ready) {
    central::NormalDriveReadinessInputs in; in.epoch=3; in.session_enable_ns=kStart;
    in.front.health.emplace(); in.rear.health.emplace(); meta(*in.front.health,ms); meta(*in.rear.health,ms);
    in.front.health->phase=in.rear.health->phase=zone::ZonePhase::Ready;
    in.rear.health->scope=zone::ZoneScope::Rear; in.front.health->ready_for_normal=in.rear.health->ready_for_normal=true;
    in.front.steering_actual.emplace(); meta(*in.front.steering_actual,ms); in.front.steering_actual->kind=can::SteeringFrameKind::Actual; in.front.steering_actual->angle_rad=0;
    in.front.brake_actual.emplace(); meta(*in.front.brake_actual,ms); in.front.brake_actual->kind=can::BrakeFrameKind::Actual; in.front.brake_actual->pressure_pa=100000;
    in.rear.drive_actual.emplace(); meta(*in.rear.drive_actual,ms); in.rear.drive_actual->kind=can::DriveFrameKind::Actual;
    in.rear.drive_actual->torque_nm=0; in.rear.drive_actual->wheel_speed=can::DriveWheelSpeed{0,ns(ms)};
    can::BmsMessage power,limits; meta(power,ms); meta(limits,ms); power.kind=can::BmsFrameKind::PowerStatus; limits.kind=can::BmsFrameKind::PowerLimits;
    can::BmsPowerStatus p; p.state=ready?can::BmsPowerState::HvReady:can::BmsPowerState::Off; p.positive_contactor_closed=p.negative_contactor_closed=ready;
    p.precharge_contactor_closed=false; p.hv_bus_voltage_v=ready?400:0; p.condition_bits=7; p.condition_validity=31; p.input_time_ns=ns(ms); power.content=p;
    limits.content=can::BmsPowerLimits{30000,80000,can::BmsLimitReason::Nominal,can::BmsLimitReason::Nominal,ns(ms)};
    const can::BmsQualities q{can::BmsFieldQuality::Usable,can::BmsFieldQuality::Usable,can::BmsFieldQuality::NotApplicable};
    in.rear.power_status=can::BmsCurrentSample{power,q}; in.rear.power_limits=can::BmsCurrentSample{limits,q}; return in;
}
class CoordinatorTest : public ::testing::Test {
protected:
    Port port; central::VehicleCoordinator coordinator{port}; std::uint32_t lifecycle_sequence{0};
    void SetUp() override { ASSERT_TRUE(coordinator.start_session({3,kStart})); }
    central::LifecycleRequest root(std::uint32_t ms) { return {{3,lifecycle_sequence++,ns(ms),ns(ms+60)},can::BmsPowerAction::Enable}; }
    central::VehicleRequest vehicle(std::uint32_t ms,std::uint32_t sequence=0) { return {3,sequence,ns(ms),ns(ms+60),.2,0,0,false}; }
    void request(std::uint32_t ms) { port.now=ns(ms); ASSERT_EQ(coordinator.receive_lifecycle(root(ms),port.now),central::CoordinatorReceive::Accepted); }
    central::NormalDriveReadinessInputs inputs(std::uint32_t ms,bool ready=true) {
        auto in=feedback(ms,ready);
        if(port.sent_power) { in.rear.power_status->message.causal_sequence=port.sent_power->power_request.sequence;
            std::get<can::BmsPowerStatus>(in.rear.power_status->message.content).accepted_request_source_time_ns=port.sent_power->power_request.source_time_ns; }
        return in;
    }
    void tick(std::uint32_t ms,bool ready=true) { port.now=ns(ms); ASSERT_TRUE(coordinator.tick(inputs(ms,ready),port.now)); }
    void normal() {
        request(10); tick(10,false); request(20); tick(20); ASSERT_TRUE(coordinator.decision().normal_armed);
        ASSERT_EQ(coordinator.receive_vehicle(vehicle(20),port.now),central::CoordinatorReceive::Accepted);
        request(30); tick(30); ASSERT_EQ(coordinator.receive_vehicle(vehicle(30,1),port.now),central::CoordinatorReceive::Accepted); tick(40); ASSERT_FALSE(port.commands.empty());
    }
    central::NormalStopRequest stop(std::uint32_t ms,std::uint32_t sequence=0) { return {{3,sequence,ns(ms),ns(ms+60)},0}; }
};
TEST(Coordinator, BeforeTrustedInitNoPortsOrOutputsAreUsed) {
    Port port; central::VehicleCoordinator c{port}; EXPECT_FALSE(c.tick({},kStart));
    EXPECT_EQ(c.receive_lifecycle({{3,0,kStart,kStart+60*kMs},can::BmsPowerAction::Enable},kStart),central::CoordinatorReceive::NotInitialized);
    EXPECT_TRUE(port.events.empty()); EXPECT_FALSE(c.start_session({0,kStart}));
}
TEST_F(CoordinatorTest, StartupPermissionArmAndTwentyMillisecondAllocationFollowOneOwnerOrder) {
    normal(); EXPECT_EQ(port.arms,1U); EXPECT_EQ(port.commands.size(),1U);
    const auto& c=port.commands.front(); EXPECT_EQ(c.parent.sequence,1U); EXPECT_EQ(c.parent.source_time_ns,ns(30)); EXPECT_EQ(c.steering.source_time_ns,ns(40));
    const std::vector<std::string> tail{"health","power","permission","commands"};
    ASSERT_GE(port.events.size(),tail.size()); EXPECT_EQ(std::vector<std::string>(port.events.end()-4,port.events.end()),tail);
}
TEST_F(CoordinatorTest, VehicleCannotArmBeforeReadinessAndActiveShutdownRequiresControlledStop) {
    EXPECT_EQ(coordinator.receive_vehicle(vehicle(10),kStart),central::CoordinatorReceive::NotReady); normal();
    auto shutdown=root(40); shutdown.action=can::BmsPowerAction::Shutdown;
    EXPECT_EQ(coordinator.receive_lifecycle(shutdown,port.now),central::CoordinatorReceive::StopRequired);
    EXPECT_EQ(coordinator.decision().fault,central::CoordinatorFault::None);
}
TEST_F(CoordinatorTest, DuplicatesAndRejectedMutationDoNotReauthorizeOrRenewRoots) {
    port.now=ns(10); auto r=root(10); ASSERT_EQ(coordinator.receive_lifecycle(r,port.now),central::CoordinatorReceive::Accepted);
    EXPECT_EQ(coordinator.receive_lifecycle(r,port.now),central::CoordinatorReceive::Unchanged); EXPECT_EQ(port.lifecycles.size(),1U);
    r.identity.expires_at_ns+=kMs; EXPECT_EQ(coordinator.receive_lifecycle(r,port.now),central::CoordinatorReceive::Rejected); EXPECT_EQ(port.lifecycles.size(),1U);
}
TEST_F(CoordinatorTest, MissingStartupFeedbackUsesBoundedWaitAndCannotBeHealedByFreshInputs) {
    for(std::uint32_t ms=10;ms<=80;ms+=10) { port.now=ns(ms); auto in=feedback(ms,false); in.front.brake_actual.reset(); coordinator.tick(in,port.now); }
    EXPECT_EQ(coordinator.decision().fault,central::CoordinatorFault::Management); EXPECT_EQ(port.protections,1U); tick(90,false);
    EXPECT_FALSE(coordinator.decision().management.normal_allowed); EXPECT_EQ(port.protections,1U);
}
TEST_F(CoordinatorTest, SourceLossAndWrongSessionCloseTheNormalPathBeforeAnyNewDelivery) {
    normal(); const auto count=port.commands.size(); auto in=inputs(50); in.front.health.reset(); port.now=ns(50);
    coordinator.tick(in,port.now); EXPECT_EQ(coordinator.decision().fault,central::CoordinatorFault::Management);
    EXPECT_EQ(port.commands.size(),count); EXPECT_FALSE(coordinator.decision().management.normal_allowed);
}
TEST_F(CoordinatorTest, WrongFeedbackEpochProtectsBeforePowerOutput) {
    port.now=ns(10); auto in=feedback(10,false); in.epoch=4; coordinator.tick(in,port.now);
    EXPECT_EQ(coordinator.decision().fault,central::CoordinatorFault::SessionMismatch); EXPECT_FALSE(port.sent_power); EXPECT_EQ(port.protections,1U);
}
TEST_F(CoordinatorTest, RootDeliveryFailureLatchesAndCannotBeRetriedByPacketFlood) {
    port.root_ok=false; port.protect_ok=false; port.now=ns(10); const auto r=root(10);
    EXPECT_EQ(coordinator.receive_lifecycle(r,port.now),central::CoordinatorReceive::Latched);
    for(int i=0;i<20;++i) EXPECT_EQ(coordinator.receive_lifecycle(r,port.now),central::CoordinatorReceive::Latched);
    EXPECT_EQ(port.protections,1U); tick(10,false); EXPECT_EQ(port.protections,2U);
    port.protect_ok=true; tick(20,false); EXPECT_EQ(port.protections,3U); tick(30,false); EXPECT_EQ(port.protections,3U);
}
TEST_F(CoordinatorTest, PartialArmFailureSelectsProtectionAndSendsNoAllowNormal) {
    request(10); tick(10,false); request(20); port.arm_ok=false; tick(20);
    EXPECT_EQ(coordinator.decision().fault,central::CoordinatorFault::Arm); EXPECT_EQ(port.protections,1U);
    ASSERT_TRUE(port.sent_power); EXPECT_EQ(std::get<can::BmsDriveGrant>(port.sent_power->drive_permission.content).permission,can::BmsDrivePermission::Inhibit);
}
TEST_F(CoordinatorTest, PowerAndCommandFailuresDoNotRetryNormalOutput) {
    normal(); port.commands_ok=false; request(50); tick(50); port.now=ns(60);
    ASSERT_EQ(coordinator.receive_vehicle(vehicle(60,2),port.now),central::CoordinatorReceive::Accepted); tick(60);
    EXPECT_EQ(coordinator.decision().fault,central::CoordinatorFault::CommandDelivery); EXPECT_EQ(port.protections,1U);
    const auto count=port.commands.size(); tick(70); EXPECT_EQ(port.commands.size(),count);
}
TEST_F(CoordinatorTest, PowerDeliveryFailureSkipsAllocationAndSelectsProtection) {
    port.power_ok=false; request(10); tick(10,false); EXPECT_EQ(coordinator.decision().fault,central::CoordinatorFault::PowerDelivery);
    EXPECT_TRUE(port.commands.empty()); EXPECT_EQ(port.protections,1U);
}
TEST_F(CoordinatorTest, CallbackOverrunAndClockRollbackNeverDispatchLaterNormalCommands) {
    port.power_delay_ns=31*kMs; request(10); tick(10,false); EXPECT_EQ(coordinator.decision().fault,central::CoordinatorFault::ControlDeadline);
    EXPECT_TRUE(port.commands.empty()); coordinator.tick({},ns(9)); EXPECT_EQ(coordinator.decision().fault,central::CoordinatorFault::ClockError);
}
TEST_F(CoordinatorTest, QuietRequestRenewalCannotReplaceAnOverdueRunnable) {
    request(10); tick(10,false); port.now=ns(41);
    EXPECT_EQ(coordinator.receive_lifecycle(root(41),port.now),central::CoordinatorReceive::Latched);
    EXPECT_EQ(coordinator.decision().fault,central::CoordinatorFault::ControlDeadline);
}
TEST_F(CoordinatorTest, RestartRequiresNewerEpochAndParticipantPreflightWithoutClearingFaultOnFailure) {
    coordinator.request_protection(kStart); EXPECT_FALSE(coordinator.start_session({3,kStart}));
    EXPECT_FALSE(coordinator.start_session({4,kStart})); EXPECT_NE(coordinator.decision().fault,central::CoordinatorFault::None);
    port.epoch=4; port.ready=false; EXPECT_FALSE(coordinator.start_session({4,kStart}));
    port.ready=true; EXPECT_TRUE(coordinator.start_session({4,kStart})); EXPECT_EQ(coordinator.decision().fault,central::CoordinatorFault::None);
    EXPECT_EQ(coordinator.receive_lifecycle({{3,0,kStart,kStart+60*kMs},can::BmsPowerAction::Enable},kStart),central::CoordinatorReceive::Rejected);
}
TEST_F(CoordinatorTest, StopOwnsIssuerContinuationAndBlocksNormalIngressBeforeHandoff) {
    normal(); port.now=ns(50); ASSERT_EQ(coordinator.receive_stop(stop(50),port.now),central::CoordinatorReceive::Accepted);
    EXPECT_EQ(coordinator.receive_vehicle(vehicle(50,1),port.now),central::CoordinatorReceive::Stopping);
    EXPECT_EQ(coordinator.receive_lifecycle(root(50),port.now),central::CoordinatorReceive::Stopping);
    tick(50); ASSERT_FALSE(port.lifecycles.empty()); EXPECT_EQ(port.lifecycles.back().identity.sequence,3U);
    EXPECT_EQ(port.lifecycles.back().identity.source_time_ns,ns(50)); EXPECT_EQ(port.handoffs,0U);
    for(std::uint32_t ms=60;ms<=110;ms+=10) {
        port.now=ns(ms); ASSERT_EQ(coordinator.receive_stop(stop(ms,ms/10-5),port.now),central::CoordinatorReceive::Accepted); tick(ms);
        EXPECT_EQ(std::get<can::BmsPowerRequest>(port.sent_power->power_request.content).action,can::BmsPowerAction::Enable);
    }
    EXPECT_EQ(coordinator.decision().stop.state,central::NormalStopState::PowerDown); EXPECT_EQ(port.handoffs,1U);
}
TEST_F(CoordinatorTest, StopBesideNewNormalRootsWaitsForStrictlyNewSourceAndSuppressesPropulsion) {
    normal(); request(50); ASSERT_EQ(coordinator.receive_vehicle(vehicle(50,2),port.now),central::CoordinatorReceive::Accepted);
    ASSERT_EQ(coordinator.receive_stop(stop(50),port.now),central::CoordinatorReceive::Accepted); const auto before=port.commands.size(); tick(50);
    EXPECT_EQ(port.commands.size(),before); tick(60); EXPECT_EQ(coordinator.decision().fault,central::CoordinatorFault::None);
    ASSERT_GT(port.commands.size(),before); EXPECT_LE(port.commands.back().parent.acceleration_mps2,0);
}
TEST_F(CoordinatorTest, HandoffFailureNeverAcknowledgesShutdownAndProtectsAllParticipants) {
    normal(); port.stop_ok=false; port.now=ns(50); ASSERT_EQ(coordinator.receive_stop(stop(50),port.now),central::CoordinatorReceive::Accepted);
    for(std::uint32_t ms=50;ms<=110;ms+=10) {
        port.now=ns(ms); if(ms>50) { ASSERT_EQ(coordinator.receive_stop(stop(ms,ms/10-5),port.now),central::CoordinatorReceive::Accepted); } tick(ms);
    }
    EXPECT_EQ(coordinator.decision().fault,central::CoordinatorFault::Handoff); EXPECT_EQ(coordinator.decision().stop.state,central::NormalStopState::HandoffPending);
    EXPECT_EQ(port.protections,1U); EXPECT_EQ(std::get<can::BmsPowerRequest>(port.sent_power->power_request.content).action,can::BmsPowerAction::Enable);
}
TEST_F(CoordinatorTest, LostStopIntentCannotBeRenewedAfterItsPreviousAuthorityExpired) {
    normal(); port.now=ns(50); ASSERT_EQ(coordinator.receive_stop(stop(50),port.now),central::CoordinatorReceive::Accepted);
    for(std::uint32_t ms=50;ms<=100;ms+=10) tick(ms);
    port.now=ns(110); EXPECT_EQ(coordinator.receive_stop(stop(110,1),port.now),central::CoordinatorReceive::Latched);
    EXPECT_EQ(coordinator.decision().fault,central::CoordinatorFault::Stop); EXPECT_EQ(port.protections,1U);
}
TEST_F(CoordinatorTest, CallbackJitterCanSkipAnEarlyManagementTickWithoutRestampingOrStarvingAllocation) {
    request(10); port.health_delay_ns=2*kMs; tick(10,false); ASSERT_TRUE(port.sent_power);
    const auto source=port.sent_power->power_request.source_time_ns; EXPECT_EQ(source,ns(12));
    request(20); port.health_delay_ns=kMs; tick(20); EXPECT_EQ(port.sent_power->power_request.source_time_ns,source);
    EXPECT_EQ(coordinator.decision().fault,central::CoordinatorFault::None);
    request(30); tick(30); EXPECT_EQ(coordinator.decision().fault,central::CoordinatorFault::None);
    EXPECT_TRUE(coordinator.decision().normal_armed); EXPECT_EQ(port.arms,1U);
}
TEST_F(CoordinatorTest, ExpiredAllocationSupportIsPropagatedImmediatelyWhenANewRootArrives) {
    normal(); request(50); tick(50); tick(60); port.now=ns(61);
    EXPECT_EQ(coordinator.receive_vehicle(vehicle(61,2),port.now),central::CoordinatorReceive::Latched);
    EXPECT_EQ(coordinator.decision().fault,central::CoordinatorFault::Allocation); EXPECT_EQ(port.protections,1U);
}
}  // namespace
