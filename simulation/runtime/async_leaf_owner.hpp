#pragma once

#include "owner_transport.hpp"
#include "session_participant.hpp"
#include "latest_snapshot.hpp"
#include "vehicle_session_init.hpp"
#include "m4_faults.hpp"

namespace stratadrive::simulation {
struct OwnerSensors {
    std::uint64_t source_ns{0};
    std::optional<steering::AngleMeasurement> angle;
    std::optional<brake::PressureMeasurement> pressure;
    std::optional<drive::TorqueMeasurement> torque;
    drive::LocalSensors drive;
    std::optional<power::SensorSnapshot> power;
    battery::SensorSnapshot battery;
};
SessionResetEvidence reset_evidence(const OwnerSensors& sensors);
struct OwnerActuation {
    std::uint32_t epoch{0}; std::uint64_t source_ns{0};
    std::optional<steering::Actuation> steering;
    std::optional<brake::Actuation> brake;
    std::optional<drive::Actuation> drive;
    std::optional<power::CoilCommand> coils;
};
using BmsGateChannel=runtime::LatestSnapshot<std::optional<power::BmsSafetyGate>>;
class AsyncLeafOwner final : public session::ParticipantPort {
public:
    AsyncLeafOwner(transport::Leaf leaf,transport::Clock& clock,transport::RunGate& gate,transport::LeafLink& link,
        runtime::LatestSnapshot<OwnerSensors>& sensors,runtime::LatestSnapshot<OwnerActuation>& output,BmsGateChannel& bms_gate);
    std::uint64_t now_ns() noexcept override { return clock_.now_ns(); }
    session::Preparation prepare(const session::Plan& plan) noexcept override;
    bool initialize(const session::Plan& plan) noexcept override;
    void protect() noexcept override;
    void service() noexcept override;
    bool drop_actual{false},reject_arm{false};
    std::uint32_t epoch() const { return epoch_; }
    std::uint64_t last_body_ns() const { return last_body_; }
    std::size_t received_commands() const { return commands_; }
    bool faulted() const;
    int fault_code() const;
    const std::vector<M4Event>& input_events() const { return input_events_; } // joined only
private:
    using Actor=std::variant<vecu::SteeringActuator,vecu::BrakeActuator,vecu::DriveController,vecu::BmsController,vecu::PowerController>;
    static Actor make_actor(transport::Leaf leaf);
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
};
}  // namespace stratadrive::simulation
