#include "steering_frame_codec.hpp"

#include "steering_angle_codec.hpp"

namespace stratadrive::can {
namespace {
bool valid_envelope(const SteeringFrame& frame) {
    return (frame.can_id == kSteeringCommandId || frame.can_id == kSteeringActualId) && frame.is_fd &&
           frame.payload_length == kSteeringPayloadSize &&
           (frame.fd_flags & static_cast<std::uint8_t>(~0x04U)) == 0;
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
    if (!config || state.kind != message.kind) {
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

    const ActuatorMetadata metadata{message.sequence, message.epoch, message.source_time_ns,
                                    message.causal_sequence, message.local_state, message.origin};
    const auto payload = encode_actuator_payload(
        {angle_bytes, message.angle_rad.has_value(), metadata}, *config, state.protection);
    if (!payload) return std::nullopt;
    SteeringFrame frame;
    frame.can_id = can_id;
    frame.payload = *payload;
    return frame;
}

std::optional<SteeringMessage> decode_steering_frame(const SteeringFrame& frame) {
    if (!valid_envelope(frame)) {
        return std::nullopt;
    }

    const auto kind = static_cast<SteeringFrameKind>(frame.can_id);
    const auto config = steering_e2e_config(kind);
    if (!config) return std::nullopt;
    const auto fields = decode_actuator_payload(frame.payload, *config);
    if (!fields) return std::nullopt;
    SteeringMessage message;
    message.kind = kind;
    message.sequence = fields->metadata.sequence;
    message.epoch = fields->metadata.epoch;
    message.source_time_ns = fields->metadata.source_time_ns;
    message.causal_sequence = fields->metadata.causal_sequence;
    message.local_state = fields->metadata.local_state;
    message.origin = fields->metadata.origin;
    if (fields->valid) {
        message.angle_rad = decode_steering_angle(fields->value);
        if (!message.angle_rad) return std::nullopt;
    } else if (fields->value != AngleBytes{0x00, 0x80}) {
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
