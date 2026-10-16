#include "power_model.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <numeric>
#include <stdexcept>

namespace stratadrive::simulation {
namespace {
bool same(PowerEnvironment a, PowerEnvironment b) {
    return a.pack_voltage_v == b.pack_voltage_v && a.bus_load_current_a == b.bus_load_current_a &&
        a.lv_available == b.lv_available && a.interlock_closed == b.interlock_closed && a.isolation_ok == b.isolation_ok &&
        a.charger_connected == b.charger_connected && a.power_fault == b.power_fault &&
        a.source_resistance_ohm == b.source_resistance_ohm && a.auxiliary_current_a == b.auxiliary_current_a &&
        a.bus_load_power_w == b.bus_load_power_w;
}
}  // namespace
PowerModel::PowerModel(PowerModelConfig config) : config_(config) {
    for (const auto value : {config.capacitance_f, config.precharge_resistance_ohm, config.main_resistance_ohm,
         config.discharge_resistance_ohm, config.maximum_voltage_v, config.maximum_abs_load_current_a}) {
        if (!std::isfinite(value) || value <= 0) throw std::invalid_argument("PowerModel electrical configuration");
    }
    if (config.maximum_voltage_v > 6553.4 || config.maximum_abs_load_current_a > 3276.7 ||
        config.main_resistance_ohm >= config.precharge_resistance_ohm || config.contactor_delay_ns == 0 ||
        config.contactor_delay_ns > 1000000000 || config.max_step_ns == 0 || config.max_step_ns > 50000000 ||
        config.max_input_age_ns < config.max_step_ns || config.max_input_age_ns > 70000000 ||
        config.integration_step_ns == 0 || config.integration_step_ns > 1000000) {
        throw std::invalid_argument("PowerModel configuration");
    }
}
bool PowerModel::initialize(battery::ModelIdentity scenario, double initial_bus_voltage_v,
                            power::ContactorPositions initial_contactors) {
    if (scenario.epoch == 0 || scenario.sequence != 0 || !std::isfinite(initial_bus_voltage_v) || initial_bus_voltage_v < 0 ||
        initial_bus_voltage_v > config_.maximum_voltage_v || (state_.identity.epoch != 0 &&
        (scenario.epoch <= state_.identity.epoch || scenario.source_time_ns < last_observed_ns_))) return false;
    state_ = {scenario, initial_bus_voltage_v, 0, initial_contactors};
    const std::array<bool, 3> actual{initial_contactors.positive, initial_contactors.negative, initial_contactors.precharge};
    contacts_ = {};
    for (std::size_t i = 0; i < contacts_.size(); ++i) contacts_[i].actual = contacts_[i].target = actual[i];
    previous_.reset(); observation_.reset(); flow_.reset(); fault_ = PowerModelFault::None;
    initialization_ns_ = last_observed_ns_ = scenario.source_time_ns;
    return true;
}
PowerModelFault PowerModel::fail(PowerModelFault fault) { observation_.reset(); flow_.reset(); fault_ = fault; return fault; }
PowerModelFault PowerModel::step(const PowerInterval& interval, const PowerFaultInjection& injection) {
    if (fault_ != PowerModelFault::None) return fault_;
    if (interval.end_ns < last_observed_ns_) return fail(PowerModelFault::Clock);
    last_observed_ns_ = interval.end_ns;
    if (interval.begin_ns != state_.identity.source_time_ns || interval.end_ns <= interval.begin_ns ||
        interval.end_ns-interval.begin_ns > config_.max_step_ns) return fail(PowerModelFault::Timing);
    const auto& env = interval.environment;
    if (env.identity.epoch != state_.identity.epoch) return fail(PowerModelFault::Identity);
    if (env.input_time_ns < initialization_ns_ || env.input_time_ns > env.identity.source_time_ns ||
        env.identity.source_time_ns > interval.begin_ns) return fail(PowerModelFault::Input);
    if (interval.end_ns-env.input_time_ns > config_.max_input_age_ns) return fail(PowerModelFault::Stale);
    if (!std::isfinite(env.value.pack_voltage_v) || env.value.pack_voltage_v < 0 || env.value.pack_voltage_v > config_.maximum_voltage_v ||
        !std::isfinite(env.value.bus_load_current_a) || std::abs(env.value.bus_load_current_a) > config_.maximum_abs_load_current_a) {
        return fail(PowerModelFault::Input);
    }
    const auto& value = env.value;
    if (!std::isfinite(value.source_resistance_ohm) || value.source_resistance_ohm < 0 ||
        !std::isfinite(value.auxiliary_current_a) || value.auxiliary_current_a < 0 || value.auxiliary_current_a > config_.maximum_abs_load_current_a ||
        (value.bus_load_power_w && (!std::isfinite(*value.bus_load_power_w) || value.bus_load_current_a != 0 ||
            value.pack_voltage_v <= value.source_resistance_ohm*value.auxiliary_current_a)) ||
        (!value.bus_load_power_w && (value.source_resistance_ohm != 0 || value.auxiliary_current_a != 0))) return fail(PowerModelFault::Input);
    if (previous_) {
        const auto& p = *previous_;
        const bool cached = env.identity.sequence == p.identity.sequence;
        if (env.identity.sequence < p.identity.sequence || env.input_time_ns < p.input_time_ns ||
            (cached && (env.identity.source_time_ns != p.identity.source_time_ns || env.input_time_ns != p.input_time_ns || !same(env.value, p.value))) ||
            (!cached && env.identity.source_time_ns <= p.identity.source_time_ns)) return fail(PowerModelFault::Identity);
    }
    if (state_.identity.sequence == std::numeric_limits<std::uint32_t>::max()) return fail(PowerModelFault::SequenceExhausted);
    auto contacts = contacts_; // reject the entire step on impossible electrical evolution
    const std::array<bool, 3> requested{interval.coils.close.positive, interval.coils.close.negative, interval.coils.close.precharge};
    for (std::size_t i = 0; i < contacts.size(); ++i) {
        auto& c = contacts[i]; const auto mode = injection.contactors[i];
        if (mode != ContactorFailure::None) {
            c.actual = c.target = mode == ContactorFailure::StuckClosed; c.due.reset();
        } else {
            const bool target = requested[i] && env.value.lv_available;
            if (target != c.target) {
                c.target = target;
                // A due event past this interval need not be representable at UINT64_MAX.
                if (interval.begin_ns > std::numeric_limits<std::uint64_t>::max()-config_.contactor_delay_ns) return fail(PowerModelFault::Timing);
                c.due = interval.begin_ns+config_.contactor_delay_ns;
            }
        }
    }
    auto voltage = state_.bus_voltage_v;
    PowerCircuitFlow flow;
    const auto constant_power = value.bus_load_power_w;
    auto cursor = interval.begin_ns;
    const auto conductance = [&]() {
        return contacts[1].actual ? (contacts[0].actual ? 1/config_.main_resistance_ohm : 0) +
            (contacts[2].actual ? 1/config_.precharge_resistance_ohm : 0) : 0;
    };
    while (cursor < interval.end_ns) {
        const auto end = std::accumulate(contacts.begin(), contacts.end(), interval.end_ns,
            [cursor](std::uint64_t next, const Contact& c) { return std::min(next, std::max(cursor, c.due.value_or(next))); });
        if (end > cursor) {
            const auto gp = conductance();
            const auto gd = interval.coils.discharge_bus ? 1/config_.discharge_resistance_ohm : 0;
            const auto dt = static_cast<double>(end-cursor)/1e9;
            if (constant_power) {
                const auto effective_g = gp/(1+value.source_resistance_ohm*gp);
                const auto source_v = value.pack_voltage_v-value.source_resistance_ohm*value.auxiliary_current_a;
                const auto gmain = contacts[1].actual && contacts[0].actual ? 1/config_.main_resistance_ohm : 0;
                const auto gpre = contacts[1].actual && contacts[2].actual ? 1/config_.precharge_resistance_ohm : 0;
                const auto record_peak = [&](double bus_v) {
                    const auto path_i = effective_g*(source_v-bus_v);
                    const auto battery_i = path_i+value.auxiliary_current_a;
                    const auto pack_v = value.pack_voltage_v-value.source_resistance_ohm*battery_i;
                    if (!std::isfinite(pack_v) || pack_v <= 0 || pack_v > config_.maximum_voltage_v ||
                        !std::isfinite(battery_i) || std::abs(battery_i) > config_.maximum_abs_load_current_a ||
                        (*constant_power != 0 && (bus_v <= 0 || std::abs(*constant_power/bus_v) > config_.maximum_abs_load_current_a))) return false;
                    flow.battery.peak_abs_terminal_w = std::max(flow.battery.peak_abs_terminal_w, std::abs(pack_v*battery_i));
                    flow.battery.peak_abs_branch_w = std::max(flow.battery.peak_abs_branch_w, std::abs(pack_v*path_i));
                    flow.battery.peak_auxiliary_w = std::max(flow.battery.peak_auxiliary_w, pack_v*value.auxiliary_current_a);
                    return true;
                };
                if (!record_peak(voltage)) return fail(PowerModelFault::Electrical);
                auto sub_cursor = cursor;
                std::uint32_t substeps = 0;
                while (sub_cursor < end) {
                    if (++substeps > 200000) return fail(PowerModelFault::Electrical);
                    auto ns = std::min(config_.integration_step_ns, end-sub_cursor);
                    if (effective_g+gd > 0) {
                        const auto tau_ns = config_.capacitance_f/(effective_g+gd)*1e9;
                        if (!std::isfinite(tau_ns) || tau_ns < 1) return fail(PowerModelFault::Electrical);
                        if (tau_ns < static_cast<double>(ns)) ns = static_cast<std::uint64_t>(tau_ns);
                    }
                    const auto seconds = static_cast<double>(ns)/1e9;
                    const auto factor = seconds/(2*config_.capacitance_f);
                    const auto a = 1+factor*(effective_g+gd), b = voltage+factor*effective_g*source_v;
                    const auto discriminant = b*b-4*a*factor*(*constant_power);
                    if (!std::isfinite(discriminant) || discriminant < 0) return fail(PowerModelFault::Electrical);
                    const auto midpoint = (b+std::sqrt(discriminant))/(2*a);
                    const auto next = 2*midpoint-voltage;
                    if (!std::isfinite(next) || next < 0 || next > config_.maximum_voltage_v ||
                        !record_peak(midpoint) || !record_peak(next)) return fail(PowerModelFault::Electrical);
                    const auto path_i = effective_g*(source_v-midpoint), battery_i = path_i+value.auxiliary_current_a;
                    const auto pack_v = value.pack_voltage_v-value.source_resistance_ohm*battery_i;
                    const auto branch_j = pack_v*path_i*seconds;
                    flow.battery.charge_c += battery_i*seconds;
                    flow.battery.current_squared_a2s += battery_i*battery_i*seconds;
                    flow.battery.drawn_dc_j += std::max(0.0, branch_j);
                    flow.battery.received_dc_j += std::max(0.0, -branch_j);
                    flow.battery.auxiliary_j += pack_v*value.auxiliary_current_a*seconds;
                    if (gp > 0) {
                        const auto drop = path_i/gp;
                        flow.main_loss_j += drop*drop*gmain*seconds;
                        flow.precharge_loss_j += drop*drop*gpre*seconds;
                    }
                    flow.discharge_loss_j += midpoint*midpoint*gd*seconds;
                    flow.load_j += *constant_power*seconds;
                    voltage = next; sub_cursor += ns;
                }
            } else if (gp+gd > 0) {
                const auto equilibrium = (gp*env.value.pack_voltage_v-env.value.bus_load_current_a)/(gp+gd);
                voltage += (equilibrium-voltage)*(-std::expm1(-(gp+gd)*dt/config_.capacitance_f));
            } else voltage -= env.value.bus_load_current_a*dt/config_.capacitance_f;
            if (!std::isfinite(voltage) || voltage < 0 || voltage > config_.maximum_voltage_v) return fail(PowerModelFault::Electrical);
        }
        cursor = end;
        for (auto& c : contacts) if (c.due && *c.due <= cursor) { c.actual = c.target; c.due.reset(); }
    }
    // Events exactly at end are reflected in contact feedback, after integrating the preceding interval.
    for (auto& c : contacts) if (c.due && *c.due <= interval.end_ns) { c.actual = c.target; c.due.reset(); }
    const auto effective_g = conductance()/(1+value.source_resistance_ohm*conductance());
    const auto path_i = effective_g*(value.pack_voltage_v-value.source_resistance_ohm*value.auxiliary_current_a-voltage);
    const auto current = path_i+value.auxiliary_current_a;
    const auto pack_voltage = value.pack_voltage_v-value.source_resistance_ohm*current;
    if (!std::isfinite(current)) return fail(PowerModelFault::Electrical);
    if (constant_power) {
        if (pack_voltage <= 0 || pack_voltage > config_.maximum_voltage_v || std::abs(current) > config_.maximum_abs_load_current_a) return fail(PowerModelFault::Electrical);
        flow.battery.identity = {state_.identity.epoch, state_.identity.sequence+1, interval.end_ns};
        flow.battery.input_time_ns = env.input_time_ns; flow.battery.end_current_a = current;
        flow.battery.peak_abs_terminal_w = std::max(flow.battery.peak_abs_terminal_w, std::abs(pack_voltage*current));
        flow.battery.peak_abs_branch_w = std::max(flow.battery.peak_abs_branch_w, std::abs(pack_voltage*path_i));
        flow.battery.peak_auxiliary_w = std::max(flow.battery.peak_auxiliary_w, pack_voltage*value.auxiliary_current_a);
        flow.capacitor_delta_j = 0.5*config_.capacitance_f*(voltage*voltage-state_.bus_voltage_v*state_.bus_voltage_v);
    }
    contacts_ = contacts; previous_ = env;
    ++state_.identity.sequence; state_.identity.source_time_ns = interval.end_ns;
    state_.bus_voltage_v = voltage; state_.pack_current_a = current;
    state_.contactors = {contacts[0].actual, contacts[1].actual, contacts[2].actual};
    flow_ = constant_power ? std::optional<PowerCircuitFlow>{flow} : std::nullopt;
    if (injection.hold_sensors) return fault_;
    power::SensorSnapshot s{state_.identity, env.input_time_ns, pack_voltage, voltage, current, state_.contactors,
        {env.value.lv_available, env.value.interlock_closed, env.value.isolation_ok, env.value.charger_connected, env.value.power_fault}};
    if (injection.invalidate_pack) s.pack_voltage_v.reset();
    if (injection.invalidate_bus) s.bus_voltage_v.reset();
    if (injection.invalidate_current) s.pack_current_a.reset();
    if (injection.invalidate_contactors) s.contactors.reset();
    if (injection.invalidate_conditions) s.conditions = {};
    observation_ = s;
    return fault_;
}
}  // namespace stratadrive::simulation
