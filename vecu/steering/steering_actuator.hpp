#pragma once

#include "steering_receiver.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>

namespace stratadrive::vecu {
struct SteeringActuatorConfig {
    double command_min_rad;
    double command_max_rad;
    double angle_min_rad;
    double angle_max_rad;
    double initial_angle_rad;
    double max_rate_rad_s;
    std::uint64_t delay_ns;
    std::uint64_t period_ns{10000000};
    std::uint64_t max_tick_gap_ns{30000000};
    std::uint64_t max_source_age_ns{30000000};
    std::uint64_t timeout_ns{80000000};
};
enum class SteeringFault { None, CommandUnavailable, ContinuityLost, ClockError, ControlDeadline };

// Single owner, externally supplied monotonic clock. Functional SIL model;
// no OS scheduler, vehicle dynamics, steering sensor or jam detector.
class SteeringActuator {
public:
    explicit SteeringActuator(SteeringActuatorConfig config);
    bool start_session(std::uint32_t epoch, std::uint64_t enable_ns);
    can::SteeringReceiveResult receive(const can::SteeringFrame& frame, std::uint64_t now_ns);
    void mark_continuity_lost(std::uint64_t now_ns);
    // At most one publication per period. A missed control deadline holds the
    // angle rather than catching up physics. No output with an untrusted clock.
    std::optional<can::SteeringFrame> tick(std::uint64_t now_ns);
    double actual_angle_rad() const { return actual_; }
    SteeringFault fault() const { return fault_; }
    // Current command snapshot for ingress diagnostics; not actuator feedback.
    std::optional<can::SteeringMessage> current_sample(std::uint64_t now_ns) {
        return fault_ == SteeringFault::None ? receiver_.current_sample(now_ns) : std::nullopt;
    }
    const can::SteeringReceiver& receiver() const { return receiver_; }
private:
    struct Demand { double angle; std::uint64_t due_ns; };
    void fail(SteeringFault fault);
    void move(std::uint64_t elapsed_ns);
    void advance(std::uint64_t now_ns);
    const SteeringActuatorConfig config_;
    can::SteeringReceiver receiver_;
    can::SteeringTxState tx_{can::SteeringFrameKind::Actual};
    std::array<Demand, 128> pending_{};
    std::size_t head_{0}, size_{0};
    double actual_, target_;
    std::optional<double> staged_;
    std::uint32_t epoch_{0}, sequence_{0};
    std::uint64_t last_tick_ns_{0};
    bool sequence_exhausted_{false};
    SteeringFault fault_{SteeringFault::None};
};
}  // namespace stratadrive::vecu
