#include "drive_receiver.hpp"
#include "drive_value_codec.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <cmath>
#include <limits>

namespace {
using namespace stratadrive::can;
using stratadrive::e2e::P05Status;
constexpr std::uint64_t kStart = 1000000000ULL, kMs = 1000000ULL;

DriveMessage sample(DriveFrameKind kind = DriveFrameKind::Command) {
    DriveMessage message;
    message.kind = kind;
    message.epoch = 1;
    message.source_time_ns = kStart;
    message.local_state = ActuatorLocalState::Normal;
    message.origin = ActuatorOrigin::NormalPath;
    message.torque_nm = -200;
    if (kind == DriveFrameKind::Actual) {
        message.wheel_speed = DriveWheelSpeed{12.34, kStart};
        message.regen_capability = DriveRegenCapability{200, kStart, kStart};
        message.regen_limit_reason = DriveRegenLimitReason::ChargeAcceptanceLimited;
    }
    return message;
}
DriveReceiverConfig config(DriveFrameKind kind = DriveFrameKind::Command) {
    return {kind, {-300, 500}, 100, 300};  // Host fixture calibration only.
}
DriveFrame encode(const DriveMessage& message, DriveTxState& tx) {
    const auto frame = encode_drive_frame(message, tx);
    EXPECT_TRUE(frame);
    return frame.value_or(DriveFrame{});
}
void reseal(DriveFrame& frame) {
    const auto crc = drive_frame_crc(frame);
    ASSERT_TRUE(crc);
    frame.payload[29] = static_cast<std::uint8_t>(*crc);
    frame.payload[30] = static_cast<std::uint8_t>(*crc >> 8U);
}
void advance(DriveMessage& message, unsigned int ms) {
    ++message.sequence;
    message.source_time_ns = kStart + ms * kMs;
}

TEST(DriveValues, DirectionZeroAndReservedCodes) {
    EXPECT_EQ(encode_drive_torque(200), (DriveValueBytes{0xD0, 0x07}));
    EXPECT_EQ(encode_drive_torque(-200), (DriveValueBytes{0x30, 0xF8}));
    EXPECT_EQ(encode_drive_torque(0), (DriveValueBytes{0, 0}));
    EXPECT_FALSE(decode_drive_torque({0, 0x80}));
    EXPECT_FALSE(decode_drive_wheel_speed({0xFF, 0xFF}));
    EXPECT_FALSE(decode_drive_regen_limit({0, 0x80}));
    EXPECT_FALSE(decode_drive_regen_limit({0xFF, 0xFF}));
    EXPECT_EQ(encode_drive_regen_limit(0), (DriveValueBytes{0, 0}));
    EXPECT_EQ(encode_drive_wheel_speed(12.34), (DriveValueBytes{0xD2, 0x04}));
    EXPECT_EQ(encode_drive_torque(0.25), (DriveValueBytes{3, 0}));
    EXPECT_EQ(encode_drive_torque(-0.25), (DriveValueBytes{0xFD, 0xFF}));
}

TEST(DriveValues, ExhaustiveRawRoundTripsAndQuantizationBound) {
    for (std::uint32_t raw = 0; raw <= 65535; ++raw) {
        const DriveValueBytes bytes{static_cast<std::uint8_t>(raw), static_cast<std::uint8_t>(raw >> 8U)};
        const auto torque = decode_drive_torque(bytes);
        if (raw == 32768) EXPECT_FALSE(torque);
        else { ASSERT_TRUE(torque); EXPECT_EQ(encode_drive_torque(*torque), bytes); }
        const auto speed = decode_drive_wheel_speed(bytes);
        if (raw == 65535) EXPECT_FALSE(speed);
        else { ASSERT_TRUE(speed); EXPECT_EQ(encode_drive_wheel_speed(*speed), bytes); }
        const auto limit = decode_drive_regen_limit(bytes);
        if (raw > 32767) EXPECT_FALSE(limit);
        else { ASSERT_TRUE(limit); EXPECT_EQ(encode_drive_regen_limit(*limit), bytes); }
    }
    for (const double value : {-299.93, -0.26, -0.04, 0.04, 0.26, 499.93}) {
        const auto bytes = encode_drive_torque(value);
        ASSERT_TRUE(bytes);
        EXPECT_LE(std::abs(*decode_drive_torque(*bytes) - value), 0.050000000001);
    }
}

TEST(DriveValues, RejectsNonfiniteAndPreRoundingRangeViolations) {
    for (const double value : {NAN, INFINITY, -INFINITY}) {
        EXPECT_FALSE(encode_drive_torque(value));
        EXPECT_FALSE(encode_drive_wheel_speed(value));
        EXPECT_FALSE(encode_drive_regen_limit(value));
    }
    EXPECT_FALSE(encode_drive_torque(kDriveTorqueWireMaxNm + 0.001));
    EXPECT_FALSE(encode_drive_torque(-kDriveTorqueWireMaxNm - 0.001));
    EXPECT_FALSE(encode_drive_wheel_speed(-0.001));
    EXPECT_FALSE(encode_drive_wheel_speed(kDriveWheelSpeedWireMaxRadS + 0.001));
    EXPECT_FALSE(encode_drive_regen_limit(-0.001));
    EXPECT_FALSE(encode_drive_regen_limit(kDriveTorqueWireMaxNm + 0.001));
}

TEST(DriveFrame, IndependentCrcGoldenVectors) {
    auto command = sample();
    command.causal_sequence = 7;
    DriveTxState command_tx{command.kind};
    const auto command_frame = encode(command, command_tx);
    const ActuatorPayload command_golden{0x30,0xF8,2,1,0,0,0,0,1,0,0,0,0,0xCA,0x9A,0x3B,
        0,0,0,0,7,0,0,0,1,1,0,0,0,0xA1,0x47,0};
    EXPECT_TRUE(std::equal(command_golden.begin(), command_golden.end(), command_frame.payload.begin()));
    EXPECT_EQ(command_frame.payload_length, 32);
    auto actual = sample(DriveFrameKind::Actual);
    actual.source_time_ns += 10 * kMs;
    actual.torque_nm = -150;
    actual.wheel_speed->source_time_ns = actual.source_time_ns;
    actual.regen_capability = DriveRegenCapability{200, actual.source_time_ns, kStart + 5 * kMs};
    DriveTxState actual_tx{actual.kind};
    const auto actual_frame = encode(actual, actual_tx);
    const ExtendedActuatorPayload actual_golden{0x24,0xFA,2,1,0,0,0,0,1,0,0,0,0x80,0x60,0x33,0x3C,
        0,0,0,0,0,0,0,0,1,1,0,0,0,0x2F,0xE6,0,0xD2,4,1,2,0xD0,7,1,0,
        0x80,0x60,0x33,0x3C,0,0,0,0,0x80,0x60,0x33,0x3C,0,0,0,0,0x40,0x15,0xE7,0x3B,0,0,0,0};
    EXPECT_EQ(actual_frame.payload, actual_golden);
    EXPECT_EQ(actual_frame.payload_length, 64);
    const auto decoded = decode_drive_frame(actual_frame);
    ASSERT_TRUE(decoded && decoded->wheel_speed && decoded->regen_capability);
    EXPECT_DOUBLE_EQ(*decoded->torque_nm, -150);
    EXPECT_DOUBLE_EQ(decoded->wheel_speed->value_rad_s, 12.34);
    EXPECT_EQ(decoded->regen_capability->input_time_ns, kStart + 5 * kMs);
}

TEST(DriveFrame, ZeroCapabilityAndUnavailableHaveDistinctCanonicalEncoding) {
    auto message = sample(DriveFrameKind::Actual);
    DriveTxState tx{message.kind};
    message.torque_nm = 0;
    message.regen_capability->torque_limit_nm = 0;
    message.regen_limit_reason = DriveRegenLimitReason::Disabled;
    auto decoded = decode_drive_frame(encode(message, tx));
    ASSERT_TRUE(decoded && decoded->torque_nm && decoded->regen_capability);
    EXPECT_DOUBLE_EQ(*decoded->torque_nm, 0);
    EXPECT_DOUBLE_EQ(decoded->regen_capability->torque_limit_nm, 0);
    message.torque_nm.reset();
    message.wheel_speed.reset();
    message.regen_capability.reset();
    message.regen_limit_reason = DriveRegenLimitReason::InputsInvalid;
    const auto frame = encode(message, tx);
    decoded = decode_drive_frame(frame);
    ASSERT_TRUE(decoded);
    EXPECT_FALSE(decoded->torque_nm);
    EXPECT_FALSE(decoded->wheel_speed);
    EXPECT_FALSE(decoded->regen_capability);
    EXPECT_EQ(frame.payload[0], 0);
    EXPECT_EQ(frame.payload[1], 0x80);
    EXPECT_EQ(frame.payload[32], 0xFF);
    EXPECT_EQ(frame.payload[36], 0xFF);
    EXPECT_EQ(frame.payload[35], 4);
}

TEST(DriveFrame, AllBytesIncludingCapabilityInputTimeAreCrcProtected) {
    auto message = sample(DriveFrameKind::Actual);
    DriveTxState tx{message.kind};
    const auto frame = encode(message, tx);
    for (std::size_t offset = 0; offset < frame.payload_length; ++offset) {
        auto corrupt = frame;
        corrupt.payload[offset] ^= 1;
        EXPECT_FALSE(decode_drive_frame(corrupt)) << offset;
    }
}

TEST(DriveFrame, RejectsResealedNoncanonicalPayloadAndMalformedEnvelopes) {
    DriveTxState tx{DriveFrameKind::Actual};
    const auto frame = encode(sample(DriveFrameKind::Actual), tx);
    struct Mutation { std::size_t offset; std::uint8_t value; };
    for (const Mutation mutation : {Mutation{2,3}, {3,2}, {24,4}, {25,3}, {26,1},
                                   {34,2}, {35,5}, {38,2}, {39,1}, {35,4}}) {
        auto bad = frame;
        bad.payload[mutation.offset] = mutation.value;
        reseal(bad);
        EXPECT_FALSE(decode_drive_frame(bad)) << mutation.offset;
    }
    for (unsigned int fault = 0; fault < 5; ++fault) {
        auto bad = frame;
        if (fault == 0) bad.payload_length = 32;
        if (fault == 1) bad.can_id |= 0x80000000U;
        if (fault == 2) bad.is_fd = false;
        if (fault == 3) bad.fd_flags = 1;
        if (fault == 4) bad.can_id = 0x181; // unrelated stream
        EXPECT_FALSE(decode_drive_frame(bad)) << fault;
    }
}

TEST(DriveFrame, FullWidthTimesAndFailedEncodeDoNotAdvanceCounter) {
    auto message = sample(DriveFrameKind::Actual);
    message.sequence = message.epoch = message.causal_sequence = UINT32_MAX;
    message.source_time_ns = UINT64_MAX;
    message.wheel_speed->source_time_ns = 9007199254740993ULL;
    message.regen_capability->source_time_ns = UINT64_MAX;
    message.regen_capability->input_time_ns = 9007199254740993ULL;
    DriveTxState tx{message.kind};
    const auto decoded = decode_drive_frame(encode(message, tx));
    ASSERT_TRUE(decoded && decoded->wheel_speed && decoded->regen_capability);
    EXPECT_EQ(decoded->source_time_ns, UINT64_MAX);
    EXPECT_EQ(decoded->wheel_speed->source_time_ns, 9007199254740993ULL);
    EXPECT_EQ(decoded->regen_capability->source_time_ns, UINT64_MAX);
    EXPECT_EQ(decoded->regen_capability->input_time_ns, 9007199254740993ULL);
    EXPECT_EQ(decoded->epoch, UINT32_MAX);
    for (int fault = 0; fault < 6; ++fault) {
        auto bad = message;
        if (fault == 0) bad.epoch = 0;
        if (fault == 1) bad.torque_nm = INFINITY;
        if (fault == 2) bad.wheel_speed.reset();
        if (fault == 3) bad.regen_limit_reason = DriveRegenLimitReason::InputsInvalid;
        if (fault == 4) bad.regen_capability->torque_limit_nm = -1;
        if (fault == 5) bad.kind = DriveFrameKind::Command;
        EXPECT_FALSE(encode_drive_frame(bad, tx));
        EXPECT_EQ(tx.protection.counter, 1);
    }
}

TEST(DriveFrame, StreamSpecificDataIdsAndCounterWrap) {
    for (const auto kind : {DriveFrameKind::Command, DriveFrameKind::Actual}) {
        DriveTxState tx{kind};
        DriveRxState rx{kind};
        for (unsigned int index = 0; index < 258; ++index) {
            auto message = sample(kind);
            message.sequence = index;
            const auto frame = encode(message, tx);
            EXPECT_EQ(frame.payload[31], index % 256);
            EXPECT_EQ(check_drive_e2e(&frame, rx), stratadrive::e2e::P05Return::Ok);
            EXPECT_EQ(rx.check.status, P05Status::Ok);
        }
        EXPECT_EQ(check_drive_e2e(nullptr, rx), stratadrive::e2e::P05Return::Ok);
        EXPECT_EQ(rx.check.status, P05Status::NoNewData);
    }
}

TEST(DriveReceiver, AcceptsPropulsionRegenAndZeroForBothStreams) {
    for (const auto kind : {DriveFrameKind::Command, DriveFrameKind::Actual}) {
        DriveReceiver receiver(config(kind));
        ASSERT_TRUE(receiver.start_session(1, kStart));
        DriveTxState tx{kind};
        auto message = sample(kind);
        for (const double torque : {200.0, -200.0, 0.0}) {
            message.torque_nm = torque;
            EXPECT_EQ(receiver.receive(encode(message, tx), message.source_time_ns).decision,
                      ActuatorReceiveDecision::Accepted);
            ASSERT_TRUE(receiver.current_sample(message.source_time_ns));
            EXPECT_DOUBLE_EQ(*receiver.current_sample(message.source_time_ns)->torque_nm, torque);
            advance(message, static_cast<unsigned int>(message.sequence + 1) * 10);
        }
    }
}

TEST(DriveReceiver, RejectsInvalidConfigurationAndRequiresTrustedEpoch) {
    for (unsigned int fault = 0; fault < 8; ++fault) {
        auto invalid = config();
        if (fault == 0) invalid.torque_nm.minimum = 0;
        if (fault == 1) invalid.torque_nm.maximum = INFINITY;
        if (fault == 2) invalid.max_wheel_speed_rad_s = 0;
        if (fault == 3) invalid.max_regen_torque_nm = 301;
        if (fault == 4) invalid.max_feedback_age_ns = 0;
        if (fault == 5) invalid.max_feedback_age_ns = 31 * kMs;
        if (fault == 6) invalid.timeout_ns = 81 * kMs;
        if (fault == 7) invalid.kind = static_cast<DriveFrameKind>(0);
        DriveReceiver receiver(invalid);
        EXPECT_FALSE(receiver.start_session(1, kStart));
        EXPECT_EQ(receiver.health(), ActuatorReceiverHealth::NotInitialized);
    }
    DriveReceiver receiver(config());
    DriveTxState tx{DriveFrameKind::Command};
    EXPECT_EQ(receiver.receive(encode(sample(), tx), kStart).decision, ActuatorReceiveDecision::NotInitialized);
    EXPECT_FALSE(receiver.start_session(0, kStart));
    ASSERT_TRUE(receiver.start_session(1, kStart));
    EXPECT_FALSE(receiver.start_session(1, kStart));
}

TEST(DriveReceiver, RejectedMessagesNeverRefreshCriticalHistory) {
    DriveReceiver receiver(config());
    ASSERT_TRUE(receiver.start_session(1, kStart));
    DriveTxState tx{DriveFrameKind::Command};
    auto message = sample();
    const auto first = encode(message, tx);
    ASSERT_EQ(receiver.receive(first, kStart).decision, ActuatorReceiveDecision::Accepted);
    EXPECT_EQ(receiver.receive(first, kStart + kMs).e2e_status, P05Status::Repeated);
    for (unsigned int fault = 0; fault < 8; ++fault) {
        auto bad_message = message;
        bad_message.sequence = 1;
        bad_message.source_time_ns += (fault + 2) * kMs;
        if (fault == 0) bad_message.torque_nm = -301;
        if (fault == 1) bad_message.torque_nm.reset();
        if (fault == 2) bad_message.origin = ActuatorOrigin::LocalProtection;
        if (fault == 3) bad_message.epoch = 2;
        if (fault == 4) bad_message.sequence = 0;
        if (fault == 5) bad_message.source_time_ns = kStart;
        auto bad = encode(bad_message, tx);
        if (fault == 6) bad.payload[0] ^= 1;
        if (fault == 7) bad.payload_length = 64;
        EXPECT_NE(receiver.receive(bad, kStart + (fault + 3) * kMs).decision, ActuatorReceiveDecision::Accepted);
        ASSERT_TRUE(receiver.last_accepted());
        EXPECT_EQ(receiver.last_accepted()->received_time_ns, kStart);
        EXPECT_EQ(receiver.last_accepted()->message.sequence, 0);
    }
    EXPECT_EQ(receiver.poll(kStart + 80 * kMs), ActuatorReceiverHealth::Timeout);
}

TEST(DriveReceiver, FreshTorqueDoesNotRejuvenateCachedCapabilityOrItsInputs) {
    DriveReceiver receiver(config(DriveFrameKind::Actual));
    ASSERT_TRUE(receiver.start_session(1, kStart));
    DriveTxState tx{DriveFrameKind::Actual};
    auto message = sample(tx.kind);
    ASSERT_EQ(receiver.receive(encode(message, tx), kStart).regen_capability, DriveFeedbackQuality::Usable);
    advance(message, 20);
    message.wheel_speed->source_time_ns = message.source_time_ns;
    EXPECT_EQ(receiver.receive(encode(message, tx), message.source_time_ns).regen_capability, DriveFeedbackQuality::Usable);
    advance(message, 31);
    message.wheel_speed->source_time_ns = message.source_time_ns;
    const auto cached = receiver.receive(encode(message, tx), message.source_time_ns);
    EXPECT_EQ(cached.decision, ActuatorReceiveDecision::Accepted);
    EXPECT_EQ(cached.regen_capability, DriveFeedbackQuality::Stale);
    auto current = receiver.current_sample(message.source_time_ns);
    ASSERT_TRUE(current && current->torque_nm && current->wheel_speed);
    EXPECT_FALSE(current->regen_capability);
    advance(message, 32);
    message.wheel_speed->source_time_ns = message.source_time_ns;
    message.regen_capability->source_time_ns = message.source_time_ns; // fresh calculation, old dependency
    EXPECT_EQ(receiver.receive(encode(message, tx), message.source_time_ns).regen_capability, DriveFeedbackQuality::Stale);
    advance(message, 33);
    message.wheel_speed->source_time_ns = message.source_time_ns;
    message.regen_capability = DriveRegenCapability{0, message.source_time_ns, message.source_time_ns};
    message.regen_limit_reason = DriveRegenLimitReason::ChargeAcceptanceLimited;
    EXPECT_EQ(receiver.receive(encode(message, tx), message.source_time_ns).regen_capability, DriveFeedbackQuality::Usable);
    current = receiver.current_sample(message.source_time_ns);
    ASSERT_TRUE(current && current->regen_capability);
    EXPECT_DOUBLE_EQ(current->regen_capability->torque_limit_nm, 0);
}

TEST(DriveReceiver, IndependentAuxiliaryTimeCanFollowTorqueWithoutExtendingTorqueAge) {
    DriveReceiver receiver(config(DriveFrameKind::Actual)); ASSERT_TRUE(receiver.start_session(1,kStart));
    DriveTxState tx{DriveFrameKind::Actual}; auto message=sample(tx.kind); message.source_time_ns=kStart+5*kMs;
    message.wheel_speed->source_time_ns=kStart+9*kMs;
    message.regen_capability=DriveRegenCapability{200,kStart+10*kMs,kStart+8*kMs};
    const auto result=receiver.receive(encode(message,tx),kStart+12*kMs);
    EXPECT_EQ(result.decision,ActuatorReceiveDecision::Accepted);
    EXPECT_EQ(result.wheel_speed,DriveFeedbackQuality::Usable); EXPECT_EQ(result.regen_capability,DriveFeedbackQuality::Usable);
    const auto at_boundary=receiver.current_sample(kStart+35*kMs); ASSERT_TRUE(at_boundary && at_boundary->regen_capability);
    EXPECT_EQ(at_boundary->source_time_ns,kStart+5*kMs);
    EXPECT_FALSE(receiver.current_sample(kStart+35*kMs+1));
}
TEST(DriveReceiver, FreshAuxiliaryAndNewReportSequenceCannotRefreshTheSameTorqueSample) {
    DriveReceiver receiver(config(DriveFrameKind::Actual)); ASSERT_TRUE(receiver.start_session(1,kStart));
    DriveTxState tx{DriveFrameKind::Actual}; auto message=sample(tx.kind); message.source_time_ns=kStart+5*kMs;
    ASSERT_EQ(receiver.receive(encode(message,tx),kStart+10*kMs).decision,ActuatorReceiveDecision::Accepted);
    ++message.sequence; message.wheel_speed->source_time_ns=kStart+20*kMs;
    message.regen_capability=DriveRegenCapability{200,kStart+20*kMs,kStart+20*kMs};
    EXPECT_EQ(receiver.receive(encode(message,tx),kStart+20*kMs).decision,ActuatorReceiveDecision::SourceNotIncreasing);
    EXPECT_EQ(receiver.last_accepted()->received_time_ns,kStart+10*kMs);
    EXPECT_EQ(receiver.poll(kStart+90*kMs),ActuatorReceiverHealth::Timeout);
    ++message.sequence; message.source_time_ns=kStart+90*kMs;
    EXPECT_EQ(receiver.receive(encode(message,tx),kStart+90*kMs).decision,ActuatorReceiveDecision::Timeout);
}
TEST(DriveReceiver, AuxiliaryAfterTorqueStillRejectsFutureOrRegressingSamples) {
    DriveReceiver receiver(config(DriveFrameKind::Actual)); ASSERT_TRUE(receiver.start_session(1,kStart));
    DriveTxState tx{DriveFrameKind::Actual}; auto message=sample(tx.kind); message.source_time_ns=kStart+5*kMs;
    message.wheel_speed->source_time_ns=kStart+10*kMs;
    message.regen_capability=DriveRegenCapability{200,kStart+10*kMs,kStart+9*kMs};
    ASSERT_EQ(receiver.receive(encode(message,tx),kStart+11*kMs).regen_capability,DriveFeedbackQuality::Usable);
    advance(message,6); message.wheel_speed->source_time_ns=kStart+12*kMs;
    EXPECT_EQ(receiver.receive(encode(message,tx),kStart+11*kMs).wheel_speed,DriveFeedbackQuality::Invalid);
    advance(message,7); message.wheel_speed->source_time_ns=kStart+9*kMs;
    EXPECT_EQ(receiver.receive(encode(message,tx),kStart+12*kMs).wheel_speed,DriveFeedbackQuality::Invalid);
}
TEST(DriveReceiver, AuxiliaryRangeTimeAndChangedCacheDoNotInvalidateFreshTorque) {
    for (unsigned int fault = 0; fault < 9; ++fault) {
        DriveReceiver receiver(config(DriveFrameKind::Actual));
        ASSERT_TRUE(receiver.start_session(1, kStart));
        DriveTxState tx{DriveFrameKind::Actual};
        auto message = sample(tx.kind);
        ASSERT_EQ(receiver.receive(encode(message, tx), kStart).decision, ActuatorReceiveDecision::Accepted);
        advance(message, 10);
        if (fault == 0) message.wheel_speed->value_rad_s = 101;
        if (fault == 1) message.wheel_speed->source_time_ns = message.source_time_ns + 1;
        if (fault == 2) message.regen_capability->torque_limit_nm = 301;
        if (fault == 3) message.regen_capability->source_time_ns = message.source_time_ns + 1;
        if (fault == 4) message.regen_capability->input_time_ns = kStart - 1;
        if (fault == 5) message.regen_capability->input_time_ns = kStart + 1;
        if (fault == 6) message.regen_capability->torque_limit_nm = 100; // changed value, same generation time
        if (fault == 7) message.wheel_speed->value_rad_s = 10; // changed speed, same source time
        if (fault == 8) message.regen_limit_reason = DriveRegenLimitReason::MotorOrSpeedLimited;
        const auto result = receiver.receive(encode(message, tx), message.source_time_ns);
        EXPECT_EQ(result.decision, ActuatorReceiveDecision::Accepted);
        EXPECT_EQ(result.regen_capability, DriveFeedbackQuality::Invalid);
        const auto current = receiver.current_sample(message.source_time_ns);
        ASSERT_TRUE(current && current->torque_nm);
        EXPECT_FALSE(current->regen_capability);
        EXPECT_EQ(receiver.last_accepted()->received_time_ns, message.source_time_ns);
    }
}

TEST(DriveReceiver, AuxiliaryExpiryIsIndependentOfTorqueAgeAndNoFallbackToOldCap) {
    DriveReceiver receiver(config(DriveFrameKind::Actual));
    ASSERT_TRUE(receiver.start_session(1, kStart));
    DriveTxState tx{DriveFrameKind::Actual};
    auto message = sample(tx.kind);
    ASSERT_EQ(receiver.receive(encode(message, tx), kStart).decision, ActuatorReceiveDecision::Accepted);
    advance(message, 20);
    message.wheel_speed->source_time_ns = message.source_time_ns;
    ASSERT_EQ(receiver.receive(encode(message, tx), message.source_time_ns).regen_capability, DriveFeedbackQuality::Usable);
    auto current = receiver.current_sample(kStart + 30 * kMs);
    ASSERT_TRUE(current && current->regen_capability);
    current = receiver.current_sample(kStart + 30 * kMs + 1);
    ASSERT_TRUE(current && current->wheel_speed && current->torque_nm);
    EXPECT_FALSE(current->regen_capability);
    advance(message, 31);
    message.regen_capability.reset();
    message.regen_limit_reason = DriveRegenLimitReason::InputsInvalid;
    ASSERT_EQ(receiver.receive(encode(message, tx), message.source_time_ns).regen_capability, DriveFeedbackQuality::Unavailable);
    EXPECT_FALSE(receiver.current_sample(message.source_time_ns)->regen_capability);
    EXPECT_FALSE(receiver.current_sample(kStart + 62 * kMs));
}

TEST(DriveReceiver, MissingTorqueCannotBeReplacedByValidCapability) {
    DriveReceiver receiver(config(DriveFrameKind::Actual));
    ASSERT_TRUE(receiver.start_session(1, kStart));
    DriveTxState tx{DriveFrameKind::Actual};
    auto message = sample(tx.kind);
    message.torque_nm.reset();
    EXPECT_EQ(receiver.receive(encode(message, tx), kStart).decision, ActuatorReceiveDecision::Unavailable);
    EXPECT_FALSE(receiver.last_accepted());
    EXPECT_EQ(receiver.poll(kStart + 80 * kMs), ActuatorReceiverHealth::Timeout);
}

TEST(DriveReceiver, TimeoutClockRollbackAndRecoveryAreLatched) {
    DriveReceiver receiver(config());
    ASSERT_TRUE(receiver.start_session(1, kStart));
    DriveTxState tx{DriveFrameKind::Command};
    auto message = sample();
    ASSERT_EQ(receiver.receive(encode(message, tx), kStart).decision, ActuatorReceiveDecision::Accepted);
    EXPECT_TRUE(receiver.current_sample(kStart + 30 * kMs));
    EXPECT_FALSE(receiver.current_sample(kStart + 30 * kMs + 1));
    advance(message, 80);
    EXPECT_EQ(receiver.receive(encode(message, tx), message.source_time_ns).decision, ActuatorReceiveDecision::Timeout);
    EXPECT_FALSE(receiver.start_session(1, message.source_time_ns));
    ASSERT_TRUE(receiver.start_session(2, message.source_time_ns));
    message.epoch = 2;
    message.sequence = 0;
    DriveTxState restarted{message.kind};
    ASSERT_EQ(receiver.receive(encode(message, restarted), message.source_time_ns).decision, ActuatorReceiveDecision::Accepted);
    EXPECT_EQ(receiver.poll(message.source_time_ns - 1), ActuatorReceiverHealth::ClockError);
    EXPECT_EQ(receiver.poll(message.source_time_ns + 1), ActuatorReceiverHealth::ClockError);
    EXPECT_FALSE(receiver.current_sample(message.source_time_ns + 1));
}
TEST(DriveReceiver, ExplicitDependencyAgeLeavesTorqueAndAuxiliarySourceBudgetsUnchanged) {
    auto cfg = config(DriveFrameKind::Actual);
    cfg.max_capability_input_age_ns = 70000000ULL;
    DriveReceiver receiver(cfg); ASSERT_TRUE(receiver.start_session(1, kStart));
    auto message = sample(DriveFrameKind::Actual); DriveTxState tx{message.kind};
    ASSERT_EQ(receiver.receive(encode(message, tx), kStart).decision, ActuatorReceiveDecision::Accepted);
    advance(message, 60);
    message.wheel_speed->source_time_ns = message.source_time_ns;
    message.regen_capability->source_time_ns = message.source_time_ns;
    const auto result = receiver.receive(encode(message, tx), message.source_time_ns);
    EXPECT_EQ(result.regen_capability, DriveFeedbackQuality::Usable);
    ASSERT_TRUE(receiver.current_sample(kStart+70*kMs)->regen_capability);
    const auto expired = receiver.current_sample(kStart+71*kMs); ASSERT_TRUE(expired);
    EXPECT_TRUE(expired->torque_nm); EXPECT_FALSE(expired->regen_capability);
    EXPECT_FALSE(receiver.current_sample(kStart+91*kMs)); // torque source still 30 ms
    EXPECT_EQ(cfg.max_source_age_ns, 30000000ULL); EXPECT_EQ(cfg.max_feedback_age_ns, 30000000ULL);
    for (const auto limit : {0ULL, 80000000ULL, 80000001ULL}) {
        cfg.max_capability_input_age_ns = limit;
        DriveReceiver invalid(cfg); EXPECT_FALSE(invalid.start_session(1, kStart));
    }
}

}  // namespace
