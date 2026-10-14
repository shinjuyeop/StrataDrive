#pragma once

#include <array>
#include <cstdint>
#include <optional>

namespace stratadrive::can {
enum class BmsValueKind { Soc, Voltage, Current, Temperature, PowerLimit };
using BmsValueBytes = std::array<std::uint8_t, 2>;
// Wire representation only; physical calibration/limits are receiver/model inputs.
std::optional<BmsValueBytes> encode_bms_value(BmsValueKind kind, double value);
std::optional<double> decode_bms_value(BmsValueKind kind, const BmsValueBytes& bytes);
}  // namespace stratadrive::can
