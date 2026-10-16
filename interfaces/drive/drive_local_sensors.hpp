#pragma once

#include "battery_sensor_snapshot.hpp"

namespace stratadrive::drive {
// Actual local inverter feedback, not Central permission or a CAN PowerStatus.
struct HvFeedback { double bus_voltage_v; bool inverter_ready; bool local_fault; };
// Independent physical acquisitions in a separately trusted model epoch. Speed
// is aggregate driven-wheel rad/s, nonnegative in the current forward-only ODD.
struct LocalSensors {
    std::optional<battery::ModelMeasurement<double>> wheel_speed;
    std::optional<battery::ModelMeasurement<HvFeedback>> hv;
};
enum class SensorDecision { Accepted, Unavailable, NotInitialized, ClockError, Identity, Time, Value };
struct SensorResult { SensorDecision wheel_speed, hv; };
}  // namespace stratadrive::drive
