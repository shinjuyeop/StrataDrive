#include "power_controller.hpp"

#include <cmath>
#include <limits>
#include <stdexcept>

namespace stratadrive::vecu {
namespace {
bool all_open(power::ContactorPositions p) { return !p.positive && !p.negative && !p.precharge; }
bool same(power::ContactorPositions a, power::ContactorPositions b) {
    return a.positive == b.positive && a.negative == b.negative && a.precharge == b.precharge;
}
bool same(const power::SensorSnapshot& a, const power::SensorSnapshot& b) {
    return a.input_time_ns == b.input_time_ns && a.pack_voltage_v == b.pack_voltage_v && a.bus_voltage_v == b.bus_voltage_v &&
        a.pack_current_a == b.pack_current_a && a.contactors.has_value() == b.contactors.has_value() &&
        (!a.contactors || same(*a.contactors, *b.contactors)) &&
        a.conditions.lv_available == b.conditions.lv_available && a.conditions.interlock_closed == b.conditions.interlock_closed &&
        a.conditions.isolation_ok == b.conditions.isolation_ok && a.conditions.charger_connected == b.conditions.charger_connected &&
        a.conditions.power_fault == b.conditions.power_fault;
}
bool complete(const power::SensorSnapshot& s) {
    const auto& c = s.conditions;
    return s.pack_voltage_v && s.bus_voltage_v && s.pack_current_a && s.contactors &&
        c.lv_available && c.interlock_closed && c.isolation_ok && c.charger_connected && c.power_fault;
}
bool conditions_safe(const power::SensorSnapshot& s) {
    const auto& c = s.conditions;
    return c.lv_available == true && c.interlock_closed == true && c.isolation_ok == true &&
        c.charger_connected == false && c.power_fault == false;
}
bool voltage_ready(const power::SensorSnapshot& s, const PowerControllerConfig& c) {
    return s.pack_voltage_v && s.bus_voltage_v && *s.pack_voltage_v >= c.minimum_pack_v && *s.pack_voltage_v <= c.maximum_pack_v &&
        *s.bus_voltage_v >= *s.pack_voltage_v*c.precharge_ratio && std::abs(*s.pack_voltage_v-*s.bus_voltage_v) <= c.ready_delta_v;
}
bool energizing(PowerPhase p) { return p >= PowerPhase::Checks && p <= PowerPhase::Ready; }
can::BmsPowerState wire_state(PowerPhase p) {
    if (p == PowerPhase::Off) return can::BmsPowerState::Off;
    if (p == PowerPhase::Checks) return can::BmsPowerState::Checks;
    if (p >= PowerPhase::CloseNegative && p <= PowerPhase::OpenPrecharge) return can::BmsPowerState::Precharge;
    if (p == PowerPhase::Ready) return can::BmsPowerState::HvReady;
    return can::BmsPowerState::Shutdown;
}
}  // namespace
PowerController::PowerController(PowerControllerConfig config) : config_(config),
    requests_({can::BmsFrameKind::PowerRequest, config.physical, config.max_source_age_ns, config.max_dependency_age_ns}) {
    if (!std::isfinite(config.minimum_pack_v) || !std::isfinite(config.maximum_pack_v) ||
        !std::isfinite(config.off_bus_max_v) || !std::isfinite(config.precharge_ratio) ||
        !std::isfinite(config.ready_delta_v) || !std::isfinite(config.opening_current_max_a) ||
        config.off_bus_max_v < 0 || config.off_bus_max_v >= config.minimum_pack_v || config.minimum_pack_v >= config.maximum_pack_v ||
        config.maximum_pack_v > config.physical.voltage_v.maximum || config.precharge_ratio <= 0 || config.precharge_ratio >= 1 ||
        config.ready_delta_v <= 0 || config.ready_delta_v > config.minimum_pack_v || config.opening_current_max_a <= 0 ||
        config.period_ns == 0 || config.max_tick_gap_ns < config.period_ns || config.max_tick_gap_ns > config.max_source_age_ns ||
        config.max_source_age_ns > 50000000 || config.max_dependency_age_ns > 70000000 ||
        config.max_dependency_age_ns < config.max_source_age_ns || config.checks_dwell_ns < config.period_ns ||
        config.ready_dwell_ns < config.period_ns || config.current_dwell_ns < config.period_ns ||
        config.checks_timeout_ns <= config.checks_dwell_ns || config.contactor_timeout_ns <= config.period_ns ||
        config.precharge_timeout_ns <= config.ready_dwell_ns || config.shutdown_current_timeout_ns <= config.current_dwell_ns ||
        config.discharge_timeout_ns <= config.period_ns) throw std::invalid_argument("PowerController configuration");
}
bool PowerController::start_session(std::uint32_t application_epoch, std::uint32_t model_epoch, std::uint64_t enable_ns) {
    if (application_epoch == 0 || model_epoch == 0 || (epoch_ != 0 && (application_epoch <= epoch_ ||
        model_epoch < model_epoch_ || enable_ns < last_observed_ns_)) || !requests_.start_session(application_epoch, enable_ns)) return false;
    epoch_ = application_epoch; model_epoch_ = model_epoch; enable_ns_ = last_observed_ns_ = phase_since_ns_ = enable_ns;
    previous_.reset(); previous_gate_.reset(); last_request_.reset(); last_tick_ns_.reset(); dwell_ = {};
    output_ = {}; sequence_ = 0; stopped_ = qualified_ = false; // no plant reset and no coil write at INIT
    return true;
}
void PowerController::fail(PowerControlFault fault) {
    if (fault != PowerControlFault::None && (output_.fault == PowerControlFault::None || fault == PowerControlFault::ClockError ||
        fault == PowerControlFault::ControlDeadline || fault == PowerControlFault::SequenceExhausted)) output_.fault = fault;
    output_.inhibit_drive = true;
}
can::BmsReceiveResult PowerController::receive(const can::BmsFrame& frame, std::uint64_t now_ns, const can::BmsParentContext* parent) {
    if (epoch_ != 0 && now_ns < last_observed_ns_) { fail(PowerControlFault::ClockError); stopped_ = true; output_.coils.reset(); }
    if (now_ns > last_observed_ns_) last_observed_ns_ = now_ns;
    auto result = requests_.receive(frame, now_ns, parent);
    if (result.decision == can::ActuatorReceiveDecision::Accepted && result.quality[0] == can::BmsFieldQuality::Usable) {
        last_request_ = requests_.last_accepted()->message;
    }
    return result;
}
void PowerController::mark_continuity_lost(std::uint64_t now_ns) {
    if (now_ns < last_observed_ns_) { fail(PowerControlFault::ClockError); stopped_ = true; output_.coils.reset(); return; }
    last_observed_ns_ = now_ns;
    requests_.mark_continuity_lost(now_ns); fail(PowerControlFault::ContinuityLost);
}
bool PowerController::Dwell::observe(bool condition, std::uint64_t source_ns, std::uint64_t duration_ns) {
    if (!condition) { first.reset(); last.reset(); return false; }
    if (!last || source_ns < *last || source_ns-*last > 50000000) first = source_ns;
    last = source_ns;
    return source_ns-*first >= duration_ns;
}
bool PowerController::valid_sensor(const power::SensorSnapshot& s, std::uint64_t now_ns) const {
    if (s.identity.epoch != model_epoch_ || s.input_time_ns < enable_ns_ || s.input_time_ns > s.identity.source_time_ns ||
        s.identity.source_time_ns > now_ns || now_ns-s.identity.source_time_ns > config_.max_source_age_ns ||
        now_ns-s.input_time_ns > config_.max_dependency_age_ns) return false;
    const auto in_range = [](std::optional<double> x, can::ActuatorValueRange range) {
        return !x || (std::isfinite(*x) && *x >= range.minimum && *x <= range.maximum);
    };
    if (!in_range(s.pack_voltage_v, config_.physical.voltage_v) || !in_range(s.bus_voltage_v, config_.physical.voltage_v) ||
        !in_range(s.pack_current_a, config_.physical.current_a)) return false;
    if (previous_) {
        const auto& old = *previous_;
        const bool cached = s.identity.sequence == old.identity.sequence;
        if (s.identity.sequence < old.identity.sequence || s.input_time_ns < old.input_time_ns ||
            (cached && (s.identity.source_time_ns != old.identity.source_time_ns || !same(s, old))) ||
            (!cached && s.identity.source_time_ns <= old.identity.source_time_ns)) return false;
    }
    return true;
}
bool PowerController::bms_allows(const std::optional<power::BmsSafetyGate>& gate, std::uint64_t now_ns) {
    if (!gate || gate->application_epoch != epoch_ || !gate->inhibit || gate->input_time_ns < enable_ns_ ||
        gate->input_time_ns > gate->source_time_ns || gate->source_time_ns > now_ns ||
        now_ns-gate->source_time_ns > config_.max_source_age_ns || now_ns-gate->input_time_ns > config_.max_dependency_age_ns) return false;
    if (previous_gate_) {
        const auto& old = *previous_gate_;
        const bool cached = gate->sequence == old.sequence;
        if (gate->sequence < old.sequence || gate->input_time_ns < old.input_time_ns ||
            (cached && (gate->source_time_ns != old.source_time_ns || gate->input_time_ns != old.input_time_ns || gate->inhibit != old.inhibit)) ||
            (!cached && gate->source_time_ns <= old.source_time_ns)) return false;
    }
    previous_gate_ = gate;
    return !*gate->inhibit;
}
void PowerController::enter(PowerPhase phase, std::uint64_t now_ns) {
    if (phase == PowerPhase::CloseNegative) qualified_ = true;
    output_.phase = phase; phase_since_ns_ = now_ns; dwell_ = {}; output_.inhibit_drive = phase != PowerPhase::Ready;
    if (phase == PowerPhase::Off || phase == PowerPhase::Checks || phase == PowerPhase::Discharging) output_.coils = power::CoilCommand{{}, true};
    if (phase == PowerPhase::CloseNegative) output_.coils = power::CoilCommand{{false, true, false}, false};
    if (phase == PowerPhase::Precharging) output_.coils = power::CoilCommand{{false, true, true}, false};
    if (phase == PowerPhase::ClosePositive) output_.coils = power::CoilCommand{{true, true, true}, false};
    if (phase == PowerPhase::OpenPrecharge || phase == PowerPhase::Ready) output_.coils = power::CoilCommand{{true, true, false}, false};
    if (phase == PowerPhase::OpenContactors) output_.coils = power::CoilCommand{};
}
void PowerController::shutdown(PowerControlFault fault, std::uint64_t now_ns, const power::SensorSnapshot* sensor) {
    fail(fault);
    if (output_.phase >= PowerPhase::WaitCurrent) return;
    // Cancel unconfirmed closing targets using fresh actual feedback. Keep the
    // already-closed path until measured current is low; never infer zero current.
    if (sensor && sensor->contactors) output_.coils = power::CoilCommand{*sensor->contactors, false};
    else output_.coils.reset(); // no invented coil action when actual contacts are unknown
    enter(PowerPhase::WaitCurrent, now_ns);
}
std::optional<can::BmsMessage> PowerController::tick(const std::optional<power::SensorSnapshot>& sensors,
        const std::optional<power::BmsSafetyGate>& bms, std::uint64_t now_ns) {
    if (epoch_ == 0 || stopped_) return std::nullopt;
    if (now_ns < last_observed_ns_) { fail(PowerControlFault::ClockError); stopped_ = true; output_.coils.reset(); return std::nullopt; }
    last_observed_ns_ = now_ns;
    if (last_tick_ns_ && now_ns-*last_tick_ns_ < config_.period_ns) return std::nullopt;
    const bool deadline = now_ns-last_tick_ns_.value_or(enable_ns_) > config_.max_tick_gap_ns;
    last_tick_ns_ = now_ns;
    const auto* s = sensors && valid_sensor(*sensors, now_ns) ? &*sensors : nullptr;
    if (s) previous_ = *s;
    const bool bms_ok = bms_allows(bms, now_ns);
    auto request = requests_.current_sample(now_ns);
    std::optional<can::BmsPowerAction> action;
    if (request) action = std::get<can::BmsPowerRequest>(request->message.content).action;
    if (deadline) shutdown(PowerControlFault::ControlDeadline, now_ns, s);
    if (output_.fault != PowerControlFault::None && energizing(output_.phase)) shutdown(output_.fault, now_ns, s);
    if (!s || !complete(*s)) {
        dwell_ = {};
        if (output_.phase == PowerPhase::Off && qualified_) fail(PowerControlFault::InputsUnavailable);
        else if (output_.phase != PowerPhase::Inspect && output_.phase != PowerPhase::Off) shutdown(PowerControlFault::InputsUnavailable, now_ns, s);
    } else {
        if (output_.phase == PowerPhase::Inspect) {
            if (all_open(*s->contactors)) enter(*s->bus_voltage_v <= config_.off_bus_max_v ? PowerPhase::Off : PowerPhase::Discharging, now_ns);
            else shutdown(PowerControlFault::StartupEnergized, now_ns, s);
        }
        if (energizing(output_.phase)) {
            if (!action) shutdown(PowerControlFault::RequestLost, now_ns, s);
            else if (*action != can::BmsPowerAction::Enable) shutdown(PowerControlFault::None, now_ns, s);
            else if (!conditions_safe(*s)) shutdown(PowerControlFault::ConditionsUnsafe, now_ns, s);
            else if (output_.phase != PowerPhase::Checks && !bms_ok) shutdown(PowerControlFault::BmsInhibit, now_ns, s);
        }
        const auto elapsed = now_ns-phase_since_ns_;
        const auto& p = *s->contactors;
        switch (output_.phase) {
        case PowerPhase::Off:
            if (!all_open(p) || *s->bus_voltage_v > config_.off_bus_max_v) shutdown(PowerControlFault::StartupEnergized, now_ns, s);
            else if (output_.fault == PowerControlFault::None && action == can::BmsPowerAction::Enable &&
                request->message.source_time_ns >= phase_since_ns_) enter(PowerPhase::Checks, now_ns);
            break;
        case PowerPhase::Checks:
            if (!all_open(p)) shutdown(PowerControlFault::ContactorResponse, now_ns, s);
            else if (dwell_.observe(bms_ok && conditions_safe(*s) && *s->pack_voltage_v >= config_.minimum_pack_v &&
                *s->pack_voltage_v <= config_.maximum_pack_v && *s->bus_voltage_v <= config_.off_bus_max_v,
                s->identity.source_time_ns, config_.checks_dwell_ns)) enter(PowerPhase::CloseNegative, now_ns);
            else if (elapsed >= config_.checks_timeout_ns) shutdown(PowerControlFault::BmsInhibit, now_ns, s);
            break;
        case PowerPhase::CloseNegative:
            if (p.positive || p.precharge || (!p.negative && elapsed >= config_.contactor_timeout_ns)) shutdown(PowerControlFault::ContactorResponse, now_ns, s);
            else if (p.negative) enter(PowerPhase::Precharging, now_ns);
            break;
        case PowerPhase::Precharging:
            if (!p.negative || p.positive) shutdown(PowerControlFault::ContactorResponse, now_ns, s);
            else if (dwell_.observe(p.precharge && voltage_ready(*s, config_), s->identity.source_time_ns, config_.ready_dwell_ns)) enter(PowerPhase::ClosePositive, now_ns);
            else if (elapsed >= config_.precharge_timeout_ns) shutdown(PowerControlFault::PrechargeTimeout, now_ns, s);
            break;
        case PowerPhase::ClosePositive:
            if (!p.negative || !p.precharge || !voltage_ready(*s, config_)) shutdown(PowerControlFault::BusNotReady, now_ns, s);
            else if (p.positive) enter(PowerPhase::OpenPrecharge, now_ns);
            else if (elapsed >= config_.contactor_timeout_ns) shutdown(PowerControlFault::ContactorResponse, now_ns, s);
            break;
        case PowerPhase::OpenPrecharge:
            if (!p.negative || !p.positive || !voltage_ready(*s, config_)) shutdown(PowerControlFault::BusNotReady, now_ns, s);
            else if (!p.precharge) enter(PowerPhase::Ready, now_ns);
            else if (elapsed >= config_.contactor_timeout_ns) shutdown(PowerControlFault::ContactorResponse, now_ns, s);
            break;
        case PowerPhase::Ready:
            if (!p.positive || !p.negative || p.precharge) shutdown(PowerControlFault::ContactorResponse, now_ns, s);
            else if (!voltage_ready(*s, config_)) shutdown(PowerControlFault::BusNotReady, now_ns, s);
            break;
        case PowerPhase::WaitCurrent:
            if (dwell_.observe(std::abs(*s->pack_current_a) <= config_.opening_current_max_a, s->identity.source_time_ns,
                config_.current_dwell_ns)) enter(PowerPhase::OpenContactors, now_ns);
            else if (elapsed >= config_.shutdown_current_timeout_ns) { fail(PowerControlFault::ShutdownCurrentBlocked); output_.shutdown_blocked = true; }
            break;
        case PowerPhase::OpenContactors:
            if (all_open(p)) enter(PowerPhase::Discharging, now_ns);
            else if (elapsed >= config_.contactor_timeout_ns) { fail(PowerControlFault::ContactorResponse); output_.shutdown_blocked = true; }
            break;
        case PowerPhase::Discharging:
            if (!all_open(p)) { fail(PowerControlFault::ContactorResponse); output_.shutdown_blocked = true; output_.coils = power::CoilCommand{}; }
            else if (*s->bus_voltage_v <= config_.off_bus_max_v) { enter(PowerPhase::Off, now_ns); output_.shutdown_blocked = false; }
            else if (elapsed >= config_.discharge_timeout_ns) { fail(PowerControlFault::DischargeTimeout); output_.shutdown_blocked = true; }
            break;
        case PowerPhase::Inspect: break;
        }
    }
    if ((output_.phase == PowerPhase::WaitCurrent && now_ns-phase_since_ns_ >= config_.shutdown_current_timeout_ns) ||
        (output_.phase == PowerPhase::OpenContactors && now_ns-phase_since_ns_ >= config_.contactor_timeout_ns) ||
        (output_.phase == PowerPhase::Discharging && now_ns-phase_since_ns_ >= config_.discharge_timeout_ns)) {
        output_.shutdown_blocked = true;
    }
    if (sequence_ == std::numeric_limits<std::uint32_t>::max()) {
        fail(PowerControlFault::SequenceExhausted); stopped_ = true; output_.coils.reset(); return std::nullopt;
    }
    can::BmsMessage message;
    message.kind = can::BmsFrameKind::PowerStatus; message.epoch = epoch_; message.sequence = sequence_++; message.source_time_ns = now_ns;
    message.causal_sequence = last_request_ ? last_request_->sequence : 0;
    message.local_state = output_.fault != PowerControlFault::None ? can::ActuatorLocalState::FailSafe :
        qualified_ ? can::ActuatorLocalState::Normal : can::ActuatorLocalState::Init;
    message.origin = output_.fault != PowerControlFault::None ? can::ActuatorOrigin::LocalProtection :
        last_request_ ? can::ActuatorOrigin::NormalPath : can::ActuatorOrigin::NoAcceptedInput;
    can::BmsPowerStatus status;
    status.accepted_request_source_time_ns = last_request_ ? last_request_->source_time_ns : 0;
    if (s) {
        if (output_.phase != PowerPhase::Inspect) status.state = wire_state(output_.phase);
        status.input_time_ns = s->input_time_ns; status.input_sequence = s->identity.sequence;
        if (s->contactors) { status.positive_contactor_closed = s->contactors->positive;
            status.negative_contactor_closed = s->contactors->negative; status.precharge_contactor_closed = s->contactors->precharge; }
        status.hv_bus_voltage_v = s->bus_voltage_v;
        const std::array<std::optional<bool>, 5> bits{s->conditions.lv_available, s->conditions.interlock_closed,
            s->conditions.isolation_ok, s->conditions.charger_connected,
            output_.fault != PowerControlFault::None ? std::optional<bool>{true} : s->conditions.power_fault};
        for (std::size_t i = 0; i < bits.size(); ++i) if (bits[i]) {
            status.condition_validity |= static_cast<std::uint8_t>(1U << i);
            if (*bits[i]) status.condition_bits |= static_cast<std::uint8_t>(1U << i);
        }
    }
    if (!status.state && !status.positive_contactor_closed && !status.negative_contactor_closed &&
        !status.precharge_contactor_closed && !status.hv_bus_voltage_v && status.condition_validity == 0) {
        status.input_time_ns = 0; status.input_sequence = 0;
    }
    message.content = status;
    return message;
}
}  // namespace stratadrive::vecu
