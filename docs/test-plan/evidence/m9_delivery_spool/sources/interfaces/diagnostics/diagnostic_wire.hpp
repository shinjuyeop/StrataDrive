#pragma once
#include "diagnostics.hpp"
#include <variant>

namespace stratadrive::diagnostics::wire {
using Bytes=std::vector<std::uint8_t>;
constexpr std::size_t kMaxPacket=2048;
struct Data { std::uint64_t stream,sequence; std::uint32_t registry; Event event; };
struct Ack { std::uint64_t stream,sequence; std::uint32_t registry,event_crc; };
using Message=std::variant<Data,Ack>;
// Non-RT canonical datagrams. CRC detects corruption, not peer impersonation.
std::uint32_t event_crc(const Event&);
Bytes encode(const Message&);
Message decode(const Bytes&);
} // namespace stratadrive::diagnostics::wire
