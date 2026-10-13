#include "brake_frame_codec.hpp"

#include "brake_pressure_codec.hpp"

namespace stratadrive::can {
namespace {
bool valid_envelope(const BrakeFrame& frame) {
    return (frame.can_id == kBrakeCommandId || frame.can_id == kBrakeActualId) &&
           frame.is_fd && frame.payload_length == kBrakePayloadSize &&
           (frame.fd_flags & static_cast<std::uint8_t>(~0x04U)) == 0;
}
}  // namespace

std::optional<e2e::P05Config> brake_e2e_config(BrakeFrameKind kind) {
    if (kind == BrakeFrameKind::Command) {
        return e2e::P05Config{kBrakeCommandDataId, 256, kBrakeE2eOffsetBits, kBrakeMaxDeltaCounter};
    }
    if (kind == BrakeFrameKind::Actual) {
        return e2e::P05Config{kBrakeActualDataId, 256, kBrakeE2eOffsetBits, kBrakeMaxDeltaCounter};
    }
    return std::nullopt;
}

std::optional<std::uint16_t> brake_frame_crc(std::uint16_t can_id, const BrakePayload& payload) {
    const auto config = brake_e2e_config(static_cast<BrakeFrameKind>(can_id));
    if (!config) return std::nullopt;
    return e2e::p05_crc(*config, payload.data(), payload.size());
}

std::optional<BrakeFrame> encode_brake_frame(const BrakeMessage& message, BrakeTxState& state) {
    const auto config = brake_e2e_config(message.kind);
    if (!config || state.kind != message.kind) return std::nullopt;
    PressureBytes bytes{0xFF, 0xFF};
    if (message.pressure_pa) {
        const auto encoded = encode_brake_pressure(*message.pressure_pa);
        if (!encoded) return std::nullopt;
        bytes = *encoded;
    }
    const auto payload = encode_actuator_payload(
        {bytes, message.pressure_pa.has_value(), message}, *config, state.protection);
    if (!payload) return std::nullopt;
    BrakeFrame frame;
    frame.can_id = static_cast<std::uint16_t>(message.kind);
    frame.payload = *payload;
    return frame;
}

std::optional<BrakeMessage> decode_brake_frame(const BrakeFrame& frame) {
    if (!valid_envelope(frame)) return std::nullopt;
    const auto kind = static_cast<BrakeFrameKind>(frame.can_id);
    const auto config = brake_e2e_config(kind);
    if (!config) return std::nullopt;
    const auto fields = decode_actuator_payload(frame.payload, *config);
    if (!fields) return std::nullopt;
    BrakeMessage message;
    static_cast<ActuatorMetadata&>(message) = fields->metadata;
    message.kind = kind;
    if (fields->valid) {
        message.pressure_pa = decode_brake_pressure(fields->value);
        if (!message.pressure_pa) return std::nullopt;
    } else if (fields->value != PressureBytes{0xFF, 0xFF}) {
        return std::nullopt;
    }
    return message;
}

e2e::P05Return check_brake_e2e(const BrakeFrame* frame, BrakeRxState& state) {
    const auto config = brake_e2e_config(state.kind);
    if (!config) return e2e::P05Return::InputWrong;
    if (frame == nullptr) return e2e::p05_check(*config, state.check, nullptr, 0);
    if (!valid_envelope(*frame) || frame->can_id != static_cast<std::uint16_t>(state.kind)) {
        return e2e::P05Return::InputWrong;
    }
    return e2e::p05_check(*config, state.check, frame->payload.data(), frame->payload.size());
}
}  // namespace stratadrive::can
