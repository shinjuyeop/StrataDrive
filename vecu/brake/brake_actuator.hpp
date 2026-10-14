#pragma once

#include "brake_receiver.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>

namespace stratadrive::vecu {
struct BrakeActuatorConfig {
    double command_max_pa;
    double max_pressure_pa;
    double initial_pressure_pa;
    double rise_rate_pa_s;          // 가압 속도 상한, Pa/s
    double fall_rate_pa_s;          // 감압 속도 상한, Pa/s
    double fault_pressure_floor_pa; // fault 시 max(현재 압력, 이 값); 시험용 보호 설정
    std::uint64_t delay_ns;
    std::uint64_t period_ns{10000000};
    std::uint64_t max_tick_gap_ns{30000000};
    std::uint64_t max_source_age_ns{30000000};
    std::uint64_t timeout_ns{80000000};
};
enum class BrakeFault { None, CommandUnavailable, ContinuityLost, ClockError, ControlDeadline };

// Single owner, externally supplied monotonic clock. Functional SIL model;
// no OS scheduler, vehicle dynamics, hydraulic sensor or response-fault detector.
class BrakeActuator {
public:
    explicit BrakeActuator(BrakeActuatorConfig config);
    bool start_session(std::uint32_t epoch, std::uint64_t enable_ns);
    can::BrakeReceiveResult receive(const can::BrakeFrame& frame, std::uint64_t now_ns);
    void mark_continuity_lost(std::uint64_t now_ns);
    // At most one publication per period. A missed control deadline holds the
    // pressure rather than catching up physics. No output with an untrusted clock.
    std::optional<can::BrakeFrame> tick(std::uint64_t now_ns);
    double actual_pressure_pa() const { return actual_; }
    BrakeFault fault() const { return fault_; }
    // Current command snapshot for ingress diagnostics; not actuator feedback.
    std::optional<can::BrakeMessage> current_sample(std::uint64_t now_ns) {
        return fault_ == BrakeFault::None ? receiver_.current_sample(now_ns) : std::nullopt;
    }
    const can::BrakeReceiver& receiver() const { return receiver_; }
private:
    struct Demand { double pressure; std::uint64_t due_ns; };
    void fail(BrakeFault fault, std::uint64_t now_ns);
    void move(std::uint64_t elapsed_ns);
    void advance(std::uint64_t now_ns);
    const BrakeActuatorConfig config_;
    can::BrakeReceiver receiver_;
    can::BrakeTxState tx_{can::BrakeFrameKind::Actual};
    std::array<Demand, 128> pending_{};
    std::size_t head_{0}, size_{0};
    double actual_, target_;
    std::optional<double> staged_;
    std::uint32_t epoch_{0}, sequence_{0};
    std::uint64_t last_tick_ns_{0}, protection_enable_ns_{0};
    bool sequence_exhausted_{false};
    BrakeFault fault_{BrakeFault::None};
};
}  // namespace stratadrive::vecu
