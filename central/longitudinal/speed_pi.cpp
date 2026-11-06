#include "speed_pi.hpp"

#include <algorithm>
#include <cmath>
#include <limits>

namespace stratadrive::central {
static_assert(std::numeric_limits<double>::is_iec559 &&
              std::numeric_limits<double>::digits == 53 && sizeof(double) == 8,
              "m6-pi-v1 requires IEEE 754 binary64");

bool SpeedPI::initialize(std::uint32_t epoch) noexcept {
    if (epoch <= state_.epoch) return false;
    state_ = {};
    state_.epoch = epoch;
    return true;
}

SpeedPIReason SpeedPI::validate(std::uint64_t now_ns, double target_mps,
                                const std::optional<SpeedSample>& sample, bool permission) const noexcept {
    // Preserve the Python model's rejection precedence, including fault latch.
    if (state_.epoch == 0) return SpeedPIReason::Uninitialized;
    if (state_.fault) return SpeedPIReason::Latched;
    if (state_.last_ns && (now_ns < *state_.last_ns || now_ns - *state_.last_ns != kPeriodNs)) {
        return SpeedPIReason::SampleTime;
    }
    if (!permission) return SpeedPIReason::Permission;
    if (!std::isfinite(target_mps) || target_mps < 0 || target_mps > kMaxTargetMps) return SpeedPIReason::Target;
    if (!sample || !std::isfinite(sample->speed_mps) || sample->speed_mps < 0) return SpeedPIReason::InvalidSpeed;
    if (sample->epoch != state_.epoch) return SpeedPIReason::Epoch;
    if (sample->source_ns > now_ns || now_ns - sample->source_ns > kMaxAgeNs) return SpeedPIReason::SourceAge;
    if (state_.sample) {
        const auto& old = *state_.sample;
        const bool same = sample->epoch == old.epoch && sample->sequence == old.sequence &&
                          sample->source_ns == old.source_ns && sample->speed_mps == old.speed_mps;
        if (sample->sequence < old.sequence || sample->source_ns < old.source_ns ||
            (sample->sequence == old.sequence && !same) ||
            (sample->sequence > old.sequence && sample->source_ns <= old.source_ns)) {
            return SpeedPIReason::Identity;
        }
    }
    return SpeedPIReason::Normal;
}

SpeedPIOutput SpeedPI::step(std::uint64_t now_ns, double target_mps,
                           const std::optional<SpeedSample>& sample, bool permission, bool propulsion_saturated,
                           bool braking_saturated) noexcept {
    const auto reason = validate(now_ns, target_mps, sample, permission);
    if (reason != SpeedPIReason::Normal) {
        state_.fault = true;
        return {std::nullopt, false, reason, state_.integral, sample ? sample->source_ns : 0};
    }

    constexpr double dt = static_cast<double>(kPeriodNs) * 1e-9;
    const double rate = state_.target_mps ? (target_mps - *state_.target_mps) / dt : 0.0;
    const double reference = std::max(0.0, target_mps + kBrakingPreviewS * std::min(0.0, rate));
    const double error = reference - sample->speed_mps;
    const double raw = rate + kKp * error + state_.integral;
    const double bounded = std::max(kLowMps2, std::min(kHighMps2, raw));
    const double output = std::max(state_.previous_mps2 - kSlewMps3 * dt,
                                   std::min(state_.previous_mps2 + kSlewMps3 * dt, bounded));
    // Calculate output using the old integral. Both amplitude and slew limits
    // participate in conditional integration, in the same order as the model.
    if ((raw - output) * error <= 0 && !(propulsion_saturated && error > 0) &&
        !(braking_saturated && error < 0)) state_.integral += kKi * error * dt;
    state_.target_mps = target_mps;
    state_.last_ns = now_ns;
    state_.previous_mps2 = output;
    state_.sample = sample;
    return {output, true, SpeedPIReason::Normal, state_.integral, sample->source_ns};
}

}  // namespace stratadrive::central
