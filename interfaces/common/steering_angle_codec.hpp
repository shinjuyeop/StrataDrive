#pragma once

#include <array>
#include <cstdint>
#include <optional>

namespace stratadrive::can {

// M1 field 초안. 전체 frame validation이나 actuator 허용 범위 검사는 아니다.
using AngleBytes = std::array<std::uint8_t, 2>;
inline constexpr double kAngleResolutionRad = 0.0001;
inline constexpr double kAngleWireMaxRad = 32767 * kAngleResolutionRad;

// 표현 범위 밖, NaN, Inf는 nullopt를 반환한다. Clamp하지 않는다.
std::optional<AngleBytes> encode_steering_angle(double angle_rad);

// 입력은 frame에서 추출한 정확히 2 bytes다. Reserved raw는 nullopt다.
std::optional<double> decode_steering_angle(const AngleBytes& bytes);

}  // namespace stratadrive::can
