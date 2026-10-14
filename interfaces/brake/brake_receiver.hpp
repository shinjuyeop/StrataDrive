#pragma once

#include "actuator_receiver_state.hpp"
#include "brake_frame_codec.hpp"

namespace stratadrive::can {
struct BrakeReceiverConfig {
    BrakeFrameKind kind;
    // 실제 압력 한계는 caller가 명시한다. wire 최대값을 차량 calibration으로 쓰지 않는다.
    double min_pressure_pa;
    double max_pressure_pa;
    std::uint64_t max_source_age_ns{30000000ULL};
    std::uint64_t timeout_ns{80000000ULL};
};
using BrakeReceiverHealth = ActuatorReceiverHealth;
using BrakeReceiveDecision = ActuatorReceiveDecision;
using BrakeReceiveResult = ActuatorReceiveResult;
struct BrakeAcceptedSample { BrakeMessage message; std::uint64_t received_time_ns; };

// Socket/clock/actuator model과 독립인 단일-thread, stream별 application receiver.
class BrakeReceiver {
public:
    explicit BrakeReceiver(BrakeReceiverConfig config);
    // Trusted INIT 전용: 더 큰 Epoch와 비감소 clock으로만 재초기화한다.
    bool start_session(std::uint32_t epoch, std::uint64_t monitoring_enable_ns);
    void mark_continuity_lost(std::uint64_t now_ns) { state_.mark_continuity_lost(now_ns); }
    BrakeReceiveResult receive(const BrakeFrame& frame, std::uint64_t now_ns);
    BrakeReceiverHealth poll(std::uint64_t now_ns) { return state_.poll(now_ns); }
    std::optional<BrakeMessage> current_sample(std::uint64_t now_ns);
    BrakeReceiverHealth health() const { return state_.health(); }
    // 진단 이력이다. 제어 입력은 current_sample(now_ns)로 조회한다.
    const std::optional<BrakeAcceptedSample>& last_accepted() const { return accepted_; }
    const std::optional<std::uint64_t>& last_raw_rx_time_ns() const { return state_.last_raw_rx_time_ns(); }

private:
    const BrakeReceiverConfig config_;
    BrakeRxState e2e_;
    ActuatorReceiverState state_;
    std::optional<BrakeAcceptedSample> accepted_;
};
}  // namespace stratadrive::can
