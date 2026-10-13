#include "brake_pressure_codec.hpp"

#include <cmath>

namespace stratadrive::can {
std::optional<PressureBytes> encode_brake_pressure(double pressure_pa) {
    if (!std::isfinite(pressure_pa) || pressure_pa < 0 || pressure_pa > kBrakePressureWireMaxPa) {
        return std::nullopt;
    }
    const auto raw = static_cast<std::uint16_t>(std::lround(pressure_pa / kBrakePressureResolutionPa));
    return PressureBytes{static_cast<std::uint8_t>(raw & 0xFFU),
                         static_cast<std::uint8_t>(raw >> 8U)};
}

std::optional<double> decode_brake_pressure(const PressureBytes& bytes) {
    const auto raw = static_cast<std::uint32_t>(bytes[0]) |
                     (static_cast<std::uint32_t>(bytes[1]) << 8U);
    if (raw == 0xFFFFU) return std::nullopt;
    return raw * kBrakePressureResolutionPa;
}
}  // namespace stratadrive::can
