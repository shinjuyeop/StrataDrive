#pragma once

#include "drive_energy_model.hpp"
#include "power_model.hpp"

namespace stratadrive::simulation {
struct EvElectricalEnvironment {
    double auxiliary_current_a{0}; // actual pack-side DC current, independent of the HV contacts
    bool inverter_enabled{false}, lv_available{true}, interlock_closed{true}, isolation_ok{true};
    bool charger_connected{false}, power_fault{false};
};
struct EvPowerInputs {
    std::optional<ModelMeasurement<double>> actual_torque_nm, wheel_speed_rad_s;
    std::optional<ModelMeasurement<EvElectricalEnvironment>> electrical;
};
struct EvPowerInterval {
    std::uint64_t begin_ns, end_ns;
    EvPowerInputs inputs;
    power::CoilCommand coils; // applied physical output at begin, constant until end
};
// Whole-interval mechanical integration, NOT an acquired wheel-speed sample.
// The physical motion owner supplies one result with source=end and original
// oldest dependency. Scalar input acquisitions retain their original metadata.
struct IntegratedMotorWork {
    ModelIdentity identity{};
    std::uint64_t begin_ns{0}, end_ns{0}, input_time_ns{0};
    double mechanical_j{0};
};
enum class EvPowerFault { None, NotInitialized, Timing, Clock, Inputs, Identity, Stale, Skew, InverterOff, Circuit, Battery, EnergyBalance };
struct EvPowerStep {
    EvPowerFault fault;
    PowerModelFault circuit_fault{PowerModelFault::None};
    BatteryFault battery_fault{BatteryFault::None};
    double boundary_excess_j{0};
};
struct EvPowerState {
    ModelIdentity identity{};
    double mechanical_w{0}, motor_loss_w{0}, bus_load_w{0};
    double mechanical_j{0}, motor_loss_j{0}, precharge_loss_j{0}, main_loss_j{0}, discharge_loss_j{0};
    double initial_capacitor_j{0}, capacitor_j{0}, balance_error_j{0};
};

// Single-owner physical composition. BatteryModel owns chemical energy/heat;
// PowerModel owns capacitor/contact state. Both commit together or neither does.
// No Central grant, CAN, speed dynamics or ECU restart is synthesized here.
class EvPowerModel {
public:
    EvPowerModel(DriveEnergyConfig drive, BatteryConfig battery, PowerModelConfig circuit);
    bool initialize(BatteryInitialization initial, double bus_voltage_v, power::ContactorPositions contacts = {});
    EvPowerStep step(const EvPowerInterval& interval, const PowerFaultInjection& injection = {}, const BatterySensorCapture& capture = {});
    EvPowerStep step_integrated_motion(const EvPowerInterval& interval, const IntegratedMotorWork& work,
        const PowerFaultInjection& injection = {}, const BatterySensorCapture& capture = {});
    const BatteryObservation& battery_observation() const { return battery_observation_; }
    const std::optional<power::SensorSnapshot>& power_observation() const { return power_observation_; }
    const BatteryState& battery_state() const { return battery_->diagnostic_state(); }
    const PowerPhysicalState& power_state() const { return circuit_->diagnostic_state(); }
    const EvPowerState& diagnostic_state() const { return state_; }
    const std::optional<PowerCircuitFlow>& last_flow() const { return flow_; } // internal physics diagnostics, not an ECU sensor bypass
    EvPowerFault fault() const { return result_.fault; }
private:
    EvPowerStep step_impl(const EvPowerInterval&, const IntegratedMotorWork*, const PowerFaultInjection&, const BatterySensorCapture&);
    struct Sum {
        double value{0}, correction{0};
        void add(double increment);
    };
    EvPowerStep fail(EvPowerFault fault);
    const DriveEnergyConfig drive_config_;
    const BatteryConfig battery_config_;
    const PowerModelConfig circuit_config_;
    std::optional<BatteryModel> battery_;
    std::optional<PowerModel> circuit_;
    BatteryObservation battery_observation_{};
    std::optional<power::SensorSnapshot> power_observation_;
    std::optional<PowerCircuitFlow> flow_;
    std::optional<EvPowerInputs> previous_;
    std::array<Sum, 5> totals_{};
    EvPowerState state_{};
    EvPowerStep result_{EvPowerFault::NotInitialized};
    std::uint64_t initialization_ns_{0}, last_observed_ns_{0};
};
}  // namespace stratadrive::simulation
