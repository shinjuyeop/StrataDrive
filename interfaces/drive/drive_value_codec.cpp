#include "drive_value_codec.hpp"

#include <cmath>

namespace stratadrive::can {
namespace {
DriveValueBytes bytes(std::uint16_t raw) {
    return {static_cast<std::uint8_t>(raw & 0xFFU), static_cast<std::uint8_t>(raw >> 8U)};
}
std::uint32_t raw_value(const DriveValueBytes& value) {
    return static_cast<std::uint32_t>(value[0]) | (static_cast<std::uint32_t>(value[1]) << 8U);
}
struct UnsignedScale { double resolution; double maximum; };
std::optional<DriveValueBytes> encode_unsigned(double value, UnsignedScale scale) {
    if (!std::isfinite(value) || value < 0 || value > scale.maximum) return std::nullopt;
    return bytes(static_cast<std::uint16_t>(std::lround(value / scale.resolution)));
}
}  // namespace

std::optional<DriveValueBytes> encode_drive_torque(double torque_nm) {
    if (!std::isfinite(torque_nm) || std::abs(torque_nm) > kDriveTorqueWireMaxNm) return std::nullopt;
    // signed -> unsigned 변환은 modulo 2^16이다. unsigned -> signed narrowing에 의존하지 않는다.
    return bytes(static_cast<std::uint16_t>(std::lround(torque_nm / kDriveTorqueResolutionNm)));
}
std::optional<double> decode_drive_torque(const DriveValueBytes& value) {
    const auto raw = raw_value(value);
    if (raw == 0x8000U) return std::nullopt;
    const auto signed_raw = raw >= 0x8000U ? static_cast<std::int32_t>(raw) - 65536
                                         : static_cast<std::int32_t>(raw);
    return signed_raw * kDriveTorqueResolutionNm;
}
std::optional<DriveValueBytes> encode_drive_wheel_speed(double speed_rad_s) {
    return encode_unsigned(speed_rad_s, {kDriveWheelSpeedResolutionRadS, kDriveWheelSpeedWireMaxRadS});
}
std::optional<double> decode_drive_wheel_speed(const DriveValueBytes& value) {
    const auto raw = raw_value(value);
    if (raw == 0xFFFFU) return std::nullopt;
    return raw * kDriveWheelSpeedResolutionRadS;
}
std::optional<DriveValueBytes> encode_drive_regen_limit(double torque_nm) {
    return encode_unsigned(torque_nm, {kDriveTorqueResolutionNm, kDriveTorqueWireMaxNm});
}
std::optional<double> decode_drive_regen_limit(const DriveValueBytes& value) {
    const auto raw = raw_value(value);
    if (raw > 32767) return std::nullopt;
    return raw * kDriveTorqueResolutionNm;
}
}  // namespace stratadrive::can
