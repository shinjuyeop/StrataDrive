#include "steering_response.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace stratadrive::simulation {
SteeringResponse::SteeringResponse(SteeringResponseConfig config)
    : config_(config), actual_(config.initial_rad), target_(actual_) {
    if (!std::isfinite(config.minimum_rad) || !std::isfinite(config.maximum_rad) ||
        !std::isfinite(config.maximum_rad-config.minimum_rad) || !std::isfinite(actual_) ||
        !std::isfinite(config.rate_rad_s) || config.minimum_rad >= config.maximum_rad ||
        actual_ < config.minimum_rad || actual_ > config.maximum_rad || config.rate_rad_s <= 0 || config.model_epoch == 0) {
        throw std::invalid_argument("SteeringResponse configuration");
    }
}
bool SteeringResponse::begin(std::uint64_t now_ns) {
    if (initialized_ && now_ns < last_observed_ns_) return false;
    initialized_ = true; return hold(now_ns);
}
bool SteeringResponse::hold(std::uint64_t now_ns) {
    if (!initialized_ || now_ns < last_observed_ns_) return false;
    head_ = size_ = 0; staged_.reset(); target_ = actual_;
    last_step_ns_ = last_observed_ns_ = now_ns;
    return true;
}
bool SteeringResponse::set_target(double angle_rad, std::uint64_t now_ns) {
    if (!initialized_ || now_ns < last_observed_ns_ || !std::isfinite(angle_rad) ||
        angle_rad < config_.minimum_rad || angle_rad > config_.maximum_rad) return false;
    last_observed_ns_ = now_ns;
    if (staged_ && angle_rad == *staged_) return true;
    if (size_ == pending_.size() || now_ns > std::numeric_limits<std::uint64_t>::max()-config_.delay_ns) return false;
    pending_[(head_+size_)%pending_.size()] = {angle_rad, now_ns+config_.delay_ns};
    ++size_; staged_ = angle_rad; return true;
}
void SteeringResponse::move(std::uint64_t elapsed_ns, SteeringResponseInjection injection) {
    if (injection.jammed) return;
    const auto distance = config_.rate_rad_s*injection.rate_scale*(static_cast<double>(elapsed_ns)/1e9);
    actual_ += std::clamp(target_-actual_, -distance, distance);
    actual_ = std::clamp(actual_, config_.minimum_rad, config_.maximum_rad);
}
bool SteeringResponse::advance(std::uint64_t now_ns, SteeringResponseInjection injection) {
    if (!initialized_ || now_ns < last_observed_ns_ || !std::isfinite(injection.rate_scale) ||
        injection.rate_scale < 0 || injection.rate_scale > 2) return false;
    auto cursor = last_step_ns_;
    while (size_ != 0 && pending_[head_].due_ns <= now_ns) {
        const auto demand = pending_[head_];
        move(demand.due_ns-cursor, injection); cursor = demand.due_ns; target_ = demand.angle;
        head_ = (head_+1)%pending_.size(); --size_;
    }
    move(now_ns-cursor, injection); last_step_ns_ = last_observed_ns_ = now_ns; return true;
}
std::optional<steering::AngleMeasurement> SteeringResponse::capture(SteeringSensorAction action,
        std::optional<double> sensed_angle_override) {
    if (!initialized_) return std::nullopt;
    if (action == SteeringSensorAction::Invalidate) sensor_.reset();
    if (action == SteeringSensorAction::Acquire) {
        if (sensor_sequence_ == std::numeric_limits<std::uint64_t>::max() || last_step_ns_ != last_observed_ns_ ||
            (last_acquisition_ns_ && last_step_ns_ <= *last_acquisition_ns_)) return std::nullopt;
        sensor_ = steering::AngleMeasurement{config_.model_epoch, sensor_sequence_++, last_step_ns_, sensed_angle_override.value_or(actual_)};
        last_acquisition_ns_ = last_step_ns_;
    }
    return sensor_;
}
}  // namespace stratadrive::simulation
