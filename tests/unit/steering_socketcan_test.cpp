#include "steering_socketcan.hpp"
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
}  // namespace
