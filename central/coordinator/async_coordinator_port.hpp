#pragma once

#include "vehicle_coordinator.hpp"
#include "owner_transport.hpp"
#include "steering_receiver.hpp"
#include "brake_receiver.hpp"
#include "drive_receiver.hpp"

namespace stratadrive::central {
// Central owner only. No references to remote gateways/controllers. A successful
// delivery callback means transport enqueue; independently correlated TX results
// and original deadlines are monitored even when no new request arrives.
class AsyncCoordinatorPort final : public CoordinatorPort {
public:
    AsyncCoordinatorPort(transport::Clock& clock,transport::RunGate& gate,transport::ZoneLink& front,transport::ZoneLink& rear);
    bool initialize(CoordinatorSession session);
    void service();
    NormalDriveReadinessInputs feedback();
    bool transport_fault() const { return failed_; }
    std::uint64_t completed_batches() const { return completed_batches_; }
    std::uint64_t now_ns() noexcept override { return clock_.now_ns(); }
    bool session_ready(CoordinatorSession session) noexcept override;
    bool healthy(std::uint32_t epoch) noexcept override;
    bool authorize_lifecycle(const LifecycleRequest& root) noexcept override;
    bool authorize_vehicle(const VehicleRequest& root) noexcept override;
    bool arm(std::uint32_t epoch) noexcept override { return arm_status(epoch)==OperationStatus::Accepted; }
    OperationStatus arm_status(std::uint32_t epoch) noexcept override;
    bool deliver_power(const VehicleManagementOutput& output) noexcept override;
    std::optional<can::BmsCurrentSample> current_permission() noexcept override;
    std::optional<can::BmsParentContext> received_permission_parent() noexcept override;
    bool deliver_commands(const AllocatedCommands& commands) noexcept override;
    bool select_stop(const NormalStopPlan& plan) noexcept override { return stop_status(plan)==OperationStatus::Accepted; }
    OperationStatus stop_status(const NormalStopPlan& plan) noexcept override;
    bool protect() noexcept override;
private:
    struct Pending { transport::ZoneRequest request; std::size_t zone; };
    struct IssuedPermission { can::BmsMessage message; std::optional<can::BmsParentContext> parent; };
    bool post(std::size_t zone,const transport::ZoneWork& work,std::uint64_t expiry) noexcept;
    void result(std::size_t zone,const transport::TxResult& result);
    void receive(std::size_t zone,const transport::Feedback& value);
    void fail();
    transport::Clock& clock_; transport::RunGate& gate_;
    std::array<transport::ZoneLink*,2> links_;
    CoordinatorSession session_{}; std::uint64_t observed_{0},next_token_{1},completed_batches_{0}; bool failed_{false};
    std::array<std::optional<Pending>,16> pending_{};
    std::array<std::optional<IssuedPermission>,16> issued_{}; std::size_t issued_next_{0};
    std::optional<AllocatedCommands> commands_;
    std::array<bool,2> armed_{},stopped_{}; bool arm_sent_{false}; std::optional<ActuatorStopLease> stop_;
    can::SteeringReceiver steering_{{can::SteeringFrameKind::Actual,-.3,.3}};
    can::BrakeReceiver brake_{{can::BrakeFrameKind::Actual,0,1500000}};
    can::DriveReceiver drive_{{can::DriveFrameKind::Actual,{-300,500},100,300}};
    can::BmsReceiver status_,limits_,permission_;
    zone::ZoneStatusReceiver front_{zone::ZoneScope::Front},rear_{zone::ZoneScope::Rear};
};
}  // namespace stratadrive::central
