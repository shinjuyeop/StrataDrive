#pragma once

#include "torque_response.hpp"
#include <limits>

namespace stratadrive::simulation {
class DriveSilPlant {
public:
    explicit DriveSilPlant(const drive::ResponseConfig& config) : response_(config) {}
    void begin(std::uint32_t model_epoch, std::uint64_t now_ns) {
        model_epoch_ = model_epoch; response_.begin(now_ns);
    }
    bool apply(const drive::Actuation& out) {
        if (out.mode == drive::ActuationMode::Zero) response_.request_zero(out.issued_time_ns);
        if (out.envelope && !response_.constrain(*out.envelope, out.issued_time_ns)) return false;
        return out.mode != drive::ActuationMode::Target || response_.set_target(out.target_nm, out.issued_time_ns);
    }
    bool advance(std::uint64_t now_ns, bool execution_gap) {
        if (execution_gap) { response_.skip_to(now_ns); return true; }
        return response_.advance(now_ns);
    }
    std::optional<drive::TorqueMeasurement> capture(std::uint64_t now_ns) {
        if (sequence_ == std::numeric_limits<std::uint64_t>::max() || (last_capture_ns_ && now_ns <= *last_capture_ns_)) return std::nullopt;
        last_capture_ns_ = now_ns;
        return drive::TorqueMeasurement{model_epoch_, sequence_++, now_ns, response_.actual_nm()};
    }
    double actual_nm() const { return response_.actual_nm(); }
private:
    TorqueResponse response_;
    std::uint32_t model_epoch_{0};
    std::uint64_t sequence_{0};
    std::optional<std::uint64_t> last_capture_ns_;
};
} // namespace stratadrive::simulation
