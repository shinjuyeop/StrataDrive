#pragma once

#include <cstdint>

namespace stratadrive::brake {
// Local acquisition identity is independent of the application's command epoch.
struct PressureMeasurement {
    std::uint32_t model_epoch;
    std::uint64_t sequence, source_time_ns;
    double pressure_pa;
};
}  // namespace stratadrive::brake
