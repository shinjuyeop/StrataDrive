#pragma once
#include <cstdint>

namespace stratadrive::can {
// Caller supplies a separately validated Central power-request identity/deadline.
// Never construct this trusted context by reading the incoming CAN frame alone.
struct BmsParentContext {
    std::uint32_t epoch;
    std::uint32_t sequence;
    std::uint64_t source_time_ns;
    std::uint64_t expires_at_ns;
};
} // namespace stratadrive::can
