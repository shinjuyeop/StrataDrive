#pragma once
#include <cstddef>
#include <cstdint>

namespace stratadrive::remote {
// Trace correlation only. Does not validate a packet, grant authority, or
// replace the full canonical decoder/CRC/clock checks on admission.
struct OwnerTraceIdentity {
    std::uint32_t epoch{0};std::uint64_t token{0};std::uint32_t sender{0},receiver{0};
};
inline OwnerTraceIdentity owner_trace_identity(const std::uint8_t* bytes,std::size_t size) noexcept {
    if(!bytes || size<58 || bytes[0]!='S' || bytes[1]!='D' || bytes[2]!='R' || bytes[3]!='V' ||
       bytes[4]!=1 || bytes[5] || bytes[6] || bytes[7] || (bytes[24]!=3 && bytes[24]!=4))return {};
    const auto read=[&](std::size_t at,unsigned width){std::uint64_t value=0;for(unsigned i=0;i<width;++i)value|=std::uint64_t(bytes[at+i])<<(8*i);return value;};
    return {static_cast<std::uint32_t>(read(25,4)),read(29,8),static_cast<std::uint32_t>(read(8,4)),static_cast<std::uint32_t>(read(12,4))};
}
} // namespace stratadrive::remote
