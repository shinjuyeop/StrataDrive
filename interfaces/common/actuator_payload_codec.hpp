#pragma once

#include "e2e_profile5.hpp"

#include <array>
#include <cstdint>
#include <optional>

namespace stratadrive::can {

using ActuatorPayload = std::array<std::uint8_t, 32>;
using ExtendedActuatorPayload = std::array<std::uint8_t, 64>;
using ActuatorExtension = std::array<std::uint8_t, 32>;
enum class ActuatorLocalState : std::uint8_t { Init, Normal, Degraded, FailSafe };
enum class ActuatorOrigin : std::uint8_t { NoAcceptedInput, NormalPath, LocalProtection };

struct ActuatorMetadata {
    std::uint32_t sequence{0};
    std::uint32_t epoch{0};
    std::uint64_t source_time_ns{0};
    std::uint32_t causal_sequence{0};
    ActuatorLocalState local_state{ActuatorLocalState::Init};
    ActuatorOrigin origin{ActuatorOrigin::NoAcceptedInput};
};

struct ActuatorPayloadFields {
    std::array<std::uint8_t, 2> value{};
    bool valid{false};
    ActuatorMetadata metadata{};
};

// Schema 2의 공통 wire 배치와 P05만 담당한다. 값의 단위/invalid code와
// CAN envelope, freshness, mode/range 수용 정책은 각 actuator가 검사한다.
std::optional<ActuatorPayload> encode_actuator_payload(
    const ActuatorPayloadFields& fields, const e2e::P05Config& config,
    e2e::P05ProtectState& state);
std::optional<ActuatorPayloadFields> decode_actuator_payload(
    const ActuatorPayload& payload, const e2e::P05Config& config);

// 첫 32 byte의 schema 2 배치는 동일하다. 뒤 32 byte도 같은 P05 CRC로 보호한다.
// Extension의 의미/유효성은 domain codec이 검사한다.
struct ExtendedActuatorPayloadFields {
    ActuatorPayloadFields base;
    ActuatorExtension extension;
};
std::optional<ExtendedActuatorPayload> encode_extended_actuator_payload(
    const ExtendedActuatorPayloadFields& fields, const e2e::P05Config& config,
    e2e::P05ProtectState& state);
std::optional<ExtendedActuatorPayloadFields> decode_extended_actuator_payload(
    const ExtendedActuatorPayload& payload, const e2e::P05Config& config);

}  // namespace stratadrive::can
