#include "bms_value_codec.hpp"

#include <cmath>

namespace stratadrive::can {
namespace {
struct Scale { double step; double minimum; double maximum; bool signed_value; };
std::optional<Scale> scale(BmsValueKind kind) {
    switch (kind) {
    case BmsValueKind::Soc: return Scale{0.0001, 0, 1, false};
    case BmsValueKind::Voltage: return Scale{0.1, 0, 6553.4, false};
    case BmsValueKind::Current:
    case BmsValueKind::Temperature: return Scale{0.1, -3276.7, 3276.7, true};
    case BmsValueKind::PowerLimit: return Scale{10, 0, 655340, false};
    }
    return std::nullopt;
}
}  // namespace
std::optional<BmsValueBytes> encode_bms_value(BmsValueKind kind, double value) {
    const auto config = scale(kind);
    if (!config || !std::isfinite(value) || value < config->minimum || value > config->maximum) {
        return std::nullopt;
    }
    const auto raw = static_cast<std::uint16_t>(std::lround(value / config->step));
    return BmsValueBytes{static_cast<std::uint8_t>(raw), static_cast<std::uint8_t>(raw >> 8U)};
}
std::optional<double> decode_bms_value(BmsValueKind kind, const BmsValueBytes& bytes) {
    const auto config = scale(kind);
    if (!config) return std::nullopt;
    const auto raw = static_cast<std::uint32_t>(bytes[0]) | (static_cast<std::uint32_t>(bytes[1]) << 8U);
    if ((config->signed_value && raw == 32768) || (!config->signed_value && raw == 65535) ||
        (kind == BmsValueKind::Soc && raw > 10000)) return std::nullopt;
    const auto value = config->signed_value && raw >= 32768 ? static_cast<std::int32_t>(raw) - 65536
                                                          : static_cast<std::int32_t>(raw);
    // Divide by the integer raw-per-unit scale so endpoint decoding does not
    // produce one ULP outside the decimal wire range (e.g. 65534 * 0.1).
    if (kind == BmsValueKind::PowerLimit) return value * 10.0;
    return value / (kind == BmsValueKind::Soc ? 10000.0 : 10.0);
}
}  // namespace stratadrive::can
