#pragma once

#include "drive_actuation.hpp"

namespace stratadrive::vecu {
class TorqueFeedback {
public:
    void begin(std::uint32_t epoch, std::uint64_t enable_ns) {
        epoch_ = epoch; enable_ns_ = enable_ns; previous_.reset();
    }
    struct Result { bool valid{false}; std::optional<double> fresh; };
    Result observe(const std::optional<drive::TorqueMeasurement>& sensor, std::uint64_t now_ns,
            double minimum, double maximum) {
        if (!sensor) return {};
        const auto& s = *sensor;
        if (s.model_epoch != epoch_ || s.source_time_ns < enable_ns_ || s.source_time_ns > now_ns ||
            now_ns-s.source_time_ns > 30000000 || !std::isfinite(s.torque_nm) || s.torque_nm < minimum || s.torque_nm > maximum) return {};
        const bool cached = previous_ && s.sequence == previous_->sequence;
        if (previous_ && (s.sequence < previous_->sequence ||
            (cached && (s.source_time_ns != previous_->source_time_ns || s.torque_nm != previous_->torque_nm)) ||
            (!cached && s.source_time_ns <= previous_->source_time_ns))) return {};
        previous_ = s;
        // The current Drive wire has no separate torque acquisition timestamp.
        // Only an end-of-job acquisition is published with this report's time.
        return {true, !cached && s.source_time_ns == now_ns ? std::optional<double>{s.torque_nm} : std::nullopt};
    }
private:
    std::uint32_t epoch_{0};
    std::uint64_t enable_ns_{0};
    std::optional<drive::TorqueMeasurement> previous_;
};
} // namespace stratadrive::vecu
