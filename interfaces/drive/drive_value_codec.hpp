#pragma once

#include <array>
#include <cstdint>
#include <optional>

namespace stratadrive::can {
using DriveValueBytes = std::array<std::uint8_t, 2>;
inline constexpr double kDriveTorqueResolutionNm = 0.1;
inline constexpr double kDriveTorqueWireMaxNm = 32767 * kDriveTorqueResolutionNm;
inline constexpr double kDriveWheelSpeedResolutionRadS = 0.01;
inline constexpr double kDriveWheelSpeedWireMaxRadS = 65534 * kDriveWheelSpeedResolutionRadS;

// Aggregate driven-wheel 기준. +구동/-전진 회생/0 토크 요구 없음; 00 80은 invalid.
// Wire 범위를 반올림 전에 검사한다. 물리 calibration이나 saturation은 아니다.
std::optional<DriveValueBytes> encode_drive_torque(double torque_nm);
std::optional<double> decode_drive_torque(const DriveValueBytes& bytes);
// 전진 ODD: nonnegative wheel speed; FF FF는 invalid.
std::optional<DriveValueBytes> encode_drive_wheel_speed(double speed_rad_s);
std::optional<double> decode_drive_wheel_speed(const DriveValueBytes& bytes);
// Nonnegative 회생 토크 크기. Command의 음수 표현 범위를 넘는 한계는 거부한다.
std::optional<DriveValueBytes> encode_drive_regen_limit(double torque_nm);
std::optional<double> decode_drive_regen_limit(const DriveValueBytes& bytes);
}  // namespace stratadrive::can
