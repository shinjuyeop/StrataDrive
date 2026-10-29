#pragma once
#include "drive_controller.hpp"
namespace stratadrive::vecu {
struct WallDriveControllerConfig : DriveControllerConfig {
    std::uint64_t hv_dependency_age_ns{30000000};
};
class WallDriveController {
public:
    explicit WallDriveController(WallDriveControllerConfig config);
    bool start_session(ActuatorSession session, DriveCommandStartup startup = DriveCommandStartup::Immediate);
    // Trusted coordinator callback only. NonDriving requires continuously fresh
    // Inhibit/limits/local sensors; it never consumes or restamps torque commands.
    bool arm_normal_commands(std::uint64_t now_ns);
    bool select_normal_stop(const ActuatorStopLease& lease, std::uint64_t now_ns);
    bool normal_stop_selected() const { return stop_.active(); }
    can::DriveReceiveResult receive_command(const can::DriveFrame& frame, std::uint64_t now_ns);
    can::BmsReceiveResult receive_limits(const can::BmsFrame& frame, std::uint64_t now_ns);
    can::BmsReceiveResult receive_permission(const can::BmsFrame& frame, std::uint64_t now_ns, const can::BmsParentContext* parent);
    drive::SensorResult observe_local(const drive::LocalSensors& sensors, std::uint64_t now_ns);
    void mark_continuity_lost(std::uint64_t now_ns);
    void request_local_protection(std::uint64_t now_ns); // trusted local port; no EV gate bypass
    bool prepare(std::uint64_t now_ns);
    std::optional<can::DriveFrame> complete(const std::optional<drive::TorqueMeasurement>& sensor, std::uint64_t now_ns);
    void mark_output_rejected(std::uint64_t now_ns) { fail(DriveGateFault::ControlDeadline, now_ns); }
    const drive::Actuation& output() const { return output_; }
    bool execution_gap() const { return execution_gap_; }
    const DriveControlDecision& decision() const { return decision_; }
    std::uint32_t application_epoch() const { return epoch_; }
private:
    struct Inputs {
        std::optional<can::DriveMessage> command;
        std::optional<can::BmsCurrentSample> limits, permission;
        std::optional<battery::ModelMeasurement<double>> speed;
        std::optional<battery::ModelMeasurement<drive::HvFeedback>> hv;
        bool complete{false}, allowed{false};
    };
    bool clock(std::uint64_t now_ns);
    void fail(DriveGateFault fault, std::uint64_t now_ns);
    Inputs monitor(std::uint64_t now_ns);
    void calculate(const Inputs& inputs);
    const WallDriveControllerConfig config_;
    can::DriveReceiver command_;
    can::BmsReceiver limits_, permission_;
    TorqueFeedback feedback_;
    std::optional<drive::TorqueMeasurement> last_torque_;
    StopLeaseState stop_;
    drive::Actuation output_{};
    std::optional<std::uint64_t> prepared_ns_;
    std::optional<Inputs> prepared_inputs_;
    bool execution_gap_{false};
    can::DriveTxState tx_{can::DriveFrameKind::Actual};
    std::optional<battery::ModelMeasurement<double>> speed_, speed_cursor_;
    std::optional<battery::ModelMeasurement<drive::HvFeedback>> hv_, hv_cursor_;
    std::optional<can::BmsParentContext> permission_parent_;
    std::optional<std::uint64_t> last_capability_input_ns_;
    DriveControlDecision decision_{};
    std::uint32_t epoch_{0}, model_epoch_{0}, sequence_{0};
    std::uint64_t enable_ns_{0}, last_observed_ns_{0}, last_tick_ns_{0};
    bool armed_{false}, stopped_{false};
    bool command_monitoring_{true}, startup_inputs_seen_{false};
};
}  // namespace stratadrive::vecu
