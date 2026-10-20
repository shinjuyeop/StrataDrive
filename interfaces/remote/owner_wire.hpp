#pragma once
#include "owner_messages.hpp"
#include "session_control.hpp"
#include <array>

namespace stratadrive::remote {
// This credit attests the coordinator's completed global session. Receipt of
// local Release alone is insufficient. Issued only on the trusted control path.
struct RunLease {
    session::Plan plan;
    std::uint32_t sequence{0};
    std::uint64_t source_time_ns{0},expires_at_ns{0};
};
struct ProtectionRequest {
    std::uint32_t epoch{0}; std::uint64_t token{0},source_time_ns{0},deadline_ns{0};
};
struct ProtectionAck { ProtectionRequest request; std::uint64_t selected_ns{0}; bool selected{false}; };
using OwnerPayload=std::variant<session::Control,session::Ack,RunLease,transport::ZoneRequest,transport::TxResult,
    transport::LeafRequest,transport::LeafReport,ProtectionRequest,ProtectionAck,transport::Feedback>;
struct OwnerMessage {
    session::Role from{session::Role::CentralIngress},to{session::Role::FrontZone};
    std::uint64_t clock_domain{0}; // trusted boot/clock agreement; not inferred from traffic
    OwnerPayload payload;
};
inline constexpr std::uint16_t kOwnerWireVersion=1;
inline constexpr std::size_t kOwnerWireCapacity=512;
struct OwnerPacket { std::array<std::uint8_t,kOwnerWireCapacity> bytes{}; std::size_t size{0}; };
// Canonical little endian, finite binary64, explicit optional/tag discriminants.
// CRC32C covers route, clock and all sideband authority as well as raw CAN bytes.
// Neither CRC nor successful parsing authenticates a sender or grants an Epoch.
std::uint32_t owner_crc32c(const std::uint8_t* bytes,std::size_t size);
std::optional<OwnerPacket> encode_owner_message(const OwnerMessage& message);
std::optional<OwnerMessage> decode_owner_message(const std::uint8_t* bytes,std::size_t size);
} // namespace stratadrive::remote
