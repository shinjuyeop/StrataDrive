#include "brake_receiver.hpp"
#include "brake_pressure_codec.hpp"

#include <gtest/gtest.h>

#include <limits>

namespace {
using namespace stratadrive::can;
using stratadrive::e2e::P05Status;
constexpr std::uint64_t kStart = 1000000000ULL;
constexpr std::uint64_t kMs = 1000000ULL;

BrakeReceiverConfig config(BrakeFrameKind kind = BrakeFrameKind::Command) {
    return {kind, 0.0, 2000000.0};  // fixture 한계이며 차량 calibration이 아니다.
}
BrakeMessage message(BrakeFrameKind kind = BrakeFrameKind::Command) {
    BrakeMessage value;
    value.kind = kind;
    value.pressure_pa = 1500000.0;
    value.epoch = 1;
    value.source_time_ns = kStart;
    value.local_state = BrakeLocalState::Normal;
    value.origin = BrakeOrigin::NormalPath;
    return value;
}
BrakeFrame encode(const BrakeMessage& value, BrakeTxState& tx) {
    const auto frame = encode_brake_frame(value, tx);
    EXPECT_TRUE(frame);
    return frame.value_or(BrakeFrame{});
}
void reseal(BrakeFrame& frame) {
    const auto crc = brake_frame_crc(static_cast<std::uint16_t>(frame.can_id), frame.payload);
    ASSERT_TRUE(crc);
    frame.payload[29] = static_cast<std::uint8_t>(*crc);
    frame.payload[30] = static_cast<std::uint8_t>(*crc >> 8U);
}

TEST(BrakeReceiver, RequiresTrustedSessionAndValidConfiguration) {
    BrakeReceiver receiver(config());
    BrakeTxState tx{BrakeFrameKind::Command};
    EXPECT_EQ(receiver.receive(encode(message(), tx), kStart).decision, BrakeReceiveDecision::NotInitialized);
    EXPECT_FALSE(receiver.current_sample(kStart));
    EXPECT_FALSE(receiver.start_session(0, kStart));
    const auto infinity = std::numeric_limits<double>::infinity();
    const auto nan = std::numeric_limits<double>::quiet_NaN();
    const BrakeReceiverConfig invalid[] = {
        {static_cast<BrakeFrameKind>(0x180), 0, 2000000},
        {BrakeFrameKind::Command, -1000, 2000000},
        {BrakeFrameKind::Command, nan, 2000000},
        {BrakeFrameKind::Command, 0, infinity},
        {BrakeFrameKind::Command, 0, nan},
        {BrakeFrameKind::Command, 0, kBrakePressureWireMaxPa + 1000},
        {BrakeFrameKind::Command, 2000000, 2000000},
        {BrakeFrameKind::Command, 2000000, 0},
        {BrakeFrameKind::Command, 0, 2000000, 0, 80 * kMs},
        {BrakeFrameKind::Command, 0, 2000000, 30 * kMs, 0},
        {BrakeFrameKind::Command, 0, 2000000, 80 * kMs, 80 * kMs},
        {BrakeFrameKind::Command, 0, 2000000, 30 * kMs, 80 * kMs + 1},
    };
    for (const auto& candidate : invalid) {
        BrakeReceiver bad(candidate);
        EXPECT_FALSE(bad.start_session(1, kStart));
        EXPECT_EQ(bad.health(), BrakeReceiverHealth::NotInitialized);
    }
    BrakeReceiver customized({BrakeFrameKind::Command, 0, 2000000, 10 * kMs, 20 * kMs});
    ASSERT_TRUE(customized.start_session(1, kStart));
    EXPECT_EQ(customized.poll(kStart + 20 * kMs - 1), BrakeReceiverHealth::Waiting);
    EXPECT_EQ(customized.poll(kStart + 20 * kMs), BrakeReceiverHealth::Timeout);
}

TEST(BrakeReceiver, AcceptsProgressAndPreservesActualSourceAndCausality) {
    for (auto kind : {BrakeFrameKind::Command, BrakeFrameKind::Actual}) {
        BrakeReceiver receiver(config(kind));
        ASSERT_TRUE(receiver.start_session(1, kStart));
        BrakeTxState tx{kind};
        auto value = message(kind);
        value.causal_sequence = 42;
        const auto first = receiver.receive(encode(value, tx), kStart + kMs);
        EXPECT_EQ(first.decision, BrakeReceiveDecision::Accepted);
        EXPECT_EQ(first.e2e_status, P05Status::Ok);
        ASSERT_TRUE(receiver.last_accepted());
        EXPECT_EQ(receiver.last_accepted()->received_time_ns, kStart + kMs);
        EXPECT_EQ(receiver.last_accepted()->message.source_time_ns, kStart);
        EXPECT_EQ(receiver.last_accepted()->message.causal_sequence, 42);
        value.sequence = 1;
        value.source_time_ns += 10 * kMs;
        value.pressure_pa = 0;
        EXPECT_EQ(receiver.receive(encode(value, tx), value.source_time_ns).decision, BrakeReceiveDecision::Accepted);
        const auto current = receiver.current_sample(kStart + 11 * kMs);
        ASSERT_TRUE(current && current->pressure_pa);
        EXPECT_DOUBLE_EQ(*current->pressure_pa, 0.0);
        EXPECT_EQ(current->sequence, 1);
    }
}

TEST(BrakeReceiver, RepeatCorruptionAndBadEnvelopesDoNotRefreshValidRx) {
    BrakeReceiver receiver(config());
    ASSERT_TRUE(receiver.start_session(1, kStart));
    BrakeTxState tx{BrakeFrameKind::Command};
    auto value = message();
    const auto first = encode(value, tx);
    ASSERT_EQ(receiver.receive(first, kStart).decision, BrakeReceiveDecision::Accepted);
    const auto repeated = receiver.receive(first, kStart + kMs);
    EXPECT_EQ(repeated.decision, BrakeReceiveDecision::E2eRejected);
    EXPECT_EQ(repeated.e2e_status, P05Status::Repeated);
    for (int mutation = 0; mutation < 5; ++mutation) {
        auto bad = first;
        if (mutation == 0) bad.can_id = kBrakeActualId;
        if (mutation == 1) bad.payload_length = 16;
        if (mutation == 2) bad.payload_length = 64;
        if (mutation == 3) bad.is_fd = false;
        if (mutation == 4) bad.fd_flags = 1;
        const auto result = receiver.receive(bad, kStart + 2 * kMs);
        EXPECT_EQ(result.decision, BrakeReceiveDecision::MalformedEnvelope);
        EXPECT_FALSE(result.e2e_status);
    }
    value.sequence = 1;
    value.source_time_ns += 3 * kMs;
    auto corrupt = encode(value, tx);
    corrupt.payload[0] ^= 1U;
    const auto result = receiver.receive(corrupt, value.source_time_ns);
    EXPECT_EQ(result.decision, BrakeReceiveDecision::E2eRejected);
    EXPECT_EQ(result.e2e_status, P05Status::Error);
    EXPECT_EQ(receiver.last_raw_rx_time_ns(), value.source_time_ns);
    EXPECT_EQ(receiver.last_accepted()->received_time_ns, kStart);
    value.sequence = 2;
    value.source_time_ns += kMs;
    EXPECT_EQ(receiver.receive(encode(value, tx), value.source_time_ns).decision, BrakeReceiveDecision::Accepted);
}

TEST(BrakeReceiver, RejectsCrcValidMalformedPayloadWithoutCommitting) {
    BrakeReceiver receiver(config());
    ASSERT_TRUE(receiver.start_session(1, kStart));
    BrakeTxState tx{BrakeFrameKind::Command};
    for (auto byte : {2U, 26U, 3U}) {
        auto malformed = encode(message(), tx);
        malformed.payload[byte] = byte == 3U ? 0 : 1;
        reseal(malformed);
        const auto result = receiver.receive(malformed, kStart);
        EXPECT_EQ(result.decision, BrakeReceiveDecision::MalformedPayload);
        EXPECT_EQ(result.e2e_status, P05Status::Ok);
        EXPECT_FALSE(receiver.last_accepted());
    }
}

TEST(BrakeReceiver, EnforcesEpochSessionFutureAndAgeBoundaries) {
    struct Case { std::uint64_t source; std::uint64_t now; std::uint32_t epoch; BrakeReceiveDecision expected; };
    const Case cases[] = {
        {kStart, kStart, 2, BrakeReceiveDecision::EpochMismatch},
        {kStart - 1, kStart, 1, BrakeReceiveDecision::SourceBeforeSession},
        {kStart + 1, kStart, 1, BrakeReceiveDecision::SourceInFuture},
        {kStart, kStart + 30 * kMs, 1, BrakeReceiveDecision::Accepted},
        {kStart, kStart + 30 * kMs + 1, 1, BrakeReceiveDecision::SourceStale},
    };
    for (const auto& test : cases) {
        BrakeReceiver receiver(config());
        ASSERT_TRUE(receiver.start_session(1, kStart));
        BrakeTxState tx{BrakeFrameKind::Command};
        auto value = message();
        value.epoch = test.epoch;
        value.source_time_ns = test.source;
        EXPECT_EQ(receiver.receive(encode(value, tx), test.now).decision, test.expected);
        EXPECT_EQ(receiver.last_accepted().has_value(), test.expected == BrakeReceiveDecision::Accepted);
    }
}

TEST(BrakeReceiver, RejectsRepackagedReplayAndPreservesApplicationCursors) {
    BrakeReceiver receiver(config());
    ASSERT_TRUE(receiver.start_session(1, kStart));
    BrakeTxState tx{BrakeFrameKind::Command};
    auto value = message();
    value.sequence = 8;
    ASSERT_EQ(receiver.receive(encode(value, tx), kStart).decision, BrakeReceiveDecision::Accepted);
    const auto replay = receiver.receive(encode(value, tx), kStart + kMs);
    EXPECT_EQ(replay.e2e_status, P05Status::Ok);
    EXPECT_EQ(replay.decision, BrakeReceiveDecision::SequenceRejected);
    value.sequence = 18;
    value.source_time_ns += 2 * kMs;
    ASSERT_EQ(receiver.receive(encode(value, tx), value.source_time_ns).decision, BrakeReceiveDecision::Accepted);
    for (auto sequence : {29U, 17U, 18U}) {
        value.sequence = sequence;
        value.source_time_ns += kMs;
        EXPECT_EQ(receiver.receive(encode(value, tx), value.source_time_ns).decision, BrakeReceiveDecision::SequenceRejected);
        EXPECT_EQ(receiver.last_accepted()->message.sequence, 18);
        EXPECT_EQ(receiver.last_accepted()->received_time_ns, kStart + 2 * kMs);
    }
    value.sequence = 19;
    value.source_time_ns = kStart + 2 * kMs;
    EXPECT_EQ(receiver.receive(encode(value, tx), kStart + 6 * kMs).decision, BrakeReceiveDecision::SourceNotIncreasing);
    value.source_time_ns = kStart + 7 * kMs;
    EXPECT_EQ(receiver.receive(encode(value, tx), value.source_time_ns).decision, BrakeReceiveDecision::Accepted);
}

TEST(BrakeReceiver, FirstSequenceMustBeInsideStartupWindow) {
    for (auto sequence : {0U, 9U, 10U, std::numeric_limits<std::uint32_t>::max()}) {
        BrakeReceiver receiver(config());
        ASSERT_TRUE(receiver.start_session(1, kStart));
        BrakeTxState tx{BrakeFrameKind::Command};
        auto value = message();
        value.sequence = sequence;
        EXPECT_EQ(receiver.receive(encode(value, tx), kStart).decision,
                  sequence < 10 ? BrakeReceiveDecision::Accepted : BrakeReceiveDecision::SequenceRejected);
    }
}

TEST(BrakeReceiver, PhysicalPressureLimitsAreIndependentOfWireCapacity) {
    for (double pressure : {0.0, 1000.0, 2000000.0, 2001000.0, kBrakePressureWireMaxPa}) {
        BrakeReceiver receiver(config());
        ASSERT_TRUE(receiver.start_session(1, kStart));
        BrakeTxState tx{BrakeFrameKind::Command};
        auto value = message();
        value.pressure_pa = pressure;
        EXPECT_EQ(receiver.receive(encode(value, tx), kStart).decision,
                  pressure > 2000000 ? BrakeReceiveDecision::PressureOutOfRange : BrakeReceiveDecision::Accepted);
    }
    BrakeReceiver bounded({BrakeFrameKind::Command, 1000, 2000000});
    ASSERT_TRUE(bounded.start_session(1, kStart));
    BrakeTxState tx{BrakeFrameKind::Command};
    auto value = message();
    value.pressure_pa = 0;
    EXPECT_EQ(bounded.receive(encode(value, tx), kStart).decision, BrakeReceiveDecision::PressureOutOfRange);
}

TEST(BrakeReceiver, UnavailableAndOutOfRangeTrafficCannotRenewValidAge) {
    BrakeReceiver receiver(config());
    ASSERT_TRUE(receiver.start_session(1, kStart));
    BrakeTxState tx{BrakeFrameKind::Command};
    auto value = message();
    ASSERT_EQ(receiver.receive(encode(value, tx), kStart).decision, BrakeReceiveDecision::Accepted);
    for (std::uint32_t index = 1; index < 8; ++index) {
        value.sequence = index;
        value.source_time_ns = kStart + index * 10ULL * kMs;
        value.pressure_pa = index % 2U == 0 ? std::optional<double>{2001000} : std::nullopt;
        EXPECT_EQ(receiver.receive(encode(value, tx), value.source_time_ns).decision,
                  value.pressure_pa ? BrakeReceiveDecision::PressureOutOfRange : BrakeReceiveDecision::Unavailable);
        EXPECT_EQ(receiver.last_accepted()->received_time_ns, kStart);
        EXPECT_EQ(receiver.last_accepted()->message.sequence, 0);
    }
    EXPECT_EQ(receiver.poll(kStart + 80 * kMs), BrakeReceiverHealth::Timeout);
}

TEST(BrakeReceiver, CommandModeRequiresNormalPathAndNormalOrDegraded) {
    for (auto state : {BrakeLocalState::Init, BrakeLocalState::Normal, BrakeLocalState::Degraded, BrakeLocalState::FailSafe}) {
        for (auto origin : {BrakeOrigin::NoAcceptedInput, BrakeOrigin::NormalPath, BrakeOrigin::LocalProtection}) {
            BrakeReceiver receiver(config());
            ASSERT_TRUE(receiver.start_session(1, kStart));
            BrakeTxState tx{BrakeFrameKind::Command};
            auto value = message();
            value.local_state = state;
            value.origin = origin;
            const bool allowed = origin == BrakeOrigin::NormalPath &&
                                 (state == BrakeLocalState::Normal || state == BrakeLocalState::Degraded);
            EXPECT_EQ(receiver.receive(encode(value, tx), kStart).decision,
                      allowed ? BrakeReceiveDecision::Accepted : BrakeReceiveDecision::ModeRejected);
        }
    }
}

TEST(BrakeReceiver, ActualSampleValidityDoesNotOverrideSenderHealth) {
    for (auto state : {BrakeLocalState::Init, BrakeLocalState::Normal, BrakeLocalState::Degraded, BrakeLocalState::FailSafe}) {
        for (auto origin : {BrakeOrigin::NoAcceptedInput, BrakeOrigin::NormalPath, BrakeOrigin::LocalProtection}) {
            BrakeReceiver receiver(config(BrakeFrameKind::Actual));
            ASSERT_TRUE(receiver.start_session(1, kStart));
            BrakeTxState tx{BrakeFrameKind::Actual};
            auto value = message(BrakeFrameKind::Actual);
            value.local_state = state;
            value.origin = origin;
            const bool allowed = origin != BrakeOrigin::NoAcceptedInput || state == BrakeLocalState::Init;
            EXPECT_EQ(receiver.receive(encode(value, tx), kStart).decision,
                      allowed ? BrakeReceiveDecision::Accepted : BrakeReceiveDecision::ModeRejected);
            const auto current = receiver.current_sample(kStart);
            ASSERT_EQ(current.has_value(), allowed);
            if (current) {
                EXPECT_EQ(current->local_state, state);
                EXPECT_EQ(current->origin, origin);
            }
        }
    }
}

TEST(BrakeReceiver, SourceAgeExpiresBeforeRxTimeoutAndHistoryRemainsDiagnostic) {
    BrakeReceiver receiver(config());
    ASSERT_TRUE(receiver.start_session(1, kStart));
    BrakeTxState tx{BrakeFrameKind::Command};
    ASSERT_EQ(receiver.receive(encode(message(), tx), kStart + 10 * kMs).decision, BrakeReceiveDecision::Accepted);
    EXPECT_TRUE(receiver.current_sample(kStart + 30 * kMs));
    EXPECT_FALSE(receiver.current_sample(kStart + 30 * kMs + 1));
    EXPECT_EQ(receiver.health(), BrakeReceiverHealth::Receiving);
    EXPECT_EQ(receiver.poll(kStart + 90 * kMs - 1), BrakeReceiverHealth::Receiving);
    EXPECT_EQ(receiver.poll(kStart + 90 * kMs), BrakeReceiverHealth::Timeout);
    EXPECT_FALSE(receiver.current_sample(kStart + 90 * kMs));
    EXPECT_TRUE(receiver.last_accepted());
}

TEST(BrakeReceiver, DeadlineAndLateValidFrameCannotClearTimeoutLatch) {
    for (bool accept_first : {false, true}) {
        BrakeReceiver receiver(config());
        ASSERT_TRUE(receiver.start_session(1, kStart));
        BrakeTxState tx{BrakeFrameKind::Command};
        auto value = message();
        if (accept_first) {
            ASSERT_EQ(receiver.receive(encode(value, tx), kStart).decision, BrakeReceiveDecision::Accepted);
        }
        value.source_time_ns += 80 * kMs;
        value.sequence = 1;
        const auto at_deadline = receiver.receive(encode(value, tx), value.source_time_ns);
        EXPECT_EQ(at_deadline.decision, BrakeReceiveDecision::Timeout);
        EXPECT_FALSE(at_deadline.e2e_status);
        EXPECT_FALSE(receiver.start_session(1, value.source_time_ns));
        EXPECT_FALSE(receiver.start_session(2, value.source_time_ns - 1));
        value.source_time_ns += kMs;
        EXPECT_EQ(receiver.receive(encode(value, tx), value.source_time_ns).decision, BrakeReceiveDecision::Timeout);
        ASSERT_TRUE(receiver.start_session(2, value.source_time_ns));
        EXPECT_FALSE(receiver.last_accepted());
        EXPECT_FALSE(receiver.last_raw_rx_time_ns());
        BrakeTxState restarted{BrakeFrameKind::Command};
        value.epoch = 2;
        value.sequence = 0;
        EXPECT_EQ(receiver.receive(encode(value, restarted), value.source_time_ns).decision, BrakeReceiveDecision::Accepted);
    }
}

TEST(BrakeReceiver, ClockRollbackLatchesUntilNewExplicitSession) {
    BrakeReceiver receiver(config());
    ASSERT_TRUE(receiver.start_session(1, kStart));
    BrakeTxState tx{BrakeFrameKind::Command};
    ASSERT_EQ(receiver.receive(encode(message(), tx), kStart).decision, BrakeReceiveDecision::Accepted);
    receiver.poll(kStart + 10 * kMs);
    const auto result = receiver.receive(encode(message(), tx), kStart + 9 * kMs);
    EXPECT_EQ(result.decision, BrakeReceiveDecision::ClockError);
    EXPECT_FALSE(result.e2e_status);
    EXPECT_EQ(receiver.last_raw_rx_time_ns(), kStart);
    EXPECT_FALSE(receiver.current_sample(kStart + 11 * kMs));
    EXPECT_FALSE(receiver.start_session(2, kStart + 10 * kMs));
    EXPECT_EQ(receiver.last_accepted()->received_time_ns, kStart);
    EXPECT_TRUE(receiver.start_session(2, kStart + 11 * kMs));
}

TEST(BrakeReceiver, CounterResynchronizationDoesNotCommitRejectedMetadata) {
    BrakeReceiver receiver(config());
    ASSERT_TRUE(receiver.start_session(1, kStart));
    BrakeTxState tx{BrakeFrameKind::Command};
    auto value = message();
    ASSERT_EQ(receiver.receive(encode(value, tx), kStart).decision, BrakeReceiveDecision::Accepted);
    for (int index = 0; index < 11; ++index) encode(value, tx);
    value.sequence = 1;
    value.source_time_ns += kMs;
    const auto jump = receiver.receive(encode(value, tx), value.source_time_ns);
    EXPECT_EQ(jump.decision, BrakeReceiveDecision::E2eRejected);
    EXPECT_EQ(jump.e2e_status, P05Status::WrongSequence);
    EXPECT_EQ(receiver.last_accepted()->message.sequence, 0);
    value.sequence = 2;
    value.source_time_ns += kMs;
    EXPECT_EQ(receiver.receive(encode(value, tx), value.source_time_ns).decision, BrakeReceiveDecision::Accepted);
}

TEST(BrakeReceiver, CommandAndActualHaveIndependentSessionAndCounterState) {
    BrakeReceiver command(config());
    BrakeReceiver actual(config(BrakeFrameKind::Actual));
    ASSERT_TRUE(command.start_session(1, kStart));
    ASSERT_TRUE(actual.start_session(2, kStart));
    BrakeTxState command_tx{BrakeFrameKind::Command};
    BrakeTxState actual_tx{BrakeFrameKind::Actual};
    auto actual_message = message(BrakeFrameKind::Actual);
    actual_message.epoch = 2;
    const auto command_frame = encode(message(), command_tx);
    const auto actual_frame = encode(actual_message, actual_tx);
    EXPECT_EQ(actual.receive(command_frame, kStart).decision, BrakeReceiveDecision::MalformedEnvelope);
    EXPECT_EQ(command.receive(actual_frame, kStart).decision, BrakeReceiveDecision::MalformedEnvelope);
    EXPECT_EQ(command.receive(command_frame, kStart).decision, BrakeReceiveDecision::Accepted);
    EXPECT_EQ(actual.receive(actual_frame, kStart).decision, BrakeReceiveDecision::Accepted);
    EXPECT_EQ(command.poll(kStart + 80 * kMs), BrakeReceiverHealth::Timeout);
    actual_message.sequence = 1;
    actual_message.source_time_ns += 70 * kMs;
    EXPECT_EQ(actual.receive(encode(actual_message, actual_tx), actual_message.source_time_ns).decision, BrakeReceiveDecision::Accepted);
    EXPECT_EQ(actual.health(), BrakeReceiverHealth::Receiving);
    EXPECT_EQ(command.health(), BrakeReceiverHealth::Timeout);
}
}  // namespace
