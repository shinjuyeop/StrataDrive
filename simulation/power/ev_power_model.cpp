#include "ev_power_model.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <utility>

namespace stratadrive::simulation {
namespace {
bool equal(double a, double b) { return a == b; }
bool equal(EvElectricalEnvironment a, EvElectricalEnvironment b) {
    return a.auxiliary_current_a == b.auxiliary_current_a && a.inverter_enabled == b.inverter_enabled &&
        a.lv_available == b.lv_available && a.interlock_closed == b.interlock_closed && a.isolation_ok == b.isolation_ok &&
        a.charger_connected == b.charger_connected && a.power_fault == b.power_fault;
}
struct Context { std::uint32_t epoch; std::uint64_t enable, begin, end, age; };
template <typename T> EvPowerFault check(const ModelMeasurement<T>& x, const std::optional<ModelMeasurement<T>>& old, const Context& c) {
    if (x.identity.epoch != c.epoch) return EvPowerFault::Identity;
    if (x.input_time_ns < c.enable || x.input_time_ns > x.identity.source_time_ns || x.identity.source_time_ns > c.begin) return EvPowerFault::Inputs;
    if (c.end-x.input_time_ns > c.age) return EvPowerFault::Stale;
    if (old) {
        const bool cached = x.identity.sequence == old->identity.sequence;
        if (x.identity.sequence < old->identity.sequence || x.input_time_ns < old->input_time_ns ||
            (cached && (x.identity.source_time_ns != old->identity.source_time_ns || x.input_time_ns != old->input_time_ns || !equal(x.value, old->value))) ||
            (!cached && x.identity.source_time_ns <= old->identity.source_time_ns)) return EvPowerFault::Identity;
    }
    return EvPowerFault::None;
}
}  // namespace
EvPowerModel::EvPowerModel(DriveEnergyConfig drive, BatteryConfig battery, PowerModelConfig circuit) :
    drive_config_(drive), battery_config_(battery), circuit_config_(circuit),
    battery_(std::in_place, battery), circuit_(std::in_place, circuit) {
    if (!calculate_motor_power(drive, drive.maximum_abs_torque_nm, drive.maximum_speed_rad_s) ||
        drive.max_step_ns == 0 || drive.max_step_ns > battery.max_step_ns || drive.max_step_ns > circuit.max_step_ns ||
        drive.max_input_age_ns < drive.max_step_ns || drive.max_input_age_ns > battery.max_input_age_ns ||
        drive.max_input_age_ns > circuit.max_input_age_ns || drive.max_source_skew_ns > drive.max_input_age_ns ||
        battery.open_circuit_voltage_v > circuit.maximum_voltage_v) throw std::invalid_argument("EvPowerModel configuration");
}
void EvPowerModel::Sum::add(double increment) {
    const auto adjusted = increment-correction, next = value+adjusted;
    correction = (next-value)-adjusted; value = next;
}
bool EvPowerModel::initialize(BatteryInitialization initial, double bus_voltage_v, power::ContactorPositions contacts) {
    if (state_.identity.epoch != 0 && (initial.epoch <= state_.identity.epoch || initial.time_ns < last_observed_ns_)) return false;
    auto battery = *battery_; auto circuit = *circuit_;
    if (!battery.initialize(initial) || !circuit.initialize({initial.epoch, 0, initial.time_ns}, bus_voltage_v, contacts)) return false;
    battery_.emplace(std::move(battery)); circuit_.emplace(std::move(circuit));
    state_ = {}; state_.identity = {initial.epoch, 0, initial.time_ns};
    state_.initial_capacitor_j = state_.capacitor_j = 0.5*circuit_config_.capacitance_f*bus_voltage_v*bus_voltage_v;
    totals_ = {}; previous_.reset(); flow_.reset(); power_observation_.reset(); battery_observation_ = battery_->observation();
    result_ = {EvPowerFault::None}; initialization_ns_ = last_observed_ns_ = initial.time_ns;
    return true;
}
EvPowerStep EvPowerModel::fail(EvPowerFault fault) {
    result_.fault = fault; flow_.reset(); power_observation_.reset(); battery_observation_ = {};
    battery_observation_.batch = state_.identity;
    battery_observation_.fault = result_.battery_fault == BatteryFault::None ? BatteryFault::PowerUnavailable : result_.battery_fault;
    return result_;
}
EvPowerStep EvPowerModel::step(const EvPowerInterval& interval, const PowerFaultInjection& injection, const BatterySensorCapture& capture) {
    if (result_.fault != EvPowerFault::None) return result_;
    if (interval.end_ns < last_observed_ns_) return fail(EvPowerFault::Clock);
    last_observed_ns_ = interval.end_ns;
    if (interval.begin_ns != state_.identity.source_time_ns || interval.end_ns <= interval.begin_ns ||
        interval.end_ns-interval.begin_ns > drive_config_.max_step_ns) return fail(EvPowerFault::Timing);
    const auto& in = interval.inputs;
    if (!in.actual_torque_nm || !in.wheel_speed_rad_s || !in.electrical) return fail(EvPowerFault::Inputs);
    const auto old = previous_.value_or(EvPowerInputs{});
    const Context context{state_.identity.epoch, initialization_ns_, interval.begin_ns, interval.end_ns, drive_config_.max_input_age_ns};
    const std::array issues{check(*in.actual_torque_nm, old.actual_torque_nm, context),
        check(*in.wheel_speed_rad_s, old.wheel_speed_rad_s, context), check(*in.electrical, old.electrical, context)};
    const auto issue = std::find_if(issues.begin(), issues.end(), [](auto x) { return x != EvPowerFault::None; });
    if (issue != issues.end()) return fail(*issue);
    const auto times = {in.actual_torque_nm->identity.source_time_ns, in.wheel_speed_rad_s->identity.source_time_ns, in.electrical->identity.source_time_ns};
    const auto bounds = std::minmax_element(times.begin(), times.end());
    if (*bounds.second-*bounds.first > drive_config_.max_source_skew_ns) return fail(EvPowerFault::Skew);
    const auto& e = in.electrical->value;
    const auto motor = calculate_motor_power(drive_config_, in.actual_torque_nm->value, in.wheel_speed_rad_s->value);
    if (!motor || !std::isfinite(e.auxiliary_current_a) || e.auxiliary_current_a < 0) return fail(EvPowerFault::Inputs);
    if (!e.inverter_enabled && in.actual_torque_nm->value != 0) return fail(EvPowerFault::InverterOff);
    const auto actual_motor = e.inverter_enabled ? *motor : MotorPower{0, 0, 0};
    const auto dependency = std::min({in.actual_torque_nm->input_time_ns, in.wheel_speed_rad_s->input_time_ns, in.electrical->input_time_ns});
    const PowerEnvironment environment{battery_config_.open_circuit_voltage_v, 0, e.lv_available, e.interlock_closed,
        e.isolation_ok, e.charger_connected, e.power_fault, battery_config_.resistance_ohm, e.auxiliary_current_a, actual_motor.dc_w};
    auto circuit = *circuit_; auto battery = *battery_; // transactional candidates; sensor faults do not erase physical flow
    const auto circuit_fault = circuit.step({interval.begin_ns, interval.end_ns,
        {environment, {state_.identity.epoch, state_.identity.sequence, interval.begin_ns}, dependency}, interval.coils}, injection);
    if (circuit_fault != PowerModelFault::None) { result_.circuit_fault = circuit_fault; return fail(EvPowerFault::Circuit); }
    if (!circuit.integrated_flow()) return fail(EvPowerFault::Circuit);
    const auto& flow = *circuit.integrated_flow();
    const auto battery_result = battery.step_integrated({interval.begin_ns, interval.end_ns, flow.battery}, capture);
    if (battery_result.fault != BatteryFault::None) {
        result_.battery_fault = battery_result.fault; result_.boundary_excess_j = battery_result.boundary_excess_j;
        return fail(EvPowerFault::Battery);
    }
    auto totals = totals_;
    const auto seconds = static_cast<double>(interval.end_ns-interval.begin_ns)/1e9;
    totals[0].add(actual_motor.mechanical_w*seconds); totals[1].add(actual_motor.loss_w*seconds);
    totals[2].add(flow.precharge_loss_j); totals[3].add(flow.main_loss_j); totals[4].add(flow.discharge_loss_j);
    const auto capacitor = 0.5*circuit_config_.capacitance_f*circuit.diagnostic_state().bus_voltage_v*circuit.diagnostic_state().bus_voltage_v;
    const auto& b = battery.diagnostic_state();
    const auto balance = (b.initial_energy_j-b.energy_j)-((capacitor-state_.initial_capacitor_j)+b.ohmic_loss_j+b.auxiliary_j+
        totals[0].value+totals[1].value+totals[2].value+totals[3].value+totals[4].value);
    if (!std::isfinite(balance) || std::abs(balance) > std::max(1e-6, battery_config_.capacity_j*4e-12)) return fail(EvPowerFault::EnergyBalance);
    state_ = {b.identity, actual_motor.mechanical_w, actual_motor.loss_w, actual_motor.dc_w,
        totals[0].value, totals[1].value, totals[2].value, totals[3].value, totals[4].value,
        state_.initial_capacitor_j, capacitor, balance};
    flow_ = flow; totals_ = totals; previous_ = in;
    battery_observation_ = battery.observation(); power_observation_ = circuit.observation();
    battery_.emplace(std::move(battery)); circuit_.emplace(std::move(circuit));
    return result_;
}
}  // namespace stratadrive::simulation
