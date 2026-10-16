#pragma once

#include "actuator_session.hpp"

#include "drive_receiver.hpp"
#include "drive_actuation.hpp"
#include "torque_feedback.hpp"

namespace stratadrive::vecu {
struct DriveActuatorConfig {
    can::ActuatorValueRange command_nm;
    drive::ResponseConfig response;
    std::uint64_t period_ns{10000000};
    std::uint64_t max_tick_gap_ns{30000000};
    std::uint64_t max_source_age_ns{30000000};
    std::uint64_t timeout_ns{80000000};
};
enum class DriveFault { None, CommandUnavailable, ContinuityLost, ClockError, ControlDeadline, TorqueFeedbackUnavailable };

// Isolated torque-response component, not a complete EV Drive ECU runtime.
// BMS constraints, drive permission, local HV and speed/capability are NOT wired.
// Only the explicit model fixture uses this adapter; no normal-drive readiness
// or available regen capability is inferred from accepting a torque command.
class DriveActuator {
public:
    explicit DriveActuator(DriveActuatorConfig config);
    bool start_session(ActuatorSession session);
    can::DriveReceiveResult receive(const can::DriveFrame& frame, std::uint64_t now_ns);
    void mark_continuity_lost(std::uint64_t now_ns);
    bool prepare(std::uint64_t now_ns);
    std::optional<can::DriveFrame> complete(const std::optional<drive::TorqueMeasurement>& sensor, std::uint64_t now_ns);
    void mark_output_rejected(std::uint64_t now_ns) { fail(DriveFault::ControlDeadline, now_ns); }
    const drive::Actuation& output() const { return output_; }
    bool execution_gap() const { return execution_gap_; }
    DriveFault fault() const { return fault_; }
    std::optional<can::DriveMessage> current_sample(std::uint64_t now_ns) {
        return fault_ == DriveFault::None ? receiver_.current_sample(now_ns) : std::nullopt;
    }
    const can::DriveReceiver& receiver() const { return receiver_; }
private:
    void fail(DriveFault fault, std::uint64_t now_ns);
    const DriveActuatorConfig config_;
    can::DriveReceiver receiver_;
    TorqueFeedback feedback_;
    drive::Actuation output_{};
    std::optional<std::uint64_t> prepared_ns_;
    bool execution_gap_{false};
    can::DriveTxState tx_{can::DriveFrameKind::Actual};
    std::uint32_t epoch_{0}, sequence_{0};
    std::uint64_t last_tick_ns_{0};
    bool sequence_exhausted_{false};
    DriveFault fault_{DriveFault::None};
};
}  // namespace stratadrive::vecu
