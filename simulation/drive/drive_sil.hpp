#pragma once

#include "drive_controller.hpp"
#include "drive_sil_plant.hpp"

namespace stratadrive::simulation {
// SIL runner: ECU phases, actuation application and physics have separate owners.
class DriveSil {
public:
    explicit DriveSil(const vecu::DriveControllerConfig& config) : ecu_(config), plant_(config.response) {}
    bool start_session(std::uint32_t epoch, std::uint32_t model_epoch, std::uint64_t enable_ns,
        vecu::DriveCommandStartup startup = vecu::DriveCommandStartup::Immediate);
    bool arm_normal_commands(std::uint64_t now_ns) { return ecu_.arm_normal_commands(now_ns); }
    can::DriveReceiveResult receive_command(const can::DriveFrame& frame, std::uint64_t now_ns);
    can::BmsReceiveResult receive_limits(const can::BmsFrame& frame, std::uint64_t now_ns);
    can::BmsReceiveResult receive_permission(const can::BmsFrame& frame, std::uint64_t now_ns, const can::BmsParentContext* parent);
    drive::SensorResult observe_local(const drive::LocalSensors& sensors, std::uint64_t now_ns);
    const vecu::DriveControlDecision& decision() const { return ecu_.decision(); }
    void mark_continuity_lost(std::uint64_t now_ns);
    std::optional<can::DriveFrame> tick(std::uint64_t now_ns);
    double actual_torque_nm() const { return plant_.actual_nm(); } // diagnostics only
private:
    vecu::DriveController ecu_;
    DriveSilPlant plant_;
};
} // namespace stratadrive::simulation
