#include "steering_receiver.hpp"

#include <gtest/gtest.h>

#include <limits>

namespace {
using namespace stratadrive::can;
using stratadrive::e2e::P05Status;
constexpr std::uint64_t kStart = 1000000000ULL;
constexpr std::uint64_t kMs = 1000000ULL;

SteeringReceiverConfig config(SteeringFrameKind kind = SteeringFrameKind::Command) {
    return {kind, -0.5, 0.5};  // 시험용 한계이며 차량 calibration이 아니다.
}

SteeringMessage message(SteeringFrameKind kind = SteeringFrameKind::Command) {
    SteeringMessage value;
    value.kind = kind;
    value.angle_rad = 0.2;
    value.epoch = 1;
    value.source_time_ns = kStart;
    value.local_state = SteeringLocalState::Normal;
    value.origin = SteeringOrigin::NormalPath;
    return value;
}

SteeringFrame encode(const SteeringMessage& value, SteeringTxState& tx) {
    const auto frame = encode_steering_frame(value, tx);
    EXPECT_TRUE(frame);
    return frame.value_or(SteeringFrame{});
}

void reseal(SteeringFrame& frame) {
    const auto crc = steering_frame_crc(static_cast<std::uint16_t>(frame.can_id), frame.payload);
    ASSERT_TRUE(crc);
    frame.payload[29] = static_cast<std::uint8_t>(*crc);
    frame.payload[30] = static_cast<std::uint8_t>(*crc >> 8U);
}

TEST(SteeringReceiver, RequiresTrustedSessionAndValidConfiguration) {
    SteeringReceiver uninitialized(config());
    SteeringTxState tx{SteeringFrameKind::Command};
    const auto frame = encode(message(), tx);
    EXPECT_EQ(uninitialized.receive(frame, kStart).decision, SteeringReceiveDecision::NotInitialized);
    EXPECT_FALSE(uninitialized.current_sample(kStart));
    EXPECT_FALSE(uninitialized.last_accepted());
    EXPECT_FALSE(uninitialized.start_session(0, kStart));
    EXPECT_EQ(uninitialized.health(), SteeringReceiverHealth::NotInitialized);

    auto invalid = config();
    const double infinity = std::numeric_limits<double>::infinity();
    const SteeringReceiverConfig cases[] = {
        {static_cast<SteeringFrameKind>(0x181), -0.5, 0.5},
        {SteeringFrameKind::Command, -infinity, 0.5},
        {SteeringFrameKind::Command, -0.5, infinity},
        {SteeringFrameKind::Command, std::numeric_limits<double>::quiet_NaN(), 0.5},
        {SteeringFrameKind::Command, -4.0, 0.5},
        {SteeringFrameKind::Command, -0.5, 4.0},
        {SteeringFrameKind::Command, 0.5, 0.5},
        {SteeringFrameKind::Command, 0.5, -0.5},
        {SteeringFrameKind::Command, -0.5, 0.5, 0, 80 * kMs},
        {SteeringFrameKind::Command, -0.5, 0.5, 30 * kMs, 0},
        {SteeringFrameKind::Command, -0.5, 0.5, 80 * kMs, 80 * kMs},
        {SteeringFrameKind::Command, -0.5, 0.5, 30 * kMs, 80 * kMs + 1},
    };
    for (const auto& candidate : cases) {
        SteeringReceiver receiver(candidate);
        EXPECT_FALSE(receiver.start_session(1, kStart));
        EXPECT_FALSE(receiver.current_sample(kStart));
    }
    invalid.max_source_age_ns = 10 * kMs;
    invalid.timeout_ns = 20 * kMs;
    SteeringReceiver customized(invalid);
    ASSERT_TRUE(customized.start_session(1, kStart));
    EXPECT_EQ(customized.poll(kStart + 20 * kMs - 1), SteeringReceiverHealth::Waiting);
    EXPECT_EQ(customized.poll(kStart + 20 * kMs), SteeringReceiverHealth::Timeout);
}

TEST(SteeringReceiver, AcceptsFreshProgressAndStoresOriginalMetadata) {
    SteeringReceiver receiver(config());
    ASSERT_TRUE(receiver.start_session(1, kStart));
    SteeringTxState tx{SteeringFrameKind::Command};
    auto value = message();
    value.causal_sequence = 42;
    const auto first = receiver.receive(encode(value, tx), kStart + kMs);
    EXPECT_EQ(first.decision, SteeringReceiveDecision::Accepted);
    EXPECT_EQ(first.e2e_status, P05Status::Ok);
    ASSERT_TRUE(receiver.last_accepted());
    EXPECT_EQ(receiver.last_accepted()->received_time_ns, kStart + kMs);
    EXPECT_EQ(receiver.last_accepted()->message.source_time_ns, kStart);
    EXPECT_EQ(receiver.last_accepted()->message.causal_sequence, 42);
    value.sequence = 1;
    value.source_time_ns += 10 * kMs;
    value.angle_rad = 0.0;
    EXPECT_EQ(receiver.receive(encode(value, tx), kStart + 11 * kMs).decision,
              SteeringReceiveDecision::Accepted);
    const auto current = receiver.current_sample(kStart + 12 * kMs);
    ASSERT_TRUE(current);
    EXPECT_EQ(current->sequence, 1);
    EXPECT_DOUBLE_EQ(*current->angle_rad, 0.0);
    EXPECT_EQ(receiver.health(), SteeringReceiverHealth::Receiving);
}

TEST(SteeringReceiver, BadFramesDoNotRefreshValidRxAndDoNotReuseOldE2eStatus) {
    SteeringReceiver receiver(config());
    ASSERT_TRUE(receiver.start_session(1, kStart));
    SteeringTxState tx{SteeringFrameKind::Command};
    auto value = message();
    const auto first = encode(value, tx);
    ASSERT_EQ(receiver.receive(first, kStart).decision, SteeringReceiveDecision::Accepted);
    const auto repeated = receiver.receive(first, kStart + kMs);
    EXPECT_EQ(repeated.decision, SteeringReceiveDecision::E2eRejected);
    EXPECT_EQ(repeated.e2e_status, P05Status::Repeated);
    for (int mutation = 0; mutation < 4; ++mutation) {
        auto bad = first;
        if (mutation == 0) bad.can_id = kSteeringActualId;
        if (mutation == 1) bad.payload_length = 31;
        if (mutation == 2) bad.is_fd = false;
        if (mutation == 3) bad.fd_flags = 1;
        const auto result = receiver.receive(bad, kStart + 2 * kMs);
        EXPECT_EQ(result.decision, SteeringReceiveDecision::MalformedEnvelope);
        EXPECT_FALSE(result.e2e_status);
    }
    value.sequence = 1;
    value.source_time_ns += 3 * kMs;
    auto damaged = encode(value, tx);
    damaged.payload[0] ^= 1U;
    const auto corrupt = receiver.receive(damaged, kStart + 3 * kMs);
    EXPECT_EQ(corrupt.decision, SteeringReceiveDecision::E2eRejected);
    EXPECT_EQ(corrupt.e2e_status, P05Status::Error);
    ASSERT_TRUE(receiver.last_accepted());
    EXPECT_EQ(receiver.last_accepted()->received_time_ns, kStart);
    EXPECT_EQ(receiver.last_accepted()->message.sequence, 0);
    EXPECT_EQ(receiver.last_raw_rx_time_ns(), kStart + 3 * kMs);
    value.sequence = 2;
    value.source_time_ns += kMs;
    const auto recovery = receiver.receive(encode(value, tx), kStart + 4 * kMs);
    EXPECT_EQ(recovery.decision, SteeringReceiveDecision::Accepted);
    EXPECT_EQ(recovery.e2e_status, P05Status::OkSomeLost);
}

TEST(SteeringReceiver, ChecksPayloadStructureAfterSuccessfulProtection) {
    SteeringReceiver receiver(config());
    ASSERT_TRUE(receiver.start_session(1, kStart));
    SteeringTxState tx{SteeringFrameKind::Command};
    for (std::size_t byte : {2U, 26U}) {
        auto value = message();
        auto malformed = encode(value, tx);
        malformed.payload[byte] = 1;
        reseal(malformed);
        const auto result = receiver.receive(malformed, kStart);
        EXPECT_EQ(result.decision, SteeringReceiveDecision::MalformedPayload);
        EXPECT_EQ(result.e2e_status, P05Status::Ok);
        EXPECT_FALSE(receiver.last_accepted());
    }
}

TEST(SteeringReceiver, E2eResynchronizationDoesNotAdvanceApplicationCursor) {
    SteeringReceiver receiver(config());
    ASSERT_TRUE(receiver.start_session(1, kStart));
    SteeringTxState tx{SteeringFrameKind::Command};
    auto value = message();
    ASSERT_EQ(receiver.receive(encode(value, tx), kStart).decision, SteeringReceiveDecision::Accepted);
    for (int index = 0; index < 11; ++index) {
        encode(value, tx);  // Counter 1..11의 수신을 생략한다.
    }
    value.sequence = 1;
    value.source_time_ns += kMs;
    const auto jump = receiver.receive(encode(value, tx), kStart + kMs);  // Counter 12
    EXPECT_EQ(jump.decision, SteeringReceiveDecision::E2eRejected);
    EXPECT_EQ(jump.e2e_status, P05Status::WrongSequence);
    EXPECT_EQ(receiver.last_accepted()->message.sequence, 0);
    EXPECT_EQ(receiver.last_accepted()->received_time_ns, kStart);
    value.sequence = 2;
    value.source_time_ns += kMs;
    const auto next = receiver.receive(encode(value, tx), kStart + 2 * kMs);
    EXPECT_EQ(next.decision, SteeringReceiveDecision::Accepted);
    EXPECT_EQ(next.e2e_status, P05Status::Ok);
}

TEST(SteeringReceiver, RejectsOtherEpochWithoutAdoptingIt) {
    SteeringReceiver receiver(config());
    ASSERT_TRUE(receiver.start_session(2, kStart));
    SteeringTxState tx{SteeringFrameKind::Command};
    auto value = message();
    EXPECT_EQ(receiver.receive(encode(value, tx), kStart).decision, SteeringReceiveDecision::EpochMismatch);
    EXPECT_FALSE(receiver.last_accepted());
    value.epoch = 2;
    value.source_time_ns += kMs;
    EXPECT_EQ(receiver.receive(encode(value, tx), kStart + kMs).decision, SteeringReceiveDecision::Accepted);
    value.epoch = 3;
    value.sequence = 1;
    value.source_time_ns += kMs;
    EXPECT_EQ(receiver.receive(encode(value, tx), kStart + 2 * kMs).decision, SteeringReceiveDecision::EpochMismatch);
    EXPECT_EQ(receiver.last_accepted()->message.epoch, 2);
    EXPECT_EQ(receiver.last_accepted()->received_time_ns, kStart + kMs);
}

TEST(SteeringReceiver, EnforcesSessionFutureAndFreshnessBoundaries) {
    struct Case {
        std::uint64_t source;
        std::uint64_t now;
        SteeringReceiveDecision expected;
    };
    const Case cases[] = {
        {kStart - 1, kStart, SteeringReceiveDecision::SourceBeforeSession},
        {kStart + 1, kStart, SteeringReceiveDecision::SourceInFuture},
        {kStart, kStart + 30 * kMs, SteeringReceiveDecision::Accepted},
        {kStart, kStart + 30 * kMs + 1, SteeringReceiveDecision::SourceStale},
    };
    for (const auto& test : cases) {
        SteeringReceiver receiver(config());
        ASSERT_TRUE(receiver.start_session(1, kStart));
        SteeringTxState tx{SteeringFrameKind::Command};
        auto value = message();
        value.source_time_ns = test.source;
        EXPECT_EQ(receiver.receive(encode(value, tx), test.now).decision, test.expected);
        EXPECT_EQ(receiver.last_accepted().has_value(), test.expected == SteeringReceiveDecision::Accepted);
    }
}

TEST(SteeringReceiver, EnforcesTraceWindowAndRejectsUint32Wrap) {
    const auto max = std::numeric_limits<std::uint32_t>::max();
    EXPECT_TRUE(steering_sequence_progresses(std::nullopt, 0));
    EXPECT_TRUE(steering_sequence_progresses(std::nullopt, 9));
    EXPECT_FALSE(steering_sequence_progresses(std::nullopt, 10));
    EXPECT_FALSE(steering_sequence_progresses(std::nullopt, max));
    EXPECT_TRUE(steering_sequence_progresses(7, 8));
    EXPECT_TRUE(steering_sequence_progresses(7, 17));
    EXPECT_FALSE(steering_sequence_progresses(7, 18));
    EXPECT_FALSE(steering_sequence_progresses(7, 7));
    EXPECT_FALSE(steering_sequence_progresses(7, 6));
    EXPECT_TRUE(steering_sequence_progresses(max - 1, max));
    EXPECT_FALSE(steering_sequence_progresses(max, 0));
    EXPECT_FALSE(steering_sequence_progresses(max, max));
}

TEST(SteeringReceiver, CachedReplayAndTraceRejectionsPreserveLastValidCursors) {
    SteeringReceiver receiver(config());
    ASSERT_TRUE(receiver.start_session(1, kStart));
    SteeringTxState tx{SteeringFrameKind::Command};
    auto value = message();
    value.sequence = 8;
    ASSERT_EQ(receiver.receive(encode(value, tx), kStart).decision, SteeringReceiveDecision::Accepted);
    // 다시 Protect해서 E2E가 OK여도 cached sample 자체는 새로 생성되지 않았다.
    const auto replay = receiver.receive(encode(value, tx), kStart + kMs);
    EXPECT_EQ(replay.e2e_status, P05Status::Ok);
    EXPECT_EQ(replay.decision, SteeringReceiveDecision::SequenceRejected);
    value.sequence = 18;
    value.source_time_ns += 2 * kMs;
    ASSERT_EQ(receiver.receive(encode(value, tx), kStart + 2 * kMs).decision, SteeringReceiveDecision::Accepted);
    for (std::uint32_t sequence : {29U, 17U, 18U}) {
        value.sequence = sequence;
        value.source_time_ns += kMs;
        EXPECT_EQ(receiver.receive(encode(value, tx), value.source_time_ns).decision,
                  SteeringReceiveDecision::SequenceRejected);
        EXPECT_EQ(receiver.last_accepted()->message.sequence, 18);
        EXPECT_EQ(receiver.last_accepted()->message.source_time_ns, kStart + 2 * kMs);
        EXPECT_EQ(receiver.last_accepted()->received_time_ns, kStart + 2 * kMs);
    }
    value.sequence = 19;
    value.source_time_ns = kStart + 2 * kMs;
    EXPECT_EQ(receiver.receive(encode(value, tx), kStart + 6 * kMs).decision,
              SteeringReceiveDecision::SourceNotIncreasing);
    value.source_time_ns = kStart + kMs;
    EXPECT_EQ(receiver.receive(encode(value, tx), kStart + 7 * kMs).decision,
              SteeringReceiveDecision::SourceNotIncreasing);
    value.source_time_ns = kStart + 8 * kMs;
    EXPECT_EQ(receiver.receive(encode(value, tx), value.source_time_ns).decision, SteeringReceiveDecision::Accepted);
}

TEST(SteeringReceiver, FirstTraceSequenceMustBeInsideStartupWindow) {
    for (std::uint32_t sequence : {0U, 9U, 10U, std::numeric_limits<std::uint32_t>::max()}) {
        SteeringReceiver receiver(config());
        ASSERT_TRUE(receiver.start_session(1, kStart));
        SteeringTxState tx{SteeringFrameKind::Command};
        auto value = message();
        value.sequence = sequence;
        EXPECT_EQ(receiver.receive(encode(value, tx), kStart).decision,
                  sequence < 10 ? SteeringReceiveDecision::Accepted : SteeringReceiveDecision::SequenceRejected);
    }
}

TEST(SteeringReceiver, AppliesExplicitRangeAndKeepsUnavailableDistinctFromZero) {
    for (double angle : {-0.5001, -0.5, 0.0, 0.5, 0.5001}) {
        SteeringReceiver receiver(config());
        ASSERT_TRUE(receiver.start_session(1, kStart));
        SteeringTxState tx{SteeringFrameKind::Command};
        auto value = message();
        value.angle_rad = angle;
        EXPECT_EQ(receiver.receive(encode(value, tx), kStart).decision,
                  angle < -0.5 || angle > 0.5 ? SteeringReceiveDecision::AngleOutOfRange : SteeringReceiveDecision::Accepted);
    }
    // 7000 * 0.0001은 literal 0.7과 1 ULP 다를 수 있다. 같은 wire 경계는 수용한다.
    for (double angle : {-0.7001, -0.7, 0.7, 0.7001}) {
        SteeringReceiver boundary({SteeringFrameKind::Command, -0.7, 0.7});
        ASSERT_TRUE(boundary.start_session(1, kStart));
        SteeringTxState boundary_tx{SteeringFrameKind::Command};
        auto sample = message();
        sample.angle_rad = angle;
        EXPECT_EQ(boundary.receive(encode(sample, boundary_tx), kStart).decision,
                  angle < -0.7 || angle > 0.7 ? SteeringReceiveDecision::AngleOutOfRange : SteeringReceiveDecision::Accepted);
    }
    SteeringReceiver receiver(config());
    ASSERT_TRUE(receiver.start_session(1, kStart));
    SteeringTxState tx{SteeringFrameKind::Command};
    auto value = message();
    ASSERT_EQ(receiver.receive(encode(value, tx), kStart).decision, SteeringReceiveDecision::Accepted);
    value.sequence = 1;
    value.source_time_ns += kMs;
    value.angle_rad.reset();
    EXPECT_EQ(receiver.receive(encode(value, tx), kStart + kMs).decision, SteeringReceiveDecision::Unavailable);
    EXPECT_EQ(receiver.last_accepted()->message.sequence, 0);
    EXPECT_EQ(receiver.last_accepted()->received_time_ns, kStart);
}

TEST(SteeringReceiver, CommandModeRequiresNormalPathAndNormalOrDegradedState) {
    for (auto state : {SteeringLocalState::Init, SteeringLocalState::Normal,
                       SteeringLocalState::Degraded, SteeringLocalState::FailSafe}) {
        for (auto origin : {SteeringOrigin::NoAcceptedInput, SteeringOrigin::NormalPath,
                            SteeringOrigin::LocalProtection}) {
            SteeringReceiver receiver(config());
            ASSERT_TRUE(receiver.start_session(1, kStart));
            SteeringTxState tx{SteeringFrameKind::Command};
            auto value = message();
            value.local_state = state;
            value.origin = origin;
            const bool allowed = origin == SteeringOrigin::NormalPath &&
                                 (state == SteeringLocalState::Normal || state == SteeringLocalState::Degraded);
            EXPECT_EQ(receiver.receive(encode(value, tx), kStart).decision,
                      allowed ? SteeringReceiveDecision::Accepted : SteeringReceiveDecision::ModeRejected);
            EXPECT_EQ(receiver.last_accepted().has_value(), allowed);
        }
    }
}

TEST(SteeringReceiver, ActualValidityDoesNotImplyHealthyActuatorOrNormalDriving) {
    for (auto state : {SteeringLocalState::Init, SteeringLocalState::Normal,
                       SteeringLocalState::Degraded, SteeringLocalState::FailSafe}) {
        for (auto origin : {SteeringOrigin::NoAcceptedInput, SteeringOrigin::NormalPath,
                            SteeringOrigin::LocalProtection}) {
            SteeringReceiver receiver(config(SteeringFrameKind::Actual));
            ASSERT_TRUE(receiver.start_session(1, kStart));
            SteeringTxState tx{SteeringFrameKind::Actual};
            auto value = message(SteeringFrameKind::Actual);
            value.local_state = state;
            value.origin = origin;
            const bool allowed = origin != SteeringOrigin::NoAcceptedInput || state == SteeringLocalState::Init;
            EXPECT_EQ(receiver.receive(encode(value, tx), kStart).decision,
                      allowed ? SteeringReceiveDecision::Accepted : SteeringReceiveDecision::ModeRejected);
            const auto current = receiver.current_sample(kStart);
            ASSERT_EQ(current.has_value(), allowed);
            if (current) {
                EXPECT_EQ(current->local_state, state);
                EXPECT_EQ(current->origin, origin);
                EXPECT_EQ(receiver.health(), SteeringReceiverHealth::Receiving);
            }
        }
    }
}

TEST(SteeringReceiver, SourceAgeExpiresBeforeCommunicationTimeout) {
    SteeringReceiver receiver(config());
    ASSERT_TRUE(receiver.start_session(1, kStart));
    SteeringTxState tx{SteeringFrameKind::Command};
    ASSERT_EQ(receiver.receive(encode(message(), tx), kStart + 10 * kMs).decision,
              SteeringReceiveDecision::Accepted);
    EXPECT_TRUE(receiver.current_sample(kStart + 30 * kMs));
    EXPECT_FALSE(receiver.current_sample(kStart + 30 * kMs + 1));
    EXPECT_EQ(receiver.health(), SteeringReceiverHealth::Receiving);
    EXPECT_EQ(receiver.poll(kStart + 90 * kMs - 1), SteeringReceiverHealth::Receiving);
    EXPECT_EQ(receiver.poll(kStart + 90 * kMs), SteeringReceiverHealth::Timeout);
    EXPECT_FALSE(receiver.current_sample(kStart + 90 * kMs));
    ASSERT_TRUE(receiver.last_accepted());  // 진단 이력만 보존한다.
}

TEST(SteeringReceiver, MissingFirstInputTimesOutAndRequiresNewExplicitSession) {
    SteeringReceiver receiver(config());
    ASSERT_TRUE(receiver.start_session(1, kStart));
    EXPECT_EQ(receiver.poll(kStart + 80 * kMs - 1), SteeringReceiverHealth::Waiting);
    SteeringTxState tx{SteeringFrameKind::Command};
    auto value = message();
    value.source_time_ns += 80 * kMs;
    // Deadline과 같은 시각의 valid frame도 먼저 검출된 timeout을 해제하지 못한다.
    EXPECT_EQ(receiver.receive(encode(value, tx), value.source_time_ns).decision, SteeringReceiveDecision::Timeout);
    EXPECT_FALSE(receiver.last_accepted());
    EXPECT_FALSE(receiver.start_session(1, value.source_time_ns));
    EXPECT_FALSE(receiver.start_session(2, value.source_time_ns - 1));
    EXPECT_EQ(receiver.health(), SteeringReceiverHealth::Timeout);
    ASSERT_TRUE(receiver.start_session(2, value.source_time_ns));
    value.epoch = 2;
    SteeringTxState restarted{SteeringFrameKind::Command};
    const auto accepted = receiver.receive(encode(value, restarted), value.source_time_ns);
    EXPECT_EQ(accepted.decision, SteeringReceiveDecision::Accepted);
    EXPECT_EQ(accepted.e2e_status, P05Status::Ok);
}

TEST(SteeringReceiver, RejectedTrafficCannotPostponeTimeoutOrCauseAutomaticRecovery) {
    SteeringReceiver receiver(config());
    ASSERT_TRUE(receiver.start_session(1, kStart));
    SteeringTxState tx{SteeringFrameKind::Command};
    auto value = message();
    const auto first = encode(value, tx);
    ASSERT_EQ(receiver.receive(first, kStart).decision, SteeringReceiveDecision::Accepted);
    for (std::uint64_t step = 10; step <= 70; step += 10) {
        EXPECT_EQ(receiver.receive(first, kStart + step * kMs).decision, SteeringReceiveDecision::E2eRejected);
        EXPECT_EQ(receiver.last_accepted()->received_time_ns, kStart);
    }
    value.sequence = 1;
    value.source_time_ns += 80 * kMs;
    EXPECT_EQ(receiver.receive(encode(value, tx), value.source_time_ns).decision, SteeringReceiveDecision::Timeout);
    value.source_time_ns += kMs;
    EXPECT_EQ(receiver.receive(encode(value, tx), value.source_time_ns).decision, SteeringReceiveDecision::Timeout);
    EXPECT_EQ(receiver.last_raw_rx_time_ns(), value.source_time_ns);
    EXPECT_FALSE(receiver.current_sample(value.source_time_ns));
    EXPECT_EQ(receiver.last_accepted()->message.sequence, 0);
}

TEST(SteeringReceiver, ClockRegressionLatchesFaultAndInvalidInitPreservesHistory) {
    SteeringReceiver receiver(config());
    ASSERT_TRUE(receiver.start_session(1, kStart));
    SteeringTxState tx{SteeringFrameKind::Command};
    ASSERT_EQ(receiver.receive(encode(message(), tx), kStart + 10 * kMs).decision,
              SteeringReceiveDecision::Accepted);
    EXPECT_FALSE(receiver.start_session(1, kStart + 10 * kMs));
    EXPECT_FALSE(receiver.start_session(2, kStart + 9 * kMs));
    EXPECT_EQ(receiver.health(), SteeringReceiverHealth::Receiving);
    EXPECT_EQ(receiver.poll(kStart + 9 * kMs), SteeringReceiverHealth::ClockError);
    EXPECT_EQ(receiver.receive(encode(message(), tx), kStart + 11 * kMs).decision, SteeringReceiveDecision::ClockError);
    EXPECT_FALSE(receiver.current_sample(kStart + 12 * kMs));
    EXPECT_EQ(receiver.last_accepted()->received_time_ns, kStart + 10 * kMs);
    EXPECT_EQ(receiver.last_raw_rx_time_ns(), kStart + 10 * kMs);
    EXPECT_FALSE(receiver.start_session(2, kStart + 11 * kMs));
    ASSERT_TRUE(receiver.start_session(2, kStart + 12 * kMs));
    EXPECT_EQ(receiver.health(), SteeringReceiverHealth::Waiting);
    EXPECT_FALSE(receiver.last_accepted());
    EXPECT_FALSE(receiver.last_raw_rx_time_ns());
}

TEST(SteeringReceiver, P05CounterWrapDoesNotResetApplicationProgress) {
    SteeringReceiver receiver(config());
    ASSERT_TRUE(receiver.start_session(1, kStart));
    SteeringTxState tx{SteeringFrameKind::Command};
    auto value = message();
    for (std::uint32_t index = 0; index <= 256; ++index) {
        value.sequence = index;
        value.source_time_ns = kStart + index * kMs;
        const auto frame = encode(value, tx);
        const auto result = receiver.receive(frame, value.source_time_ns);
        ASSERT_EQ(result.decision, SteeringReceiveDecision::Accepted) << index;
        EXPECT_EQ(result.e2e_status, P05Status::Ok);
        EXPECT_EQ(frame.payload[31], static_cast<std::uint8_t>(index));
    }
    EXPECT_EQ(receiver.last_accepted()->message.sequence, 256);
}

TEST(SteeringReceiver, UsesExactUint64SubtractionsWithoutTimestampOverflow) {
    const auto max = std::numeric_limits<std::uint64_t>::max();
    const auto start = max - 80 * kMs;
    SteeringReceiver receiver(config());
    ASSERT_TRUE(receiver.start_session(1, start));
    SteeringTxState tx{SteeringFrameKind::Command};
    auto value = message();
    value.source_time_ns = start;
    ASSERT_EQ(receiver.receive(encode(value, tx), start).decision, SteeringReceiveDecision::Accepted);
    EXPECT_EQ(receiver.last_accepted()->message.source_time_ns, start);
    EXPECT_TRUE(receiver.current_sample(start + 30 * kMs));
    EXPECT_EQ(receiver.poll(max - 1), SteeringReceiverHealth::Receiving);
    EXPECT_EQ(receiver.poll(max), SteeringReceiverHealth::Timeout);
}
}  // namespace
