#include "battery_model.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace stratadrive::simulation {
namespace {
bool extrema_valid(CellExtrema values, double lower) {
    return std::isfinite(values.minimum) && std::isfinite(values.maximum) &&
           values.minimum >= lower && values.minimum <= values.maximum;
}
template <typename T> void acquire(std::optional<ModelMeasurement<T>>& destination, SensorAction action,
                                  std::optional<T> value, ModelIdentity identity, std::uint64_t input_ns) {
    if (action == SensorAction::Hold) return;
    destination.reset();
    if (action == SensorAction::Acquire && value) destination = ModelMeasurement<T>{*value, identity, input_ns};
}
}  // namespace

BatteryModel::BatteryModel(BatteryConfig config) : config_(config) {
    if (!std::isfinite(config.capacity_j) || config.capacity_j <= 0 ||
        !std::isfinite(config.open_circuit_voltage_v) || config.open_circuit_voltage_v <= 0 ||
        !std::isfinite(config.open_circuit_voltage_v * config.open_circuit_voltage_v) ||
        !std::isfinite(config.resistance_ohm) || config.resistance_ohm < 0 ||
        !std::isfinite(config.thermal_capacity_j_k) || config.thermal_capacity_j_k <= 0 ||
        !std::isfinite(config.cooling_w_k) || config.cooling_w_k < 0 ||
        !std::isfinite(config.ambient_temperature_c) || config.ambient_temperature_c < -273.15 ||
        config.series_cells == 0 || !std::isfinite(config.cell_voltage_half_spread_v) ||
        config.cell_voltage_half_spread_v < 0 ||
        config.cell_voltage_half_spread_v > config.open_circuit_voltage_v / (2.0*config.series_cells) ||
        !std::isfinite(config.cell_temperature_half_spread_c) || config.cell_temperature_half_spread_c < 0 ||
        !std::isfinite(config.max_abs_power_w) || config.max_abs_power_w <= 0 ||
        config.max_step_ns == 0 || config.max_step_ns > 1000000000 ||
        config.max_input_age_ns < config.max_step_ns || config.max_input_age_ns > 1000000000) {
        throw std::invalid_argument("BatteryModel configuration");
    }
}
void BatteryModel::Sum::add(double increment) {
    const auto adjusted = increment - correction;
    const auto next = value + adjusted;
    correction = (next - value) - adjusted;
    value = next;
}
bool BatteryModel::initialize(BatteryInitialization initial) {
    if (initial.epoch == 0 || !std::isfinite(initial.soc) || initial.soc < 0 || initial.soc > 1 ||
        !std::isfinite(initial.temperature_c) || initial.temperature_c < -273.15 ||
        (initialized_ && (initial.epoch <= state_.identity.epoch || initial.time_ns < last_observed_ns_))) return false;
    state_ = {};
    state_.identity = {initial.epoch, 0, initial.time_ns};
    state_.initial_energy_j = state_.energy_j = config_.capacity_j * initial.soc;
    state_.soc = initial.soc; state_.temperature_c = initial.temperature_c;
    totals_ = {}; previous_flow_.reset(); observation_ = {}; observation_.fault = BatteryFault::None;
    stored_energy_ = {state_.energy_j, 0};
    last_observed_ns_ = initialization_time_ns_ = initial.time_ns; boundary_excess_j_ = 0; initialized_ = true;
    capture_sensors({});
    return true;
}
BatteryStepResult BatteryModel::fail(BatteryFault fault, double excess_j) {
    observation_ = {}; observation_.batch = state_.identity; observation_.fault = fault;
    boundary_excess_j_ = excess_j;
    return {fault, excess_j};
}
BatteryStepResult BatteryModel::step(const BatteryInterval& interval, const BatterySensorCapture& capture) {
    if (observation_.fault != BatteryFault::None) return {observation_.fault, boundary_excess_j_};
    if (previous_flow_) return fail(BatteryFault::InvalidInput); // integration modes do not change within a scenario
    if (interval.end_ns < last_observed_ns_) return fail(BatteryFault::ClockError);
    last_observed_ns_ = interval.end_ns;
    if (interval.begin_ns != state_.identity.source_time_ns || interval.end_ns <= interval.begin_ns ||
        interval.end_ns - interval.begin_ns > config_.max_step_ns) return fail(BatteryFault::TimingError);
    const auto& power = interval.power;
    const auto& id = power.identity;
    if (id.epoch != state_.identity.epoch) return fail(BatteryFault::IdentityError);
    if (power.input_time_ns > id.source_time_ns || id.source_time_ns > interval.begin_ns) return fail(BatteryFault::InvalidInput);
    // No physical sample from before this scenario initialization is accepted.
    if (power.input_time_ns < initialization_time_ns_) return fail(BatteryFault::InvalidInput);
    if (interval.end_ns - power.input_time_ns > config_.max_input_age_ns) return fail(BatteryFault::InputStale);
    if (!power.traction_dc_w || !power.auxiliary_w) return fail(BatteryFault::PowerUnavailable);
    if (!std::isfinite(*power.traction_dc_w) || !std::isfinite(*power.auxiliary_w) || *power.auxiliary_w < 0 ||
        std::abs(*power.traction_dc_w) > config_.max_abs_power_w || *power.auxiliary_w > config_.max_abs_power_w) {
        return fail(BatteryFault::InvalidInput);
    }
    if (state_.power) {
        const auto& previous = *state_.power;
        const bool cached = id.sequence == previous.identity.sequence;
        if (id.sequence < previous.identity.sequence || power.input_time_ns < previous.input_time_ns ||
            (cached && (id.source_time_ns != previous.identity.source_time_ns ||
             power.input_time_ns != previous.input_time_ns || power.traction_dc_w != previous.traction_dc_w ||
             power.auxiliary_w != previous.auxiliary_w)) ||
            (!cached && id.source_time_ns <= previous.identity.source_time_ns)) return fail(BatteryFault::IdentityError);
    }
    if (state_.identity.sequence == std::numeric_limits<std::uint32_t>::max()) return fail(BatteryFault::SequenceExhausted);
    const auto terminal_w = *power.traction_dc_w + *power.auxiliary_w;
    if (!std::isfinite(terminal_w) || std::abs(terminal_w) > config_.max_abs_power_w) return fail(BatteryFault::InvalidInput);
    const auto voc = config_.open_circuit_voltage_v;
    const auto resistance = config_.resistance_ohm;
    const auto discriminant = voc*voc - 4*resistance*terminal_w;
    if (!std::isfinite(discriminant)) return fail(BatteryFault::NumericalError);
    if (discriminant < 0) return fail(BatteryFault::ElectricalInfeasible);
    const auto current_a = resistance == 0 ? terminal_w / voc : 2*terminal_w / (voc + std::sqrt(discriminant));
    if (!std::isfinite(current_a) || (terminal_w != 0 && current_a == 0)) return fail(BatteryFault::NumericalError);
    const auto dt = static_cast<double>(interval.end_ns-interval.begin_ns)/1e9;
    const IntegratedBatteryFlow flow{{id.epoch, id.sequence, interval.end_ns}, power.input_time_ns,
        current_a*dt, current_a*current_a*dt, current_a,
        std::max(0.0, *power.traction_dc_w)*dt, std::max(0.0, -*power.traction_dc_w)*dt, *power.auxiliary_w*dt,
        std::abs(terminal_w), std::abs(*power.traction_dc_w), *power.auxiliary_w};
    return commit(flow, power, capture);
}
BatteryStepResult BatteryModel::step_integrated(const BatteryElectricalInterval& interval, const BatterySensorCapture& capture) {
    if (observation_.fault != BatteryFault::None) return {observation_.fault, boundary_excess_j_};
    if (state_.power && !previous_flow_) return fail(BatteryFault::InvalidInput);
    if (interval.end_ns < last_observed_ns_) return fail(BatteryFault::ClockError);
    last_observed_ns_ = interval.end_ns;
    if (interval.begin_ns != state_.identity.source_time_ns || interval.end_ns <= interval.begin_ns ||
        interval.end_ns-interval.begin_ns > config_.max_step_ns) return fail(BatteryFault::TimingError);
    const auto& f = interval.flow;
    if (f.identity.epoch != state_.identity.epoch || (previous_flow_ && f.identity.sequence <= previous_flow_->identity.sequence)) return fail(BatteryFault::IdentityError);
    if (f.identity.source_time_ns != interval.end_ns || f.input_time_ns < initialization_time_ns_ ||
        f.input_time_ns > interval.begin_ns || (previous_flow_ && f.input_time_ns < previous_flow_->input_time_ns)) return fail(BatteryFault::InvalidInput);
    if (interval.end_ns-f.input_time_ns > config_.max_input_age_ns) return fail(BatteryFault::InputStale);
    for (const auto x : {f.charge_c, f.current_squared_a2s, f.end_current_a, f.drawn_dc_j, f.received_dc_j,
        f.auxiliary_j, f.peak_abs_terminal_w, f.peak_abs_branch_w, f.peak_auxiliary_w}) {
        if (!std::isfinite(x)) return fail(BatteryFault::InvalidInput);
    }
    const auto dt = static_cast<double>(interval.end_ns-interval.begin_ns)/1e9;
    const auto end_voltage = config_.open_circuit_voltage_v-config_.resistance_ohm*f.end_current_a;
    const auto terminal_j = (f.drawn_dc_j-f.received_dc_j)+f.auxiliary_j;
    const auto chemical_j = config_.open_circuit_voltage_v*f.charge_c;
    const auto heat_j = config_.resistance_ohm*f.current_squared_a2s;
    if (f.current_squared_a2s < 0 || f.drawn_dc_j < 0 || f.received_dc_j < 0 || f.auxiliary_j < 0 ||
        f.peak_abs_terminal_w < 0 || f.peak_abs_branch_w < 0 || f.peak_auxiliary_w < 0 ||
        f.peak_abs_terminal_w > config_.max_abs_power_w || f.peak_abs_branch_w > config_.max_abs_power_w || f.peak_auxiliary_w > config_.max_abs_power_w ||
        end_voltage <= 0 || !std::isfinite(end_voltage) || !std::isfinite(chemical_j) || !std::isfinite(heat_j) ||
        f.charge_c*f.charge_c > dt*f.current_squared_a2s+1e-12*std::max(1.0, f.charge_c*f.charge_c) ||
        f.drawn_dc_j > f.peak_abs_branch_w*dt+1e-9 || f.received_dc_j > f.peak_abs_branch_w*dt+1e-9 ||
        f.auxiliary_j > f.peak_auxiliary_w*dt+1e-9 || std::abs(terminal_j) > f.peak_abs_terminal_w*dt+1e-9 ||
        std::abs(end_voltage*f.end_current_a) > f.peak_abs_terminal_w+1e-8 ||
        std::abs(chemical_j-terminal_j-heat_j) > std::max(1e-8, std::abs(chemical_j)*1e-10)) return fail(BatteryFault::InvalidInput);
    if (state_.identity.sequence == std::numeric_limits<std::uint32_t>::max()) return fail(BatteryFault::SequenceExhausted);
    const ActualBatteryPower power{{f.identity.epoch, f.identity.sequence, interval.begin_ns}, f.input_time_ns,
        (f.drawn_dc_j-f.received_dc_j)/dt, f.auxiliary_j/dt}; // interval means for diagnostics only
    const auto result = commit(f, power, capture);
    if (result.fault == BatteryFault::None) previous_flow_ = f;
    return result;
}
BatteryStepResult BatteryModel::commit(const IntegratedBatteryFlow& flow, const ActualBatteryPower& power, const BatterySensorCapture& capture) {
    const auto dt = static_cast<double>(flow.identity.source_time_ns-state_.identity.source_time_ns)/1e9;
    const auto terminal_v = config_.open_circuit_voltage_v-config_.resistance_ohm*flow.end_current_a;
    const auto heat_j = config_.resistance_ohm*flow.current_squared_a2s;
    const auto heat_w = heat_j/dt; // mean heat; thermal response is a lumped interval approximation
    const auto thermal_x = config_.cooling_w_k*dt/config_.thermal_capacity_j_k;
    const auto thermal_gain = thermal_x == 0 ? 1 : -std::expm1(-thermal_x)/thermal_x;
    const auto temperature = state_.temperature_c+
        (heat_w-config_.cooling_w_k*(state_.temperature_c-config_.ambient_temperature_c))*
        (dt/config_.thermal_capacity_j_k)*thermal_gain;
    auto totals = totals_;
    totals[0].add(flow.drawn_dc_j); totals[1].add(flow.received_dc_j); totals[2].add(flow.auxiliary_j); totals[3].add(heat_j);
    const auto chemical_delta_j = config_.open_circuit_voltage_v*flow.charge_c;
    auto stored_energy = stored_energy_; stored_energy.add(-chemical_delta_j);
    const auto energy = stored_energy.value;
    const auto balance_error = (state_.initial_energy_j-energy)-
        ((totals[0].value-totals[1].value)+totals[2].value+totals[3].value);
    if (!std::isfinite(flow.end_current_a) || !std::isfinite(chemical_delta_j) || !std::isfinite(terminal_v) || terminal_v <= 0 ||
        !std::isfinite(heat_w) || !std::isfinite(temperature) || !std::isfinite(energy) || !std::isfinite(balance_error) ||
        !std::isfinite(totals[0].value) || !std::isfinite(totals[1].value) || !std::isfinite(totals[2].value) || !std::isfinite(totals[3].value) ||
        std::abs(balance_error) > std::max(1e-6, config_.capacity_j*1e-12)) return fail(BatteryFault::NumericalError);
    if (chemical_delta_j > state_.energy_j) return fail(BatteryFault::CapacityViolation, chemical_delta_j-state_.energy_j);
    if (-chemical_delta_j > config_.capacity_j-state_.energy_j) return fail(BatteryFault::CapacityViolation, -chemical_delta_j-(config_.capacity_j-state_.energy_j));
    if (energy < 0 || energy > config_.capacity_j) return fail(BatteryFault::CapacityViolation, energy < 0 ? -energy : energy-config_.capacity_j);
    totals_ = totals; stored_energy_ = stored_energy;
    ++state_.identity.sequence; state_.identity.source_time_ns = flow.identity.source_time_ns;
    state_.energy_j = energy; state_.soc = energy/config_.capacity_j; state_.temperature_c = temperature;
    state_.drawn_dc_j = totals[0].value; state_.received_dc_j = totals[1].value; state_.auxiliary_j = totals[2].value;
    state_.ohmic_loss_j = totals[3].value; state_.balance_error_j = balance_error;
    state_.electrical = ElectricalPair{terminal_v, flow.end_current_a}; state_.power = power;
    capture_sensors(capture);
    return {BatteryFault::None};
}
void BatteryModel::capture_sensors(const BatterySensorCapture& capture) {
    observation_.available = true;
    const auto identity = state_.identity;
    const auto input_ns = state_.power ? state_.power->input_time_ns : identity.source_time_ns;
    observation_.batch = identity;
    acquire<double>(observation_.soc, capture.soc, state_.soc, identity, input_ns);
    acquire<ElectricalPair>(observation_.electrical, capture.electrical, state_.electrical, identity, input_ns);
    acquire<double>(observation_.temperature, capture.temperature, state_.temperature_c, identity, input_ns);
    std::optional<CellExtrema> voltage;
    if (state_.electrical) {
        const auto mean = state_.electrical->voltage_v / config_.series_cells;
        voltage = capture.voltage_override.value_or(CellExtrema{mean - config_.cell_voltage_half_spread_v,
                                                               mean + config_.cell_voltage_half_spread_v});
        if (!extrema_valid(*voltage, 0)) voltage.reset();
    }
    auto temperature = capture.temperature_override.value_or(CellExtrema{
        state_.temperature_c - config_.cell_temperature_half_spread_c,
        state_.temperature_c + config_.cell_temperature_half_spread_c});
    const auto valid_temperature = extrema_valid(temperature, -273.15) ? std::optional<CellExtrema>{temperature} : std::nullopt;
    acquire<CellExtrema>(observation_.cell_voltage, capture.cell_voltage, voltage, identity, input_ns);
    acquire<CellExtrema>(observation_.cell_temperature, capture.cell_temperature, valid_temperature, identity, input_ns);
}
}  // namespace stratadrive::simulation
