#include "brake_pressure_codec.hpp"
#include "brake_frame_codec.hpp"
#include "steering_frame_codec.hpp"

#include <gtest/gtest.h>

#include <cmath>
#include <limits>

namespace {
using namespace stratadrive::can;
using stratadrive::e2e::P05Return;
using stratadrive::e2e::P05Status;

// ICD의 독립 vectors: Python struct packing + binascii.crc_hqx로 계산했다.
constexpr BrakePayload kCommand{
    0xD0, 0x07, 0x02, 0x01, 0x00, 0x00, 0x00, 0x00,
    0x01, 0x00, 0x00, 0x00, 0x00, 0xCA, 0x9A, 0x3B,
    0x00, 0x00, 0x00, 0x00, 0x07, 0x00, 0x00, 0x00,
    0x01, 0x01, 0x00, 0x00, 0x00, 0xCA, 0x36, 0x00};
constexpr BrakePayload kActual{
    0xDC, 0x05, 0x02, 0x01, 0x00, 0x00, 0x00, 0x00,
    0x01, 0x00, 0x00, 0x00, 0x80, 0x60, 0x33, 0x3C,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x01, 0x01, 0x00, 0x00, 0x00, 0x73, 0x3D, 0x00};
constexpr BrakePayload kZero{
    0x00, 0x00, 0x02, 0x01, 0x00, 0x00, 0x00, 0x00,
    0x01, 0x00, 0x00, 0x00, 0x00, 0xCA, 0x9A, 0x3B,
    0x00, 0x00, 0x00, 0x00, 0x07, 0x00, 0x00, 0x00,
    0x01, 0x01, 0x00, 0x00, 0x00, 0x2A, 0x0D, 0x00};
constexpr BrakePayload kUnavailable{
    0xFF, 0xFF, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x01, 0x00, 0x00, 0x00, 0x80, 0x60, 0x33, 0x3C,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0xB3, 0x6B, 0x00};

BrakeMessage sample(BrakeFrameKind kind = BrakeFrameKind::Command) {
    BrakeMessage message;
    message.kind = kind;
    message.pressure_pa = kind == BrakeFrameKind::Command ? 2000000.0 : 1500000.0;
    message.epoch = 1;
    message.source_time_ns = kind == BrakeFrameKind::Command ? 1000000000 : 1010000000;
    message.causal_sequence = kind == BrakeFrameKind::Command ? 7 : 0;
    message.local_state = BrakeLocalState::Normal;
    message.origin = BrakeOrigin::NormalPath;
    return message;
}

BrakeFrame command_frame() {
    BrakeFrame frame;
    frame.can_id = kBrakeCommandId;
    frame.payload = kCommand;
    return frame;
}

void reseal(BrakeFrame& frame) {
    const auto crc = brake_frame_crc(static_cast<std::uint16_t>(frame.can_id), frame.payload);
    ASSERT_TRUE(crc);
    frame.payload[29] = static_cast<std::uint8_t>(*crc & 0xFFU);
    frame.payload[30] = static_cast<std::uint8_t>(*crc >> 8U);
}

TEST(BrakePressureCodec, UsesUnsignedLittleEndianAndValidZero) {
    EXPECT_EQ(encode_brake_pressure(2000000), (PressureBytes{0xD0, 0x07}));
    EXPECT_EQ(encode_brake_pressure(0), (PressureBytes{0, 0}));
    EXPECT_EQ(encode_brake_pressure(kBrakePressureWireMaxPa), (PressureBytes{0xFE, 0xFF}));
    EXPECT_EQ(decode_brake_pressure({0, 0}), 0.0);
    EXPECT_FALSE(decode_brake_pressure({0xFF, 0xFF}));
}

TEST(BrakePressureCodec, RoundsToNearestWithPositiveHalfUp) {
    EXPECT_EQ(encode_brake_pressure(499), (PressureBytes{0, 0}));
    EXPECT_EQ(encode_brake_pressure(500), (PressureBytes{1, 0}));
    EXPECT_EQ(encode_brake_pressure(1499), (PressureBytes{1, 0}));
    EXPECT_EQ(encode_brake_pressure(1500), (PressureBytes{2, 0}));
    EXPECT_EQ(decode_brake_pressure(*encode_brake_pressure(2000499)), 2000000.0);
}

TEST(BrakePressureCodec, RejectsBadInputBeforeRoundingWithoutClamping) {
    const double infinity = std::numeric_limits<double>::infinity();
    for (const double input : {-1.0, std::nextafter(0.0, -1.0),
                               std::nextafter(kBrakePressureWireMaxPa, infinity),
                               65535000.0, std::numeric_limits<double>::max(),
                               infinity, -infinity, std::numeric_limits<double>::quiet_NaN()}) {
        EXPECT_FALSE(encode_brake_pressure(input));
    }
}

TEST(BrakePressureCodec, EveryValidRawCodeRoundTrips) {
    for (std::uint32_t raw = 0; raw < 65535; ++raw) {
        const PressureBytes bytes{static_cast<std::uint8_t>(raw & 0xFFU),
                                  static_cast<std::uint8_t>(raw >> 8U)};
        const auto pressure = decode_brake_pressure(bytes);
        ASSERT_TRUE(pressure);
        EXPECT_EQ(*pressure, raw * 1000.0);
        EXPECT_EQ(encode_brake_pressure(*pressure), bytes);
    }
}

TEST(BrakeFrameCodec, MatchesIndependentGoldenVectors) {
    auto zero = sample();
    zero.pressure_pa = 0;
    auto unavailable = sample(BrakeFrameKind::Actual);
    unavailable.pressure_pa.reset();
    unavailable.local_state = BrakeLocalState::Init;
    unavailable.origin = BrakeOrigin::NoAcceptedInput;
    struct Vector { BrakeMessage message; BrakePayload payload; };
    const Vector vectors[] = {{sample(), kCommand}, {sample(BrakeFrameKind::Actual), kActual},
                              {zero, kZero}, {unavailable, kUnavailable}};
    for (const auto& vector : vectors) {
        BrakeTxState tx{vector.message.kind};
        const auto frame = encode_brake_frame(vector.message, tx);
        ASSERT_TRUE(frame);
        EXPECT_EQ(frame->payload, vector.payload);
        EXPECT_EQ(frame->can_id, static_cast<std::uint16_t>(vector.message.kind));
        EXPECT_EQ(frame->payload_length, 32);
        EXPECT_TRUE(frame->is_fd);
        EXPECT_EQ(frame->fd_flags, 0);
        const auto decoded = decode_brake_frame(*frame);
        ASSERT_TRUE(decoded);
        EXPECT_EQ(decoded->pressure_pa, vector.message.pressure_pa);
        EXPECT_EQ(decoded->sequence, vector.message.sequence);
        EXPECT_EQ(decoded->epoch, vector.message.epoch);
        EXPECT_EQ(decoded->source_time_ns, vector.message.source_time_ns);
        EXPECT_EQ(decoded->causal_sequence, vector.message.causal_sequence);
        EXPECT_EQ(decoded->local_state, vector.message.local_state);
        EXPECT_EQ(decoded->origin, vector.message.origin);
    }
}

TEST(BrakeFrameCodec, RetainsFullWidthMetadata) {
    auto message = sample();
    message.sequence = message.epoch = message.causal_sequence = UINT32_MAX;
    for (const std::uint64_t timestamp : {std::uint64_t{9007199254740993ULL}, UINT64_MAX}) {
        message.source_time_ns = timestamp;
        BrakeTxState tx{message.kind};
        const auto frame = encode_brake_frame(message, tx);
        ASSERT_TRUE(frame);
        const auto decoded = decode_brake_frame(*frame);
        ASSERT_TRUE(decoded);
        EXPECT_EQ(decoded->source_time_ns, timestamp);
        EXPECT_EQ(decoded->sequence, UINT32_MAX);
        EXPECT_EQ(decoded->epoch, UINT32_MAX);
        EXPECT_EQ(decoded->causal_sequence, UINT32_MAX);
    }
}

TEST(BrakeFrameCodec, InvalidFieldsDoNotConsumeTxCounter) {
    BrakeTxState tx{BrakeFrameKind::Command};
    for (unsigned int fault = 0; fault < 7; ++fault) {
        auto message = sample();
        switch (fault) {
            case 0: message.epoch = 0; break;
            case 1: message.pressure_pa = -1; break;
            case 2: message.pressure_pa = INFINITY; break;
            case 3: message.local_state = static_cast<BrakeLocalState>(4); break;
            case 4: message.origin = static_cast<BrakeOrigin>(3); break;
            case 5: message.kind = BrakeFrameKind::Actual; break;
            case 6: message.kind = static_cast<BrakeFrameKind>(0x182); break;
        }
        EXPECT_FALSE(encode_brake_frame(message, tx));
        EXPECT_EQ(tx.protection.counter, 0);
    }
    EXPECT_EQ(encode_brake_frame(sample(), tx)->payload, kCommand);
}

TEST(BrakeFrameCodec, RejectsEveryByteCorruption) {
    for (std::size_t index = 0; index < 32; ++index) {
        auto frame = command_frame();
        frame.payload[index] ^= 1;
        EXPECT_FALSE(decode_brake_frame(frame)) << index;
    }
}

TEST(BrakeFrameCodec, RejectsBadFieldsEvenWithValidCrc) {
    const std::pair<std::size_t, std::uint8_t> faults[] = {
        {2, 1}, {3, 2}, {8, 0}, {24, 4}, {25, 3}, {26, 1}, {27, 1}, {28, 1}};
    for (const auto& fault : faults) {
        auto frame = command_frame();
        frame.payload[fault.first] = fault.second;
        reseal(frame);
        EXPECT_FALSE(decode_brake_frame(frame)) << fault.first;
    }
    auto frame = command_frame();
    frame.payload[0] = frame.payload[1] = 0xFF;
    reseal(frame);
    EXPECT_FALSE(decode_brake_frame(frame));  // Validity=1과 invalid code 불일치
    frame = command_frame();
    frame.payload[3] = 0;
    reseal(frame);
    EXPECT_FALSE(decode_brake_frame(frame));  // Validity=0이면 반드시 FF FF
}

TEST(BrakeFrameCodec, RejectsWrongEnvelopeWithoutChangingE2eState) {
    for (unsigned int fault = 0; fault < 8; ++fault) {
        auto frame = command_frame();
        switch (fault) {
            case 0: frame.is_fd = false; break;
            case 1: frame.payload_length = 16; break;
            case 2: frame.payload_length = 64; break;
            case 3: frame.can_id |= 0x80000000U; break;
            case 4: frame.can_id |= 0x40000000U; break;
            case 5: frame.can_id |= 0x20000000U; break;
            case 6: frame.fd_flags = 1; break;
            case 7: frame.fd_flags = 2; break;
        }
        BrakeRxState rx{BrakeFrameKind::Command};
        EXPECT_FALSE(decode_brake_frame(frame));
        EXPECT_EQ(check_brake_e2e(&frame, rx), P05Return::InputWrong);
        EXPECT_EQ(rx.check.counter, 255);
        EXPECT_EQ(rx.check.status, P05Status::Error);
    }
    auto frame = command_frame();
    frame.fd_flags = 4;  // Linux FDF marker는 허용한다.
    EXPECT_TRUE(decode_brake_frame(frame));
}

TEST(BrakeFrameCodec, DataIdSeparatesBrakeCommandActualAndSteering) {
    auto brake = command_frame();
    brake.can_id = kBrakeActualId;
    EXPECT_FALSE(decode_brake_frame(brake));
    BrakeRxState actual_rx{BrakeFrameKind::Actual};
    EXPECT_EQ(check_brake_e2e(&brake, actual_rx), P05Return::Ok);
    EXPECT_EQ(actual_rx.check.status, P05Status::Error);
    brake = command_frame();
    EXPECT_EQ(check_brake_e2e(&brake, actual_rx), P05Return::InputWrong);
    SteeringFrame steering;
    steering.can_id = kSteeringCommandId;
    steering.payload = kCommand;
    EXPECT_FALSE(decode_steering_frame(steering));
    const auto config = brake_e2e_config(BrakeFrameKind::Command);
    ASSERT_TRUE(config);
    EXPECT_EQ(config->data_id, 0x1101);
    EXPECT_EQ(config->data_length_bits, 256);
    EXPECT_EQ(config->offset_bits, 232);
    EXPECT_EQ(config->max_delta_counter, 10);
    EXPECT_FALSE(brake_e2e_config(static_cast<BrakeFrameKind>(0x180)));
    EXPECT_FALSE(brake_frame_crc(0x180, kCommand));
}

TEST(BrakeFrameCodec, TracksRepeatLossCorruptionAndNoNewData) {
    BrakeTxState tx{BrakeFrameKind::Command};
    BrakeRxState rx{BrakeFrameKind::Command};
    auto frame = encode_brake_frame(sample(), tx);
    ASSERT_TRUE(frame);
    EXPECT_EQ(check_brake_e2e(&*frame, rx), P05Return::Ok);
    EXPECT_EQ(rx.check.status, P05Status::Ok);
    check_brake_e2e(&*frame, rx);
    EXPECT_EQ(rx.check.status, P05Status::Repeated);
    ASSERT_TRUE(encode_brake_frame(sample(), tx));  // counter 1은 손실
    frame = encode_brake_frame(sample(), tx);
    check_brake_e2e(&*frame, rx);
    EXPECT_EQ(rx.check.status, P05Status::OkSomeLost);
    frame = encode_brake_frame(sample(), tx);
    frame->payload[0] ^= 1;
    check_brake_e2e(&*frame, rx);
    EXPECT_EQ(rx.check.status, P05Status::Error);
    EXPECT_EQ(rx.check.counter, 2);
    EXPECT_EQ(check_brake_e2e(nullptr, rx), P05Return::Ok);
    EXPECT_EQ(rx.check.status, P05Status::NoNewData);
}

TEST(BrakeFrameCodec, IndependentStreamsWrapCounters) {
    BrakeTxState command{BrakeFrameKind::Command}, actual{BrakeFrameKind::Actual};
    BrakeRxState rx{BrakeFrameKind::Command};
    for (unsigned int index = 0; index <= 256; ++index) {
        const auto frame = encode_brake_frame(sample(), command);
        ASSERT_TRUE(frame);
        EXPECT_EQ(frame->payload[31], index % 256);
        EXPECT_EQ(check_brake_e2e(&*frame, rx), P05Return::Ok);
        EXPECT_EQ(rx.check.status, P05Status::Ok);
    }
    EXPECT_EQ(encode_brake_frame(sample(BrakeFrameKind::Actual), actual)->payload[31], 0);
}

TEST(ActuatorPayloadCodec, RejectsConfigThatDoesNotMatchFixedLayout) {
    ActuatorPayloadFields fields;
    fields.metadata.epoch = 1;
    for (const auto config : {stratadrive::e2e::P05Config{0x1101, 128, 0, 10},
                              stratadrive::e2e::P05Config{0x1101, 256, 0, 10}}) {
        stratadrive::e2e::P05ProtectState tx;
        EXPECT_FALSE(encode_actuator_payload(fields, config, tx));
        EXPECT_EQ(tx.counter, 0);
        EXPECT_FALSE(decode_actuator_payload(kCommand, config));
    }
}
}  // namespace
