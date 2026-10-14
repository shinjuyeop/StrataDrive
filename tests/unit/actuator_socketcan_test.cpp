#include "actuator_socketcan.hpp"
#include "steering_receiver.hpp"

#include <gtest/gtest.h>

#include <stdexcept>

namespace {
using namespace stratadrive;

TEST(SteeringSocketcan, RoundTripPreservesEncodedPayload) {
    can::SteeringMessage message;
    message.angle_rad = -0.2;
    message.epoch = 1;
    message.source_time_ns = 12345;
    can::SteeringTxState tx{can::SteeringFrameKind::Command};
    const auto encoded = can::encode_steering_frame(message, tx);
    ASSERT_TRUE(encoded);
    const auto result = socketcan::to_steering(socketcan::to_socketcan(*encoded));
    EXPECT_EQ(result.payload, encoded->payload);
    EXPECT_EQ(result.can_id, encoded->can_id);
    EXPECT_EQ(result.payload_length, 32);
    ASSERT_TRUE(can::decode_steering_frame(result));
    EXPECT_DOUBLE_EQ(*can::decode_steering_frame(result)->angle_rad, -0.2);
}

TEST(SteeringSocketcan, DoesNotNormalizeMalformedEnvelopeIntoValidSteering) {
    can::SteeringReceiver receiver({can::SteeringFrameKind::Command, -0.5, 0.5});
    ASSERT_TRUE(receiver.start_session(1, 100));
    socketcan::Frame transport;
    transport.can_id = can::kSteeringCommandId | 0x80000000U;
    transport.fd_flags = 1;
    transport.payload_length = 64;
    for (std::size_t index = 0; index < transport.payload.size(); ++index) {
        transport.payload[index] = static_cast<std::uint8_t>(index);
    }
    auto frame = socketcan::to_steering(transport);
    EXPECT_EQ(frame.can_id, transport.can_id);
    EXPECT_EQ(frame.fd_flags, transport.fd_flags);
    EXPECT_EQ(frame.payload_length, 64);
    EXPECT_EQ(frame.payload.back(), 31);
    EXPECT_EQ(receiver.receive(frame, 101).decision, can::SteeringReceiveDecision::MalformedEnvelope);
    transport.is_fd = false;
    transport.payload_length = 2;
    frame = socketcan::to_steering(transport);
    EXPECT_FALSE(frame.is_fd);
    EXPECT_EQ(frame.payload_length, 2);
    EXPECT_EQ(receiver.receive(frame, 102).decision, can::SteeringReceiveDecision::MalformedEnvelope);
    EXPECT_FALSE(receiver.last_accepted());
}

TEST(SteeringSocketcan, RejectsTransmitLengthBeyondSteeringStorage) {
    can::SteeringFrame frame;
    frame.payload_length = 64;
    EXPECT_THROW(socketcan::to_socketcan(frame), std::invalid_argument);
}

TEST(SteeringSocketcan, ValidatesInterfaceNameBeforeOpeningSocket) {
    EXPECT_THROW(socketcan::Endpoint(""), std::invalid_argument);
    EXPECT_THROW(socketcan::Endpoint("interface_name_is_too_long"), std::invalid_argument);
    EXPECT_THROW(socketcan::Endpoint(std::string("vcan\0hidden", 11)), std::invalid_argument);
    EXPECT_THROW(socketcan::Endpoint("vcan0", 0x800), std::invalid_argument);
}

TEST(BrakeSocketcan, RoundTripPreservesPressureAndUnavailable) {
    for (const auto kind : {can::BrakeFrameKind::Command, can::BrakeFrameKind::Actual}) {
        can::BrakeTxState tx{kind};
        can::BrakeMessage message;
        message.kind = kind;
        message.epoch = 1;
        for (const auto pressure : {std::optional<double>{2000000.0}, std::optional<double>{0.0},
                                   std::optional<double>{}}) {
            message.pressure_pa = pressure;
            const auto encoded = can::encode_brake_frame(message, tx);
            ASSERT_TRUE(encoded);
            const auto result = socketcan::to_brake(socketcan::to_socketcan(*encoded));
            EXPECT_EQ(result.payload, encoded->payload);
            EXPECT_EQ(result.can_id, encoded->can_id);
            EXPECT_EQ(result.payload_length, 32);
            const auto decoded = can::decode_brake_frame(result);
            ASSERT_TRUE(decoded);
            EXPECT_EQ(decoded->pressure_pa, pressure);
        }
    }
}

TEST(BrakeSocketcan, PreservesMalformedEnvelopeAndRejectsOversizedTx) {
    socketcan::Frame transport;
    transport.can_id = can::kBrakeCommandId | 0x80000000U;
    transport.payload_length = 64;
    transport.fd_flags = 1;
    auto frame = socketcan::to_brake(transport);
    EXPECT_EQ(frame.can_id, transport.can_id);
    EXPECT_EQ(frame.payload_length, 64);
    EXPECT_EQ(frame.fd_flags, 1);
    EXPECT_FALSE(can::decode_brake_frame(frame));
    EXPECT_THROW(socketcan::to_socketcan(frame), std::invalid_argument);
    transport.is_fd = false;
    transport.payload_length = 2;
    frame = socketcan::to_brake(transport);
    EXPECT_FALSE(frame.is_fd);
    EXPECT_EQ(frame.payload_length, 2);
    EXPECT_FALSE(can::decode_brake_frame(frame));
}

TEST(DriveSocketcan, PreservesCommandAndAll64ActualBytes) {
    for (const auto kind : {can::DriveFrameKind::Command, can::DriveFrameKind::Actual}) {
        can::DriveMessage message;
        message.kind = kind;
        message.epoch = 1;
        message.source_time_ns = 1000000000;
        message.torque_nm = -150;
        if (kind == can::DriveFrameKind::Actual) {
            message.wheel_speed = can::DriveWheelSpeed{10, 999000000};
            message.regen_capability = can::DriveRegenCapability{200, 999000000, 998000000};
            message.regen_limit_reason = can::DriveRegenLimitReason::ChargeAcceptanceLimited;
        }
        can::DriveTxState tx{kind};
        const auto encoded = can::encode_drive_frame(message, tx);
        ASSERT_TRUE(encoded);
        const auto result = socketcan::to_drive(socketcan::to_socketcan(*encoded));
        EXPECT_EQ(result.payload, encoded->payload);
        EXPECT_EQ(result.can_id, encoded->can_id);
        EXPECT_EQ(result.payload_length, encoded->payload_length);
        const auto decoded = can::decode_drive_frame(result);
        ASSERT_TRUE(decoded);
        EXPECT_EQ(decoded->torque_nm, message.torque_nm);
        if (message.regen_capability) {
            ASSERT_TRUE(decoded->regen_capability);
            EXPECT_EQ(decoded->regen_capability->input_time_ns, 998000000);
        }
        auto malformed = result;
        malformed.can_id |= 0x80000000U;
        malformed.payload_length = 48;
        malformed.fd_flags = 1;
        const auto preserved = socketcan::to_drive(socketcan::to_socketcan(malformed));
        EXPECT_EQ(preserved.can_id, malformed.can_id);
        EXPECT_EQ(preserved.payload_length, 48);
        EXPECT_EQ(preserved.fd_flags, 1);
        EXPECT_FALSE(can::decode_drive_frame(preserved));
    }
}
TEST(BmsSocketcan, Preserves48And64BytesWithoutAdmittingMalformedEnvelope) {
    for (const auto kind : {can::BmsFrameKind::PowerRequest, can::BmsFrameKind::PowerStatus,
                           can::BmsFrameKind::PowerLimits, can::BmsFrameKind::BatteryState,
                           can::BmsFrameKind::DriveBatteryLimits, can::BmsFrameKind::DrivePermission}) {
        can::BmsFrame frame;
        frame.can_id = static_cast<std::uint16_t>(kind);
        frame.payload_length = static_cast<std::uint8_t>(can::bms_e2e_config(kind)->data_length_bits/8);
        frame.payload[0] = 0x12; frame.payload[frame.payload_length-1] = 0x34;
        const auto decoded = socketcan::to_bms(socketcan::to_socketcan(frame));
        EXPECT_EQ(decoded.payload, frame.payload); EXPECT_EQ(decoded.payload_length, frame.payload_length);
        auto native = socketcan::to_socketcan(frame); native.can_id |= 0x80000000U; native.is_fd = false;
        native.payload_length = 49; native.fd_flags = 2;
        const auto malformed = socketcan::to_bms(native);
        EXPECT_EQ(malformed.can_id, native.can_id); EXPECT_EQ(malformed.payload_length, 49);
        EXPECT_FALSE(can::decode_bms_frame(malformed));
        frame.payload_length = 65; EXPECT_THROW(socketcan::to_socketcan(frame), std::invalid_argument);
    }
}

}  // namespace
