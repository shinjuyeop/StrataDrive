#pragma once

#include "local_safety.hpp"
#include "bounded_rx_queue.hpp"

namespace stratadrive::zone {
using CommandFrame = std::variant<can::SteeringFrame, can::BrakeFrame, can::DriveFrame>;
class GatewayPort : public ProtectionPort {
public:
    virtual std::uint64_t now_ns() noexcept = 0;
    // Synchronous bounded/nonblocking enqueue. Check context.expires_at_ns at
    // the final enqueue too; retain context in any additional application queue.
    virtual bool send(const CommandFrame& frame, const central::CommandContext& context) noexcept = 0;
};
struct GatewayDecision {
    AdmissionDecision admission;
    SafetyDecision safety;
    std::size_t pending{0};
};
struct GatewayDispatch {
    std::size_t frames_enqueued{0}, superseded{0};
    bool partial_front{false}; // two CAN writes are not atomic
};

// Single owner, one independent instance/port/CAN interface per logical Zone.
// Only new accepted commands enter the bounded FIFO; no periodic restamping.
class CommandGateway {
public:
    static constexpr std::size_t kCapacity = 8;
    CommandGateway(ZoneScope scope, GatewayPort& port, const AdmissionConfig& config = {});
    bool start_session(std::uint32_t epoch, std::uint64_t enable_ns);
    bool arm();
    AdmissionResult authorize_request(const central::VehicleRequest& parent);
    AdmissionResult enqueue(const central::ScopedCommands& commands);
    GatewayDispatch dispatch(); // bounded drain; at most one batch / two frames
    GatewayDecision poll(); // independently schedule at <=10 ms; retries pending protection once
    void mark_continuity_lost();
    void request_protection(); // trusted coordinator/protection path, never normal payload
private:
    bool refresh();
    void fail(ProtectionCause cause);
    const ZoneScope scope_;
    GatewayPort& port_;
    CommandAdmission admission_;
    LocalSafety safety_;
    can::BoundedRxQueue<central::ScopedCommands, kCapacity> queue_;
    can::SteeringTxState steering_tx_{can::SteeringFrameKind::Command};
    can::BrakeTxState brake_tx_{can::BrakeFrameKind::Command};
    can::DriveTxState drive_tx_{can::DriveFrameKind::Command};
    std::uint32_t epoch_{0};
    std::uint64_t observed_ns_{0};
};
}  // namespace stratadrive::zone
