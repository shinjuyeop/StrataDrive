#include "async_coordinator_port.hpp"
#include "async_zone_owner.hpp"

#include <gtest/gtest.h>
#include <memory>
#include <vector>

namespace {
using namespace stratadrive;
constexpr std::uint64_t kMs=1000000,kStart=1000000000;
class Clock : public transport::Clock {
public:
    std::uint64_t now{kStart};
    std::uint64_t now_ns() noexcept override { return now; }
};
struct AsyncOwnerTest : ::testing::Test {
    Clock clock; transport::RunGate gate;
    std::unique_ptr<transport::ZoneLink> front{std::make_unique<transport::ZoneLink>()},rear{std::make_unique<transport::ZoneLink>()};
    central::AsyncCoordinatorPort port{clock,gate,*front,*rear};
    void initialize() { ASSERT_TRUE(port.initialize({3,clock.now})); gate.release(3); }
    void ack(transport::ZoneLink& link,const transport::ZoneRequest& r,bool accepted=true,std::size_t frames=0) {
        ASSERT_TRUE(link.results.push({r.epoch,r.token,clock.now,transport::operation(r.work),accepted,frames}));
    }
};
TEST_F(AsyncOwnerTest, EvCapabilityDependencyKeepsItsOriginalSeventyMillisecondBudget) {
    initialize();clock.now=kStart+50*kMs;
    can::DriveMessage m;m.kind=can::DriveFrameKind::Actual;m.epoch=3;m.sequence=0;
    m.source_time_ns=clock.now;m.local_state=can::ActuatorLocalState::Normal;m.origin=can::ActuatorOrigin::NormalPath;
    m.torque_nm=0;m.wheel_speed=can::DriveWheelSpeed{5,clock.now};
    m.regen_capability=can::DriveRegenCapability{200,clock.now,clock.now-40*kMs};m.regen_limit_reason=can::DriveRegenLimitReason::Nominal;
    can::DriveTxState tx{can::DriveFrameKind::Actual};const auto frame=can::encode_drive_frame(m,tx);ASSERT_TRUE(frame);
    ASSERT_TRUE(rear->feedback.push(*frame));port.service();const auto f=port.feedback();
    ASSERT_TRUE(f.rear.drive_actual);ASSERT_TRUE(f.rear.drive_actual->torque_nm);ASSERT_TRUE(f.rear.drive_actual->wheel_speed);
    ASSERT_TRUE(f.rear.drive_actual->regen_capability);
    EXPECT_EQ(f.rear.drive_actual->regen_capability->input_time_ns,kStart+10*kMs);
    // The capability source/torque age remains30ms; no stale-data revival.
    clock.now+=30*kMs+1;EXPECT_FALSE(port.feedback().rear.drive_actual);
}
TEST_F(AsyncOwnerTest, SessionAndGlobalGatePrecedeAllNormalIngress) {
    const central::LifecycleRequest root{{3,0,kStart,kStart+60*kMs},can::BmsPowerAction::Enable};
    EXPECT_FALSE(port.authorize_lifecycle(root)); ASSERT_TRUE(port.initialize({3,kStart}));
    EXPECT_FALSE(port.authorize_lifecycle(root)); EXPECT_EQ(port.arm_status(3),central::OperationStatus::Rejected);
    gate.release(3); EXPECT_TRUE(port.authorize_lifecycle(root)); EXPECT_TRUE(rear->work.pop());
    gate.close(); EXPECT_FALSE(port.authorize_lifecycle(root)); EXPECT_FALSE(front->work.pop());
}
TEST_F(AsyncOwnerTest, ArmNeedsTwoCorrelatedAcksAndDoesNotResendWhilePending) {
    initialize(); EXPECT_EQ(port.arm_status(3),central::OperationStatus::Pending);
    const auto f=front->work.pop(),r=rear->work.pop(); ASSERT_TRUE(f); ASSERT_TRUE(r);
    ack(*front,*f); port.service(); EXPECT_EQ(port.arm_status(3),central::OperationStatus::Pending); EXPECT_FALSE(front->work.pop());
    ack(*rear,*r); port.service(); EXPECT_EQ(port.arm_status(3),central::OperationStatus::Accepted);
}
TEST_F(AsyncOwnerTest, NegativePartialArmClosesGateAndSignalsBothZones) {
    initialize(); port.arm_status(3); const auto f=front->work.pop(),r=rear->work.pop(); ASSERT_TRUE(f); ASSERT_TRUE(r);
    ack(*front,*f); ack(*rear,*r,false); port.service();
    EXPECT_TRUE(port.transport_fault()); EXPECT_FALSE(gate.allows(3)); EXPECT_TRUE(front->protection.pending(3)); EXPECT_TRUE(rear->protection.pending(3));
    EXPECT_FALSE(port.protect()); front->protection.selected.store(3); rear->protection.selected.store(3); EXPECT_TRUE(port.protect());
}
TEST_F(AsyncOwnerTest, MissingOrLateTxResultCannotRenewTheOriginalDeadline) {
    initialize(); port.arm_status(3); const auto f=front->work.pop(); ASSERT_TRUE(f);
    clock.now=f->deadline_ns; ack(*front,*f); port.service(); EXPECT_TRUE(port.transport_fault()); EXPECT_FALSE(gate.allows(3));
}
TEST_F(AsyncOwnerTest, WrongZoneOrOperationResultLatchesProtection) {
    initialize(); port.arm_status(3); const auto f=front->work.pop(); ASSERT_TRUE(f);
    ack(*rear,*f); port.service(); EXPECT_TRUE(port.transport_fault());
}
TEST_F(AsyncOwnerTest, FrontTxMustSucceedBeforeRearCommandIsEvenQueued) {
    initialize(); central::AllocatedCommands commands; commands.parent={3,0,kStart,kStart+60*kMs}; commands.expires_at_ns=kStart+30*kMs;
    ASSERT_TRUE(port.deliver_commands(commands)); EXPECT_FALSE(rear->work.pop()); const auto f=front->work.pop(); ASSERT_TRUE(f);
    ack(*front,*f,false,1); port.service(); EXPECT_FALSE(rear->work.pop()); EXPECT_TRUE(port.transport_fault());
}
TEST_F(AsyncOwnerTest, CommandResultsHaveExactFrameCountsAndRearFollowsFront) {
    initialize(); central::AllocatedCommands commands; commands.parent={3,0,kStart,kStart+60*kMs}; commands.expires_at_ns=kStart+30*kMs;
    ASSERT_TRUE(port.deliver_commands(commands)); const auto f=front->work.pop(); ASSERT_TRUE(f); ack(*front,*f,true,2); port.service();
    const auto r=rear->work.pop(); ASSERT_TRUE(r); EXPECT_EQ(std::get<central::ScopedCommands>(r->work).index(),1U);
    ack(*rear,*r,true,1); port.service(); EXPECT_EQ(port.completed_batches(),1U); EXPECT_FALSE(port.transport_fault());
}
TEST_F(AsyncOwnerTest, PendingAllocationDoesNotRenewResultOrConsumeAnotherBatch) {
    initialize(); central::AllocatedCommands commands; commands.parent={3,0,kStart,kStart+60*kMs}; commands.expires_at_ns=kStart+30*kMs;
    ASSERT_TRUE(port.deliver_commands(commands));const auto f=front->work.pop();ASSERT_TRUE(f);
    const central::VehicleManagementOutput output{};
    clock.now=f->deadline_ns-1;EXPECT_FALSE(port.allocation_ready(output,clock.now));
    EXPECT_FALSE(port.deliver_commands(commands));EXPECT_FALSE(front->work.pop());EXPECT_TRUE(gate.allows(3));
    clock.now=f->deadline_ns;port.service();
    EXPECT_EQ(port.fault(),central::AsyncTransportFault::ResultTimeout);EXPECT_FALSE(gate.allows(3));
    ack(*front,*f,true,2);port.service();EXPECT_FALSE(rear->work.pop());EXPECT_FALSE(gate.allows(3));
    ++clock.now;EXPECT_FALSE(port.initialize({3,clock.now}));ASSERT_TRUE(port.initialize({4,clock.now}));
    ack(*front,*f,true,2);port.service();EXPECT_FALSE(port.transport_fault());EXPECT_FALSE(gate.allows(4));
    EXPECT_FALSE(rear->work.pop());EXPECT_TRUE(port.commands_settled());
}
TEST_F(AsyncOwnerTest, NewEpochDiscardsOldResultWithoutReopeningGate) {
    initialize(); port.arm_status(3); const auto old=front->work.pop(); ASSERT_TRUE(old); gate.close(); clock.now+=kMs;
    ASSERT_TRUE(port.initialize({4,clock.now})); ack(*front,*old); port.service();
    EXPECT_FALSE(port.transport_fault()); EXPECT_FALSE(gate.allows(4)); EXPECT_EQ(port.arm_status(3),central::OperationStatus::Rejected);
}
TEST_F(AsyncOwnerTest, AllocationWaitsForReceivedGrantAndUsesItsOriginalIssuedParent) {
    initialize();
    central::VehicleManagementOutput out;
    out.power_request.kind=can::BmsFrameKind::PowerRequest;
    out.drive_permission.kind=can::BmsFrameKind::DrivePermission;
    for(auto* message:{&out.power_request,&out.drive_permission}) {
        message->epoch=3; message->source_time_ns=kStart; message->local_state=can::ActuatorLocalState::Normal; message->origin=can::ActuatorOrigin::NormalPath;
    }
    out.power_request.content=can::BmsPowerRequest{can::BmsPowerAction::Enable,kStart+60*kMs,kStart};
    out.drive_permission.content=can::BmsDriveGrant{can::BmsDrivePermission::AllowNormal,0,kStart,kStart,kStart+60*kMs};
    out.power_parent=out.permission_parent=can::BmsParentContext{3,0,kStart,kStart+60*kMs};
    ASSERT_TRUE(port.deliver_power(out)); EXPECT_FALSE(port.allocation_ready(out,kStart)); EXPECT_FALSE(port.current_permission());
    can::BmsTxState tx{can::BmsFrameKind::DrivePermission}; const auto frame=can::encode_bms_frame(out.drive_permission,tx); ASSERT_TRUE(frame);
    ASSERT_TRUE(rear->feedback.push(*frame)); port.service(); EXPECT_TRUE(port.allocation_ready(out,kStart));
    const auto first=port.received_permission_parent(); ASSERT_TRUE(first); EXPECT_EQ(first->sequence,0U); EXPECT_EQ(first->source_time_ns,kStart);
    clock.now+=10*kMs; auto newer=out; newer.drive_permission.sequence=1; newer.drive_permission.source_time_ns=clock.now; newer.drive_permission.causal_sequence=1;
    newer.permission_parent=can::BmsParentContext{3,1,clock.now,clock.now+60*kMs};
    ASSERT_TRUE(port.deliver_power(newer)); EXPECT_FALSE(port.allocation_ready(newer,clock.now));
    const auto still_first=port.received_permission_parent(); ASSERT_TRUE(still_first); EXPECT_EQ(still_first->sequence,0U);
}
// Saved normal failure: next release=532747851408166, latest grant
// source=532747855410737, expiry=532747871338563 (69,603ns short).
TEST_F(AsyncOwnerTest, ReadinessRequiresCurrentUsableGrantWithoutRestamping) {
    initialize();
    central::VehicleManagementOutput out;
    for(auto* m:{&out.power_request,&out.drive_permission}) {
        m->epoch=3; m->source_time_ns=kStart; m->local_state=can::ActuatorLocalState::Normal;
        m->origin=can::ActuatorOrigin::NormalPath;
    }
    out.power_request.kind=can::BmsFrameKind::PowerRequest;
    out.drive_permission.kind=can::BmsFrameKind::DrivePermission;
    out.power_request.content=can::BmsPowerRequest{can::BmsPowerAction::Enable,kStart+60*kMs,kStart};
    out.drive_permission.content=can::BmsDriveGrant{can::BmsDrivePermission::AllowNormal,0,kStart,kStart,kStart+30*kMs};
    out.power_parent=out.permission_parent=can::BmsParentContext{3,0,kStart,kStart+60*kMs};
    ASSERT_TRUE(port.deliver_power(out));const auto request=rear->work.pop();ASSERT_TRUE(request);
    can::BmsTxState tx{can::BmsFrameKind::DrivePermission};const auto frame=can::encode_bms_frame(out.drive_permission,tx);ASSERT_TRUE(frame);
    clock.now=kStart+kMs;ack(*rear,*request,true,2);ASSERT_TRUE(rear->feedback.push(*frame));port.service();
    clock.now=kStart+6*kMs;
    ASSERT_TRUE(port.current_permission());
    EXPECT_FALSE(port.allocation_ready(out,clock.now)); // Preserve the release phase contract.
    EXPECT_TRUE(port.allocation_ready(out,kStart));
    EXPECT_EQ(port.current_permission()->message.source_time_ns,kStart);
    EXPECT_EQ(std::get<can::BmsDriveGrant>(port.current_permission()->message.content).expires_at_ns,kStart+30*kMs);
    // Do not turn the observed 69,603ns shortfall into a synthetic longer grant.
    const auto short_release=kStart+10*kMs+69603;
    clock.now=short_release;EXPECT_FALSE(port.allocation_ready(out,short_release));
    clock.now=kStart+30*kMs;EXPECT_FALSE(port.allocation_ready(out,kStart)); // Was true on metadata identity alone.
    EXPECT_FALSE(port.allocation_ready(out,short_release));
    ASSERT_TRUE(port.current_permission()); // Expired current view is canonical unavailable.
    EXPECT_FALSE(can::bms_permission_allows_normal(*port.current_permission()));
    EXPECT_EQ(std::get<can::BmsDriveGrant>(out.drive_permission.content).expires_at_ns,kStart+30*kMs);
}
TEST_F(AsyncOwnerTest, RecordedInsufficientGrantCannotCoverNextTwentyMillisecondRelease) {
    constexpr std::uint64_t release=532747851408166,source=532747855410737,expiry=532747871338563;
    EXPECT_EQ(release+20*kMs-expiry,69603U);
    clock.now=source;initialize();
    struct Trace final:transport::TransportTrace {
        std::vector<transport::TransportTraceRow> rows;
        void record(transport::TransportTraceRow row) noexcept override {rows.push_back(row);}
    } trace;
    trace.rows.reserve(32);port.transport_trace(&trace);
    central::VehicleManagementOutput out;
    for(auto* m:{&out.power_request,&out.drive_permission}) {
        m->epoch=3;m->source_time_ns=source;m->local_state=can::ActuatorLocalState::Normal;m->origin=can::ActuatorOrigin::NormalPath;
    }
    out.power_request.kind=can::BmsFrameKind::PowerRequest;out.drive_permission.kind=can::BmsFrameKind::DrivePermission;
    out.power_request.content=can::BmsPowerRequest{can::BmsPowerAction::Enable,source+50*kMs,source};
    out.drive_permission.content=can::BmsDriveGrant{can::BmsDrivePermission::AllowNormal,0,source,source,expiry};
    out.power_parent=out.permission_parent=can::BmsParentContext{3,0,source,source+60*kMs};
    ASSERT_TRUE(port.deliver_power(out));const auto r=rear->work.pop();ASSERT_TRUE(r);
    can::BmsTxState tx{can::BmsFrameKind::DrivePermission};const auto frame=can::encode_bms_frame(out.drive_permission,tx);ASSERT_TRUE(frame);
    clock.now=532747855631899;ack(*rear,*r,true,2);ASSERT_TRUE(rear->feedback.push(*frame));port.service();
    ASSERT_TRUE(port.current_permission());EXPECT_TRUE(port.commands_settled());
    EXPECT_FALSE(port.allocation_ready(out,release));
    ASSERT_FALSE(trace.rows.empty());const auto& decision=trace.rows.back();
    EXPECT_STREQ(decision.stage,"allocation-readiness");EXPECT_EQ(decision.outcome,3);
    EXPECT_EQ(decision.token,0U);EXPECT_EQ(decision.operation,-1); // Not a transaction identity.
    EXPECT_EQ(decision.sent_ns,release);EXPECT_EQ(decision.original_source_ns,source);
    EXPECT_EQ(decision.inner_deadline_ns,expiry);
    clock.now=532747859008926;EXPECT_FALSE(port.allocation_ready(out,release));
    EXPECT_TRUE(gate.allows(3)); // This port does not fabricate a Leaf completion or expiry extension.
    EXPECT_FALSE(front->work.pop());EXPECT_FALSE(rear->work.pop());
}
TEST_F(AsyncOwnerTest, BrokenMailboxCannotBeRepairedByEpochAndProtectionBypassesIt) {
    initialize(); const transport::ZoneRequest value{};
    for(std::size_t i=0;i<transport::kBudget;++i) ASSERT_TRUE(front->work.push(value));
    EXPECT_FALSE(front->work.push(value)); port.service(); EXPECT_FALSE(gate.allows(3)); EXPECT_TRUE(front->protection.pending(3));
    clock.now+=kMs; EXPECT_FALSE(port.initialize({4,clock.now}));
}
TEST_F(AsyncOwnerTest, ClockRollbackClosesBothZonesWithoutNormalRetry) {
    initialize(); --clock.now; port.service(); EXPECT_TRUE(port.transport_fault()); EXPECT_FALSE(gate.allows(3)); EXPECT_TRUE(rear->protection.pending(3));
}
TEST(AsyncZoneOwner, PartialLeafArmMustProtectBothLeavesThroughIndependentSignals) {
    Clock clock; transport::RunGate gate; auto central=std::make_unique<transport::ZoneLink>();
    auto leaves=std::make_unique<std::array<transport::LeafLink,transport::kLeaves>>();
    std::array<transport::LeafLink*,transport::kLeaves> ptrs{}; for(std::size_t i=0;i<ptrs.size();++i) ptrs[i]=&(*leaves)[i];
    zone::AsyncZoneOwner zone{zone::ZoneScope::Front,clock,gate,*central,ptrs}; ASSERT_TRUE(zone.initialize(3,kStart)); gate.release(3);
    ASSERT_TRUE(central->work.push({3,1,kStart,kStart+20*kMs,transport::Arm{}})); zone.service();
    const auto steer=(*leaves)[0].work.pop(),brake=(*leaves)[1].work.pop(); ASSERT_TRUE(steer); ASSERT_TRUE(brake);
    ASSERT_TRUE((*leaves)[0].reports.push(transport::LeafResult{3,1,kStart,transport::LeafOperation::Arm,true}));
    ASSERT_TRUE((*leaves)[1].reports.push(transport::LeafResult{3,1,kStart,transport::LeafOperation::Arm,false})); zone.service();
    EXPECT_TRUE(zone.faulted()); EXPECT_FALSE(gate.allows(3));
    EXPECT_TRUE((*leaves)[0].protection.pending(3)); EXPECT_TRUE((*leaves)[1].protection.pending(3));
    const auto result=central->results.pop(); ASSERT_TRUE(result); EXPECT_FALSE(result->accepted); EXPECT_FALSE(zone.protected_selected());
    (*leaves)[0].protection.selected.store(3); (*leaves)[1].protection.selected.store(3); zone.service(); EXPECT_TRUE(central->protection.acknowledged(3));
}
TEST(AsyncZoneOwner, ExpiredQueueEntryIsRejectedWithoutRestampingOrLeafDispatch) {
    Clock clock; transport::RunGate gate; auto central=std::make_unique<transport::ZoneLink>();
    auto leaves=std::make_unique<std::array<transport::LeafLink,transport::kLeaves>>();
    std::array<transport::LeafLink*,transport::kLeaves> ptrs{}; for(std::size_t i=0;i<ptrs.size();++i) ptrs[i]=&(*leaves)[i];
    zone::AsyncZoneOwner zone{zone::ZoneScope::Front,clock,gate,*central,ptrs}; ASSERT_TRUE(zone.initialize(3,kStart)); gate.release(3);
    const transport::ZoneRequest original{3,9,kStart,kStart+20*kMs,transport::Arm{}}; ASSERT_TRUE(central->work.push(original));
    clock.now=original.deadline_ns; zone.service(); const auto result=central->results.pop(); ASSERT_TRUE(result);
    EXPECT_FALSE(result->accepted); EXPECT_EQ(result->token,original.token); EXPECT_FALSE((*leaves)[0].work.pop()); EXPECT_FALSE((*leaves)[1].work.pop());
    EXPECT_TRUE(zone.faulted()); EXPECT_TRUE((*leaves)[0].protection.pending(3));
}
}  // namespace
