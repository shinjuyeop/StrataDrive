#include "drive_frame_codec.hpp"

#include "drive_value_codec.hpp"

#include <algorithm>

namespace stratadrive::can {
namespace {
struct Field { std::size_t offset; std::size_t width; };
constexpr Field kSpeedTime{8, 8}, kCapabilityTime{16, 8}, kInputTime{24, 8};
void write_le(ActuatorExtension& extension, Field field, std::uint64_t value) {
    for (std::size_t index = 0; index < field.width; ++index) {
        extension[field.offset + index] = static_cast<std::uint8_t>(value & 0xFFU);
        value >>= 8U;
    }
}
std::uint64_t read_le(const ActuatorExtension& extension, Field field) {
    std::uint64_t value = 0;
    for (std::size_t index = 0; index < field.width; ++index) {
        value |= static_cast<std::uint64_t>(extension[field.offset + index]) << (8U * index);
    }
    return value;
}
bool valid_envelope(const DriveFrame& frame) {
    if (frame.can_id != kDriveCommandId && frame.can_id != kDriveActualId) return false;
    const auto config = drive_e2e_config(static_cast<DriveFrameKind>(frame.can_id));
    return config && frame.is_fd && frame.payload_length == config->data_length_bits / 8 &&
           (frame.fd_flags & static_cast<std::uint8_t>(~0x04U)) == 0;
}
std::optional<ActuatorExtension> encode_extension(const DriveMessage& message) {
    ActuatorExtension extension{};
    extension[0] = extension[1] = extension[4] = extension[5] = 0xFF;
    extension[3] = static_cast<std::uint8_t>(message.regen_limit_reason);
    if (message.wheel_speed) {
        const auto speed = encode_drive_wheel_speed(message.wheel_speed->value_rad_s);
        if (!speed) return std::nullopt;
        extension[0] = (*speed)[0];
        extension[1] = (*speed)[1];
        extension[2] = 1;
        write_le(extension, kSpeedTime, message.wheel_speed->source_time_ns);
    }
    if (message.regen_capability) {
        const auto limit = encode_drive_regen_limit(message.regen_capability->torque_limit_nm);
        if (!limit || !message.wheel_speed || extension[3] >= 4 ||
            (message.regen_limit_reason == DriveRegenLimitReason::Disabled && *limit != DriveValueBytes{0, 0})) {
            return std::nullopt;
        }
        extension[4] = (*limit)[0];
        extension[5] = (*limit)[1];
        extension[6] = 1;
        write_le(extension, kCapabilityTime, message.regen_capability->source_time_ns);
        write_le(extension, kInputTime, message.regen_capability->input_time_ns);
    } else if (message.regen_limit_reason != DriveRegenLimitReason::InputsInvalid) {
        return std::nullopt;
    }
    return extension;
}
bool decode_extension(const ActuatorExtension& extension, DriveMessage& message) {
    if (extension[2] > 1 || extension[6] > 1 || extension[3] > 4 || extension[7] != 0) return false;
    const DriveValueBytes speed_bytes{extension[0], extension[1]};
    if (extension[2] == 1) {
        const auto speed = decode_drive_wheel_speed(speed_bytes);
        if (!speed) return false;
        message.wheel_speed = DriveWheelSpeed{*speed, read_le(extension, kSpeedTime)};
    } else if (speed_bytes != DriveValueBytes{0xFF, 0xFF} || read_le(extension, kSpeedTime) != 0) {
        return false;
    }
    message.regen_limit_reason = static_cast<DriveRegenLimitReason>(extension[3]);
    const DriveValueBytes limit_bytes{extension[4], extension[5]};
    if (extension[6] == 1) {
        const auto limit = decode_drive_regen_limit(limit_bytes);
        if (!limit || !message.wheel_speed || extension[3] >= 4 ||
            (message.regen_limit_reason == DriveRegenLimitReason::Disabled && *limit != 0)) return false;
        message.regen_capability = DriveRegenCapability{
            *limit, read_le(extension, kCapabilityTime), read_le(extension, kInputTime)};
    } else if (limit_bytes != DriveValueBytes{0xFF, 0xFF} || extension[3] != 4 ||
               read_le(extension, kCapabilityTime) != 0 || read_le(extension, kInputTime) != 0) {
        return false;
    }
    return true;
}
}  // namespace

std::optional<e2e::P05Config> drive_e2e_config(DriveFrameKind kind) {
    if (kind == DriveFrameKind::Command) return e2e::P05Config{kDriveCommandDataId, 256, 232, 10};
    if (kind == DriveFrameKind::Actual) return e2e::P05Config{kDriveActualDataId, 512, 232, 10};
    return std::nullopt;
}
std::optional<std::uint16_t> drive_frame_crc(const DriveFrame& frame) {
    if (!valid_envelope(frame)) return std::nullopt;
    return e2e::p05_crc(*drive_e2e_config(static_cast<DriveFrameKind>(frame.can_id)),
                        frame.payload.data(), frame.payload_length);
}
std::optional<DriveFrame> encode_drive_frame(const DriveMessage& message, DriveTxState& state) {
    const auto config = drive_e2e_config(message.kind);
    if (!config || state.kind != message.kind) return std::nullopt;
    DriveValueBytes torque{0x00, 0x80};
    if (message.torque_nm) {
        const auto value = encode_drive_torque(*message.torque_nm);
        if (!value) return std::nullopt;
        torque = *value;
    }
    DriveFrame frame;
    frame.can_id = static_cast<std::uint16_t>(message.kind);
    frame.payload_length = static_cast<std::uint8_t>(config->data_length_bits / 8);
    const ActuatorPayloadFields base{torque, message.torque_nm.has_value(), message};
    if (message.kind == DriveFrameKind::Command) {
        if (message.wheel_speed || message.regen_capability ||
            message.regen_limit_reason != DriveRegenLimitReason::InputsInvalid) return std::nullopt;
        const auto payload = encode_actuator_payload(base, *config, state.protection);
        if (!payload) return std::nullopt;
        std::copy(payload->begin(), payload->end(), frame.payload.begin());
    } else {
        const auto extension = encode_extension(message);
        if (!extension) return std::nullopt;
        const auto payload = encode_extended_actuator_payload({base, *extension}, *config, state.protection);
        if (!payload) return std::nullopt;
        frame.payload = *payload;
    }
    return frame;
}
std::optional<DriveMessage> decode_drive_frame(const DriveFrame& frame) {
    if (!valid_envelope(frame)) return std::nullopt;
    DriveMessage message;
    message.kind = static_cast<DriveFrameKind>(frame.can_id);
    const auto config = *drive_e2e_config(message.kind);
    std::optional<ActuatorPayloadFields> base;
    if (message.kind == DriveFrameKind::Command) {
        ActuatorPayload payload{};
        std::copy_n(frame.payload.begin(), payload.size(), payload.begin());
        base = decode_actuator_payload(payload, config);
    } else {
        const auto fields = decode_extended_actuator_payload(frame.payload, config);
        if (!fields || !decode_extension(fields->extension, message)) return std::nullopt;
        base = fields->base;
    }
    if (!base) return std::nullopt;
    static_cast<ActuatorMetadata&>(message) = base->metadata;
    if (base->valid) {
        message.torque_nm = decode_drive_torque(base->value);
        if (!message.torque_nm) return std::nullopt;
    } else if (base->value != DriveValueBytes{0x00, 0x80}) {
        return std::nullopt;
    }
    return message;
}
e2e::P05Return check_drive_e2e(const DriveFrame* frame, DriveRxState& state) {
    const auto config = drive_e2e_config(state.kind);
    if (!config) return e2e::P05Return::InputWrong;
    if (frame == nullptr) return e2e::p05_check(*config, state.check, nullptr, 0);
    if (!valid_envelope(*frame) || frame->can_id != static_cast<std::uint16_t>(state.kind)) {
        return e2e::P05Return::InputWrong;
    }
    return e2e::p05_check(*config, state.check, frame->payload.data(), frame->payload_length);
}
}  // namespace stratadrive::can
