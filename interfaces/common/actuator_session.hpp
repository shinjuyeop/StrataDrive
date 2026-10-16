#pragma once

#include <cstdint>

namespace stratadrive {
// Trusted local application-to-physical mapping. This is not learned from CAN
// or a measurement. Group the mapping and enable boundary as one startup input.
struct ActuatorSession {
    std::uint32_t application_epoch;
    std::uint32_t model_epoch;
    std::uint64_t enable_ns;
};
} // namespace stratadrive
