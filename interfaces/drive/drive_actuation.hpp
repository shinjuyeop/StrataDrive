#pragma once

#include <cmath>
#include <cstdint>
#include <optional>

namespace stratadrive::drive {
// Plain calibration/port data; no dependency on the simulation implementation.
struct ResponseConfig {
    double minimum_nm, maximum_nm, initial_nm, rate_nm_s, zero_rate_nm_s;
    std::uint64_t delay_ns;
};
inline bool valid_response_config(const ResponseConfig& c) {
    return std::isfinite(c.minimum_nm) && std::isfinite(c.maximum_nm) &&
        std::isfinite(c.maximum_nm-c.minimum_nm) && std::isfinite(c.initial_nm) &&
        std::isfinite(c.rate_nm_s) && std::isfinite(c.zero_rate_nm_s) &&
        c.minimum_nm < 0 && c.maximum_nm > 0 && c.initial_nm >= c.minimum_nm &&
        c.initial_nm <= c.maximum_nm && c.rate_nm_s > 0 && c.zero_rate_nm_s > 0;
}
struct TorqueEnvelope { double minimum_nm, maximum_nm; };
struct TorqueMeasurement {
    std::uint32_t model_epoch;
    std::uint64_t sequence, source_time_ns;
    double torque_nm;
};
enum class ActuationMode { Target, Zero };
struct Actuation {
    ActuationMode mode{ActuationMode::Zero};
    double target_nm{0};
    std::optional<TorqueEnvelope> envelope;
    std::uint64_t issued_time_ns{0};
};
} // namespace stratadrive::drive
