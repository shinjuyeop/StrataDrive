#pragma once

#include "drive_actuator.hpp"
#include "drive_sil_plant.hpp"

namespace stratadrive::simulation {
// SIL runner: ECU phases, actuation application and physics have separate owners.
class DriveActuatorSil {
public:
    explicit DriveActuatorSil(const vecu::DriveActuatorConfig& config) : ecu_(config), plant_(config.response) {}
    bool start_session(std::uint32_t epoch, std::uint64_t enable_ns);
    can::DriveReceiveResult receive(const can::DriveFrame& frame, std::uint64_t now_ns);
    vecu::DriveFault fault() const { return ecu_.fault(); }
    std::optional<can::DriveMessage> current_sample(std::uint64_t now_ns) { return ecu_.current_sample(now_ns); }
    const can::DriveReceiver& receiver() const { return ecu_.receiver(); }
    void mark_continuity_lost(std::uint64_t now_ns);
    std::optional<can::DriveFrame> tick(std::uint64_t now_ns);
    double actual_torque_nm() const { return plant_.actual_nm(); } // diagnostics only
private:
    vecu::DriveActuator ecu_;
    DriveSilPlant plant_;
};
} // namespace stratadrive::simulation
