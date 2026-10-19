#pragma once

#include "steering_angle_sensor.hpp"

#include <array>
#include <cstddef>
#include <optional>

namespace stratadrive::vecu {
struct SteeringMonitorConfig {
    double minimum_rad, maximum_rad, minimum_rate_rad_s, maximum_rate_rad_s;
    std::uint64_t delay_ns;
    double tolerance_rad{0.01};
    std::uint64_t confirmation_ns{60000000}, sensor_age_ns{20000000}, sample_gap_ns{30000000};
};
enum class SteeringMonitorFault { None, NotInitialized, SensorUnavailable, SensorInvalid, ClockError, TrackingError };
struct SteeringMonitorDecision {
    SteeringMonitorFault fault{SteeringMonitorFault::NotInitialized};
    std::optional<double> measured_rad, expected_min_rad, expected_max_rad;
    std::optional<std::uint64_t> source_time_ns, violation_since_ns, detected_time_ns;
    double residual_rad{0};
    bool new_measurement{false};
};

// Pure local monitor: only issued targets and independent acquisitions enter.
// No simulation headers, injected fault flags or physical-truth getter.
class SteeringResponseMonitor {
public:
    explicit SteeringResponseMonitor(SteeringMonitorConfig config);
    bool begin(std::uint32_t model_epoch, std::uint64_t enable_ns);
    bool hold(std::uint64_t now_ns); // cancel delayed demands without resetting sensor identity/faults
    bool set_target(double bounded_angle_rad, std::uint64_t now_ns);
    const SteeringMonitorDecision& observe(const std::optional<steering::AngleMeasurement>& sensor,
        std::uint64_t now_ns, bool tracking_enabled);
    const SteeringMonitorDecision& decision() const { return decision_; }
private:
    struct Demand { double angle; std::uint64_t due_ns; };
    void latch(SteeringMonitorFault fault, std::uint64_t now_ns);
    void predict(std::uint64_t source_ns);
    void move(std::uint64_t elapsed_ns);
    const SteeringMonitorConfig config_;
    std::array<Demand, 128> pending_{};
    std::size_t head_{0}, size_{0};
    double lower_{0}, upper_{0}, target_{0};
    std::optional<double> staged_;
    std::optional<steering::AngleMeasurement> previous_;
    SteeringMonitorDecision decision_{};
    std::uint32_t model_epoch_{0};
    std::uint64_t enable_ns_{0}, last_observed_ns_{0}, cursor_ns_{0};
    bool seeded_{false};
};
}  // namespace stratadrive::vecu
