#include "steering_frame_codec.hpp"

#include "steering_angle_codec.hpp"

namespace stratadrive::can {
namespace {
constexpr std::uint8_t kSchemaVersion = 2;
constexpr std::uint8_t kFdFrameMarker = 0x04;
struct Field {
    std::size_t offset;
    std::size_t width;
};
constexpr Field kSequenceField{4, 4};
constexpr Field kEpochField{8, 4};
constexpr Field kSourceTimeField{12, 8};
constexpr Field kCausalSequenceField{20, 4};
constexpr Field kReservedField{26, 3};
constexpr Field kCrcField{29, 2};

bool known_id(std::uint32_t can_id) {
    return can_id == kSteeringCommandId || can_id == kSteeringActualId;
}

bool known_state(SteeringLocalState state) {
    return static_cast<std::uint8_t>(state) <=
           static_cast<std::uint8_t>(SteeringLocalState::FailSafe);
}

bool known_origin(SteeringOrigin origin) {
    return static_cast<std::uint8_t>(origin) <=
           static_cast<std::uint8_t>(SteeringOrigin::LocalProtection);
}

// 이름 있는 고정 field를 전달해 offset/width/value의 인자 순서 혼동을 줄인다.
void write_le(SteeringPayload& payload, const Field& field, std::uint64_t value) {
    for (std::size_t index = 0; index < field.width; ++index) {
        payload[field.offset + index] = static_cast<std::uint8_t>(value & 0xFFU);
        value >>= 8U;
    }
}

std::uint64_t read_le(const SteeringPayload& payload, const Field& field) {
    std::uint64_t value = 0;
    for (std::size_t index = 0; index < field.width; ++index) {
        value |= static_cast<std::uint64_t>(payload[field.offset + index]) << (8U * index);
    }
    return value;
}

bool valid_envelope(const SteeringFrame& frame) {
    return known_id(frame.can_id) && frame.is_fd &&
           frame.payload_length == kSteeringPayloadSize &&
           (frame.fd_flags & static_cast<std::uint8_t>(~kFdFrameMarker)) == 0;
}
}  // namespace

std::optional<e2e::P05Config> steering_e2e_config(SteeringFrameKind kind) {
    if (kind == SteeringFrameKind::Command) {
        return e2e::P05Config{kSteeringCommandDataId, 256, kSteeringE2eOffsetBits,
                              kSteeringMaxDeltaCounter};
    }
    if (kind == SteeringFrameKind::Actual) {
        return e2e::P05Config{kSteeringActualDataId, 256, kSteeringE2eOffsetBits,
                              kSteeringMaxDeltaCounter};
    }
    return std::nullopt;
}

std::optional<std::uint16_t> steering_frame_crc(std::uint16_t can_id,
                                               const SteeringPayload& payload) {
    const auto config = steering_e2e_config(static_cast<SteeringFrameKind>(can_id));
    if (!config) {
        return std::nullopt;
    }
    return e2e::p05_crc(*config, payload.data(), payload.size());
}

std::optional<SteeringFrame> encode_steering_frame(const SteeringMessage& message,
                                                 SteeringTxState& state) {
    const auto can_id = static_cast<std::uint16_t>(message.kind);
    const auto config = steering_e2e_config(message.kind);
    if (!config || state.kind != message.kind || message.epoch == 0 || !known_state(message.local_state) ||
        !known_origin(message.origin)) {
        return std::nullopt;
    }

    AngleBytes angle_bytes{0x00, 0x80};
    if (message.angle_rad) {
        const auto encoded = encode_steering_angle(*message.angle_rad);
        if (!encoded) {
            return std::nullopt;
        }
        angle_bytes = *encoded;
    }

    SteeringFrame frame;
    frame.can_id = can_id;
    auto& payload = frame.payload;
    payload[0] = angle_bytes[0];
    payload[1] = angle_bytes[1];
    payload[2] = kSchemaVersion;
    payload[3] = message.angle_rad.has_value() ? 1 : 0;
    write_le(payload, kSequenceField, message.sequence);
    write_le(payload, kEpochField, message.epoch);
    write_le(payload, kSourceTimeField, message.source_time_ns);
    write_le(payload, kCausalSequenceField, message.causal_sequence);
    payload[24] = static_cast<std::uint8_t>(message.local_state);
    payload[25] = static_cast<std::uint8_t>(message.origin);
    // 0으로 초기화된 payload[26..28]는 reserved=0으로 유지한다.
    if (e2e::p05_protect(*config, state.protection, payload.data(), payload.size()) !=
        e2e::P05Return::Ok) {
        return std::nullopt;
    }
    return frame;
}

std::optional<SteeringMessage> decode_steering_frame(const SteeringFrame& frame) {
    if (!valid_envelope(frame)) {
        return std::nullopt;
    }

    const auto& payload = frame.payload;
    const auto can_id = static_cast<std::uint16_t>(frame.can_id);
    const auto crc = steering_frame_crc(can_id, payload);
    if (!crc || read_le(payload, kCrcField) != *crc ||
        payload[2] != kSchemaVersion || payload[3] > 1 || read_le(payload, kReservedField) != 0) {
        return std::nullopt;
    }

    SteeringMessage message;
    message.kind = static_cast<SteeringFrameKind>(can_id);
    message.sequence = static_cast<std::uint32_t>(read_le(payload, kSequenceField));
    message.epoch = static_cast<std::uint32_t>(read_le(payload, kEpochField));
    message.source_time_ns = read_le(payload, kSourceTimeField);
    message.causal_sequence = static_cast<std::uint32_t>(read_le(payload, kCausalSequenceField));
    message.local_state = static_cast<SteeringLocalState>(payload[24]);
    message.origin = static_cast<SteeringOrigin>(payload[25]);
    if (message.epoch == 0 || !known_state(message.local_state) || !known_origin(message.origin)) {
        return std::nullopt;
    }

    const AngleBytes angle_bytes{payload[0], payload[1]};
    if (payload[3] == 1) {
        message.angle_rad = decode_steering_angle(angle_bytes);
        if (!message.angle_rad) {
            return std::nullopt;
        }
    } else if (angle_bytes != AngleBytes{0x00, 0x80}) {
        return std::nullopt;
    }
    return message;
}

e2e::P05Return check_steering_e2e(const SteeringFrame* frame, SteeringRxState& state) {
    const auto config = steering_e2e_config(state.kind);
    if (!config) {
        return e2e::P05Return::InputWrong;
    }
    if (frame == nullptr) {
        return e2e::p05_check(*config, state.check, nullptr, 0);
    }
    if (!valid_envelope(*frame) || frame->can_id != static_cast<std::uint16_t>(state.kind)) {
        return e2e::P05Return::InputWrong;
    }
    return e2e::p05_check(*config, state.check, frame->payload.data(), frame->payload.size());
}

}  // namespace stratadrive::can
