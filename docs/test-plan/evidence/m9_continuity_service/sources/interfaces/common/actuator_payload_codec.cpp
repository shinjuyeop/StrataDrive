#include "actuator_payload_codec.hpp"

#include <algorithm>
#include <cstddef>

namespace stratadrive::can {
namespace {
struct Field { std::size_t offset; std::size_t width; };
constexpr Field kSequence{4, 4}, kEpoch{8, 4}, kSourceTime{12, 8};
constexpr Field kCausalSequence{20, 4}, kReserved{26, 3}, kCrc{29, 2};

void write_le(std::uint8_t* payload, Field field, std::uint64_t value) {
    for (std::size_t index = 0; index < field.width; ++index) {
        payload[field.offset + index] = static_cast<std::uint8_t>(value & 0xFFU);
        value >>= 8U;
    }
}

std::uint64_t read_le(const std::uint8_t* payload, Field field) {
    std::uint64_t value = 0;
    for (std::size_t index = 0; index < field.width; ++index) {
        value |= static_cast<std::uint64_t>(payload[field.offset + index]) << (8U * index);
    }
    return value;
}

bool valid_metadata(const ActuatorMetadata& metadata) {
    return metadata.epoch != 0 &&
           static_cast<std::uint8_t>(metadata.local_state) <= 3 &&
           static_cast<std::uint8_t>(metadata.origin) <= 2;
}

bool matches_layout(const e2e::P05Config& config, std::size_t length) {
    // 이 codec의 CRC/Counter 위치는 고정이다. 다른 P05 배치를 조용히 허용하지 않는다.
    return config.data_length_bits == length * 8 && config.offset_bits == 232;
}
void write_fields(std::uint8_t* payload, const ActuatorPayloadFields& fields) {
    payload[0] = fields.value[0];
    payload[1] = fields.value[1];
    payload[2] = 2;
    payload[3] = fields.valid ? 1 : 0;
    write_le(payload, kSequence, fields.metadata.sequence);
    write_le(payload, kEpoch, fields.metadata.epoch);
    write_le(payload, kSourceTime, fields.metadata.source_time_ns);
    write_le(payload, kCausalSequence, fields.metadata.causal_sequence);
    payload[24] = static_cast<std::uint8_t>(fields.metadata.local_state);
    payload[25] = static_cast<std::uint8_t>(fields.metadata.origin);
}
std::optional<ActuatorPayloadFields> read_fields(
    const std::uint8_t* payload, std::size_t length, const e2e::P05Config& config) {
    if (!matches_layout(config, length)) return std::nullopt;
    const auto crc = e2e::p05_crc(config, payload, length);
    if (!crc || read_le(payload, kCrc) != *crc || payload[2] != 2 ||
        payload[3] > 1 || read_le(payload, kReserved) != 0) return std::nullopt;
    ActuatorPayloadFields fields;
    fields.value = {payload[0], payload[1]};
    fields.valid = payload[3] == 1;
    fields.metadata.sequence = static_cast<std::uint32_t>(read_le(payload, kSequence));
    fields.metadata.epoch = static_cast<std::uint32_t>(read_le(payload, kEpoch));
    fields.metadata.source_time_ns = read_le(payload, kSourceTime);
    fields.metadata.causal_sequence = static_cast<std::uint32_t>(read_le(payload, kCausalSequence));
    fields.metadata.local_state = static_cast<ActuatorLocalState>(payload[24]);
    fields.metadata.origin = static_cast<ActuatorOrigin>(payload[25]);
    if (!valid_metadata(fields.metadata)) return std::nullopt;
    return fields;
}
}  // namespace

std::optional<ActuatorPayload> encode_actuator_payload(
    const ActuatorPayloadFields& fields, const e2e::P05Config& config,
    e2e::P05ProtectState& state) {
    ActuatorPayload payload{};
    if (!matches_layout(config, payload.size()) || !valid_metadata(fields.metadata)) return std::nullopt;
    write_fields(payload.data(), fields);
    if (e2e::p05_protect(config, state, payload.data(), payload.size()) != e2e::P05Return::Ok) return std::nullopt;
    return payload;
}

std::optional<ActuatorPayloadFields> decode_actuator_payload(
    const ActuatorPayload& payload, const e2e::P05Config& config) {
    return read_fields(payload.data(), payload.size(), config);
}

std::optional<ExtendedActuatorPayload> encode_extended_actuator_payload(
    const ExtendedActuatorPayloadFields& fields, const e2e::P05Config& config,
    e2e::P05ProtectState& state) {
    ExtendedActuatorPayload payload{};
    if (!matches_layout(config, payload.size()) || !valid_metadata(fields.base.metadata)) return std::nullopt;
    write_fields(payload.data(), fields.base);
    std::copy(fields.extension.begin(), fields.extension.end(), payload.begin() + 32);
    if (e2e::p05_protect(config, state, payload.data(), payload.size()) != e2e::P05Return::Ok) return std::nullopt;
    return payload;
}

std::optional<ExtendedActuatorPayloadFields> decode_extended_actuator_payload(
    const ExtendedActuatorPayload& payload, const e2e::P05Config& config) {
    const auto base = read_fields(payload.data(), payload.size(), config);
    if (!base) return std::nullopt;
    ExtendedActuatorPayloadFields fields{*base, {}};
    std::copy(payload.begin() + 32, payload.end(), fields.extension.begin());
    return fields;
}
}  // namespace stratadrive::can
