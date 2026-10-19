#pragma once

#include "brake_pressure_sensor.hpp"

#include <array>
#include <cstddef>
#include <optional>

namespace stratadrive::vecu {
struct BrakeMonitorConfig {
    double maximum_pa, minimum_rise_pa_s, maximum_rise_pa_s, minimum_fall_pa_s, maximum_fall_pa_s;
    std::uint64_t delay_ns;
    double tolerance_pa{25000};
    std::uint64_t confirmation_ns{60000000}, sensor_age_ns{20000000}, sample_gap_ns{30000000};
};
enum class BrakeMonitorFault { None, NotInitialized, SensorUnavailable, SensorInvalid, ClockError, ResponseError };
struct BrakeMonitorDecision {
    BrakeMonitorFault fault{BrakeMonitorFault::NotInitialized};
    std::optional<double> measured_pa, expected_min_pa, expected_max_pa;
    std::optional<std::uint64_t> source_time_ns, violation_since_ns, detected_time_ns;
    double residual_pa{0};
    bool new_measurement{false};
};

// Pure local monitor: only issued targets and independent acquisitions enter.
// No simulation headers, injected fault flags or physical-truth getter.
class BrakeResponseMonitor {
public:
    explicit BrakeResponseMonitor(BrakeMonitorConfig config);
    bool begin(std::uint32_t model_epoch, std::uint64_t enable_ns);
    bool hold(std::uint64_t now_ns); // cancel delayed demands without resetting sensor identity/faults
    bool set_target(double bounded_pressure_pa, std::uint64_t now_ns);
    const BrakeMonitorDecision& observe(const std::optional<brake::PressureMeasurement>& sensor,
        std::uint64_t now_ns, bool tracking_enabled);
    const BrakeMonitorDecision& decision() const { return decision_; }
private:
    struct Demand { double pressure; std::uint64_t due_ns; };
    void latch(BrakeMonitorFault fault, std::uint64_t now_ns);
    void predict(std::uint64_t source_ns);
    void move(std::uint64_t elapsed_ns);
    const BrakeMonitorConfig config_;
    std::array<Demand, 128> pending_{};
    std::size_t head_{0}, size_{0};
    double lower_{0}, upper_{0}, target_{0};
    std::optional<double> staged_;
    std::optional<brake::PressureMeasurement> previous_;
    BrakeMonitorDecision decision_{};
    std::uint32_t model_epoch_{0};
    std::uint64_t enable_ns_{0}, last_observed_ns_{0}, cursor_ns_{0};
    bool seeded_{false};
};
}  // namespace stratadrive::vecu
