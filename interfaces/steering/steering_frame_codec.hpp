#pragma once

#include "actuator_payload_codec.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>

namespace stratadrive::can {

inline constexpr std::uint16_t kSteeringCommandId = 0x180;
inline constexpr std::uint16_t kSteeringActualId = 0x280;
inline constexpr std::size_t kSteeringPayloadSize = 32;
inline constexpr std::uint16_t kSteeringCommandDataId = 0x1001;
inline constexpr std::uint16_t kSteeringActualDataId = 0x1002;
inline constexpr std::uint16_t kSteeringE2eOffsetBits = 232;  // byte 29부터 CRC/Counter
inline constexpr std::uint8_t kSteeringMaxDeltaCounter = 10;  // 프로젝트 설정 후보
using SteeringPayload = std::array<std::uint8_t, kSteeringPayloadSize>;

enum class SteeringFrameKind : std::uint16_t {
    Command = kSteeringCommandId,
    Actual = kSteeringActualId,
};
using SteeringLocalState = ActuatorLocalState;
using SteeringOrigin = ActuatorOrigin;

struct SteeringMessage {
    SteeringFrameKind kind{SteeringFrameKind::Command};
    // 값 없음은 Validity=0과 reserved angle로 표현한다. 실제값 0 rad와 다르다.
    std::optional<double> angle_rad;
    std::uint32_t sequence{0};
    std::uint32_t epoch{0};
    std::uint64_t source_time_ns{0};
    std::uint32_t causal_sequence{0};
    SteeringLocalState local_state{SteeringLocalState::Init};
    SteeringOrigin origin{SteeringOrigin::NoAcceptedInput};
};

// SocketCAN struct와 분리한 입력. Adapter는 실제 수신 종류/길이/flags를 보존해야 한다.
struct SteeringFrame {
    std::uint32_t can_id{0};
    bool is_fd{true};
    std::uint8_t fd_flags{0};  // BRS=1, ESI=2; FDF=4 표시는 허용한다.
    std::uint8_t payload_length{kSteeringPayloadSize};
    SteeringPayload payload{};
};

// Command/Actual stream마다 별도 state를 유지한다. 새 epoch의 explicit INIT에서만 초기화한다.
struct SteeringTxState {
    const SteeringFrameKind kind;
    e2e::P05ProtectState protection{};
};
struct SteeringRxState {
    const SteeringFrameKind kind;
    e2e::P05CheckState check{};
};

std::optional<e2e::P05Config> steering_e2e_config(SteeringFrameKind kind);
// P05: payload[0..28] + payload[31] + 설정된 DataID low/high; CRC byte 29–30 제외.
std::optional<std::uint16_t> steering_frame_crc(std::uint16_t can_id,
                                               const SteeringPayload& payload);

std::optional<SteeringFrame> encode_steering_frame(const SteeringMessage& message,
                                                 SteeringTxState& state);

// Envelope/CRC/field 표현을 검사한다. Freshness/sequence 진행/물리 한계/command 수용은 별도다.
// 성공해도 angle_rad가 없을 수 있으며, 이는 invalid/unavailable 진단 frame이다.
std::optional<SteeringMessage> decode_steering_frame(const SteeringFrame& frame);

// Stateful P05 검사. nullptr은 NONEWDATA. Frame 종류/ID/길이/flags도 검사한다.
// E2E 결과는 mode/epoch/source age/trace Sequence나 command 수용을 대신하지 않는다.
e2e::P05Return check_steering_e2e(const SteeringFrame* frame, SteeringRxState& state);

}  // namespace stratadrive::can
