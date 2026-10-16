#pragma once

#include "power_sensor_snapshot.hpp"
#include "battery_model.hpp"

#include <array>

namespace stratadrive::simulation {
struct PowerModelConfig {
    double capacitance_f, precharge_resistance_ohm, main_resistance_ohm, discharge_resistance_ohm;
    double maximum_voltage_v, maximum_abs_load_current_a;
    std::uint64_t contactor_delay_ns{20000000}, max_step_ns{20000000}, max_input_age_ns{50000000};
    std::uint64_t integration_step_ns{50000}; // constant-power mode, also bounded by the electrical time constant
};
struct PowerEnvironment {
    double pack_voltage_v, bus_load_current_a; // actual signed load, +draw/-return; valid zero is explicit
    bool lv_available, interlock_closed, isolation_ok, charger_connected, power_fault;
    // Coupled mode: pack_voltage_v is constant OCV, Rint is inside this circuit.
    // Pack-side auxiliary is actual held DC current; inverter power is held at the bus.
    double source_resistance_ohm{0}, auxiliary_current_a{0};
    std::optional<double> bus_load_power_w{}; // null preserves the standalone constant-current fixture
};
enum class ContactorFailure { None, StuckOpen, StuckClosed };
struct PowerFaultInjection {
    std::array<ContactorFailure, 3> contactors{}; // positive, negative, precharge
    bool hold_sensors{false};
    bool invalidate_pack{false}, invalidate_bus{false}, invalidate_current{false};
    bool invalidate_contactors{false}, invalidate_conditions{false};
};
struct PowerInterval {
    std::uint64_t begin_ns, end_ns;
    battery::ModelMeasurement<PowerEnvironment> environment;
    power::CoilCommand coils; // applied at begin, constant until end; never retroactive
};
enum class PowerModelFault { None, NotInitialized, Timing, Clock, Input, Identity, Stale, Electrical, SequenceExhausted };
struct PowerPhysicalState {
    battery::ModelIdentity identity{};
    double bus_voltage_v{0}, pack_current_a{0};
    power::ContactorPositions contactors{};
};
struct PowerCircuitFlow {
    IntegratedBatteryFlow battery;
    double load_j{0}, precharge_loss_j{0}, main_loss_j{0}, discharge_loss_j{0}, capacitor_delta_j{0};
};
// DC-link/contactor functional plant. No power lifecycle controller or battery
// SOC integration. Actual inverter load and pack voltage are explicit inputs.
class PowerModel {
public:
    explicit PowerModel(PowerModelConfig config);
    bool initialize(battery::ModelIdentity scenario, double initial_bus_voltage_v,
                    power::ContactorPositions initial_contactors = {});
    PowerModelFault step(const PowerInterval& interval, const PowerFaultInjection& injection = {});
    const std::optional<power::SensorSnapshot>& observation() const { return observation_; }
    const PowerPhysicalState& diagnostic_state() const { return state_; }
    PowerModelFault fault() const { return fault_; }
    const std::optional<PowerCircuitFlow>& integrated_flow() const { return flow_; }
private:
    struct Contact { bool actual{false}, target{false}; std::optional<std::uint64_t> due; };
    PowerModelFault fail(PowerModelFault fault);
    const PowerModelConfig config_;
    std::array<Contact, 3> contacts_{};
    PowerPhysicalState state_{};
    std::optional<power::SensorSnapshot> observation_;
    std::optional<PowerCircuitFlow> flow_;
    std::optional<battery::ModelMeasurement<PowerEnvironment>> previous_;
    PowerModelFault fault_{PowerModelFault::NotInitialized};
    std::uint64_t initialization_ns_{0}, last_observed_ns_{0};
};
}  // namespace stratadrive::simulation
