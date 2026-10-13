#pragma once

#include "actuator_payload_codec.hpp"

#include <cstddef>

namespace stratadrive::can {
inline constexpr std::uint16_t kBrakeCommandId = 0x181;
inline constexpr std::uint16_t kBrakeActualId = 0x281;
inline constexpr std::size_t kBrakePayloadSize = 32;
inline constexpr std::uint16_t kBrakeCommandDataId = 0x1101;
inline constexpr std::uint16_t kBrakeActualDataId = 0x1102;
inline constexpr std::uint16_t kBrakeE2eOffsetBits = 232;
inline constexpr std::uint8_t kBrakeMaxDeltaCounter = 10;
using BrakePayload = ActuatorPayload;

enum class BrakeFrameKind : std::uint16_t { Command = kBrakeCommandId, Actual = kBrakeActualId };
using BrakeLocalState = ActuatorLocalState;
using BrakeOrigin = ActuatorOrigin;

struct BrakeMessage : ActuatorMetadata {
    BrakeFrameKind kind{BrakeFrameKind::Command};
    // 유효한 0 Pa와 구분한다. Actual은 독립 모델 sample이며 Command echo가 아니다.
    std::optional<double> pressure_pa;
};

struct BrakeFrame {
    std::uint32_t can_id{0};
    bool is_fd{true};
    std::uint8_t fd_flags{0};
    std::uint8_t payload_length{kBrakePayloadSize};
    BrakePayload payload{};
};

struct BrakeTxState { const BrakeFrameKind kind; e2e::P05ProtectState protection{}; };
struct BrakeRxState { const BrakeFrameKind kind; e2e::P05CheckState check{}; };

std::optional<e2e::P05Config> brake_e2e_config(BrakeFrameKind kind);
std::optional<std::uint16_t> brake_frame_crc(std::uint16_t can_id, const BrakePayload& payload);
std::optional<BrakeFrame> encode_brake_frame(const BrakeMessage& message, BrakeTxState& state);
// Stateless wire decode: 성공해도 pressure가 없을 수 있다. Freshness/mode/물리 범위 수용은 별도다.
std::optional<BrakeMessage> decode_brake_frame(const BrakeFrame& frame);
e2e::P05Return check_brake_e2e(const BrakeFrame* frame, BrakeRxState& state);
}  // namespace stratadrive::can
