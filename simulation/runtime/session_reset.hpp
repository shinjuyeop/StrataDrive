#pragma once
#include "drive_actuation.hpp"
#include "power_sensor_snapshot.hpp"

namespace stratadrive::simulation {
struct SessionResetEvidence {
    std::optional<battery::ModelMeasurement<double>> wheel_speed_rad_s;
    std::optional<drive::TorqueMeasurement> torque;
    std::optional<power::SensorSnapshot> power;
};
// Functional SIL reset preconditions, not production vehicle calibration.
// Each acquisition retains its own source/dependency time and model identity.
bool session_reset_safe(const SessionResetEvidence& evidence,std::uint32_t model_epoch,std::uint64_t now_ns);
} // namespace stratadrive::simulation
