#pragma once

#include <cstdint>

namespace stratadrive::brake {
// Selected ECU output, not measured feedback. The SIL runner applies it outside
// ECU execution. issued_time_ns is the selection boundary, not target arrival.
enum class ActuationMode { Hold, Target, Protect };
struct Actuation {
    ActuationMode mode{ActuationMode::Hold};
    double target_pa{0};
    std::uint64_t issued_time_ns{0};
};
} // namespace stratadrive::brake
