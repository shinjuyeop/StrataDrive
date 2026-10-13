#pragma once

#include <array>
#include <cstdint>
#include <optional>

namespace stratadrive::can {
using PressureBytes = std::array<std::uint8_t, 2>;
inline constexpr double kBrakePressureResolutionPa = 1000.0;
inline constexpr double kBrakePressureWireMaxPa = 65534 * kBrakePressureResolutionPa;

// 유효 raw 0..65534, unsigned LE. 0은 제동 해제이며 FF FF는 invalid/unavailable.
// 비유한/음수/wire 범위 초과를 반올림 전에 거부한다. 물리 한계로 clamp하지 않는다.
std::optional<PressureBytes> encode_brake_pressure(double pressure_pa);
std::optional<double> decode_brake_pressure(const PressureBytes& bytes);
}  // namespace stratadrive::can
