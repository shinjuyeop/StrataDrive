#pragma once

#include <cstdint>

namespace stratadrive::steering {
// Selected ECU output, not measured feedback. The SIL runner applies it outside
// ECU execution. issued_time_ns is the selection boundary, not target arrival.
enum class ActuationMode { Hold, Target };
struct Actuation {
    ActuationMode mode{ActuationMode::Hold};
    double target_rad{0};
    std::uint64_t issued_time_ns{0};
};
} // namespace stratadrive::steering
