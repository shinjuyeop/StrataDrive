#pragma once

#include "steering_receiver.hpp"
#include "steering_response.hpp"
#include "steering_response_monitor.hpp"

#include <cstdint>
#include <optional>

namespace stratadrive::vecu {
struct SteeringActuatorConfig {
    double command_min_rad;
    double command_max_rad;
    double angle_min_rad;
    double angle_max_rad;
    double initial_angle_rad;
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
    SensorUnavailable, SensorInvalid, TrackingError, PhysicalModelError };

// Single-owner functional SIL composition, not an OS task/production SWC.
// The plant and local sensor monitor are separate modules; fault injection
// enters the plant/capture only. The monitor never sees physical truth or jam flags.
class SteeringActuator {
public:
    explicit SteeringActuator(SteeringActuatorConfig config);
    bool start_session(std::uint32_t epoch, std::uint64_t enable_ns);
    can::SteeringReceiveResult receive(const can::SteeringFrame& frame, std::uint64_t now_ns);
    void mark_continuity_lost(std::uint64_t now_ns);
    // At most one publication per period. A missed control deadline holds the
    // angle rather than catching up physics. No output with an untrusted clock.
    // Physical injection covers the elapsed interval ending at now_ns. Sensor
    // action/override applies to the end acquisition; explicit SIL fixture inputs.
    std::optional<can::SteeringFrame> tick(std::uint64_t now_ns, simulation::SteeringResponseInjection injection = {},
        simulation::SteeringSensorAction sensor_action = simulation::SteeringSensorAction::Acquire,
        std::optional<double> sensed_angle_override = std::nullopt);
    double actual_angle_rad() const { return response_.actual_angle_rad(); } // diagnostics, never sensor fallback
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
    simulation::SteeringResponse response_;
    SteeringResponseMonitor monitor_;
    std::uint32_t epoch_{0}, sequence_{0};
    std::uint64_t last_tick_ns_{0};
    bool sequence_exhausted_{false};
    SteeringFault fault_{SteeringFault::None};
};
}  // namespace stratadrive::vecu
