#pragma once

#include "brake_actuator.hpp"
#include "brake_pressure_response.hpp"

namespace stratadrive::simulation {
// Legacy single-owner SIL runner. This is simulation composition, not an ECU
// runnable: physics/acquisition calls stay outside the vecu library.
class BrakeSil {
public:
    explicit BrakeSil(const vecu::BrakeActuatorConfig& config) : ecu_(config), plant_({config.max_pressure_pa, config.initial_pressure_pa, config.rise_rate_pa_s, config.fall_rate_pa_s, config.delay_ns}) {}
    bool start_session(std::uint32_t epoch, std::uint64_t enable_ns);
    can::BrakeReceiveResult receive(const can::BrakeFrame& frame, std::uint64_t now_ns);
    void mark_continuity_lost(std::uint64_t now_ns);
    std::optional<can::BrakeFrame> tick(std::uint64_t now_ns, const BrakePressureResponseInjection& injection = {},
        BrakeSensorAction action = BrakeSensorAction::Acquire, std::optional<double> sensed_override = std::nullopt);
    double actual_pressure_pa() const { return plant_.actual_pressure_pa(); } // diagnostics only
    vecu::BrakeFault fault() const { return ecu_.fault(); }
    const vecu::BrakeMonitorDecision& monitor_decision() const { return ecu_.monitor_decision(); }
    std::optional<bool> protection_floor_observed() const { return ecu_.protection_floor_observed(); }
    std::optional<can::BrakeMessage> current_sample(std::uint64_t now_ns) { return ecu_.current_sample(now_ns); }
    const can::BrakeReceiver& receiver() const { return ecu_.receiver(); }
private:
    bool apply(std::uint64_t now_ns);
    vecu::BrakeActuator ecu_;
    BrakePressureResponse plant_;
    std::optional<brake::Actuation> applied_;
};
} // namespace stratadrive::simulation
