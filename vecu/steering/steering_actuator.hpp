#pragma once

#include "actuator_session.hpp"

#include "steering_receiver.hpp"
#include "steering_actuation.hpp"
#include "steering_response_monitor.hpp"

#include <cstdint>
#include <optional>

namespace stratadrive::vecu {
struct SteeringActuatorConfig {
    double command_min_rad;
    double command_max_rad;
    double angle_min_rad;
    double angle_max_rad;
    double initial_angle_rad; // fixture metadata; only the SIL plant applies it
    double max_rate_rad_s;
    std::uint64_t delay_ns;
    std::uint64_t period_ns{10000000};
    std::uint64_t max_tick_gap_ns{30000000};
    std::uint64_t max_source_age_ns{30000000};
    std::uint64_t timeout_ns{80000000};
    double healthy_min_rate_fraction{0.8}, healthy_max_rate_fraction{1.2}, tracking_tolerance_rad{0.01};
    std::uint64_t tracking_confirmation_ns{60000000}, sensor_age_ns{20000000};
};
enum class SteeringFault { None, CommandUnavailable, ContinuityLost, ClockError, ControlDeadline,
    SensorUnavailable, SensorInvalid, TrackingError, PhysicalModelError, UpstreamProtection };

// ECU logic only: receiver, monitor, selected output and CAN publication.
// prepare/complete delimit one externally clocked job. Physics and acquisition
// run outside this object; use simulation's SIL runner for the legacy fixture.
class SteeringActuator {
public:
    explicit SteeringActuator(SteeringActuatorConfig config);
    bool start_session(ActuatorSession session);
    can::SteeringReceiveResult receive(const can::SteeringFrame& frame, std::uint64_t now_ns);
    void mark_continuity_lost(std::uint64_t now_ns);
    void request_local_protection(std::uint64_t now_ns); // trusted local port, not a normal CAN command
    // prepare checks clock/period/communication before external actuation.
    // complete accepts a sensor snapshot for that same time, then selects the
    // next output. No physics, sensor generation or implicit 0 fallback here.
    bool prepare(std::uint64_t now_ns);
    std::optional<can::SteeringFrame> complete(const std::optional<steering::AngleMeasurement>& sensor, std::uint64_t now_ns);
    void mark_io_error(std::uint64_t now_ns);
    void mark_output_rejected(std::uint64_t now_ns);
    const steering::Actuation& output() const { return output_; }
    bool execution_gap() const { return execution_gap_; }
    SteeringFault fault() const { return fault_; }
    const SteeringMonitorDecision& monitor_decision() const { return monitor_.decision(); }
    // Current command snapshot for ingress diagnostics; not actuator feedback.
    std::optional<can::SteeringMessage> current_sample(std::uint64_t now_ns) {
        return fault_ == SteeringFault::None ? receiver_.current_sample(now_ns) : std::nullopt;
    }
    const can::SteeringReceiver& receiver() const { return receiver_; }
private:
    void fail(SteeringFault fault, std::uint64_t now_ns);
    const SteeringActuatorConfig config_;
    can::SteeringReceiver receiver_;
    can::SteeringTxState tx_{can::SteeringFrameKind::Actual};
    SteeringResponseMonitor monitor_;
    std::uint32_t epoch_{0}, sequence_{0};
    std::uint64_t last_tick_ns_{0};
    bool sequence_exhausted_{false};
    steering::Actuation output_{};
    std::optional<std::uint64_t> prepared_ns_;
    bool execution_gap_{false};
    SteeringFault fault_{SteeringFault::None};
};
}  // namespace stratadrive::vecu
