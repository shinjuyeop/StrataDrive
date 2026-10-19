#include "brake_pressure_response.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace stratadrive::simulation {
BrakePressureResponse::BrakePressureResponse(BrakePressureResponseConfig config)
    : config_(config), actual_(config.initial_pa), target_(actual_) {
    if (!std::isfinite(config.maximum_pa) || !std::isfinite(actual_) ||
        !std::isfinite(config.rise_rate_pa_s) || !std::isfinite(config.fall_rate_pa_s) || config.maximum_pa <= 0 ||
        actual_ < 0 || actual_ > config.maximum_pa || config.rise_rate_pa_s <= 0 || config.fall_rate_pa_s <= 0 || config.model_epoch == 0) {
        throw std::invalid_argument("BrakePressureResponse configuration");
    }
}
bool BrakePressureResponse::begin(std::uint64_t now_ns) {
    if (initialized_ && now_ns < last_observed_ns_) return false;
    initialized_ = true; protecting_ = false; target_ = actual_;
    return skip_to(now_ns);
}
bool BrakePressureResponse::skip_to(std::uint64_t now_ns) {
    if (!initialized_ || now_ns < last_observed_ns_) return false;
    head_ = size_ = 0; staged_.reset();
    if (!protecting_) target_ = actual_;
    last_step_ns_ = last_observed_ns_ = now_ns;
    return true;
}
bool BrakePressureResponse::request_protection(double floor_pa, std::uint64_t now_ns) {
    if (!initialized_ || now_ns < last_observed_ns_ || !std::isfinite(floor_pa) ||
        floor_pa <= 0 || floor_pa > config_.maximum_pa) return false;
    if (protecting_) return floor_pa == target_; // duplicate request must not restart a ramp
    protecting_ = true; target_ = floor_pa;
    return skip_to(now_ns); // no motion backdated before detection
}
bool BrakePressureResponse::hold(std::uint64_t now_ns) {
    if(protecting_) return false; // a nominal hold cannot clear fault protection
    return skip_to(now_ns);
}
bool BrakePressureResponse::set_target(double pressure_pa, std::uint64_t now_ns) {
    if (!initialized_ || protecting_ || now_ns < last_observed_ns_ || !std::isfinite(pressure_pa) ||
        pressure_pa < 0 || pressure_pa > config_.maximum_pa) return false;
    last_observed_ns_ = now_ns;
    if (staged_ && pressure_pa == *staged_) return true;
    if (size_ == pending_.size() || now_ns > std::numeric_limits<std::uint64_t>::max()-config_.delay_ns) return false;
    pending_[(head_+size_)%pending_.size()] = {pressure_pa, now_ns+config_.delay_ns};
    ++size_; staged_ = pressure_pa; return true;
}
void BrakePressureResponse::move(std::uint64_t elapsed_ns, const BrakePressureResponseInjection& injection) {
    if (injection.stuck || (protecting_ && actual_ >= target_)) return;
    const auto rate = target_ >= actual_ ? config_.rise_rate_pa_s*injection.rise_rate_scale :
                                         config_.fall_rate_pa_s*injection.fall_rate_scale;
    const auto distance = rate*(static_cast<double>(elapsed_ns)/1e9);
    actual_ += std::clamp(target_-actual_, -distance, distance);
    actual_ = std::clamp(actual_, 0.0, config_.maximum_pa);
}
bool BrakePressureResponse::advance(std::uint64_t now_ns, const BrakePressureResponseInjection& injection) {
    if (!initialized_ || now_ns < last_observed_ns_ || !std::isfinite(injection.rise_rate_scale) || !std::isfinite(injection.fall_rate_scale) ||
        injection.rise_rate_scale < 0 || injection.rise_rate_scale > 2 ||
        injection.fall_rate_scale < 0 || injection.fall_rate_scale > 2) return false;
    auto cursor = last_step_ns_;
    while (size_ != 0 && pending_[head_].due_ns <= now_ns) {
        const auto demand = pending_[head_];
        move(demand.due_ns-cursor, injection); cursor = demand.due_ns; target_ = demand.pressure;
        head_ = (head_+1)%pending_.size(); --size_;
    }
    move(now_ns-cursor, injection); last_step_ns_ = last_observed_ns_ = now_ns; return true;
}
std::optional<brake::PressureMeasurement> BrakePressureResponse::capture(BrakeSensorAction action,
        std::optional<double> sensed_pressure_override) {
    if (!initialized_) return std::nullopt;
    if (action == BrakeSensorAction::Invalidate) sensor_.reset();
    if (action == BrakeSensorAction::Acquire) {
        if (sensor_sequence_ == std::numeric_limits<std::uint64_t>::max() || last_step_ns_ != last_observed_ns_ ||
            (last_acquisition_ns_ && last_step_ns_ <= *last_acquisition_ns_)) return std::nullopt;
        sensor_ = brake::PressureMeasurement{config_.model_epoch, sensor_sequence_++, last_step_ns_, sensed_pressure_override.value_or(actual_)};
        last_acquisition_ns_ = last_step_ns_;
    }
    return sensor_;
}
}  // namespace stratadrive::simulation
