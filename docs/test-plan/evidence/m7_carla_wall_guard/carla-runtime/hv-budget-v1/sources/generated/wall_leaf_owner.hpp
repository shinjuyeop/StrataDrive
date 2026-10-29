#pragma once
#include "async_leaf_owner.hpp"
#include "wall_drive_controller.hpp"
namespace stratadrive::simulation {
class WallLeafOwner final : public session::ParticipantPort {
public:
    void transport_trace(transport::TransportTrace* sink) { trace_=sink; } // before launch only
    WallLeafOwner(transport::Leaf leaf,transport::Clock& clock,transport::RunGate& gate,transport::LeafLink& link,
        runtime::LatestSnapshot<OwnerSensors>& sensors,runtime::LatestSnapshot<OwnerActuation>& output,BmsGateChannel& bms_gate,std::uint64_t hv_dependency_ns=30000000);
    std::uint64_t now_ns() noexcept override { return clock_.now_ns(); }
    session::Preparation prepare(const session::Plan& plan) noexcept override;
    bool initialize(const session::Plan& plan) noexcept override;
    void protect() noexcept override;
    void service() noexcept override;
    bool drop_actual{false},reject_arm{false};
    std::uint32_t epoch() const { return epoch_; }
    transport::Leaf leaf() const { return leaf_; }
    std::uint64_t last_body_ns() const { return last_body_; }
    std::size_t received_commands() const { return commands_; }
    bool faulted() const;
    int fault_code() const;
    const std::vector<M4Event>& input_events() const { return input_events_; } // joined only
    void execution_deadline(bool enabled) { execution_deadline_=enabled; } // startup only
private:
    transport::TransportTrace* trace_{nullptr};
    std::optional<transport::LeafRequest> traced_command_; // owner-local, diagnostic only
    using Actor=std::variant<vecu::SteeringActuator,vecu::BrakeActuator,vecu::WallDriveController,vecu::BmsController,vecu::PowerController>;
    static Actor make_actor(transport::Leaf leaf,std::uint64_t hv_dependency_ns);
    void handle(const transport::LeafRequest& request);
    void publish(const transport::Feedback& feedback);
    bool receive(const transport::LeafRequest& request);
    void runnable(const OwnerSensors& sensors,std::uint64_t now);
    void output(std::uint64_t now);
    void service_impl();
    transport::Leaf leaf_; transport::Clock& clock_; transport::RunGate& gate_; transport::LeafLink& link_;
    runtime::LatestSnapshot<OwnerSensors>& sensors_; runtime::LatestSnapshot<OwnerActuation>& output_; BmsGateChannel& bms_gate_;
    Actor actor_; std::uint32_t epoch_{0},quiesced_{0}; std::uint64_t enable_{0},last_body_{0},next_body_{0}; bool started_{false}; std::size_t commands_{0};
    can::BmsTxState bms_tx_{can::BmsFrameKind::PowerLimits},power_tx_{can::BmsFrameKind::PowerStatus};
    std::vector<M4Event> input_events_;
    std::uint64_t command_expiry_ns_{0},command_source_ns_{0}; bool expiry_reported_{false};
    std::uint32_t prepared_epoch_{0};
    bool execution_deadline_{false}; std::uint64_t body_release_{0},body_deadline_{0},receive_begin_{0};
};
}  // namespace stratadrive::simulation
