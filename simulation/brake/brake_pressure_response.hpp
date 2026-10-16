#pragma once

#include "brake_pressure_sensor.hpp"

#include <array>
#include <cstddef>
#include <optional>

namespace stratadrive::simulation {
struct BrakePressureResponseConfig {
    double maximum_pa, initial_pa, rise_rate_pa_s, fall_rate_pa_s;
    std::uint64_t delay_ns;
    std::uint32_t model_epoch{1};
};
struct BrakePressureResponseInjection {
    bool stuck{false};
    double rise_rate_scale{1}, fall_rate_scale{1}; // physical fault/variation, applied over the declared elapsed interval
};
enum class BrakeSensorAction { Acquire, Hold, Invalidate };

// Functional SIL plant. It knows neither ECU faults nor tracking thresholds.
class BrakePressureResponse {
public:
    explicit BrakePressureResponse(BrakePressureResponseConfig config);
    bool begin(std::uint64_t now_ns); // cancel commands, preserve physical pressure and sensor sequence
    bool set_target(double pressure_pa, std::uint64_t now_ns);
    bool advance(std::uint64_t now_ns, const BrakePressureResponseInjection& injection = {});
    // Functional SIL protection primitive: cancel normal demands, build to the
    // floor, never release higher pressure. Injection still applies to physics.
    bool request_protection(double floor_pa, std::uint64_t now_ns);
    bool skip_to(std::uint64_t now_ns); // no catch-up over an unobserved interval
    std::optional<brake::PressureMeasurement> capture(BrakeSensorAction action = BrakeSensorAction::Acquire,
        std::optional<double> sensed_pressure_override = std::nullopt);
    double actual_pressure_pa() const { return actual_; } // diagnostics only
    std::uint32_t model_epoch() const { return config_.model_epoch; }
private:
    struct Demand { double pressure; std::uint64_t due_ns; };
    void move(std::uint64_t elapsed_ns, const BrakePressureResponseInjection& injection);
    const BrakePressureResponseConfig config_;
    std::array<Demand, 128> pending_{};
    std::size_t head_{0}, size_{0};
    double actual_, target_;
    std::optional<double> staged_;
    std::optional<brake::PressureMeasurement> sensor_;
    std::optional<std::uint64_t> last_acquisition_ns_;
    std::uint64_t last_step_ns_{0}, last_observed_ns_{0}, sensor_sequence_{0};
    bool initialized_{false}, protecting_{false};
};
}  // namespace stratadrive::simulation
