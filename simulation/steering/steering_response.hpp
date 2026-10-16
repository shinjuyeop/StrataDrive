#pragma once

#include "steering_angle_sensor.hpp"

#include <array>
#include <cstddef>
#include <optional>

namespace stratadrive::simulation {
struct SteeringResponseConfig {
    double minimum_rad, maximum_rad, initial_rad, rate_rad_s;
    std::uint64_t delay_ns;
    std::uint32_t model_epoch{1};
};
struct SteeringResponseInjection {
    bool jammed{false};
    double rate_scale{1}; // physical fault/variation, applied over the declared elapsed interval
};
enum class SteeringSensorAction { Acquire, Hold, Invalidate };

// Functional SIL plant. It knows neither ECU faults nor tracking thresholds.
class SteeringResponse {
public:
    explicit SteeringResponse(SteeringResponseConfig config);
    bool begin(std::uint64_t now_ns); // cancel commands, preserve physical angle and sensor sequence
    bool set_target(double angle_rad, std::uint64_t now_ns);
    bool advance(std::uint64_t now_ns, SteeringResponseInjection injection = {});
    bool hold(std::uint64_t now_ns); // disable modeled motion, discard pending targets; no catch-up
    std::optional<steering::AngleMeasurement> capture(SteeringSensorAction action = SteeringSensorAction::Acquire,
        std::optional<double> sensed_angle_override = std::nullopt);
    double actual_angle_rad() const { return actual_; } // diagnostics only
    std::uint32_t model_epoch() const { return config_.model_epoch; }
private:
    struct Demand { double angle; std::uint64_t due_ns; };
    void move(std::uint64_t elapsed_ns, SteeringResponseInjection injection);
    const SteeringResponseConfig config_;
    std::array<Demand, 128> pending_{};
    std::size_t head_{0}, size_{0};
    double actual_, target_;
    std::optional<double> staged_;
    std::optional<steering::AngleMeasurement> sensor_;
    std::optional<std::uint64_t> last_acquisition_ns_;
    std::uint64_t last_step_ns_{0}, last_observed_ns_{0}, sensor_sequence_{0};
    bool initialized_{false};
};
}  // namespace stratadrive::simulation
