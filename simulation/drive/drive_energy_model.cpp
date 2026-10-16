#include "drive_energy_model.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <stdexcept>

namespace stratadrive::simulation {
namespace {
struct CheckContext {
    std::uint32_t epoch;
    std::uint64_t initialization_ns, begin_ns, end_ns, age_ns;
};
DriveEnergyFault check(const ModelMeasurement<double>& x,
        const std::optional<ModelMeasurement<double>>& old, const CheckContext& context) {
    if (x.identity.epoch != context.epoch) return DriveEnergyFault::Identity;
    if (x.input_time_ns < context.initialization_ns || x.input_time_ns > x.identity.source_time_ns ||
        x.identity.source_time_ns > context.begin_ns) return DriveEnergyFault::Timestamp;
    if (context.end_ns-x.input_time_ns > context.age_ns) return DriveEnergyFault::Stale;
    if (old) {
        const bool cached = x.identity.sequence == old->identity.sequence;
        if (x.identity.sequence < old->identity.sequence || x.input_time_ns < old->input_time_ns ||
            (cached && (x.identity.source_time_ns != old->identity.source_time_ns ||
             x.input_time_ns != old->input_time_ns || x.value != old->value)) ||
            (!cached && x.identity.source_time_ns <= old->identity.source_time_ns)) return DriveEnergyFault::Identity;
    }
    return DriveEnergyFault::None;
}
}  // namespace

std::optional<MotorPower> calculate_motor_power(const DriveEnergyConfig& c, double torque_nm, double speed_rad_s) {
    for (const auto x : {c.motoring_efficiency, c.generating_efficiency, c.copper_loss_w_per_nm2, c.inverter_idle_w,
        c.maximum_abs_torque_nm, c.maximum_speed_rad_s, torque_nm, speed_rad_s}) if (!std::isfinite(x)) return std::nullopt;
    if (c.motoring_efficiency <= 0 || c.motoring_efficiency > 1 || c.generating_efficiency <= 0 || c.generating_efficiency > 1 ||
        c.copper_loss_w_per_nm2 < 0 || c.inverter_idle_w < 0 || c.maximum_abs_torque_nm <= 0 || c.maximum_speed_rad_s <= 0 ||
        std::abs(torque_nm) > c.maximum_abs_torque_nm || speed_rad_s < 0 || speed_rad_s > c.maximum_speed_rad_s) return std::nullopt;
    const auto mechanical = torque_nm*speed_rad_s;
    const auto conversion = mechanical >= 0 ? mechanical*(1/c.motoring_efficiency-1) : -mechanical*(1-c.generating_efficiency);
    const auto loss = conversion+c.copper_loss_w_per_nm2*torque_nm*torque_nm+c.inverter_idle_w;
    if (!std::isfinite(loss) || !std::isfinite(mechanical+loss)) return std::nullopt;
    return MotorPower{mechanical, loss, mechanical+loss};
}

DriveEnergyModel::DriveEnergyModel(DriveEnergyConfig drive, BatteryConfig battery) : config_(drive),
    balance_tolerance_j_(std::max(1e-6, battery.capacity_j*2e-12)), battery_(battery) {
    for (const auto x : {drive.motoring_efficiency, drive.generating_efficiency, drive.copper_loss_w_per_nm2,
        drive.inverter_idle_w, drive.maximum_abs_torque_nm, drive.maximum_speed_rad_s}) {
        if (!std::isfinite(x)) throw std::invalid_argument("DriveEnergyModel finite configuration");
    }
    if (drive.motoring_efficiency <= 0 || drive.motoring_efficiency > 1 || drive.generating_efficiency <= 0 ||
        drive.generating_efficiency > 1 || drive.copper_loss_w_per_nm2 < 0 || drive.inverter_idle_w < 0 ||
        drive.maximum_abs_torque_nm <= 0 || drive.maximum_speed_rad_s <= 0 ||
        drive.max_step_ns == 0 || drive.max_step_ns > battery.max_step_ns || drive.max_input_age_ns < drive.max_step_ns ||
        drive.max_input_age_ns > battery.max_input_age_ns || drive.max_source_skew_ns > drive.max_input_age_ns ||
        !std::isfinite(drive.maximum_abs_torque_nm*drive.maximum_speed_rad_s/drive.motoring_efficiency+
            drive.copper_loss_w_per_nm2*drive.maximum_abs_torque_nm*drive.maximum_abs_torque_nm+drive.inverter_idle_w)) {
        throw std::invalid_argument("DriveEnergyModel configuration");
    }
}
void DriveEnergyModel::Sum::add(double increment) {
    const auto adjusted = increment-correction;
    const auto next = value+adjusted;
    correction = (next-value)-adjusted; value = next;
}
bool DriveEnergyModel::initialize(BatteryInitialization initial) {
    if (state_.identity.epoch != 0 && (initial.epoch <= state_.identity.epoch || initial.time_ns < last_observed_ns_)) return false;
    if (!battery_.initialize(initial)) return false;
    state_ = {}; state_.identity = {initial.epoch, 0, initial.time_ns};
    mechanical_ = {}; losses_ = {}; previous_.reset(); result_ = {DriveEnergyFault::None};
    initialization_ns_ = last_observed_ns_ = initial.time_ns; observation_ = battery_.observation();
    return true;
}
DriveEnergyStep DriveEnergyModel::fail(DriveEnergyFault fault) {
    result_.fault = fault; observation_ = {}; observation_.batch = state_.identity;
    observation_.fault = result_.battery_fault != BatteryFault::None ? result_.battery_fault :
        fault == DriveEnergyFault::Clock ? BatteryFault::ClockError :
        fault == DriveEnergyFault::Numerical ? BatteryFault::NumericalError : BatteryFault::PowerUnavailable;
    return result_;
}
DriveEnergyStep DriveEnergyModel::step(const DriveEnergyInterval& interval, const BatterySensorCapture& capture) {
    if (result_.fault != DriveEnergyFault::None) return result_;
    if (interval.end_ns < last_observed_ns_) return fail(DriveEnergyFault::Clock);
    last_observed_ns_ = interval.end_ns;
    if (interval.begin_ns != state_.identity.source_time_ns || interval.end_ns <= interval.begin_ns ||
        interval.end_ns-interval.begin_ns > config_.max_step_ns) return fail(DriveEnergyFault::Timing);
    const auto& in = interval.inputs;
    if (!in.actual_torque_nm || !in.wheel_speed_rad_s || !in.auxiliary_w) return fail(DriveEnergyFault::Unavailable);
    const auto old = previous_.value_or(DriveEnergyInputs{});
    const CheckContext context{state_.identity.epoch, initialization_ns_, interval.begin_ns, interval.end_ns, config_.max_input_age_ns};
    const std::array issues{check(*in.actual_torque_nm, old.actual_torque_nm, context),
        check(*in.wheel_speed_rad_s, old.wheel_speed_rad_s, context), check(*in.auxiliary_w, old.auxiliary_w, context)};
    const auto issue = std::find_if(issues.begin(), issues.end(), [](auto value) { return value != DriveEnergyFault::None; });
    if (issue != issues.end()) return fail(*issue);
    const auto times = {in.actual_torque_nm->identity.source_time_ns, in.wheel_speed_rad_s->identity.source_time_ns,
        in.auxiliary_w->identity.source_time_ns};
    const auto bounds = std::minmax_element(times.begin(), times.end());
    if (*bounds.second-*bounds.first > config_.max_source_skew_ns) return fail(DriveEnergyFault::Skew);
    const auto torque = in.actual_torque_nm->value, speed = in.wheel_speed_rad_s->value, aux = in.auxiliary_w->value;
    if (!std::isfinite(torque) || std::abs(torque) > config_.maximum_abs_torque_nm || !std::isfinite(speed) || speed < 0 ||
        speed > config_.maximum_speed_rad_s || !std::isfinite(aux) || aux < 0) return fail(DriveEnergyFault::Value);
    const auto motor = calculate_motor_power(config_, torque, speed);
    if (!motor) return fail(DriveEnergyFault::Numerical);
    const auto mechanical_w = motor->mechanical_w, loss_w = motor->loss_w, dc_w = motor->dc_w;
    const auto seconds = static_cast<double>(interval.end_ns-interval.begin_ns)/1e9;
    auto mechanical = mechanical_, losses = losses_;
    mechanical.add(mechanical_w*seconds); losses.add(loss_w*seconds);
    if (!std::isfinite(dc_w) || !std::isfinite(loss_w) || !std::isfinite(mechanical.value) || !std::isfinite(losses.value)) {
        return fail(DriveEnergyFault::Numerical);
    }
    const auto dependency = std::min({in.actual_torque_nm->input_time_ns, in.wheel_speed_rad_s->input_time_ns, in.auxiliary_w->input_time_ns});
    const ActualBatteryPower power{{state_.identity.epoch, state_.identity.sequence, interval.begin_ns}, dependency, dc_w, aux};
    const auto battery_result = battery_.step({interval.begin_ns, interval.end_ns, power}, capture);
    if (battery_result.fault != BatteryFault::None) {
        result_ = {DriveEnergyFault::Battery, battery_result.fault, battery_result.boundary_excess_j};
        return fail(DriveEnergyFault::Battery);
    }
    mechanical_ = mechanical; losses_ = losses; previous_ = in;
    const auto& battery = battery_.diagnostic_state();
    const auto balance = battery.initial_energy_j-battery.energy_j-
        (mechanical.value+losses.value+battery.auxiliary_j+battery.ohmic_loss_j);
    state_ = {battery.identity, mechanical_w, loss_w, dc_w, mechanical.value, losses.value, balance};
    if (!std::isfinite(balance) || std::abs(balance) > balance_tolerance_j_) return fail(DriveEnergyFault::Numerical);
    observation_ = battery_.observation();
    return result_;
}
}  // namespace stratadrive::simulation
