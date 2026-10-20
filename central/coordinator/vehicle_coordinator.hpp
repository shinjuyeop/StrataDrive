#pragma once

#include "control_allocation.hpp"
#include "normal_stop.hpp"

namespace stratadrive::central {
struct CoordinatorSession { std::uint32_t epoch; std::uint64_t enable_ns; };
struct CoordinatorExecution { bool external_releases{false}; };
enum class OperationStatus { Pending, Accepted, Rejected };
// Trusted single-owner adapter. Callbacks are bounded, nonblocking and must
// retain original roots/expiry. ACK means output selection/enqueue, not physics.
class CoordinatorPort {
public:
    virtual ~CoordinatorPort() = default;
    virtual std::uint64_t now_ns() noexcept = 0;
    virtual bool session_ready(CoordinatorSession session) noexcept = 0;
    virtual bool healthy(std::uint32_t epoch) noexcept = 0;
    virtual bool authorize_lifecycle(const LifecycleRequest& root) noexcept = 0;
    virtual bool authorize_vehicle(const VehicleRequest& root) noexcept = 0;
    virtual bool arm(std::uint32_t epoch) noexcept = 0;
    virtual OperationStatus arm_status(std::uint32_t epoch) noexcept {
        return arm(epoch)?OperationStatus::Accepted:OperationStatus::Rejected;
    }
    virtual bool deliver_power(const VehicleManagementOutput& output) noexcept = 0;
    // False defers this due release without constructing/queueing a replacement
    // command. Resume from current inputs; do not advance nominal release or
    // renew transport/command authority while waiting.
    virtual bool allocation_ready(const VehicleManagementOutput&,std::uint64_t) noexcept { return true; }
    virtual bool commands_settled() const noexcept { return true; }
    virtual std::optional<can::BmsCurrentSample> current_permission() noexcept = 0;
    // Async ingress can still contain an older issued grant. Its independently
    // retained parent must match that received sample, not the latest issuance.
    virtual std::optional<can::BmsParentContext> received_permission_parent() noexcept { return std::nullopt; }
    virtual bool deliver_commands(const AllocatedCommands& commands) noexcept = 0;
    virtual bool select_stop(const NormalStopPlan& plan) noexcept = 0;
    virtual OperationStatus stop_status(const NormalStopPlan& plan) noexcept {
        return select_stop(plan)?OperationStatus::Accepted:OperationStatus::Rejected;
    }
    virtual bool protect() noexcept = 0;
};
enum class CoordinatorReceive { Accepted, Unchanged, Rejected, NotInitialized, NotReady, Latched, StopRequired, Stopping };
enum class CoordinatorFault { None, ClockError, ControlDeadline, SessionMismatch, Management, Allocation, Stop,
    RequestDelivery, Arm, PowerDelivery, CommandDelivery, Handoff, LocalProtection };
struct CoordinatorDecision {
    CoordinatorFault fault;
    bool normal_armed, stopping, protection_selected;
    VehicleManagementDecision management;
    AllocationDecision allocation;
    NormalStopDecision stop;
};
// Owns all three Central state owners; never issues an application Epoch,
// advances a plant, resets remote participants or turns cached data into fresh
// input. tick uses independently validated current samples from this cycle.
class VehicleCoordinator {
public:
    explicit VehicleCoordinator(CoordinatorPort& port,CoordinatorExecution execution = {});
    bool start_session(CoordinatorSession session);
    CoordinatorReceive receive_lifecycle(const LifecycleRequest& root, std::uint64_t now_ns);
    CoordinatorReceive receive_vehicle(const VehicleRequest& root, std::uint64_t now_ns);
    CoordinatorReceive receive_stop(const NormalStopRequest& root, std::uint64_t now_ns);
    void request_protection(std::uint64_t now_ns);
    // 10 ms externally clocked runnable, allocation every 20 ms. True means
    // a cycle ran (possibly selecting protection); inspect decision().
    bool tick(const NormalDriveReadinessInputs& feedback, std::uint64_t now_ns,bool management_release = true);
    CoordinatorDecision decision() const;
    std::uint64_t next_allocation_ns() const;
private:
    bool advance(std::uint64_t now_ns);
    bool checkpoint();
    void fail(CoordinatorFault fault);
    bool accept_lifecycle(const LifecycleRequest& root);
    bool accept_vehicle(const VehicleRequest& root);
    bool allocate(const NormalDriveReadinessInputs& inputs);
    void record_allocation_release();
    OperationStatus progress_handoff();
    CoordinatorPort& port_;
    const CoordinatorExecution execution_;
    VehicleManagement management_;
    ControlAllocation allocation_;
    NormalStop stop_;
    std::uint32_t epoch_{0};
    std::uint64_t enable_ns_{0}, observed_ns_{0}, cycle_start_ns_{0};
    std::optional<std::uint64_t> tick_ns_, allocation_ns_;
    std::optional<LifecycleRequest> lifecycle_;
    std::optional<VehicleRequest> vehicle_;
    std::optional<VehicleManagementOutput> last_power_;
    std::optional<NormalStopPlan> pending_handoff_;
    CoordinatorFault fault_{CoordinatorFault::None};
    bool normal_armed_{false}, stopping_{false}, protection_selected_{false}, protection_attempted_{false}, in_cycle_{false};
};
}  // namespace stratadrive::central
