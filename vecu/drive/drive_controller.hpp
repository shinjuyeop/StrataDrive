#pragma once

#include "actuator_session.hpp"

#include "drive_receiver.hpp"
#include "drive_local_sensors.hpp"
#include "bms_receiver.hpp"
#include "drive_actuation.hpp"
#include "torque_feedback.hpp"

namespace stratadrive::vecu {
// Functional-SIL fixture parameters; no OEM calibration or motor current control.
struct DriveControllerConfig {
    can::ActuatorValueRange command_nm{-300, 500};
    drive::ResponseConfig response{-200, 300, 0, 1000, 2000, 50000000};
    double max_wheel_speed_rad_s{100}, regen_stop_rad_s{2}, regen_full_rad_s{5};
    double propulsion_mechanical_power_w{20000}, regen_mechanical_power_w{10000};
    // Positive draw envelope: Pdc = T*w/eta + loss_coefficient*T^2 + fixed reserve.
    // Charge envelope uses the upper bound Preturn <= |T|*w, never an assumed recovery efficiency.
    // The fixed reserve includes the fixture's auxiliary/idle loads sharing the pack limit.
    double motoring_efficiency_lower_bound{0.9}, copper_loss_w_per_nm2{0.01}, fixed_power_reserve_w{200};
    double minimum_hv_v{300}, maximum_hv_v{450}, maximum_bms_power_w{100000};
    std::uint64_t period_ns{10000000}, max_tick_gap_ns{30000000};
    std::uint64_t local_age_ns{30000000}, local_skew_ns{20000000};
};
enum class DriveGateFault {
    None, CommandUnavailable, LimitsUnavailable, PermissionUnavailable, PermissionInhibit,
    LocalInputsUnavailable, HvNotReady, BmsProtection, Overspeed, ContinuityLost,
    ClockError, ControlDeadline, SequenceExhausted, TorqueFeedbackUnavailable, UpstreamProtection, CommandsNotArmed
};
enum class DriveCommandStartup { Immediate, NonDriving };
struct DriveControlDecision {
    bool active{false};
    DriveGateFault fault{DriveGateFault::None};
    double selected_target_nm{0};
    std::optional<double> propulsion_limit_nm, regen_limit_nm;
    can::DriveRegenLimitReason regen_reason{can::DriveRegenLimitReason::InputsInvalid};
    std::uint64_t capability_input_time_ns{0};
    bool actual_outside_envelope{false}; // finite response residual, not silently clipped actual
};

// Mandatory EV gate with explicit actuation/sensor ports; no owned plant.
// The legacy DriveActuator remains an
// isolated response fixture. No permissive mode bypass exists in this class.
class DriveController {
public:
    explicit DriveController(DriveControllerConfig config);
    bool start_session(ActuatorSession session, DriveCommandStartup startup = DriveCommandStartup::Immediate);
    // Trusted coordinator callback only. NonDriving requires continuously fresh
    // Inhibit/limits/local sensors; it never consumes or restamps torque commands.
    bool arm_normal_commands(std::uint64_t now_ns);
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
    const DriveControllerConfig config_;
    can::DriveReceiver command_;
    can::BmsReceiver limits_, permission_;
    TorqueFeedback feedback_;
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
