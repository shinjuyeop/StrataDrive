#pragma once
#include "transport_trace.hpp"

#include "owner_transport.hpp"
#include "command_gateway.hpp"
#include "rear_power_gateway.hpp"
#include "zone_feedback_monitor.hpp"
#include "steering_receiver.hpp"
#include "brake_receiver.hpp"
#include "drive_receiver.hpp"

namespace stratadrive::zone {
// Owns only this Zone's gateways, receiver histories and feedback monitor.
// Leaf state is accessed exclusively through one directed link per Leaf.
class AsyncZoneOwner final : private GatewayPort,private RearPowerPort {
public:
    void transport_trace(transport::TransportTrace* sink) { trace_=sink; } // before launch only
    AsyncZoneOwner(ZoneScope scope,transport::Clock& clock,transport::RunGate& gate,transport::ZoneLink& central,
        const std::array<transport::LeafLink*,transport::kLeaves>& leaves);
    bool initialize(std::uint32_t epoch,std::uint64_t enable_ns);
    void service();
    void protect_local();
    void quiesce();
    bool protected_selected() const;
    std::uint32_t epoch() const { return epoch_; }
    bool faulted() const { return failed_; }
    int rejection() const { return rejection_; }
    std::size_t command_frames() const { return command_frames_; }
    std::uint64_t last_health_ns() const { return last_health_; }
    std::array<transport::InputEvidence,3> input_history() const {
        return {transport::input_evidence(steering_.last_accepted()),transport::input_evidence(brake_.last_accepted()),transport::input_evidence(drive_.last_accepted())};
    }
    // Deterministic injection at the transport write boundary, owner thread only.
    bool fail_brake_write{false},drop_feedback{false},drop_permission_feedback{false};
private:
    transport::TransportTrace* trace_{nullptr};
    std::uint64_t now_ns() noexcept override { return clock_.now_ns(); }
    bool send(const CommandFrame& frame,const central::CommandContext& context) noexcept override;
    bool send(const can::BmsFrame& frame,const RearPowerDelivery& delivery) noexcept override;
    bool arm_normal_commands(std::uint32_t epoch,std::uint64_t now_ns) noexcept override;
    bool protect(ZoneScope scope,ProtectionCause cause,std::uint64_t now_ns) noexcept override;
    bool leaf_send(transport::Leaf leaf,transport::LeafRequest packet);
    void handle(const transport::ZoneRequest& request);
    void report(transport::Leaf leaf,const transport::LeafReport& report);
    void complete(const transport::ZoneRequest& request,bool accepted,std::size_t frames=0);
    void forward(const transport::Feedback& frame);
    void progress();
    bool leaf_selected() const;
    std::pair<std::size_t,std::size_t> leaf_range() const;
    ZoneScope scope_; transport::Clock& clock_; transport::RunGate& gate_; transport::ZoneLink& central_;
    std::array<transport::LeafLink*,transport::kLeaves> leaves_;
    CommandGateway commands_; std::optional<RearPowerGateway> power_; ZoneFeedbackMonitor health_;
    can::SteeringReceiver steering_{{can::SteeringFrameKind::Actual,-.3,.3}};
    can::BrakeReceiver brake_{{can::BrakeFrameKind::Actual,0,1500000}};
    can::DriveReceiver drive_{{can::DriveFrameKind::Actual,{-300,500},100,300}};
    std::uint32_t epoch_{0}; std::uint64_t enable_{0},observed_{0},last_health_{0},sending_token_{0},sending_sent_{0},sending_deadline_{0};
    std::array<std::uint64_t,2> last_inputs_{};
    bool failed_{false},drive_arm_ack_{false}; std::size_t command_frames_{0};
    int rejection_{0};
    std::optional<transport::ZoneRequest> pending_;
    std::array<bool,transport::kLeaves> leaf_ack_{};
};
}  // namespace stratadrive::zone
