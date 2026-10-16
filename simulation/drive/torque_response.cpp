#include "torque_response.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace stratadrive::simulation {
TorqueResponse::TorqueResponse(TorqueResponseConfig config) : config_(config),
    envelope_{config.minimum_nm, config.maximum_nm}, actual_(config.initial_nm) {
    if (!std::isfinite(config.minimum_nm) || !std::isfinite(config.maximum_nm) ||
        !std::isfinite(config.maximum_nm - config.minimum_nm) || !std::isfinite(actual_) ||
        !std::isfinite(config.rate_nm_s) || !std::isfinite(config.zero_rate_nm_s) ||
        config.minimum_nm >= 0 || config.maximum_nm <= 0 ||
        actual_ < config.minimum_nm || actual_ > config.maximum_nm ||
        config.rate_nm_s <= 0 || config.zero_rate_nm_s <= 0) {
        throw std::invalid_argument("TorqueResponse configuration");
    }
}
void TorqueResponse::begin(std::uint64_t now_ns) {
    envelope_ = {config_.minimum_nm, config_.maximum_nm};
    head_ = size_ = 0; staged_.reset(); target_ = 0;
    last_step_ns_ = last_observed_ns_ = zero_enable_ns_ = now_ns; initialized_ = true; zeroing_ = true;
}
bool TorqueResponse::set_target(double torque_nm, std::uint64_t now_ns) {
    if (!initialized_ || now_ns < last_observed_ns_ || !std::isfinite(torque_nm) ||
        torque_nm < envelope_.minimum_nm || torque_nm > envelope_.maximum_nm) return false;
    last_observed_ns_ = now_ns;
    if (staged_ && torque_nm == *staged_) return true;
    if (size_ == pending_.size() || now_ns > std::numeric_limits<std::uint64_t>::max() - config_.delay_ns) return false;
    // Finish the prior zero-target interval before enabling a normal demand.
    if (zeroing_ && !advance(now_ns)) return false;
    pending_[(head_ + size_) % pending_.size()] = {torque_nm, now_ns + config_.delay_ns};
    ++size_; staged_ = torque_nm; zeroing_ = false;
    return true;
}
void TorqueResponse::move(std::uint64_t elapsed_ns, MotionRate rate) {
    const auto rate_nm_s = rate == MotionRate::Protection ? config_.zero_rate_nm_s : config_.rate_nm_s;
    auto seconds = static_cast<double>(elapsed_ns) / 1e9;
    const auto edge = std::clamp(actual_, envelope_.minimum_nm, envelope_.maximum_nm);
    if (edge != actual_) {
        const auto needed = std::abs(edge-actual_)/config_.zero_rate_nm_s;
        if (seconds <= needed) {
            actual_ += std::clamp(edge-actual_, -config_.zero_rate_nm_s*seconds, config_.zero_rate_nm_s*seconds);
            return;
        }
        actual_ = edge; seconds -= needed;
    }
    const auto distance = rate_nm_s * seconds;
    actual_ += std::clamp(target_ - actual_, -distance, distance);
    actual_ = std::clamp(actual_, config_.minimum_nm, config_.maximum_nm);
}
bool TorqueResponse::constrain(TorqueEnvelope envelope, std::uint64_t now_ns) {
    if (!initialized_ || now_ns < last_observed_ns_ || !std::isfinite(envelope.minimum_nm) || !std::isfinite(envelope.maximum_nm) ||
        envelope.minimum_nm < config_.minimum_nm || envelope.minimum_nm > 0 || envelope.maximum_nm < 0 ||
        envelope.maximum_nm > config_.maximum_nm) return false;
    if (envelope.minimum_nm == envelope_.minimum_nm && envelope.maximum_nm == envelope_.maximum_nm) return true;
    if (!advance(now_ns)) return false;
    envelope_ = envelope;
    target_ = std::clamp(target_, envelope.minimum_nm, envelope.maximum_nm);
    if (staged_) *staged_ = std::clamp(*staged_, envelope.minimum_nm, envelope.maximum_nm);
    for (std::size_t i = 0; i < size_; ++i) {
        auto& demand = pending_[(head_+i)%pending_.size()];
        demand.torque_nm = std::clamp(demand.torque_nm, envelope.minimum_nm, envelope.maximum_nm);
    }
    return true;
}
bool TorqueResponse::advance(std::uint64_t now_ns) {
    if (!initialized_ || now_ns < last_observed_ns_) return false;
    if (zeroing_) {
        move(now_ns - std::max(last_step_ns_, zero_enable_ns_), MotionRate::Protection);
    } else {
        auto cursor = last_step_ns_;
        while (size_ != 0 && pending_[head_].due_ns <= now_ns) {
            const auto demand = pending_[head_];
            move(demand.due_ns - cursor, MotionRate::Normal);
            cursor = demand.due_ns; target_ = demand.torque_nm;
            head_ = (head_ + 1) % pending_.size(); --size_;
        }
        move(now_ns - cursor, MotionRate::Normal);
    }
    last_step_ns_ = last_observed_ns_ = now_ns;
    return true;
}
void TorqueResponse::request_zero(std::uint64_t now_ns) {
    if (!initialized_ || now_ns < last_observed_ns_) return;
    if (!zeroing_) zero_enable_ns_ = now_ns;
    zeroing_ = true; target_ = 0; head_ = size_ = 0; staged_.reset();
    last_observed_ns_ = now_ns;
}
void TorqueResponse::skip_to(std::uint64_t now_ns) {
    if (initialized_ && now_ns >= last_observed_ns_) {
        request_zero(now_ns);
        last_step_ns_ = last_observed_ns_ = now_ns;
    }
}
}  // namespace stratadrive::simulation
