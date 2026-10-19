#include "bms_controller.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace stratadrive::vecu {
namespace {
bool finite(double x) { return std::isfinite(x); }
bool valid_band(BmsProtectionBand b) {
    return finite(b.trip_low) && finite(b.release_low) && finite(b.release_high) && finite(b.trip_high) &&
           b.trip_low < b.release_low && b.release_low <= b.release_high && b.release_high < b.trip_high;
}
bool valid_window(BmsTemperatureWindow w) {
    return finite(w.cold_stop) && finite(w.cold_full) && finite(w.hot_full) && finite(w.hot_stop) &&
           w.cold_stop < w.cold_full && w.cold_full <= w.hot_full && w.hot_full < w.hot_stop;
}
bool valid_ramp(BmsRamp r, bool increasing) {
    return finite(r.zero) && finite(r.full) && (increasing ? r.zero < r.full : r.zero > r.full);
}
double ramp(double value, BmsRamp r) { return std::clamp((value-r.zero)/(r.full-r.zero), 0.0, 1.0); }
double temperature_factor(double low, double high, BmsTemperatureWindow w) {
    return std::min(ramp(low, {w.cold_stop, w.cold_full}), ramp(high, {w.hot_stop, w.hot_full}));
}
bool in_release(double low, double high, BmsProtectionBand band) {
    return low >= band.release_low && high <= band.release_high;
}
bool equal_value(double a, double b) { return a == b; }
bool equal_value(battery::ElectricalPair a, battery::ElectricalPair b) {
    return a.voltage_v == b.voltage_v && a.current_a == b.current_a;
}
bool equal_value(battery::CellExtrema a, battery::CellExtrema b) {
    return a.minimum == b.minimum && a.maximum == b.maximum;
}
struct SensorCheckContext {
    const battery::ModelIdentity& batch;
    std::uint64_t enable_ns, now_ns;
    const BmsControllerConfig& config;
};
template <typename T> BmsInputIssue check_group(const battery::ModelMeasurement<T>& value,
        const std::optional<battery::ModelMeasurement<T>>& previous, const SensorCheckContext& context) {
    const auto& id = value.identity;
    if (id.epoch != context.batch.epoch || id.sequence > context.batch.sequence) return BmsInputIssue::Identity;
    if (value.input_time_ns < context.enable_ns || value.input_time_ns > id.source_time_ns ||
        id.source_time_ns > context.batch.source_time_ns) return BmsInputIssue::Timestamp;
    if (context.now_ns-id.source_time_ns > context.config.max_source_age_ns ||
        context.now_ns-value.input_time_ns > context.config.max_dependency_age_ns) return BmsInputIssue::Stale;
    if (previous) {
        const auto& old = *previous;
        const bool cached = id.sequence == old.identity.sequence;
        if (id.sequence < old.identity.sequence || value.input_time_ns < old.input_time_ns ||
            (cached && (id.source_time_ns != old.identity.source_time_ns ||
             value.input_time_ns != old.input_time_ns || !equal_value(value.value, old.value))) ||
            (!cached && id.source_time_ns <= old.identity.source_time_ns)) return BmsInputIssue::Identity;
    }
    return BmsInputIssue::None;
}
bool valid_extrema(battery::CellExtrema x, double low, double high) {
    return finite(x.minimum) && finite(x.maximum) && x.minimum >= low && x.minimum <= x.maximum && x.maximum <= high;
}
struct DirectionalLimit { double current_a, power_w; can::BmsLimitReason reason; };
struct LimitFactors { double soc, temperature, cell; };
DirectionalLimit limit(const BmsControllerConfig& config, bool charging, double voltage, LimitFactors factors) {
    // Deterministic tie priority: SOC, temperature, cell voltage. Nominal when all factors are one.
    auto factor = factors.soc;
    auto reason = factors.soc < 1 ? can::BmsLimitReason::SocLimited : can::BmsLimitReason::Nominal;
    if (factors.temperature < factor) { factor = factors.temperature; reason = can::BmsLimitReason::TemperatureLimited; }
    if (factors.cell < factor) { factor = factors.cell; reason = can::BmsLimitReason::ElectricalLimited; }
    const auto current = charging ? config.charge_current_a : config.discharge_current_a;
    const auto max_power = charging ? config.max_charge_power_w : config.max_discharge_power_w;
    const auto allowed_power = std::min(max_power, voltage * current * factor);
    // The CAN step is 10 W. Round DOWN here; the generic codec rounds to nearest.
    const auto wire_power = std::max(0.0, std::floor(allowed_power/10.0)*10.0);
    return {voltage > 0 ? wire_power/voltage : 0, wire_power, reason};
}
}  // namespace

BmsController::BmsController(BmsControllerConfig config) : config_(config) {
    if (!finite(config.charge_current_a) || config.charge_current_a <= 0 || config.charge_current_a > 3276.7 ||
        !finite(config.discharge_current_a) || config.discharge_current_a <= 0 || config.discharge_current_a > 3276.7 ||
        !finite(config.max_charge_power_w) || config.max_charge_power_w <= 0 || config.max_charge_power_w > 655340 ||
        !finite(config.max_discharge_power_w) || config.max_discharge_power_w <= 0 || config.max_discharge_power_w > 655340 ||
        !valid_ramp(config.charge_soc, false) || !valid_ramp(config.discharge_soc, true) ||
        config.discharge_soc.zero < 0 || config.discharge_soc.full > config.charge_soc.full || config.charge_soc.zero > 1 ||
        !valid_ramp(config.charge_cell_v, false) || !valid_ramp(config.discharge_cell_v, true) ||
        !valid_window(config.charge_temperature) || !valid_window(config.discharge_temperature) ||
        !valid_band(config.cell_v) || !valid_band(config.pack_v) ||
        !valid_band(config.temperature_c) || !valid_band(config.current_a) ||
        config.cell_v.trip_low < 0 || config.cell_v.trip_high > 10 ||
        config.pack_v.trip_low < 0 || config.pack_v.trip_high > 6553.4 ||
        config.temperature_c.trip_low < -273.15 || config.temperature_c.trip_high > 3276.7 ||
        config.current_a.trip_low < -3276.7 || config.current_a.trip_high > 3276.7 ||
        config.cell_v.trip_low >= config.discharge_cell_v.zero ||
        config.discharge_cell_v.full > config.charge_cell_v.full || config.charge_cell_v.zero >= config.cell_v.trip_high ||
        config.temperature_c.trip_low >= std::min(config.charge_temperature.cold_stop, config.discharge_temperature.cold_stop) ||
        config.temperature_c.trip_high <= std::max(config.charge_temperature.hot_stop, config.discharge_temperature.hot_stop) ||
        config.current_a.trip_low >= -config.charge_current_a || config.current_a.trip_high <= config.discharge_current_a ||
        config.series_cells == 0 || config.series_cells > 1000 ||
        !finite(config.pack_extrema_tolerance_v) || config.pack_extrema_tolerance_v < 0 ||
        config.period_ns == 0 || config.max_tick_gap_ns < config.period_ns ||
        config.max_source_age_ns < config.max_tick_gap_ns || config.max_dependency_age_ns < config.max_source_age_ns ||
        config.max_dependency_age_ns > 70000000 || config.max_source_age_ns > 50000000 ||
        config.max_sensor_skew_ns > config.max_source_age_ns ||
        config.trip_dwell_ns < config.period_ns || config.release_dwell_ns < config.trip_dwell_ns ||
        config.release_dwell_ns > 10000000000ULL) throw std::invalid_argument("BmsController configuration");
}
bool BmsController::start_session(std::uint32_t application_epoch, std::uint32_t model_epoch, std::uint64_t enable_ns) {
    if (application_epoch == 0 || model_epoch == 0 || (application_epoch_ != 0 &&
        (application_epoch <= application_epoch_ || model_epoch < model_epoch_ || enable_ns < last_observed_ns_))) return false;
    application_epoch_ = application_epoch; model_epoch_ = model_epoch; enable_ns_ = last_observed_ns_ = enable_ns;
    sequence_ = 0; previous_.reset(); last_tick_ns_.reset(); trip_dwell_ = {}; release_dwell_ = {};
    stopped_ = false; decision_ = {}; decision_.state = BmsControlState::InitialChecks;
    power_gate_.reset();
    return true;
}
bool BmsController::Dwell::observe(bool condition, std::uint64_t source_ns, const BmsControllerConfig& config, Kind kind) {
    if (!condition) { first.reset(); last.reset(); return false; }
    if (!last || source_ns < *last || source_ns-*last > config.max_source_age_ns) first = source_ns;
    last = source_ns;
    return source_ns-*first >= (kind == Kind::Trip ? config.trip_dwell_ns : config.release_dwell_ns);
}
void BmsController::latch(BmsControlFault fault) {
    if (decision_.fault == BmsControlFault::None || fault == BmsControlFault::ClockError ||
        fault == BmsControlFault::ControlDeadline || fault == BmsControlFault::SequenceExhausted) decision_.fault = fault;
    decision_.state = BmsControlState::Latched;
}
void BmsController::request_local_protection(std::uint64_t now_ns) {
    if(application_epoch_==0) return;
    latch(now_ns<last_observed_ns_?BmsControlFault::ClockError:BmsControlFault::Protection);
    if(now_ns>=last_observed_ns_) last_observed_ns_=now_ns;
    decision_.limits={}; decision_.inhibit_requested=true;
    power_gate_.reset();
}
BmsInputIssue BmsController::validate(const battery::SensorSnapshot& s, std::uint64_t now_ns) const {
    if (!s.available) return BmsInputIssue::Unavailable;
    if (s.batch.epoch != model_epoch_) return BmsInputIssue::Identity;
    if (s.batch.source_time_ns < enable_ns_ || s.batch.source_time_ns > now_ns) return BmsInputIssue::Timestamp;
    if (previous_ && (s.batch.sequence < previous_->batch.sequence ||
        (s.batch.sequence == previous_->batch.sequence && s.batch.source_time_ns != previous_->batch.source_time_ns) ||
        (s.batch.sequence > previous_->batch.sequence && s.batch.source_time_ns <= previous_->batch.source_time_ns))) {
        return BmsInputIssue::Identity;
    }
    if (!s.soc || !s.electrical || !s.temperature || !s.cell_voltage || !s.cell_temperature) return BmsInputIssue::Unavailable;
    const auto old = previous_.value_or(battery::SensorSnapshot{});
    if (previous_ && s.batch.sequence == old.batch.sequence &&
        (s.soc->identity.sequence != old.soc->identity.sequence ||
         s.electrical->identity.sequence != old.electrical->identity.sequence ||
         s.temperature->identity.sequence != old.temperature->identity.sequence ||
         s.cell_voltage->identity.sequence != old.cell_voltage->identity.sequence ||
         s.cell_temperature->identity.sequence != old.cell_temperature->identity.sequence)) return BmsInputIssue::Identity;
    const SensorCheckContext context{s.batch, enable_ns_, now_ns, config_};
    const std::array<BmsInputIssue, 5> issues{
        check_group(*s.soc, old.soc, context), check_group(*s.electrical, old.electrical, context),
        check_group(*s.temperature, old.temperature, context), check_group(*s.cell_voltage, old.cell_voltage, context),
        check_group(*s.cell_temperature, old.cell_temperature, context)};
    for (const auto issue : issues) if (issue != BmsInputIssue::None) return issue;
    const auto times = std::array<std::uint64_t, 5>{s.soc->identity.source_time_ns, s.electrical->identity.source_time_ns,
        s.temperature->identity.source_time_ns, s.cell_voltage->identity.source_time_ns, s.cell_temperature->identity.source_time_ns};
    const auto bounds = std::minmax_element(times.begin(), times.end());
    if (*bounds.second-*bounds.first > config_.max_sensor_skew_ns) return BmsInputIssue::Skew;
    const auto& electrical = s.electrical->value;
    if (!finite(s.soc->value) || s.soc->value < 0 || s.soc->value > 1 ||
        !finite(electrical.voltage_v) || electrical.voltage_v < 0 || electrical.voltage_v > 6553.4 ||
        !finite(electrical.current_a) || std::abs(electrical.current_a) > 3276.7 ||
        !finite(s.temperature->value) || s.temperature->value < -273.15 || s.temperature->value > 3276.7 ||
        !valid_extrema(s.cell_voltage->value, 0, 10) || !valid_extrema(s.cell_temperature->value, -273.15, 3276.7)) {
        return BmsInputIssue::Value;
    }
    const auto cells = static_cast<double>(config_.series_cells);
    if (electrical.voltage_v+config_.pack_extrema_tolerance_v < s.cell_voltage->value.minimum*cells ||
        electrical.voltage_v-config_.pack_extrema_tolerance_v > s.cell_voltage->value.maximum*cells) return BmsInputIssue::Value;
    return BmsInputIssue::None;
}
void BmsController::evaluate(const battery::SensorSnapshot& s) {
    const auto& e = s.electrical->value;
    const auto& cv = s.cell_voltage->value;
    const auto low_t = std::min(s.temperature->value, s.cell_temperature->value.minimum);
    const auto high_t = std::max(s.temperature->value, s.cell_temperature->value.maximum);
    const auto temp_source = std::min(s.temperature->identity.source_time_ns, s.cell_temperature->identity.source_time_ns);
    const std::array<bool, 8> violations{cv.minimum <= config_.cell_v.trip_low, cv.maximum >= config_.cell_v.trip_high,
        e.voltage_v <= config_.pack_v.trip_low, e.voltage_v >= config_.pack_v.trip_high,
        low_t <= config_.temperature_c.trip_low, high_t >= config_.temperature_c.trip_high,
        e.current_a <= config_.current_a.trip_low, e.current_a >= config_.current_a.trip_high};
    const std::array<std::uint64_t, 8> sources{s.cell_voltage->identity.source_time_ns, s.cell_voltage->identity.source_time_ns,
        s.electrical->identity.source_time_ns, s.electrical->identity.source_time_ns, temp_source, temp_source,
        s.electrical->identity.source_time_ns, s.electrical->identity.source_time_ns};
    decision_.pending_trips = 0;
    for (std::size_t i = 0; i < violations.size(); ++i) {
        const auto bit = static_cast<std::uint16_t>(1U << i);
        if (violations[i]) decision_.pending_trips |= bit;
        if (trip_dwell_[i].observe(violations[i], sources[i], config_)) {
            decision_.latched_trips |= bit;
            latch(BmsControlFault::Protection);
        }
    }
    const auto safe_source = std::min({s.soc->identity.source_time_ns, s.electrical->identity.source_time_ns,
        s.temperature->identity.source_time_ns, s.cell_voltage->identity.source_time_ns, s.cell_temperature->identity.source_time_ns});
    const bool safe = in_release(cv.minimum, cv.maximum, config_.cell_v) &&
        in_release(e.voltage_v, e.voltage_v, config_.pack_v) && in_release(low_t, high_t, config_.temperature_c) &&
        in_release(e.current_a, e.current_a, config_.current_a);
    decision_.recovery_ready = release_dwell_.observe(safe, safe_source, config_, Dwell::Kind::Release);
    if (decision_.state == BmsControlState::InitialChecks && decision_.recovery_ready) decision_.state = BmsControlState::Active;
    const auto input_ns = std::min({s.soc->input_time_ns, s.electrical->input_time_ns, s.temperature->input_time_ns,
        s.cell_voltage->input_time_ns, s.cell_temperature->input_time_ns});
    if (decision_.state != BmsControlState::Active || decision_.pending_trips != 0) {
        decision_.limits = {0, 0, can::BmsLimitReason::Disabled, can::BmsLimitReason::Disabled, input_ns};
        decision_.charge_current_a = decision_.discharge_current_a = 0;
        decision_.inhibit_requested = true;
        return;
    }
    const auto charge = limit(config_, true, e.voltage_v,
        {ramp(s.soc->value, config_.charge_soc), temperature_factor(low_t, high_t, config_.charge_temperature),
         ramp(cv.maximum, config_.charge_cell_v)});
    const auto discharge = limit(config_, false, e.voltage_v,
        {ramp(s.soc->value, config_.discharge_soc), temperature_factor(low_t, high_t, config_.discharge_temperature),
         ramp(cv.minimum, config_.discharge_cell_v)});
    decision_.limits = {charge.power_w, discharge.power_w, charge.reason, discharge.reason, input_ns};
    decision_.charge_current_a = charge.current_a; decision_.discharge_current_a = discharge.current_a;
    decision_.inhibit_requested = charge.power_w == 0 && discharge.power_w == 0;
}
std::optional<can::BmsMessage> BmsController::tick(const battery::SensorSnapshot& inputs, std::uint64_t now_ns) {
    if (application_epoch_ == 0 || stopped_) return std::nullopt;
    if (now_ns < last_observed_ns_) {
        latch(BmsControlFault::ClockError); decision_.limits = {}; decision_.charge_current_a.reset();
        decision_.pending_trips = 0;
        decision_.discharge_current_a.reset(); decision_.inhibit_requested = true; decision_.recovery_ready = false; stopped_ = true;
        power_gate_.reset();
        return std::nullopt;
    }
    last_observed_ns_ = now_ns;
    if (last_tick_ns_ && now_ns-*last_tick_ns_ < config_.period_ns) return std::nullopt;
    if (now_ns-last_tick_ns_.value_or(enable_ns_) > config_.max_tick_gap_ns) latch(BmsControlFault::ControlDeadline);
    last_tick_ns_ = now_ns;
    decision_.input_issue = validate(inputs, now_ns);
    decision_.limits = {}; decision_.charge_current_a.reset(); decision_.discharge_current_a.reset();
    decision_.pending_trips = 0;
    decision_.inhibit_requested = true; decision_.recovery_ready = false;
    if (decision_.input_issue != BmsInputIssue::None) {
        release_dwell_ = {}; trip_dwell_ = {}; decision_.pending_trips = 0;
        if (decision_.state == BmsControlState::Active || decision_.input_issue != BmsInputIssue::Unavailable) latch(BmsControlFault::InputsInvalid);
    } else {
        previous_ = inputs;
        if (decision_.fault != BmsControlFault::ControlDeadline) evaluate(inputs);
    }
    if (sequence_ == std::numeric_limits<std::uint32_t>::max()) {
        latch(BmsControlFault::SequenceExhausted); decision_.limits = {}; decision_.inhibit_requested = true;
        decision_.charge_current_a.reset(); decision_.discharge_current_a.reset(); decision_.recovery_ready = false;
        power_gate_.reset(); stopped_ = true; return std::nullopt;
    }
    can::BmsMessage message;
    message.kind = can::BmsFrameKind::PowerLimits; message.epoch = application_epoch_; message.sequence = sequence_++;
    message.source_time_ns = now_ns; message.causal_sequence = previous_ ? previous_->batch.sequence : 0;
    message.local_state = decision_.state == BmsControlState::InitialChecks ? can::ActuatorLocalState::Init :
        decision_.state == BmsControlState::Latched ? can::ActuatorLocalState::FailSafe :
        (decision_.pending_trips != 0 || decision_.limits.charge_reason != can::BmsLimitReason::Nominal ||
         decision_.limits.discharge_reason != can::BmsLimitReason::Nominal) ? can::ActuatorLocalState::Degraded : can::ActuatorLocalState::Normal;
    message.origin = decision_.state == BmsControlState::InitialChecks ?
        (decision_.input_issue == BmsInputIssue::None ? can::ActuatorOrigin::NormalPath : can::ActuatorOrigin::NoAcceptedInput) :
        (decision_.state == BmsControlState::Latched || decision_.pending_trips != 0) ? can::ActuatorOrigin::LocalProtection : can::ActuatorOrigin::NormalPath;
    message.content = decision_.limits;
    power_gate_ = power::BmsSafetyGate{application_epoch_, message.sequence, now_ns, decision_.limits.input_time_ns,
        decision_.limits.charge_power_w && decision_.limits.discharge_power_w ?
            std::optional<bool>{decision_.inhibit_requested} : std::nullopt};
    return message;
}
}  // namespace stratadrive::vecu
