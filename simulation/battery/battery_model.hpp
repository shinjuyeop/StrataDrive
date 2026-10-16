#pragma once

#include "battery_sensor_snapshot.hpp"

#include <array>
#include <cstdint>
#include <optional>

namespace stratadrive::simulation {
using battery::ModelIdentity;
using battery::ElectricalPair;
using battery::CellExtrema;
using battery::ModelMeasurement;
struct BatteryConfig {
    double capacity_j;
    double open_circuit_voltage_v; // constant OCV: energy fraction equals charge fraction
    double resistance_ohm;
    double thermal_capacity_j_k;
    double cooling_w_k;
    double ambient_temperature_c;
    std::uint32_t series_cells;
    double cell_voltage_half_spread_v;
    double cell_temperature_half_spread_c;
    double max_abs_power_w; // each DC component and their terminal sum
    std::uint64_t max_step_ns{40000000};
    std::uint64_t max_input_age_ns{50000000};
};
struct BatteryInitialization {
    std::uint32_t epoch;
    std::uint64_t time_ns;
    double soc;
    double temperature_c;
};
// Actual traction-branch DC power on the battery side of the inverter. Add the
// separate auxiliary load to obtain terminal power. Motor/inverter conversion
// belongs upstream; this plant adds only battery resistance loss internally.
struct ActualBatteryPower {
    ModelIdentity identity{};
    std::uint64_t input_time_ns{0}; // oldest dependency; never refreshed by caching
    std::optional<double> traction_dc_w; // +draw, -electrical return; no Command/limit input
    std::optional<double> auxiliary_w;   // nonnegative, valid zero differs from unknown
};
struct BatteryInterval {
    std::uint64_t begin_ns{0}, end_ns{0};
    ActualBatteryPower power{}; // declared constant over this entire interval
};
// Whole-interval circuit integration, not an end-point sample held backwards.
// Source=end, dependency<=begin. Rint and OCV must match the circuit solver.
struct IntegratedBatteryFlow {
    ModelIdentity identity{};
    std::uint64_t input_time_ns{0};
    double charge_c{0}, current_squared_a2s{0}, end_current_a{0};
    double drawn_dc_j{0}, received_dc_j{0}, auxiliary_j{0};
    double peak_abs_terminal_w{0}, peak_abs_branch_w{0}, peak_auxiliary_w{0};
};
struct BatteryElectricalInterval {
    std::uint64_t begin_ns, end_ns;
    IntegratedBatteryFlow flow;
};
enum class SensorAction { Acquire, Hold, Invalidate };
struct BatterySensorCapture {
    SensorAction soc{SensorAction::Acquire};
    SensorAction electrical{SensorAction::Acquire};
    SensorAction temperature{SensorAction::Acquire};
    SensorAction cell_voltage{SensorAction::Acquire};
    SensorAction cell_temperature{SensorAction::Acquire};
    std::optional<CellExtrema> voltage_override;
    std::optional<CellExtrema> temperature_override;
};
enum class BatteryFault {
    None, NotInitialized, PowerUnavailable, InvalidInput, InputStale, IdentityError,
    ClockError, TimingError, ElectricalInfeasible, CapacityViolation, NumericalError, SequenceExhausted
};
struct BatteryObservation : battery::SensorSnapshot {
    BatteryFault fault{BatteryFault::NotInitialized};
};
struct BatteryState {
    ModelIdentity identity{};
    double initial_energy_j{0}, energy_j{0}, soc{0}, temperature_c{0};
    double drawn_dc_j{0}, received_dc_j{0}, auxiliary_j{0}, ohmic_loss_j{0}, balance_error_j{0};
    std::optional<ElectricalPair> electrical;
    std::optional<ActualBatteryPower> power;
};
struct BatteryStepResult {
    BatteryFault fault;
    double boundary_excess_j{0}; // requested energy beyond full/empty; nothing is silently clipped
};

// Single-owner, externally clocked functional SIL plant. No BMS controller,
// contactors, CAN, chemistry/aging, SOC estimator or vehicle energy integration.
class BatteryModel {
public:
    explicit BatteryModel(BatteryConfig config);
    // Explicit scenario initialization with known physical state. A later reset
    // needs a newer epoch/nondecreasing clock and starts a new energy ledger.
    // ECU session restart alone must never call this to reset a physical battery.
    bool initialize(BatteryInitialization initial);
    BatteryStepResult step(const BatteryInterval& interval, const BatterySensorCapture& capture = {});
    BatteryStepResult step_integrated(const BatteryElectricalInterval& interval, const BatterySensorCapture& capture = {});
    // A held group remains an old acquisition; consumers must validate its age.
    const BatteryObservation& observation() const { return observation_; }
    // Diagnostics/tests only: never bypass sensor validity using this truth.
    const BatteryState& diagnostic_state() const { return state_; }
    BatteryFault fault() const { return observation_.fault; }
private:
    struct Sum {
        double value{0}, correction{0};
        void add(double increment);
    };
    BatteryStepResult fail(BatteryFault fault, double excess_j = 0);
    BatteryStepResult commit(const IntegratedBatteryFlow& flow, const ActualBatteryPower& power, const BatterySensorCapture& capture);
    void capture_sensors(const BatterySensorCapture& capture);
    const BatteryConfig config_;
    BatteryState state_{};
    BatteryObservation observation_{};
    std::array<Sum, 4> totals_{};
    Sum stored_energy_{};
    std::optional<IntegratedBatteryFlow> previous_flow_;
    std::uint64_t last_observed_ns_{0}, initialization_time_ns_{0};
    double boundary_excess_j_{0};
    bool initialized_{false};
};
}  // namespace stratadrive::simulation
