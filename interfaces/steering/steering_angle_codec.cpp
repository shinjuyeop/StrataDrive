#include "steering_angle_codec.hpp"

#include <cmath>

namespace stratadrive::can {

std::optional<AngleBytes> encode_steering_angle(double angle_rad) {
    if (!std::isfinite(angle_rad) || angle_rad < -kAngleWireMaxRad ||
        angle_rad > kAngleWireMaxRad) {
        return std::nullopt;
    }

    const auto raw = std::lround(angle_rad / kAngleResolutionRad);
    // 음수→unsigned 변환의 modulo 규칙으로 two's complement bytes를 만든다.
    const auto bits = static_cast<std::uint16_t>(raw);
    return AngleBytes{static_cast<std::uint8_t>(bits & 0xFFU),
                      static_cast<std::uint8_t>(bits >> 8U)};
}

std::optional<double> decode_steering_angle(const AngleBytes& bytes) {
    const std::uint32_t bits = static_cast<std::uint32_t>(bytes[0]) |
                               (static_cast<std::uint32_t>(bytes[1]) << 8U);
    if (bits == 0x8000U) {
        return std::nullopt;
    }

    // 범위 밖 unsigned→signed cast 없이 부호를 복원한다.
    const auto raw = bits < 0x8000U ? static_cast<std::int32_t>(bits)
                                  : static_cast<std::int32_t>(bits) - 65536;
    return raw * kAngleResolutionRad;
}

}  // namespace stratadrive::can
