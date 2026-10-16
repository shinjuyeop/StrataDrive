#include "brake_response_monitor.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace stratadrive::vecu {
BrakeResponseMonitor::BrakeResponseMonitor(BrakeMonitorConfig config) : config_(config) {
    if (!std::isfinite(config.maximum_pa) || !std::isfinite(config.minimum_rise_pa_s) ||
        !std::isfinite(config.maximum_rise_pa_s) || !std::isfinite(config.minimum_fall_pa_s) ||
        !std::isfinite(config.maximum_fall_pa_s) || !std::isfinite(config.tolerance_pa) ||
        config.maximum_pa <= 0 || config.minimum_rise_pa_s <= 0 || config.minimum_fall_pa_s <= 0 ||
        config.maximum_rise_pa_s < config.minimum_rise_pa_s || config.maximum_fall_pa_s < config.minimum_fall_pa_s ||
        config.tolerance_pa <= 0 || config.tolerance_pa >= config.maximum_pa || config.confirmation_ns == 0 ||
        config.sensor_age_ns == 0 || config.sample_gap_ns == 0) throw std::invalid_argument("BrakeMonitor configuration");
}
bool BrakeResponseMonitor::begin(std::uint32_t model_epoch, std::uint64_t enable_ns) {
    if (model_epoch == 0 || (model_epoch_ != 0 && enable_ns < last_observed_ns_)) return false;
    model_epoch_ = model_epoch; enable_ns_ = last_observed_ns_ = cursor_ns_ = enable_ns;
    head_ = size_ = 0; staged_.reset(); previous_.reset(); seeded_ = false;
    decision_ = {}; decision_.fault = BrakeMonitorFault::None; return true;
}
bool BrakeResponseMonitor::set_target(double pressure, std::uint64_t now_ns) {
    if (model_epoch_ == 0 || decision_.fault != BrakeMonitorFault::None || now_ns < last_observed_ns_ ||
        !std::isfinite(pressure) || pressure < 0 || pressure > config_.maximum_pa) return false;
    last_observed_ns_ = now_ns;
    if (staged_ && *staged_ == pressure) return true;
    if (size_ == pending_.size() || now_ns > std::numeric_limits<std::uint64_t>::max()-config_.delay_ns) return false;
    pending_[(head_+size_)%pending_.size()] = {pressure, now_ns+config_.delay_ns};
    ++size_; staged_ = pressure; return true;
}
void BrakeResponseMonitor::latch(BrakeMonitorFault fault, std::uint64_t now_ns) {
    if (decision_.fault == BrakeMonitorFault::None || fault == BrakeMonitorFault::ClockError) {
        decision_.fault = fault; decision_.detected_time_ns = now_ns;
    }
}
void BrakeResponseMonitor::move(std::uint64_t elapsed_ns) {
    const auto seconds = static_cast<double>(elapsed_ns)/1e9;
    const auto project = [&](double x, double rise, double fall) {
        const auto distance = (target_ >= x ? rise : fall)*seconds;
        return x+std::clamp(target_-x, -distance, distance);
    };
    lower_ = std::min(project(lower_, config_.minimum_rise_pa_s, config_.minimum_fall_pa_s),
                      project(lower_, config_.maximum_rise_pa_s, config_.maximum_fall_pa_s));
    upper_ = std::max(project(upper_, config_.minimum_rise_pa_s, config_.minimum_fall_pa_s),
                      project(upper_, config_.maximum_rise_pa_s, config_.maximum_fall_pa_s));
}
void BrakeResponseMonitor::predict(std::uint64_t source_ns) {
    while (size_ != 0 && pending_[head_].due_ns <= source_ns) {
        const auto demand = pending_[head_];
        if (seeded_) move(demand.due_ns-cursor_ns_);
        cursor_ns_ = demand.due_ns; target_ = demand.pressure;
        head_ = (head_+1)%pending_.size(); --size_;
    }
    if (seeded_) move(source_ns-cursor_ns_);
    cursor_ns_ = source_ns;
}
const BrakeMonitorDecision& BrakeResponseMonitor::observe(const std::optional<brake::PressureMeasurement>& sensor,
        std::uint64_t now_ns, bool tracking_enabled) {
    decision_.new_measurement = false; decision_.measured_pa.reset(); decision_.source_time_ns.reset();
    if (model_epoch_ == 0) return decision_;
    if (now_ns < last_observed_ns_) { latch(BrakeMonitorFault::ClockError, now_ns); return decision_; }
    last_observed_ns_ = now_ns;
    if (!sensor) { latch(BrakeMonitorFault::SensorUnavailable, now_ns); return decision_; }
    const auto& s = *sensor;
    if (s.model_epoch != model_epoch_ || s.source_time_ns < enable_ns_ || s.source_time_ns > now_ns ||
        !std::isfinite(s.pressure_pa) || s.pressure_pa < 0 || s.pressure_pa > config_.maximum_pa) {
        latch(BrakeMonitorFault::SensorInvalid, now_ns); return decision_;
    }
    if (now_ns-s.source_time_ns > config_.sensor_age_ns) { latch(BrakeMonitorFault::SensorUnavailable, now_ns); return decision_; }
    const bool cached = previous_ && s.sequence == previous_->sequence;
    if (previous_ && (s.sequence < previous_->sequence ||
        (cached && (s.source_time_ns != previous_->source_time_ns || s.pressure_pa != previous_->pressure_pa)) ||
        (!cached && s.source_time_ns <= previous_->source_time_ns))) {
        latch(BrakeMonitorFault::SensorInvalid, now_ns); return decision_;
    }
    if (previous_ && !cached && s.source_time_ns-previous_->source_time_ns > config_.sample_gap_ns) {
        // Lost observation continuity latches the fault; the independently
        // valid current acquisition can still report pressure under FAIL_SAFE.
        latch(BrakeMonitorFault::SensorUnavailable, now_ns);
    }
    decision_.measured_pa = s.pressure_pa; decision_.source_time_ns = s.source_time_ns;
    if (cached) return decision_; // repeated polling cannot confirm a fault
    previous_ = s; decision_.new_measurement = true;
    if (decision_.fault != BrakeMonitorFault::None) return decision_;
    predict(s.source_time_ns);
    if (!seeded_ || !tracking_enabled) {
        lower_ = upper_ = s.pressure_pa;
        if (!seeded_ && !staged_) target_ = s.pressure_pa;
        if (!tracking_enabled) { head_ = size_ = 0; staged_.reset(); target_ = s.pressure_pa; }
        seeded_ = true; decision_.violation_since_ns.reset(); decision_.residual_pa = 0;
    }
    decision_.expected_min_pa = lower_; decision_.expected_max_pa = upper_;
    if (!tracking_enabled) return decision_;
    decision_.residual_pa = std::max({lower_-s.pressure_pa, s.pressure_pa-upper_, 0.0});
    const auto low = std::nextafter(lower_-config_.tolerance_pa, -std::numeric_limits<double>::infinity());
    const auto high = std::nextafter(upper_+config_.tolerance_pa, std::numeric_limits<double>::infinity());
    if (s.pressure_pa < low || s.pressure_pa > high) {
        if (!decision_.violation_since_ns) decision_.violation_since_ns = s.source_time_ns;
        if (s.source_time_ns-*decision_.violation_since_ns >= config_.confirmation_ns) latch(BrakeMonitorFault::ResponseError, now_ns);
    } else decision_.violation_since_ns.reset();
    return decision_;
}
}  // namespace stratadrive::vecu
