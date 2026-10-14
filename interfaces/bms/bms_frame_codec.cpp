#include "bms_frame_codec.hpp"

#include "bms_value_codec.hpp"

namespace stratadrive::can {
namespace {
using Payload = std::array<std::uint8_t, 64>;
template <std::size_t Offset, std::size_t Width>
void write_le(Payload& data, std::uint64_t value) {
    static_assert(Width <= sizeof(value) && Offset + Width <= 64);
    for (std::size_t index = 0; index < Width; ++index) {
        data[Offset + index] = static_cast<std::uint8_t>(value);
        value >>= 8U;
    }
}
template <std::size_t Offset, std::size_t Width>
std::uint64_t read_le(const Payload& data) {
    std::uint64_t value = 0;
    static_assert(Width <= sizeof(value) && Offset + Width <= 64);
    for (std::size_t index = 0; index < Width; ++index) {
        value |= static_cast<std::uint64_t>(data[Offset + index]) << (8U * index);
    }
    return value;
}
bool lifetime(std::uint64_t source, std::uint64_t expires) {
    return expires > source && expires - source <= kBmsMaxLifetimeNs;
}
bool any_actual(const BmsPowerStatus& value) {
    return value.state || value.positive_contactor_closed || value.negative_contactor_closed ||
           value.precharge_contactor_closed || value.condition_validity != 0 || value.hv_bus_voltage_v;
}
bool valid_limit(const std::optional<double>& value, BmsLimitReason reason) {
    if (!value) return reason == BmsLimitReason::InputsInvalid;
    return static_cast<std::uint8_t>(reason) < 5 &&
           (reason != BmsLimitReason::Disabled || *value == 0);
}
bool valid_message(const BmsMessage& message) {
    if (message.epoch == 0 || static_cast<std::uint8_t>(message.local_state) > 3 ||
        static_cast<std::uint8_t>(message.origin) > 2) return false;
    const auto source = message.source_time_ns;
    switch (message.kind) {
    case BmsFrameKind::PowerRequest: {
        const auto* value = std::get_if<BmsPowerRequest>(&message.content);
        if (!value) return false;
        if (!value->action) return value->expires_at_ns == 0 && value->parent_source_time_ns == 0;
        if (static_cast<std::uint16_t>(*value->action) > 2 || !lifetime(source, value->expires_at_ns) ||
            value->parent_source_time_ns > source) return false;
        if (message.origin == ActuatorOrigin::NoAcceptedInput &&
            (*value->action != BmsPowerAction::KeepOff || message.causal_sequence != 0 ||
             value->parent_source_time_ns != 0)) return false;
        return message.origin != ActuatorOrigin::LocalProtection || *value->action != BmsPowerAction::Enable;
    }
    case BmsFrameKind::PowerLimits:
    case BmsFrameKind::DriveBatteryLimits: {
        const auto* value = std::get_if<BmsPowerLimits>(&message.content);
        return value && valid_limit(value->charge_power_w, value->charge_reason) &&
               valid_limit(value->discharge_power_w, value->discharge_reason) &&
               ((value->charge_power_w || value->discharge_power_w) ? value->input_time_ns <= source
                                                                   : value->input_time_ns == 0);
    }
    case BmsFrameKind::BatteryState: {
        const auto* value = std::get_if<BmsBatteryState>(&message.content);
        return value && (!value->soc || value->soc->source_time_ns <= source) &&
               (!value->electrical || value->electrical->source_time_ns <= source) &&
               (!value->temperature || value->temperature->source_time_ns <= source);
    }
    case BmsFrameKind::PowerStatus: {
        const auto* value = std::get_if<BmsPowerStatus>(&message.content);
        return value && (!value->state || static_cast<std::uint16_t>(*value->state) <= 4) &&
               value->condition_bits <= 31 && value->condition_validity <= 31 &&
               (value->condition_bits & static_cast<std::uint8_t>(~value->condition_validity)) == 0 &&
               (any_actual(*value) ? value->input_time_ns <= source :
                (value->input_time_ns == 0 && value->input_sequence == 0)) &&
               value->accepted_request_source_time_ns <= source &&
               (message.origin != ActuatorOrigin::NoAcceptedInput ||
                (message.causal_sequence == 0 && value->accepted_request_source_time_ns == 0));
    }
    case BmsFrameKind::DrivePermission: {
        const auto* value = std::get_if<BmsDriveGrant>(&message.content);
        if (!value) return false;
        if (!value->permission) return value->power_status_sequence == 0 &&
            value->power_status_source_time_ns == 0 && value->input_time_ns == 0 && value->expires_at_ns == 0;
        if (static_cast<std::uint16_t>(*value->permission) > 1 || !lifetime(source, value->expires_at_ns) ||
            value->input_time_ns > value->power_status_source_time_ns ||
            value->power_status_source_time_ns > source) return false;
        return *value->permission != BmsDrivePermission::AllowNormal ||
               (message.origin == ActuatorOrigin::NormalPath &&
                (message.local_state == ActuatorLocalState::Normal || message.local_state == ActuatorLocalState::Degraded));
    }
    }
    return false;
}
bool valid_envelope(const BmsFrame& frame) {
    const auto config = bms_e2e_config(static_cast<BmsFrameKind>(frame.can_id));
    // Full ID is checked; narrowing a flagged/extended ID must never admit it.
    return config && frame.can_id == static_cast<std::uint16_t>(frame.can_id) && frame.is_fd &&
           (frame.fd_flags & static_cast<std::uint8_t>(~0x04U)) == 0 &&
           frame.payload_length == config->data_length_bits / 8;
}
bool put_value(Payload& data, std::size_t offset, BmsValueKind kind, const std::optional<double>& value) {
    BmsValueBytes bytes{0xFF, 0xFF};
    if (kind == BmsValueKind::Current || kind == BmsValueKind::Temperature) bytes = {0, 0x80};
    if (value) {
        const auto encoded = encode_bms_value(kind, *value);
        if (!encoded) return false;
        bytes = *encoded;
    }
    data[offset] = bytes[0]; data[offset + 1] = bytes[1];
    return true;
}
bool get_value(const Payload& data, std::size_t offset, BmsValueKind kind, std::uint8_t flag,
               std::optional<double>& value) {
    if (flag > 1) return false;
    const BmsValueBytes bytes{data[offset], data[offset + 1]};
    if (flag == 1) { value = decode_bms_value(kind, bytes); return value.has_value(); }
    const BmsValueBytes sentinel = kind == BmsValueKind::Current || kind == BmsValueKind::Temperature
                                  ? BmsValueBytes{0, 0x80} : BmsValueBytes{0xFF, 0xFF};
    value.reset();
    return bytes == sentinel;
}
std::uint8_t contact(const std::optional<bool>& value) {
    return value ? static_cast<std::uint8_t>(*value ? 1 : 0) : 255;
}
bool get_contact(std::uint8_t raw, std::optional<bool>& value) {
    if (raw == 255) { value.reset(); return true; }
    if (raw > 1) return false;
    value = raw == 1;
    return true;
}
bool encode_content(const BmsMessage& message, Payload& data) {
    switch (message.kind) {
    case BmsFrameKind::PowerRequest: {
        const auto& value = std::get<BmsPowerRequest>(message.content);
        write_le<0, 2>(data, value.action ? static_cast<std::uint16_t>(*value.action) : 65535);
        data[3] = value.action.has_value();
        write_le<32, 8>(data, value.expires_at_ns); write_le<40, 8>(data, value.parent_source_time_ns);
        return true;
    }
    case BmsFrameKind::PowerLimits:
    case BmsFrameKind::DriveBatteryLimits: {
        const auto& value = std::get<BmsPowerLimits>(message.content);
        if (!put_value(data, 0, BmsValueKind::PowerLimit, value.charge_power_w) ||
            !put_value(data, 32, BmsValueKind::PowerLimit, value.discharge_power_w)) return false;
        data[3] = value.charge_power_w.has_value(); data[34] = value.discharge_power_w.has_value();
        data[35] = static_cast<std::uint8_t>(value.charge_reason);
        data[36] = static_cast<std::uint8_t>(value.discharge_reason);
        write_le<40, 8>(data, value.input_time_ns);
        return true;
    }
    case BmsFrameKind::BatteryState: {
        const auto& value = std::get<BmsBatteryState>(message.content);
        if (!put_value(data, 0, BmsValueKind::Soc, value.soc ? std::optional<double>{value.soc->fraction} : std::nullopt) ||
            !put_value(data, 32, BmsValueKind::Voltage, value.electrical ? std::optional<double>{value.electrical->voltage_v} : std::nullopt) ||
            !put_value(data, 34, BmsValueKind::Current, value.electrical ? std::optional<double>{value.electrical->current_a} : std::nullopt) ||
            !put_value(data, 36, BmsValueKind::Temperature, value.temperature ? std::optional<double>{value.temperature->celsius} : std::nullopt)) return false;
        data[3] = value.soc.has_value(); data[38] = value.electrical.has_value(); data[39] = value.temperature.has_value();
        write_le<40, 8>(data, value.soc ? value.soc->source_time_ns : 0);
        write_le<48, 8>(data, value.electrical ? value.electrical->source_time_ns : 0);
        write_le<56, 8>(data, value.temperature ? value.temperature->source_time_ns : 0);
        return true;
    }
    case BmsFrameKind::PowerStatus: {
        const auto& value = std::get<BmsPowerStatus>(message.content);
        write_le<0, 2>(data, value.state ? static_cast<std::uint16_t>(*value.state) : 65535);
        data[3] = value.state.has_value();
        data[32] = contact(value.positive_contactor_closed); data[33] = contact(value.negative_contactor_closed);
        data[34] = contact(value.precharge_contactor_closed); data[35] = value.condition_bits;
        data[36] = value.condition_validity; data[42] = value.hv_bus_voltage_v.has_value();
        if (!put_value(data, 40, BmsValueKind::Voltage, value.hv_bus_voltage_v)) return false;
        write_le<44, 8>(data, value.input_time_ns); write_le<52, 8>(data, value.accepted_request_source_time_ns);
        write_le<60, 4>(data, value.input_sequence);
        return true;
    }
    case BmsFrameKind::DrivePermission: {
        const auto& value = std::get<BmsDriveGrant>(message.content);
        write_le<0, 2>(data, value.permission ? static_cast<std::uint16_t>(*value.permission) : 65535);
        data[3] = value.permission.has_value();
        write_le<32, 4>(data, value.power_status_sequence); write_le<36, 8>(data, value.power_status_source_time_ns);
        write_le<44, 8>(data, value.input_time_ns); write_le<52, 8>(data, value.expires_at_ns);
        return true;
    }
    }
    return false;
}
bool decode_content(const Payload& data, BmsMessage& message) {
    const auto primary = static_cast<std::uint16_t>(read_le<0, 2>(data));
    const auto flag = data[3];
    if (flag > 1) return false;
    switch (message.kind) {
    case BmsFrameKind::PowerRequest: {
        BmsPowerRequest value;
        if (flag) { if (primary > 2) return false; value.action = static_cast<BmsPowerAction>(primary); }
        else if (primary != 65535) return false;
        value.expires_at_ns = read_le<32, 8>(data); value.parent_source_time_ns = read_le<40, 8>(data);
        message.content = value;
        break;
    }
    case BmsFrameKind::PowerLimits:
    case BmsFrameKind::DriveBatteryLimits: {
        BmsPowerLimits value;
        if (data[35] > 5 || data[36] > 5 || read_le<37, 3>(data) != 0 ||
            !get_value(data, 0, BmsValueKind::PowerLimit, flag, value.charge_power_w) ||
            !get_value(data, 32, BmsValueKind::PowerLimit, data[34], value.discharge_power_w)) return false;
        value.charge_reason = static_cast<BmsLimitReason>(data[35]);
        value.discharge_reason = static_cast<BmsLimitReason>(data[36]);
        value.input_time_ns = read_le<40, 8>(data); message.content = value;
        break;
    }
    case BmsFrameKind::BatteryState: {
        BmsBatteryState value;
        std::optional<double> soc, voltage, current, temperature;
        if (!get_value(data, 0, BmsValueKind::Soc, flag, soc) ||
            !get_value(data, 32, BmsValueKind::Voltage, data[38], voltage) ||
            !get_value(data, 34, BmsValueKind::Current, data[38], current) ||
            !get_value(data, 36, BmsValueKind::Temperature, data[39], temperature)) return false;
        if (soc) value.soc = BmsSocSample{*soc, read_le<40, 8>(data)};
        else if (read_le<40, 8>(data) != 0) return false;
        if (voltage) value.electrical = BmsElectricalSample{*voltage, *current, read_le<48, 8>(data)};
        else if (read_le<48, 8>(data) != 0) return false;
        if (temperature) value.temperature = BmsTemperatureSample{*temperature, read_le<56, 8>(data)};
        else if (read_le<56, 8>(data) != 0) return false;
        message.content = value;
        break;
    }
    case BmsFrameKind::PowerStatus: {
        BmsPowerStatus value;
        if (flag) { if (primary > 4) return false; value.state = static_cast<BmsPowerState>(primary); }
        else if (primary != 65535) return false;
        if (!get_contact(data[32], value.positive_contactor_closed) ||
            !get_contact(data[33], value.negative_contactor_closed) ||
            !get_contact(data[34], value.precharge_contactor_closed) || read_le<37, 3>(data) != 0 || data[43] != 0 ||
            !get_value(data, 40, BmsValueKind::Voltage, data[42], value.hv_bus_voltage_v)) return false;
        value.condition_bits = data[35]; value.condition_validity = data[36];
        value.input_time_ns = read_le<44, 8>(data); value.accepted_request_source_time_ns = read_le<52, 8>(data);
        value.input_sequence = static_cast<std::uint32_t>(read_le<60, 4>(data)); message.content = value;
        break;
    }
    case BmsFrameKind::DrivePermission: {
        BmsDriveGrant value;
        if (flag) { if (primary > 1) return false; value.permission = static_cast<BmsDrivePermission>(primary); }
        else if (primary != 65535) return false;
        if (read_le<60, 4>(data) != 0) return false;
        value.power_status_sequence = static_cast<std::uint32_t>(read_le<32, 4>(data));
        value.power_status_source_time_ns = read_le<36, 8>(data); value.input_time_ns = read_le<44, 8>(data);
        value.expires_at_ns = read_le<52, 8>(data); message.content = value;
        break;
    }
    }
    return valid_message(message);
}
}  // namespace

std::optional<e2e::P05Config> bms_e2e_config(BmsFrameKind kind) {
    switch (kind) {
    case BmsFrameKind::PowerRequest: return e2e::P05Config{0x1301, 384, 232, 10};
    case BmsFrameKind::PowerStatus: return e2e::P05Config{0x1302, 512, 232, 10};
    case BmsFrameKind::PowerLimits: return e2e::P05Config{0x1303, 384, 232, 10};
    case BmsFrameKind::BatteryState: return e2e::P05Config{0x1304, 512, 232, 10};
    case BmsFrameKind::DriveBatteryLimits: return e2e::P05Config{0x1203, 384, 232, 10};
    case BmsFrameKind::DrivePermission: return e2e::P05Config{0x1204, 512, 232, 10};
    }
    return std::nullopt;
}
std::optional<std::uint16_t> bms_frame_crc(const BmsFrame& frame) {
    if (!valid_envelope(frame)) return std::nullopt;
    return e2e::p05_crc(*bms_e2e_config(static_cast<BmsFrameKind>(frame.can_id)), frame.payload.data(), frame.payload_length);
}
std::optional<BmsFrame> encode_bms_frame(const BmsMessage& message, BmsTxState& state) {
    const auto config = bms_e2e_config(message.kind);
    if (!config || message.kind != state.kind || !valid_message(message)) return std::nullopt;
    BmsFrame frame;
    frame.can_id = static_cast<std::uint16_t>(message.kind);
    frame.payload_length = static_cast<std::uint8_t>(config->data_length_bits / 8);
    auto& data = frame.payload;
    data[2] = 1;
    write_le<4, 4>(data, message.sequence); write_le<8, 4>(data, message.epoch);
    write_le<12, 8>(data, message.source_time_ns); write_le<20, 4>(data, message.causal_sequence);
    data[24] = static_cast<std::uint8_t>(message.local_state); data[25] = static_cast<std::uint8_t>(message.origin);
    if (!encode_content(message, data)) return std::nullopt;
    if (e2e::p05_protect(*config, state.protection, data.data(), frame.payload_length) != e2e::P05Return::Ok) return std::nullopt;
    return frame;
}
std::optional<BmsMessage> decode_bms_frame(const BmsFrame& frame) {
    const auto crc = bms_frame_crc(frame);
    if (!crc || *crc != read_le<29, 2>(frame.payload) || frame.payload[2] != 1 || read_le<26, 3>(frame.payload) != 0) return std::nullopt;
    BmsMessage message;
    message.kind = static_cast<BmsFrameKind>(frame.can_id);
    message.sequence = static_cast<std::uint32_t>(read_le<4, 4>(frame.payload));
    message.epoch = static_cast<std::uint32_t>(read_le<8, 4>(frame.payload));
    message.source_time_ns = read_le<12, 8>(frame.payload);
    message.causal_sequence = static_cast<std::uint32_t>(read_le<20, 4>(frame.payload));
    message.local_state = static_cast<ActuatorLocalState>(frame.payload[24]);
    message.origin = static_cast<ActuatorOrigin>(frame.payload[25]);
    if (!decode_content(frame.payload, message)) return std::nullopt;
    return message;
}
e2e::P05Return check_bms_e2e(const BmsFrame* frame, BmsRxState& state) {
    const auto config = bms_e2e_config(state.kind);
    if (!config) return e2e::P05Return::InputWrong;
    if (!frame) return e2e::p05_check(*config, state.check, nullptr, 0);
    if (!valid_envelope(*frame) || frame->can_id != static_cast<std::uint16_t>(state.kind)) return e2e::P05Return::InputWrong;
    return e2e::p05_check(*config, state.check, frame->payload.data(), frame->payload_length);
}
std::optional<BmsFrame> forward_bms_limits(const BmsMessage& source, BmsTxState& downstream) {
    if (source.kind != BmsFrameKind::PowerLimits || downstream.kind != BmsFrameKind::DriveBatteryLimits) return std::nullopt;
    auto forwarded = source;
    forwarded.kind = BmsFrameKind::DriveBatteryLimits;
    return encode_bms_frame(forwarded, downstream);
}
}  // namespace stratadrive::can
