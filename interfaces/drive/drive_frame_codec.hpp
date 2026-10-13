#pragma once

#include "actuator_payload_codec.hpp"

namespace stratadrive::can {
inline constexpr std::uint16_t kDriveCommandId = 0x182;
inline constexpr std::uint16_t kDriveActualId = 0x282;
inline constexpr std::uint16_t kDriveCommandDataId = 0x1201;
inline constexpr std::uint16_t kDriveActualDataId = 0x1202;
inline constexpr std::size_t kDriveCommandPayloadSize = 32;
inline constexpr std::size_t kDriveActualPayloadSize = 64;
enum class DriveFrameKind : std::uint16_t { Command = kDriveCommandId, Actual = kDriveActualId };
enum class DriveRegenLimitReason : std::uint8_t {
    Nominal, MotorOrSpeedLimited, ChargeAcceptanceLimited, Disabled, InputsInvalid
};
struct DriveWheelSpeed { double value_rad_s; std::uint64_t source_time_ns; };
struct DriveRegenCapability {
    double torque_limit_nm;
    std::uint64_t source_time_ns;  // capability 산출 시각, cached sample은 보존
    std::uint64_t input_time_ns;   // 계산에 사용한 가장 오래된 dependency의 원천 시각
};
struct DriveMessage : ActuatorMetadata {
    DriveFrameKind kind{DriveFrameKind::Command};
    std::optional<double> torque_nm;
    std::optional<DriveWheelSpeed> wheel_speed;
    std::optional<DriveRegenCapability> regen_capability;
    DriveRegenLimitReason regen_limit_reason{DriveRegenLimitReason::InputsInvalid};
};
struct DriveFrame {
    std::uint32_t can_id{0};
    bool is_fd{true};
    std::uint8_t fd_flags{0};
    std::uint8_t payload_length{kDriveCommandPayloadSize};
    ExtendedActuatorPayload payload{};
};
struct DriveTxState { const DriveFrameKind kind; e2e::P05ProtectState protection{}; };
struct DriveRxState { const DriveFrameKind kind; e2e::P05CheckState check{}; };

std::optional<e2e::P05Config> drive_e2e_config(DriveFrameKind kind);
std::optional<std::uint16_t> drive_frame_crc(const DriveFrame& frame);
std::optional<DriveFrame> encode_drive_frame(const DriveMessage& message, DriveTxState& state);
// Stateless wire decode만 수행한다. Aux feedback과 torque의 application 유효성은 별도다.
std::optional<DriveMessage> decode_drive_frame(const DriveFrame& frame);
e2e::P05Return check_drive_e2e(const DriveFrame* frame, DriveRxState& state);
}  // namespace stratadrive::can
