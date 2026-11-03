#pragma once
#include "owner_messages.hpp"

namespace stratadrive::transport {
// Owner-local bounded evidence, not a wire type and not a diagnostic command.
struct LeafAuthorityObservation {
    Leaf leaf{Leaf::Steering};
    std::uint32_t epoch{0};
    std::uint64_t enable_ns{0},observed_ns{0};
    LeafRequest accepted;
    bool independently_expired{false};
};
} // namespace stratadrive::transport
