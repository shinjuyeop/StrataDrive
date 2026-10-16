#include "steering_response_monitor.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace stratadrive::vecu {
SteeringResponseMonitor::SteeringResponseMonitor(SteeringMonitorConfig config) : config_(config) {
    if (!std::isfinite(config.minimum_rad) || !std::isfinite(config.maximum_rad) ||
        !std::isfinite(config.maximum_rad-config.minimum_rad) || !std::isfinite(config.minimum_rate_rad_s) ||
        !std::isfinite(config.maximum_rate_rad_s) || !std::isfinite(config.tolerance_rad) ||
        config.minimum_rad >= config.maximum_rad || config.minimum_rate_rad_s <= 0 ||
        config.maximum_rate_rad_s < config.minimum_rate_rad_s || config.tolerance_rad <= 0 ||
        config.tolerance_rad >= config.maximum_rad-config.minimum_rad || config.confirmation_ns == 0 ||
        config.sensor_age_ns == 0 || config.sample_gap_ns == 0) throw std::invalid_argument("SteeringMonitor configuration");
}
bool SteeringResponseMonitor::begin(std::uint32_t model_epoch, std::uint64_t enable_ns) {
    if (model_epoch == 0 || (model_epoch_ != 0 && enable_ns < last_observed_ns_)) return false;
    model_epoch_ = model_epoch; enable_ns_ = last_observed_ns_ = cursor_ns_ = enable_ns;
    head_ = size_ = 0; staged_.reset(); previous_.reset(); seeded_ = false;
    decision_ = {}; decision_.fault = SteeringMonitorFault::None; return true;
}
bool SteeringResponseMonitor::set_target(double angle, std::uint64_t now_ns) {
    if (model_epoch_ == 0 || decision_.fault != SteeringMonitorFault::None || now_ns < last_observed_ns_ ||
        !std::isfinite(angle) || angle < config_.minimum_rad || angle > config_.maximum_rad) return false;
    last_observed_ns_ = now_ns;
    if (staged_ && *staged_ == angle) return true;
    if (size_ == pending_.size() || now_ns > std::numeric_limits<std::uint64_t>::max()-config_.delay_ns) return false;
    pending_[(head_+size_)%pending_.size()] = {angle, now_ns+config_.delay_ns};
    ++size_; staged_ = angle; return true;
}
void SteeringResponseMonitor::latch(SteeringMonitorFault fault, std::uint64_t now_ns) {
    if (decision_.fault == SteeringMonitorFault::None || fault == SteeringMonitorFault::ClockError) {
        decision_.fault = fault; decision_.detected_time_ns = now_ns;
    }
}
void SteeringResponseMonitor::move(std::uint64_t elapsed_ns) {
    const auto seconds = static_cast<double>(elapsed_ns)/1e9;
    const auto project = [&](double x, double rate) { return x+std::clamp(target_-x, -rate*seconds, rate*seconds); };
    lower_ = std::min(project(lower_, config_.minimum_rate_rad_s), project(lower_, config_.maximum_rate_rad_s));
    upper_ = std::max(project(upper_, config_.minimum_rate_rad_s), project(upper_, config_.maximum_rate_rad_s));
}
void SteeringResponseMonitor::predict(std::uint64_t source_ns) {
    while (size_ != 0 && pending_[head_].due_ns <= source_ns) {
        const auto demand = pending_[head_];
        if (seeded_) move(demand.due_ns-cursor_ns_);
        cursor_ns_ = demand.due_ns; target_ = demand.angle;
        head_ = (head_+1)%pending_.size(); --size_;
    }
    if (seeded_) move(source_ns-cursor_ns_);
    cursor_ns_ = source_ns;
}
const SteeringMonitorDecision& SteeringResponseMonitor::observe(const std::optional<steering::AngleMeasurement>& sensor,
        std::uint64_t now_ns, bool tracking_enabled) {
    decision_.new_measurement = false; decision_.measured_rad.reset(); decision_.source_time_ns.reset();
    if (model_epoch_ == 0) return decision_;
    if (now_ns < last_observed_ns_) { latch(SteeringMonitorFault::ClockError, now_ns); return decision_; }
    last_observed_ns_ = now_ns;
    if (!sensor) { latch(SteeringMonitorFault::SensorUnavailable, now_ns); return decision_; }
    const auto& s = *sensor;
    if (s.model_epoch != model_epoch_ || s.source_time_ns < enable_ns_ || s.source_time_ns > now_ns ||
        !std::isfinite(s.angle_rad) || s.angle_rad < config_.minimum_rad || s.angle_rad > config_.maximum_rad) {
        latch(SteeringMonitorFault::SensorInvalid, now_ns); return decision_;
    }
    if (now_ns-s.source_time_ns > config_.sensor_age_ns) { latch(SteeringMonitorFault::SensorUnavailable, now_ns); return decision_; }
    const bool cached = previous_ && s.sequence == previous_->sequence;
    if (previous_ && (s.sequence < previous_->sequence ||
        (cached && (s.source_time_ns != previous_->source_time_ns || s.angle_rad != previous_->angle_rad)) ||
        (!cached && s.source_time_ns <= previous_->source_time_ns))) {
        latch(SteeringMonitorFault::SensorInvalid, now_ns); return decision_;
    }
    if (previous_ && !cached && s.source_time_ns-previous_->source_time_ns > config_.sample_gap_ns) {
        latch(SteeringMonitorFault::SensorUnavailable, now_ns); return decision_;
    }
    decision_.measured_rad = s.angle_rad; decision_.source_time_ns = s.source_time_ns;
    if (cached) return decision_; // repeated polling cannot confirm a fault
    previous_ = s; decision_.new_measurement = true;
    if (decision_.fault != SteeringMonitorFault::None) return decision_;
    predict(s.source_time_ns);
    if (!seeded_ || !tracking_enabled) {
        lower_ = upper_ = s.angle_rad;
        if (!seeded_ && !staged_) target_ = s.angle_rad;
        if (!tracking_enabled) { head_ = size_ = 0; staged_.reset(); target_ = s.angle_rad; }
        seeded_ = true; decision_.violation_since_ns.reset(); decision_.residual_rad = 0;
    }
    decision_.expected_min_rad = lower_; decision_.expected_max_rad = upper_;
    if (!tracking_enabled) return decision_;
    decision_.residual_rad = std::max({lower_-s.angle_rad, s.angle_rad-upper_, 0.0});
    const auto low = std::nextafter(lower_-config_.tolerance_rad, -std::numeric_limits<double>::infinity());
    const auto high = std::nextafter(upper_+config_.tolerance_rad, std::numeric_limits<double>::infinity());
    if (s.angle_rad < low || s.angle_rad > high) {
        if (!decision_.violation_since_ns) decision_.violation_since_ns = s.source_time_ns;
        if (s.source_time_ns-*decision_.violation_since_ns >= config_.confirmation_ns) latch(SteeringMonitorFault::TrackingError, now_ns);
    } else decision_.violation_since_ns.reset();
    return decision_;
}
}  // namespace stratadrive::vecu
