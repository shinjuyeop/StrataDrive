#pragma once
#include "battery_sensor_snapshot.hpp"
#include "power_sensor_snapshot.hpp"

namespace stratadrive::simulation {
// Logical SIL sensor faults. Only values in the consuming ECU's input copy
// change; acquisition identity, source/dependency clocks and plant stay intact.
enum class PowerSensorFault { None, ChargerConnected, ContactorMismatch, BusLow };
// Lifecycle fixtures select these on the owner thread at their declared phase;
// they preserve acquisition metadata and never alter the shared physical model.
enum class PowerLifecycleSensorFault { None, PrechargeStall, StartupEnergized, CurrentHeld, DischargeHeld };
inline void inject_power_lifecycle(power::SensorSnapshot& s,PowerLifecycleSensorFault fault) {
    if(fault==PowerLifecycleSensorFault::PrechargeStall) s.bus_voltage_v=0;
    if(fault==PowerLifecycleSensorFault::StartupEnergized && s.contactors) s.contactors->positive=true;
    if(fault==PowerLifecycleSensorFault::CurrentHeld) s.pack_current_a=20;
    if(fault==PowerLifecycleSensorFault::DischargeHeld) s.bus_voltage_v=100;
}
inline void inject_bms_trips(battery::SensorSnapshot& s,unsigned mask) {
    if(mask&1U) s.cell_voltage->value.minimum=2.7;
    if(mask&2U) s.cell_voltage->value.maximum=4.3;
    if(mask&4U) { s.electrical->value.voltage_v=279; s.cell_voltage->value={2.805,2.81}; }
    if(mask&8U) { s.electrical->value.voltage_v=426; if(!(mask&2U)) s.cell_voltage->value={4.2,4.24}; }
    if(mask&16U) s.cell_temperature->value.minimum=-35;
    if(mask&32U) s.cell_temperature->value.maximum=65;
    if(mask&64U) s.electrical->value.current_a=-110;
    if(mask&128U) s.electrical->value.current_a=260;
}
inline void inject_power_sensor(power::SensorSnapshot& s,PowerSensorFault fault) {
    if(fault==PowerSensorFault::ChargerConnected) s.conditions.charger_connected=true;
    if(fault==PowerSensorFault::ContactorMismatch && s.contactors) s.contactors->precharge=true;
    if(fault==PowerSensorFault::BusLow) s.bus_voltage_v=200;
}
} // namespace stratadrive::simulation
