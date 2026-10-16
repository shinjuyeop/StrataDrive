#pragma once

#include "battery_sensor_snapshot.hpp"

namespace stratadrive::power {
struct ContactorPositions { bool positive{false}, negative{false}, precharge{false}; };
struct CoilCommand {
    ContactorPositions close{};
    bool discharge_bus{false};
};
struct Conditions {
    std::optional<bool> lv_available, interlock_closed, isolation_ok, charger_connected, power_fault;
};
// One atomic physical acquisition. Unavailable fields stay unknown; holding this
// acquisition must preserve its entire identity, dependency time and values.
struct SensorSnapshot {
    battery::ModelIdentity identity{};
    std::uint64_t input_time_ns{0};
    std::optional<double> pack_voltage_v, bus_voltage_v, pack_current_a;
    std::optional<ContactorPositions> contactors;
    Conditions conditions{};
};
// Local BMS -> power-control port, not a vehicle DrivePermission or CAN bypass.
// A continuing physical model is mapped separately at trusted application INIT.
struct BmsSafetyGate {
    std::uint32_t application_epoch{0}, sequence{0};
    std::uint64_t source_time_ns{0}, input_time_ns{0};
    std::optional<bool> inhibit;
};
}  // namespace stratadrive::power
