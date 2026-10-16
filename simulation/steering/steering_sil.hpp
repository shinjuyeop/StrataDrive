#pragma once

#include "steering_actuator.hpp"
#include "steering_response.hpp"

namespace stratadrive::simulation {
// Legacy single-owner SIL runner. This is simulation composition, not an ECU
// runnable: physics/acquisition calls stay outside the vecu library.
class SteeringSil {
public:
    explicit SteeringSil(const vecu::SteeringActuatorConfig& config) : ecu_(config), plant_({config.angle_min_rad, config.angle_max_rad, config.initial_angle_rad, config.max_rate_rad_s, config.delay_ns}) {}
    bool start_session(std::uint32_t epoch, std::uint64_t enable_ns);
    can::SteeringReceiveResult receive(const can::SteeringFrame& frame, std::uint64_t now_ns);
    void mark_continuity_lost(std::uint64_t now_ns);
    std::optional<can::SteeringFrame> tick(std::uint64_t now_ns, const SteeringResponseInjection& injection = {},
        SteeringSensorAction action = SteeringSensorAction::Acquire, std::optional<double> sensed_override = std::nullopt);
    double actual_angle_rad() const { return plant_.actual_angle_rad(); } // diagnostics only
    vecu::SteeringFault fault() const { return ecu_.fault(); }
    const vecu::SteeringMonitorDecision& monitor_decision() const { return ecu_.monitor_decision(); }
    std::optional<can::SteeringMessage> current_sample(std::uint64_t now_ns) { return ecu_.current_sample(now_ns); }
    const can::SteeringReceiver& receiver() const { return ecu_.receiver(); }
private:
    bool apply(std::uint64_t now_ns);
    vecu::SteeringActuator ecu_;
    SteeringResponse plant_;
    std::optional<steering::Actuation> applied_;
};
} // namespace stratadrive::simulation
