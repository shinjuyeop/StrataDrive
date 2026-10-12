#include "steering_frame_codec.hpp"

#include <gtest/gtest.h>

#include <limits>

namespace {
using stratadrive::can::SteeringFrame;
using stratadrive::can::SteeringFrameKind;
using stratadrive::can::SteeringLocalState;
using stratadrive::can::SteeringMessage;
using stratadrive::can::SteeringOrigin;
using stratadrive::can::SteeringPayload;
using stratadrive::can::SteeringTxState;
using stratadrive::can::SteeringRxState;
using stratadrive::can::check_steering_e2e;
using stratadrive::can::decode_steering_frame;
using stratadrive::can::encode_steering_frame;
using stratadrive::can::kSteeringActualId;
using stratadrive::can::kSteeringCommandId;
using stratadrive::can::kSteeringPayloadSize;
using stratadrive::can::steering_frame_crc;

// ICD의 독립 설계 vectors. Encoder 출력으로 생성한 기대값이 아니다.
constexpr SteeringPayload kCommandPositive{
    0xD0, 0x07, 0x02, 0x01, 0x00, 0x00, 0x00, 0x00,
    0x01, 0x00, 0x00, 0x00, 0x00, 0xCA, 0x9A, 0x3B,
    0x00, 0x00, 0x00, 0x00, 0x07, 0x00, 0x00, 0x00,
    0x01, 0x01, 0x00, 0x00, 0x00, 0xEB, 0x26, 0x00};
constexpr SteeringPayload kActualPositive{
    0xDC, 0x05, 0x02, 0x01, 0x00, 0x00, 0x00, 0x00,
    0x01, 0x00, 0x00, 0x00, 0x80, 0x60, 0x33, 0x3C,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x01, 0x01, 0x00, 0x00, 0x00, 0x52, 0x2D, 0x00};
constexpr SteeringPayload kCommandNegative{
    0x30, 0xF8, 0x02, 0x01, 0x01, 0x00, 0x00, 0x00,
    0x01, 0x00, 0x00, 0x00, 0x00, 0xF7, 0xCB, 0x3C,
    0x00, 0x00, 0x00, 0x00, 0x08, 0x00, 0x00, 0x00,
    0x01, 0x01, 0x00, 0x00, 0x00, 0x82, 0xBA, 0x01};

std::optional<SteeringFrame> encode_fixture(const SteeringMessage& message) {
    SteeringTxState tx{message.kind};
    return encode_steering_frame(message, tx);
}

SteeringMessage command_message() {
    SteeringMessage message;
    message.angle_rad = 0.2;
    message.epoch = 1;
    message.source_time_ns = 1000000000;
    message.causal_sequence = 7;
    message.local_state = SteeringLocalState::Normal;
    message.origin = SteeringOrigin::NormalPath;
    return message;
}

SteeringFrame command_frame() {
    SteeringFrame frame;
    frame.can_id = kSteeringCommandId;
    frame.payload = kCommandPositive;
    return frame;
}

// CRC를 다시 계산해, 손상 검사를 통과한 뒤에도 잘못된 field를 거부하는지 시험한다.
void reseal(SteeringFrame& frame) {
    const auto crc = steering_frame_crc(static_cast<std::uint16_t>(frame.can_id), frame.payload);
    ASSERT_TRUE(crc);
    frame.payload[29] = static_cast<std::uint8_t>(*crc & 0xFFU);
    frame.payload[30] = static_cast<std::uint8_t>(*crc >> 8U);
}

TEST(SteeringFrameCodec, MatchesIndependentGoldenVectors) {
    auto actual = command_message();
    actual.kind = SteeringFrameKind::Actual;
    actual.angle_rad = 0.15;
    actual.source_time_ns = 1010000000;
    actual.causal_sequence = 0;
    auto negative = command_message();
    negative.angle_rad = -0.2;
    negative.sequence = 1;
    negative.source_time_ns = 1020000000;
    negative.causal_sequence = 8;
    struct Vector {
        SteeringMessage message;
        SteeringPayload payload;
    };
    const Vector vectors[] = {{command_message(), kCommandPositive},
                              {actual, kActualPositive}, {negative, kCommandNegative}};
    for (const auto& vector : vectors) {
        SteeringTxState tx{vector.message.kind};
        if (vector.message.sequence == 1) {
            ASSERT_TRUE(encode_steering_frame(command_message(), tx));
        }
        const auto encoded = encode_steering_frame(vector.message, tx);
        ASSERT_TRUE(encoded);
        EXPECT_EQ(encoded->can_id, static_cast<std::uint16_t>(vector.message.kind));
        EXPECT_TRUE(encoded->is_fd);
        EXPECT_EQ(encoded->fd_flags, 0);
        EXPECT_EQ(encoded->payload_length, 32);
        EXPECT_EQ(encoded->payload, vector.payload);
        const auto decoded = decode_steering_frame(*encoded);
        ASSERT_TRUE(decoded);
        ASSERT_TRUE(decoded->angle_rad);
        EXPECT_NEAR(*decoded->angle_rad, *vector.message.angle_rad, 1e-12);
        EXPECT_EQ(decoded->kind, vector.message.kind);
        EXPECT_EQ(decoded->sequence, vector.message.sequence);
        EXPECT_EQ(decoded->epoch, vector.message.epoch);
        EXPECT_EQ(decoded->source_time_ns, vector.message.source_time_ns);
        EXPECT_EQ(decoded->causal_sequence, vector.message.causal_sequence);
        EXPECT_EQ(decoded->local_state, vector.message.local_state);
        EXPECT_EQ(decoded->origin, vector.message.origin);
    }
}

TEST(SteeringFrameCodec, RejectsInvalidEncoderFields) {
    const double infinity = std::numeric_limits<double>::infinity();
    for (double angle : {4.0, -4.0, infinity, -infinity,
                         std::numeric_limits<double>::quiet_NaN()}) {
        auto message = command_message();
        message.angle_rad = angle;
        EXPECT_FALSE(encode_fixture(message));
    }
    auto message = command_message();
    message.epoch = 0;
    EXPECT_FALSE(encode_fixture(message));
    message = command_message();
    message.kind = static_cast<SteeringFrameKind>(0x181);
    EXPECT_FALSE(encode_fixture(message));
    message = command_message();
    message.local_state = static_cast<SteeringLocalState>(4);
    EXPECT_FALSE(encode_fixture(message));
    message = command_message();
    message.origin = static_cast<SteeringOrigin>(3);
    EXPECT_FALSE(encode_fixture(message));
}

TEST(SteeringFrameCodec, DistinguishesUnavailableFromZeroAngle) {
    auto message = command_message();
    message.kind = SteeringFrameKind::Actual;
    message.angle_rad.reset();
    message.causal_sequence = 0;
    message.local_state = SteeringLocalState::Init;
    message.origin = SteeringOrigin::NoAcceptedInput;
    const auto frame = encode_fixture(message);
    ASSERT_TRUE(frame);
    EXPECT_EQ(frame->payload[0], 0x00);
    EXPECT_EQ(frame->payload[1], 0x80);
    EXPECT_EQ(frame->payload[3], 0);
    const auto decoded = decode_steering_frame(*frame);
    ASSERT_TRUE(decoded);
    EXPECT_FALSE(decoded->angle_rad);

    message.angle_rad = 0.0;
    const auto zero = encode_fixture(message);
    ASSERT_TRUE(zero);
    EXPECT_EQ(zero->payload[1], 0);
    EXPECT_EQ(zero->payload[3], 1);
    const auto decoded_zero = decode_steering_frame(*zero);
    ASSERT_TRUE(decoded_zero);
    ASSERT_TRUE(decoded_zero->angle_rad);
    EXPECT_DOUBLE_EQ(*decoded_zero->angle_rad, 0.0);

    auto inconsistent = *frame;
    inconsistent.payload[1] = 0;  // Validity=0인데 reserved angle이 아니다.
    reseal(inconsistent);
    EXPECT_FALSE(decode_steering_frame(inconsistent));
    inconsistent = *frame;
    inconsistent.payload[3] = 1;  // Validity=1인데 reserved angle이다.
    reseal(inconsistent);
    EXPECT_FALSE(decode_steering_frame(inconsistent));
}

TEST(SteeringFrameCodec, RejectsMalformedEnvelope) {
    for (std::uint32_t id : {0U, 0x181U, 0x5A0U, 0x280U,
                             0x80000180U, 0x40000180U, 0x20000180U}) {
        auto frame = command_frame();
        frame.can_id = id;
        EXPECT_FALSE(decode_steering_frame(frame)) << id;
    }
    for (std::uint8_t length : {0, 8, 31, 33, 64}) {
        auto frame = command_frame();
        frame.payload_length = length;
        EXPECT_FALSE(decode_steering_frame(frame));
    }
    auto frame = command_frame();
    frame.is_fd = false;
    EXPECT_FALSE(decode_steering_frame(frame));
    for (std::uint8_t flags : {1, 2, 3, 8, 255}) {
        frame = command_frame();
        frame.fd_flags = flags;
        EXPECT_FALSE(decode_steering_frame(frame));
    }
    frame = command_frame();
    frame.fd_flags = 4;  // SocketCAN CANFD_FDF marker는 허용한다.
    EXPECT_TRUE(decode_steering_frame(frame));
}

TEST(SteeringFrameCodec, RejectsSingleBitCorruptionInEveryPayloadByte) {
    for (std::size_t index = 0; index < kSteeringPayloadSize; ++index) {
        auto frame = command_frame();
        frame.payload[index] ^= 1U;
        EXPECT_FALSE(decode_steering_frame(frame)) << index;
    }
}

TEST(SteeringFrameCodec, RejectsInvalidStructureEvenWithMatchingCrc) {
    struct Mutation {
        std::size_t byte;
        std::uint8_t value;
    };
    const Mutation mutations[] = {{2, 0}, {2, 1}, {2, 3}, {3, 2}, {8, 0},
                                  {24, 4}, {25, 3}, {26, 1}, {28, 1}};
    for (const auto& mutation : mutations) {
        auto frame = command_frame();
        frame.payload[mutation.byte] = mutation.value;
        reseal(frame);
        EXPECT_FALSE(decode_steering_frame(frame)) << mutation.byte;
    }
}

TEST(SteeringFrameCodec, PreservesExactUint64TimeAndUint32Boundaries) {
    auto message = command_message();
    message.sequence = std::numeric_limits<std::uint32_t>::max();
    message.epoch = std::numeric_limits<std::uint32_t>::max();
    message.causal_sequence = std::numeric_limits<std::uint32_t>::max();
    // 2^53을 넘는 정수도 double을 거치지 않고 그대로 보존한다.
    struct TimestampVector {
        std::uint64_t timestamp;
        std::array<std::uint8_t, 8> bytes;
    };
    const TimestampVector vectors[] = {
        {0x0020000000000001ULL, {0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x20, 0x00}},
        {0xFFFFFFFFFFFFFFFFULL, {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF}},
    };
    for (const auto& vector : vectors) {
        message.source_time_ns = vector.timestamp;
        const auto frame = encode_fixture(message);
        ASSERT_TRUE(frame);
        for (std::size_t index = 0; index < vector.bytes.size(); ++index) {
            EXPECT_EQ(frame->payload[12 + index], vector.bytes[index]);
        }
        const auto decoded = decode_steering_frame(*frame);
        ASSERT_TRUE(decoded);
        EXPECT_EQ(decoded->source_time_ns, vector.timestamp);
        EXPECT_EQ(decoded->sequence, message.sequence);
        EXPECT_EQ(decoded->epoch, message.epoch);
        EXPECT_EQ(decoded->causal_sequence, message.causal_sequence);
    }
}

TEST(SteeringFrameCodec, CrcCoversConfiguredDataIdAndExcludesStoredCrcBytes) {
    EXPECT_EQ(steering_frame_crc(kSteeringCommandId, kCommandPositive), 0x26EB);
    EXPECT_EQ(steering_frame_crc(kSteeringActualId, kActualPositive), 0x2D52);
    EXPECT_EQ(steering_frame_crc(kSteeringCommandId, kCommandNegative), 0xBA82);
    EXPECT_NE(steering_frame_crc(kSteeringActualId, kCommandPositive), 0x26EB);
    EXPECT_FALSE(steering_frame_crc(0x181, kCommandPositive));
    auto payload = kCommandPositive;
    payload[29] = 0;
    payload[30] = 0;
    EXPECT_EQ(steering_frame_crc(kSteeringCommandId, payload), 0x26EB);
    payload[31] = 1;
    EXPECT_NE(steering_frame_crc(kSteeringCommandId, payload), 0x26EB);
}

TEST(SteeringFrameCodec, KeepsCountersPerStreamAndDoesNotConsumeRejectedEncoding) {
    SteeringTxState command_tx{SteeringFrameKind::Command};
    SteeringTxState actual_tx{SteeringFrameKind::Actual};
    auto message = command_message();
    ASSERT_TRUE(encode_steering_frame(message, command_tx));  // Command counter=0
    auto invalid = message;
    invalid.angle_rad = 4.0;
    EXPECT_FALSE(encode_steering_frame(invalid, command_tx));
    message.kind = SteeringFrameKind::Actual;
    EXPECT_FALSE(encode_steering_frame(message, command_tx));
    const auto actual = encode_steering_frame(message, actual_tx);
    ASSERT_TRUE(actual);
    EXPECT_EQ(actual->payload[31], 0);
    message.kind = SteeringFrameKind::Command;
    const auto command = encode_steering_frame(message, command_tx);
    ASSERT_TRUE(command);
    EXPECT_EQ(command->payload[31], 1);
    // Trace Sequence는 Counter와 독립이다.
    EXPECT_EQ(command->payload[4], 0);
}

TEST(SteeringFrameCodec, StatefulE2eCheckIsBoundToItsStream) {
    using stratadrive::e2e::P05Return;
    using stratadrive::e2e::P05Status;
    auto frame = command_frame();
    SteeringRxState rx{SteeringFrameKind::Command};
    EXPECT_EQ(check_steering_e2e(&frame, rx), P05Return::Ok);
    EXPECT_EQ(rx.check.status, P05Status::Ok);
    // Stateless decode는 중복 검사 없이 같은 bytes를 다시 복원한다.
    EXPECT_TRUE(decode_steering_frame(frame));
    EXPECT_EQ(check_steering_e2e(&frame, rx), P05Return::Ok);
    EXPECT_EQ(rx.check.status, P05Status::Repeated);
    EXPECT_EQ(check_steering_e2e(nullptr, rx), P05Return::Ok);
    EXPECT_EQ(rx.check.status, P05Status::NoNewData);
    frame.can_id = kSteeringActualId;
    frame.payload = kActualPositive;
    EXPECT_EQ(check_steering_e2e(&frame, rx), P05Return::InputWrong);
    EXPECT_EQ(rx.check.counter, 0);
    frame = command_frame();
    frame.payload_length = 31;
    EXPECT_EQ(check_steering_e2e(&frame, rx), P05Return::InputWrong);
    frame = command_frame();
    frame.payload[0] ^= 1;
    EXPECT_EQ(check_steering_e2e(&frame, rx), P05Return::Ok);
    EXPECT_EQ(rx.check.status, P05Status::Error);
    EXPECT_EQ(rx.check.counter, 0);
}
}  // namespace
