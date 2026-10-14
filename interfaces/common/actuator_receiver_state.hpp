#pragma once

#include "actuator_payload_codec.hpp"

#include <cstdint>
#include <optional>

namespace stratadrive::can {

// 통신 monitor 상태다. 차량/actuator의 INIT/NORMAL/DEGRADED/FAIL_SAFE와 구분한다.
enum class ActuatorReceiverHealth { NotInitialized, Waiting, Receiving, Timeout, ClockError };
enum class ActuatorReceiveDecision {
    Accepted, NotInitialized, ClockError, Timeout, MalformedEnvelope, E2eRejected,
    MalformedPayload, EpochMismatch, SourceBeforeSession, SourceInFuture, SourceStale,
    SequenceRejected, SourceNotIncreasing, Unavailable, ModeRejected, ValueOutOfRange,
    // 기존 Steering API와 Brake의 물리량 이름을 같은 공통 사유에 연결한다.
    AngleOutOfRange = ValueOutOfRange,
    PressureOutOfRange = ValueOutOfRange,
    TorqueOutOfRange = ValueOutOfRange,
};
struct ActuatorReceiveResult {
    ActuatorReceiveDecision decision;
    // 이번 호출에서 E2E API가 성공한 경우만 존재한다.
    std::optional<e2e::P05Status> e2e_status;
};

bool actuator_sequence_progresses(std::optional<std::uint32_t> previous, std::uint32_t next);
bool actuator_mode_allowed(const ActuatorMetadata& metadata, bool command);
struct ActuatorValueRange { double minimum; double maximum; };
bool actuator_value_in_range(double value, ActuatorValueRange range);
struct ActuatorReceiverTiming {
    std::uint64_t max_source_age_ns;
    std::uint64_t timeout_ns;
    // Existing critical callers retain 80 ms. BMS observation explicitly chooses 300 ms.
    std::uint64_t timeout_limit_ns{80000000ULL};
};

// Clock/session/application cursor만 관리한다. Frame/P05/domain range/dynamics는 caller 책임이다.
// Source와 now는 같은 monotonic clock domain이다. 단일 thread에서 stream별로 소유한다.
class ActuatorReceiverState {
public:
    explicit ActuatorReceiverState(ActuatorReceiverTiming timing);
    bool start_session(std::uint32_t epoch, std::uint64_t monitoring_enable_ns);
    ActuatorReceiverHealth poll(std::uint64_t now_ns);
    // nullopt는 검사를 계속할 수 있다는 뜻이며 sample 수용 완료가 아니다.
    std::optional<ActuatorReceiveDecision> begin_receive(std::uint64_t now_ns);
    std::optional<ActuatorReceiveDecision> check_metadata(
        const ActuatorMetadata& metadata, std::uint64_t now_ns) const;
    // 모든 domain 검증이 통과한 뒤에만 호출한다.
    void commit(const ActuatorMetadata& metadata, std::uint64_t now_ns);
    bool has_current_sample(std::uint64_t now_ns);
    ActuatorReceiverHealth health() const { return health_; }
    const std::optional<std::uint64_t>& last_raw_rx_time_ns() const { return last_raw_rx_ns_; }

private:
    struct AcceptedMetadata { ActuatorMetadata metadata; std::uint64_t received_time_ns; };
    const ActuatorReceiverTiming timing_;
    ActuatorReceiverHealth health_{ActuatorReceiverHealth::NotInitialized};
    std::uint32_t epoch_{0};
    std::uint64_t monitoring_enable_ns_{0};
    std::uint64_t last_observed_ns_{0};
    std::optional<AcceptedMetadata> accepted_;
    std::optional<std::uint64_t> last_raw_rx_ns_;
};
}  // namespace stratadrive::can
