#pragma once

#include "steering_frame_codec.hpp"
#include "actuator_receiver_state.hpp"

#include <cstdint>
#include <optional>

namespace stratadrive::can {

// M1 로컬 실험 후보. 실제 물리 한계는 caller가 별도로 전달한다.
struct SteeringReceiverConfig {
    SteeringFrameKind kind;
    double min_angle_rad;
    double max_angle_rad;
    std::uint64_t max_source_age_ns{30000000ULL};
    std::uint64_t timeout_ns{80000000ULL};
};

// 수신 monitor 상태이며 차량의 INIT/NORMAL/DEGRADED/FAIL_SAFE 상태와 다르다.
using SteeringReceiverHealth = ActuatorReceiverHealth;
using SteeringReceiveDecision = ActuatorReceiveDecision;
using SteeringReceiveResult = ActuatorReceiveResult;
struct SteeringAcceptedSample {
    SteeringMessage message;
    std::uint64_t received_time_ns;
};

// 첫 trace Sequence는 0..9, 이후 증가량은 1..10. 같은 Epoch의 wrap은 허용하지 않는다.
// P05의 8-bit Counter 순환과는 별개의 application 정책이다.
bool steering_sequence_progresses(std::optional<std::uint32_t> previous, std::uint32_t next);

// 단일 thread에서 stream별로 별도 소유한다. Socket/clock/coordinator 구현과 독립이다.
// SourceTimeNs와 now_ns는 같은 monotonic clock domain의 값이어야 한다.
class SteeringReceiver {
public:
    explicit SteeringReceiver(SteeringReceiverConfig config);

    // 신뢰된 INIT 설정으로만 호출한다. 재초기화는 더 큰 Epoch/비감소 clock을 요구한다.
    // 실패하면 기존 session과 fault를 보존한다. Frame에서 Epoch를 자동 학습하지 않는다.
    bool start_session(std::uint32_t epoch, std::uint64_t monitoring_enable_ns);
    SteeringReceiveResult receive(const SteeringFrame& frame, std::uint64_t now_ns);
    SteeringReceiverHealth poll(std::uint64_t now_ns) { return state_.poll(now_ns); }

    // Poll과 source age를 함께 검사한다. Timeout/clock fault/age 초과 시 값 없음.
    // Actual의 sample 유효성은 sender health나 정상 주행 가능 여부와 별개다.
    std::optional<SteeringMessage> current_sample(std::uint64_t now_ns);
    SteeringReceiverHealth health() const { return state_.health(); }
    // 진단용 이력이다. 제어 입력은 current_sample(now_ns)로 조회한다.
    const std::optional<SteeringAcceptedSample>& last_accepted() const { return accepted_; }
    const std::optional<std::uint64_t>& last_raw_rx_time_ns() const { return state_.last_raw_rx_time_ns(); }

private:
    const SteeringReceiverConfig config_;
    SteeringRxState e2e_;
    ActuatorReceiverState state_;
    std::optional<SteeringAcceptedSample> accepted_;
};

}  // namespace stratadrive::can
