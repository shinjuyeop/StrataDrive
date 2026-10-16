#pragma once

#include <cstdint>

namespace stratadrive::steering {
// Direct local angle acquisition, not a CAN command or a diagnostic plant getter.
// Repeated reads preserve identity/time/value. A new sequence requires a newer source time.
struct AngleMeasurement {
    std::uint32_t model_epoch;
    std::uint64_t sequence;
    std::uint64_t source_time_ns;
    double angle_rad;
};
}  // namespace stratadrive::steering
