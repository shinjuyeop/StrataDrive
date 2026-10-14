#include "bms_receiver.hpp"
#include "bms_value_codec.hpp"

#include <gtest/gtest.h>

#include <cmath>
#include <limits>
#include <sstream>
#include <vector>

namespace {
using namespace stratadrive::can;
using stratadrive::e2e::P05Status;
constexpr std::uint64_t kStart = 1000000000ULL, kMs = 1000000ULL;
constexpr BmsFrameKind kKinds[]{BmsFrameKind::PowerRequest, BmsFrameKind::PowerStatus,
    BmsFrameKind::PowerLimits, BmsFrameKind::BatteryState, BmsFrameKind::DriveBatteryLimits, BmsFrameKind::DrivePermission};
BmsReceiverConfig config(BmsFrameKind kind) {
    return {kind, {{0, 1000}, {-500, 500}, {-60, 200}, 200000}}; // Host fixture, not OEM calibration.
}
BmsMessage sample(BmsFrameKind kind) {
    BmsMessage message;
    message.kind = kind; message.epoch = 1; message.source_time_ns = kStart;
    message.causal_sequence = 7; message.local_state = ActuatorLocalState::Normal;
    message.origin = ActuatorOrigin::NormalPath;
    switch (kind) {
    case BmsFrameKind::PowerRequest:
        message.content = BmsPowerRequest{BmsPowerAction::Enable, kStart + 80*kMs, kStart}; break;
    case BmsFrameKind::PowerStatus:
        message.content = BmsPowerStatus{BmsPowerState::HvReady, true, true, false, 7, 31, 390, kStart, kStart, 12}; break;
    case BmsFrameKind::PowerLimits:
    case BmsFrameKind::DriveBatteryLimits:
        message.content = BmsPowerLimits{120000, 200000, BmsLimitReason::Nominal, BmsLimitReason::Nominal, kStart}; break;
    case BmsFrameKind::BatteryState:
        message.content = BmsBatteryState{BmsSocSample{0.6, kStart}, BmsElectricalSample{400, -120, kStart}, BmsTemperatureSample{25, kStart}}; break;
    case BmsFrameKind::DrivePermission:
        message.content = BmsDriveGrant{BmsDrivePermission::AllowNormal, 12, kStart, kStart, kStart+70*kMs}; break;
    }
    return message;
}
BmsParentContext parent() { return {1, 7, kStart, kStart+80*kMs}; }
void advance(BmsMessage& message, unsigned int ms) { ++message.sequence; message.source_time_ns = kStart+ms*kMs; }
BmsFrame encode(const BmsMessage& message, BmsTxState& tx) {
    const auto frame = encode_bms_frame(message, tx); EXPECT_TRUE(frame);
    return frame.value_or(BmsFrame{});
}
void reseal(BmsFrame& frame) {
    const auto crc = bms_frame_crc(frame); ASSERT_TRUE(crc);
    frame.payload[29] = static_cast<std::uint8_t>(*crc); frame.payload[30] = static_cast<std::uint8_t>(*crc >> 8U);
}
std::vector<std::uint8_t> hex_bytes(const char* hex) {
    std::istringstream input(hex); unsigned int value = 0; std::vector<std::uint8_t> output;
    while (input >> std::hex >> value) output.push_back(static_cast<std::uint8_t>(value));
    return output;
}

TEST(BmsValues, UnitsSignsZeroAndHalfAwayQuantization) {
    EXPECT_EQ(encode_bms_value(BmsValueKind::Soc, 0.6), (BmsValueBytes{0x70, 0x17}));
    EXPECT_EQ(encode_bms_value(BmsValueKind::Current, -120), (BmsValueBytes{0x50, 0xFB}));
    EXPECT_EQ(encode_bms_value(BmsValueKind::Temperature, 25), (BmsValueBytes{0xFA, 0}));
    EXPECT_EQ(encode_bms_value(BmsValueKind::PowerLimit, 120000), (BmsValueBytes{0xE0, 0x2E}));
    EXPECT_EQ(encode_bms_value(BmsValueKind::PowerLimit, 0), (BmsValueBytes{0, 0}));
    EXPECT_EQ(encode_bms_value(BmsValueKind::Current, 0.25), (BmsValueBytes{3, 0}));
    EXPECT_EQ(encode_bms_value(BmsValueKind::Temperature, -0.25), (BmsValueBytes{0xFD, 0xFF}));
    EXPECT_EQ(encode_bms_value(BmsValueKind::PowerLimit, 15), (BmsValueBytes{2, 0}));
}
TEST(BmsValues, EveryValidRawCodeRoundTripsAndSentinelsStayInvalid) {
    for (const auto kind : {BmsValueKind::Soc, BmsValueKind::Voltage, BmsValueKind::Current,
                            BmsValueKind::Temperature, BmsValueKind::PowerLimit}) {
        for (std::uint32_t raw = 0; raw <= 65535; ++raw) {
            const BmsValueBytes bytes{static_cast<std::uint8_t>(raw), static_cast<std::uint8_t>(raw >> 8U)};
            const bool signed_value = kind == BmsValueKind::Current || kind == BmsValueKind::Temperature;
            const bool invalid = signed_value ? raw == 32768 : raw == 65535 || (kind == BmsValueKind::Soc && raw > 10000);
            const auto value = decode_bms_value(kind, bytes);
            if (invalid) EXPECT_FALSE(value);
            else { ASSERT_TRUE(value); EXPECT_EQ(encode_bms_value(kind, *value), bytes); }
        }
    }
}
TEST(BmsValues, RejectsNonfiniteAndOutOfRangeBeforeRounding) {
    for (const auto kind : {BmsValueKind::Soc, BmsValueKind::Voltage, BmsValueKind::Current,
                            BmsValueKind::Temperature, BmsValueKind::PowerLimit}) {
        for (const double value : {NAN, INFINITY, -INFINITY}) EXPECT_FALSE(encode_bms_value(kind, value));
    }
    EXPECT_FALSE(encode_bms_value(BmsValueKind::Soc, 1.000001));
    EXPECT_FALSE(encode_bms_value(BmsValueKind::Soc, -0.000001));
    EXPECT_FALSE(encode_bms_value(BmsValueKind::PowerLimit, 655340.01));
    EXPECT_FALSE(encode_bms_value(BmsValueKind::Current, -3276.7001));
    EXPECT_FALSE(encode_bms_value(static_cast<BmsValueKind>(99), 0));
    EXPECT_FALSE(decode_bms_value(static_cast<BmsValueKind>(99), {0, 0}));
}
TEST(BmsFrame, MatchesSixIndependentDbcAndCrcGoldens) {
    const char* hex[]{
        "01 00 01 01 00 00 00 00 01 00 00 00 00 CA 9A 3B 00 00 00 00 07 00 00 00 01 01 00 00 00 9D C1 00 00 7E 5F 40 00 00 00 00 80 33 02 3B 00 00 00 00",
        "03 00 01 01 00 00 00 00 01 00 00 00 00 CA 9A 3B 00 00 00 00 07 00 00 00 01 01 00 00 00 3C 3F 00 01 01 00 07 1F 00 00 00 3C 0F 01 00 C0 7E 4E 3B 00 00 00 00 80 33 02 3B 00 00 00 00 0C 00 00 00",
        "E0 2E 01 01 00 00 00 00 01 00 00 00 00 CA 9A 3B 00 00 00 00 07 00 00 00 01 01 00 00 00 00 9C 00 20 4E 01 00 00 00 00 00 80 33 02 3B 00 00 00 00",
        "70 17 01 01 00 00 00 00 01 00 00 00 00 CA 9A 3B 00 00 00 00 07 00 00 00 01 01 00 00 00 33 2B 00 A0 0F 50 FB FA 00 01 01 80 33 02 3B 00 00 00 00 80 33 02 3B 00 00 00 00 80 33 02 3B 00 00 00 00",
        "E0 2E 01 01 00 00 00 00 01 00 00 00 00 CA 9A 3B 00 00 00 00 07 00 00 00 01 01 00 00 00 21 8C 00 20 4E 01 00 00 00 00 00 80 33 02 3B 00 00 00 00",
        "01 00 01 01 00 00 00 00 01 00 00 00 00 CA 9A 3B 00 00 00 00 07 00 00 00 01 01 00 00 00 CB 73 00 0C 00 00 00 C0 7E 4E 3B 00 00 00 00 80 33 02 3B 00 00 00 00 80 E7 C6 3F 00 00 00 00 00 00 00 00"};
    for (std::size_t index = 0; index < 6; ++index) {
        auto message = sample(kKinds[index]);
        if (auto* v = std::get_if<BmsPowerRequest>(&message.content)) v->parent_source_time_ns -= 10*kMs;
        if (auto* v = std::get_if<BmsPowerLimits>(&message.content)) v->input_time_ns -= 10*kMs;
        if (auto* v = std::get_if<BmsBatteryState>(&message.content)) {
            v->soc->source_time_ns -= 10*kMs; v->electrical->source_time_ns -= 10*kMs; v->temperature->source_time_ns -= 10*kMs;
        }
        if (auto* v = std::get_if<BmsPowerStatus>(&message.content)) { v->input_time_ns -= 5*kMs; v->accepted_request_source_time_ns -= 10*kMs; }
        if (auto* v = std::get_if<BmsDriveGrant>(&message.content)) { v->power_status_source_time_ns -= 5*kMs; v->input_time_ns -= 10*kMs; }
        BmsTxState tx{message.kind}; const auto frame = encode(message, tx);
        EXPECT_EQ(std::vector<std::uint8_t>(frame.payload.begin(), frame.payload.begin()+frame.payload_length), hex_bytes(hex[index]));
        const auto decoded = decode_bms_frame(frame); ASSERT_TRUE(decoded);
        BmsTxState roundtrip{message.kind}; EXPECT_EQ(encode(*decoded, roundtrip).payload, frame.payload);
    }
}
TEST(BmsFrame, AllPayloadBitsAndWrongDataIdAreProtected) {
    for (const auto kind : kKinds) {
        auto message = sample(kind); BmsTxState tx{kind}; const auto frame = encode(message, tx);
        for (std::size_t byte = 0; byte < frame.payload_length; ++byte) {
            for (unsigned int bit = 0; bit < 8; ++bit) {
                auto corrupt = frame; corrupt.payload[byte] ^= static_cast<std::uint8_t>(1U << bit);
                EXPECT_FALSE(decode_bms_frame(corrupt));
                BmsRxState rx{kind}; EXPECT_EQ(check_bms_e2e(&corrupt, rx), stratadrive::e2e::P05Return::Ok);
                EXPECT_EQ(rx.check.status, P05Status::Error);
            }
        }
        auto config = *bms_e2e_config(kind); ++config.data_id;
        EXPECT_NE(stratadrive::e2e::p05_crc(config, frame.payload.data(), frame.payload_length), bms_frame_crc(frame));
    }
}
TEST(BmsFrame, RejectsEnvelopeWithoutNormalizingFlagsIdOrLength) {
    for (const auto kind : kKinds) {
        BmsTxState tx{kind}; const auto original = encode(sample(kind), tx);
        for (unsigned int mutation = 0; mutation < 6; ++mutation) {
            auto frame = original;
            if (mutation == 0) frame.is_fd = false;
            if (mutation == 1) frame.fd_flags = 1;
            if (mutation == 2) frame.fd_flags = 2;
            if (mutation == 3) --frame.payload_length;
            if (mutation == 4) ++frame.payload_length;
            if (mutation == 5) frame.can_id |= 0x80000000U;
            EXPECT_FALSE(decode_bms_frame(frame)); EXPECT_FALSE(bms_frame_crc(frame));
        }
        auto marker = original; marker.fd_flags = 4; EXPECT_TRUE(decode_bms_frame(marker));
        BmsRxState wrong{static_cast<BmsFrameKind>(0)};
        EXPECT_EQ(check_bms_e2e(&original, wrong), stratadrive::e2e::P05Return::InputWrong);
    }
}
TEST(BmsFrame, RejectsResealedNoncanonicalPayloads) {
    for (const auto kind : kKinds) {
        BmsTxState tx{kind}; const auto original = encode(sample(kind), tx);
        for (const auto offset : {2, 3, 8, 24, 25, 27}) {
            auto corrupt = original;
            corrupt.payload[offset] = offset == 8 ? 0 : 255;
            reseal(corrupt); EXPECT_FALSE(decode_bms_frame(corrupt));
        }
    }
    BmsTxState tx{BmsFrameKind::BatteryState}; auto frame = encode(sample(tx.kind), tx);
    frame.payload[0] = 0x11; frame.payload[1] = 0x27; reseal(frame); EXPECT_FALSE(decode_bms_frame(frame)); // SOC raw 10001
    frame = encode(sample(tx.kind), tx); frame.payload[38] = 0; reseal(frame); EXPECT_FALSE(decode_bms_frame(frame));
    BmsTxState power{BmsFrameKind::PowerStatus}; frame = encode(sample(power.kind), power);
    frame.payload[36] = 0; reseal(frame); EXPECT_FALSE(decode_bms_frame(frame));
    frame = encode(sample(power.kind), power); frame.payload[32] = 2; reseal(frame); EXPECT_FALSE(decode_bms_frame(frame));
    BmsTxState limits{BmsFrameKind::PowerLimits}; frame = encode(sample(limits.kind), limits);
    frame.payload[35] = 4; reseal(frame); EXPECT_FALSE(decode_bms_frame(frame));
    BmsTxState permit{BmsFrameKind::DrivePermission}; frame = encode(sample(permit.kind), permit);
    frame.payload[60] = 1; reseal(frame); EXPECT_FALSE(decode_bms_frame(frame));
}
TEST(BmsFrame, InvalidEncodeNeverAdvancesCounterAndRejectsVariantMismatch) {
    for (const auto kind : kKinds) {
        BmsTxState tx{kind}; auto message = sample(kind); message.epoch = 0;
        EXPECT_FALSE(encode_bms_frame(message, tx)); EXPECT_EQ(tx.protection.counter, 0);
        message = sample(kind); message.content = kind == BmsFrameKind::BatteryState ? BmsContent{BmsPowerRequest{}} : BmsContent{BmsBatteryState{}};
        EXPECT_FALSE(encode_bms_frame(message, tx)); EXPECT_EQ(tx.protection.counter, 0);
    }
    BmsTxState tx{BmsFrameKind::PowerLimits}; auto message = sample(tx.kind);
    std::get<BmsPowerLimits>(message.content).charge_power_w = INFINITY;
    EXPECT_FALSE(encode_bms_frame(message, tx)); EXPECT_EQ(tx.protection.counter, 0);
    message = sample(tx.kind); std::get<BmsPowerLimits>(message.content).input_time_ns = kStart+1;
    EXPECT_FALSE(encode_bms_frame(message, tx));
    message = sample(BmsFrameKind::DrivePermission); BmsTxState grant{message.kind};
    std::get<BmsDriveGrant>(message.content).expires_at_ns = kStart+80*kMs+1;
    EXPECT_FALSE(encode_bms_frame(message, grant)); EXPECT_EQ(grant.protection.counter, 0);
}
TEST(BmsFrame, KeepsFullWidthTimestampsAndSafeExpiryArithmetic) {
    for (const auto stamp : {(1ULL << 53U)+1, std::numeric_limits<unsigned long long>::max()}) {
        for (const auto kind : kKinds) {
            auto message = sample(kind); message.source_time_ns = stamp;
            if (auto* v = std::get_if<BmsPowerRequest>(&message.content)) {
                message.source_time_ns = stamp-1; v->parent_source_time_ns = stamp-1; v->expires_at_ns = stamp;
            }
            if (auto* v = std::get_if<BmsPowerLimits>(&message.content)) v->input_time_ns = stamp;
            if (auto* v = std::get_if<BmsBatteryState>(&message.content)) {
                v->soc->source_time_ns = stamp; v->electrical->source_time_ns = stamp; v->temperature->source_time_ns = stamp;
            }
            if (auto* v = std::get_if<BmsPowerStatus>(&message.content)) { v->input_time_ns = stamp; v->accepted_request_source_time_ns = stamp; }
            if (auto* v = std::get_if<BmsDriveGrant>(&message.content)) {
                message.source_time_ns = stamp-1; v->power_status_source_time_ns = stamp-1; v->input_time_ns = stamp-1; v->expires_at_ns = stamp;
            }
            BmsTxState tx{kind}; const auto decoded = decode_bms_frame(encode(message, tx)); ASSERT_TRUE(decoded);
            EXPECT_EQ(decoded->source_time_ns, message.source_time_ns);
            if (const auto* v = std::get_if<BmsPowerLimits>(&decoded->content)) { EXPECT_EQ(v->input_time_ns, stamp); }
            if (const auto* v = std::get_if<BmsBatteryState>(&decoded->content)) { EXPECT_EQ(v->electrical->source_time_ns, stamp); }
        }
    }
    auto message = sample(BmsFrameKind::PowerRequest); message.source_time_ns = UINT64_MAX;
    std::get<BmsPowerRequest>(message.content).expires_at_ns = 0;
    BmsTxState tx{message.kind}; EXPECT_FALSE(encode_bms_frame(message, tx));
}
TEST(BmsFrame, ForwardingPreservesOriginalSampleWithIndependentCounter) {
    auto message = sample(BmsFrameKind::PowerLimits); message.sequence = 9; message.epoch = 42;
    BmsTxState upstream{message.kind}, downstream{BmsFrameKind::DriveBatteryLimits}; downstream.protection.counter = 17;
    const auto original = encode(message, upstream); const auto forwarded = forward_bms_limits(message, downstream); ASSERT_TRUE(forwarded);
    for (std::size_t i = 0; i < original.payload_length; ++i) {
        if (i < 29 || i > 31) { EXPECT_EQ(original.payload[i], forwarded->payload[i]); }
    }
    EXPECT_EQ(forwarded->payload[31], 17); EXPECT_EQ(original.payload[31], 0);
    const auto decoded = decode_bms_frame(*forwarded); ASSERT_TRUE(decoded);
    EXPECT_EQ(decoded->source_time_ns, message.source_time_ns); EXPECT_EQ(decoded->epoch, 42); EXPECT_EQ(decoded->sequence, 9);
    EXPECT_FALSE(forward_bms_limits(sample(BmsFrameKind::BatteryState), downstream));
}
TEST(BmsFrame, ValidZeroUnknownAndPartialSensorsRoundTripSeparately) {
    auto message = sample(BmsFrameKind::PowerLimits); auto& limits = std::get<BmsPowerLimits>(message.content);
    limits.charge_power_w = 0; limits.charge_reason = BmsLimitReason::Disabled;
    limits.discharge_power_w.reset(); limits.discharge_reason = BmsLimitReason::InputsInvalid;
    BmsTxState tx{message.kind}; const auto decoded = decode_bms_frame(encode(message, tx)); ASSERT_TRUE(decoded);
    const auto& value = std::get<BmsPowerLimits>(decoded->content); ASSERT_TRUE(value.charge_power_w); EXPECT_EQ(*value.charge_power_w, 0); EXPECT_FALSE(value.discharge_power_w);
    message = sample(BmsFrameKind::BatteryState); std::get<BmsBatteryState>(message.content).temperature.reset();
    BmsTxState battery{message.kind}; const auto packet = decode_bms_frame(encode(message, battery)); ASSERT_TRUE(packet);
    EXPECT_TRUE(std::get<BmsBatteryState>(packet->content).electrical); EXPECT_FALSE(std::get<BmsBatteryState>(packet->content).temperature);
}
TEST(BmsReceiver, EveryStreamRequiresTrustedInitAndAcceptsItsOwnFrame) {
    for (const auto kind : kKinds) {
        BmsReceiver receiver(config(kind)); BmsTxState tx{kind}; const auto packet = encode(sample(kind), tx); const auto root = parent();
        EXPECT_EQ(receiver.receive(packet, kStart, &root).decision, ActuatorReceiveDecision::NotInitialized);
        ASSERT_TRUE(receiver.start_session(1, kStart)); EXPECT_EQ(receiver.receive(packet, kStart, &root).decision, ActuatorReceiveDecision::Accepted);
        EXPECT_EQ(receiver.current_sample(kStart)->quality[0], BmsFieldQuality::Usable);
        EXPECT_FALSE(receiver.start_session(1, kStart)); EXPECT_FALSE(receiver.start_session(0, kStart));
    }
}
TEST(BmsReceiver, InvalidConfigurationAndCriticalTimeoutBudgetsAreRejected) {
    for (unsigned int mutation = 0; mutation < 7; ++mutation) {
        auto cfg = config(BmsFrameKind::PowerLimits);
        if (mutation == 0) cfg.timeout_ns = 80000001;
        if (mutation == 1) cfg.max_source_age_ns = cfg.timeout_ns;
        if (mutation == 2) cfg.max_dependency_age_ns = 0;
        if (mutation == 3) cfg.physical.max_power_limit_w = NAN;
        if (mutation == 4) cfg.physical.voltage_v = {100, 0};
        if (mutation == 5) cfg.observation_timeout_ns = 300000001;
        if (mutation == 6) cfg.kind = static_cast<BmsFrameKind>(0);
        BmsReceiver receiver(cfg); EXPECT_FALSE(receiver.start_session(1, kStart));
    }
}
TEST(BmsReceiver, RejectsCounterMetadataAndStaleEnvelopesWithoutRefreshingFields) {
    BmsReceiver receiver(config(BmsFrameKind::PowerLimits)); ASSERT_TRUE(receiver.start_session(1, kStart));
    auto message = sample(BmsFrameKind::PowerLimits); BmsTxState tx{message.kind}; const auto good = encode(message, tx);
    ASSERT_EQ(receiver.receive(good, kStart).decision, ActuatorReceiveDecision::Accepted);
    EXPECT_EQ(receiver.receive(good, kStart+kMs).decision, ActuatorReceiveDecision::E2eRejected);
    auto corrupt = good; corrupt.payload[32] ^= 1;
    EXPECT_EQ(receiver.receive(corrupt, kStart+2*kMs).decision, ActuatorReceiveDecision::E2eRejected);
    advance(message, 10); message.epoch = 2;
    EXPECT_EQ(receiver.receive(encode(message, tx), kStart+10*kMs).decision, ActuatorReceiveDecision::EpochMismatch);
    message.epoch = 1; message.sequence = 0;
    EXPECT_EQ(receiver.receive(encode(message, tx), kStart+11*kMs).decision, ActuatorReceiveDecision::SequenceRejected);
    message.sequence = 1; message.source_time_ns = kStart+20*kMs;
    EXPECT_EQ(receiver.receive(encode(message, tx), kStart+12*kMs).decision, ActuatorReceiveDecision::SourceInFuture);
    message.source_time_ns = kStart;
    EXPECT_EQ(receiver.receive(encode(message, tx), kStart+51*kMs).decision, ActuatorReceiveDecision::SourceStale);
    EXPECT_EQ(receiver.last_usable_rx_time_ns(0), kStart); EXPECT_EQ(receiver.last_accepted()->message.sequence, 0);
    EXPECT_EQ(receiver.poll(kStart+80*kMs), ActuatorReceiverHealth::Timeout);
}
TEST(BmsReceiver, DependencyAgeIsIndependentOfFreshCalculationAndExpiresAtBoundary) {
    BmsReceiver receiver(config(BmsFrameKind::PowerLimits)); ASSERT_TRUE(receiver.start_session(1, kStart));
    auto message = sample(BmsFrameKind::PowerLimits); message.source_time_ns += 60*kMs;
    BmsTxState tx{message.kind}; const auto result = receiver.receive(encode(message, tx), kStart+70*kMs);
    EXPECT_EQ(result.quality[0], BmsFieldQuality::Usable);
    const auto at_boundary = receiver.current_sample(kStart+70*kMs); ASSERT_TRUE(at_boundary);
    EXPECT_TRUE(std::get<BmsPowerLimits>(at_boundary->message.content).charge_power_w);
    const auto stale = receiver.current_sample(kStart+71*kMs); ASSERT_TRUE(stale);
    EXPECT_EQ(stale->quality[0], BmsFieldQuality::Stale); EXPECT_FALSE(std::get<BmsPowerLimits>(stale->message.content).charge_power_w);
    advance(message, 72); const auto repeat = receiver.receive(encode(message, tx), kStart+72*kMs);
    EXPECT_EQ(repeat.quality[0], BmsFieldQuality::Stale); EXPECT_EQ(receiver.last_usable_rx_time_ns(0), kStart+70*kMs);
    EXPECT_EQ(receiver.last_accepted()->message.source_time_ns, kStart+72*kMs);
}
TEST(BmsReceiver, MissingChargeLimitCannotHideBehindFreshDischargeAndLateDataCannotRecover) {
    BmsReceiver receiver(config(BmsFrameKind::PowerLimits)); ASSERT_TRUE(receiver.start_session(1, kStart));
    auto message = sample(BmsFrameKind::PowerLimits); BmsTxState tx{message.kind}; ASSERT_EQ(receiver.receive(encode(message, tx), kStart).decision, ActuatorReceiveDecision::Accepted);
    auto& limits = std::get<BmsPowerLimits>(message.content); limits.charge_power_w.reset(); limits.charge_reason = BmsLimitReason::InputsInvalid;
    for (const auto ms : {20U, 40U, 60U}) {
        advance(message, ms); ++message.causal_sequence; limits.input_time_ns = message.source_time_ns;
        const auto result = receiver.receive(encode(message, tx), message.source_time_ns);
        EXPECT_EQ(result.quality[0], BmsFieldQuality::Unavailable); EXPECT_EQ(result.quality[1], BmsFieldQuality::Usable);
        EXPECT_FALSE(std::get<BmsPowerLimits>(receiver.current_sample(message.source_time_ns)->message.content).charge_power_w);
    }
    EXPECT_EQ(receiver.last_usable_rx_time_ns(0), kStart); EXPECT_EQ(receiver.last_usable_rx_time_ns(1), kStart+60*kMs);
    advance(message, 80); limits.charge_power_w = 0; limits.charge_reason = BmsLimitReason::Disabled; limits.input_time_ns = message.source_time_ns; ++message.causal_sequence;
    EXPECT_EQ(receiver.receive(encode(message, tx), message.source_time_ns).decision, ActuatorReceiveDecision::Timeout);
    EXPECT_FALSE(receiver.current_sample(message.source_time_ns));
    EXPECT_FALSE(receiver.start_session(1, message.source_time_ns)); ASSERT_TRUE(receiver.start_session(2, message.source_time_ns));
    message.epoch = 2; message.sequence = 0; stratadrive::e2e::p05_protect_init(tx.protection);
    EXPECT_EQ(receiver.receive(encode(message, tx), message.source_time_ns).quality[0], BmsFieldQuality::Usable);
}
TEST(BmsReceiver, SensorGroupsHaveIndependentAgesAndDoNotFallbackToOldValues) {
    BmsReceiver receiver(config(BmsFrameKind::BatteryState)); ASSERT_TRUE(receiver.start_session(1, kStart));
    auto message = sample(BmsFrameKind::BatteryState); BmsTxState tx{message.kind}; receiver.receive(encode(message, tx), kStart);
    auto& state = std::get<BmsBatteryState>(message.content);
    advance(message, 100); state.electrical->source_time_ns = message.source_time_ns; state.temperature.reset();
    const auto first = receiver.receive(encode(message, tx), message.source_time_ns);
    EXPECT_EQ(first.quality[0], BmsFieldQuality::Usable); EXPECT_EQ(first.quality[2], BmsFieldQuality::Unavailable);
    EXPECT_EQ(receiver.last_usable_rx_time_ns(0), kStart);
    advance(message, 200); state.electrical->source_time_ns = message.source_time_ns;
    EXPECT_EQ(receiver.receive(encode(message, tx), message.source_time_ns).quality[0], BmsFieldQuality::Stale);
    const auto current = receiver.current_sample(message.source_time_ns); ASSERT_TRUE(current);
    const auto& observed = std::get<BmsBatteryState>(current->message.content);
    EXPECT_FALSE(observed.soc); EXPECT_FALSE(observed.temperature); EXPECT_TRUE(observed.electrical);
    advance(message, 400); state.electrical->source_time_ns = message.source_time_ns;
    EXPECT_EQ(receiver.receive(encode(message, tx), message.source_time_ns).quality[1], BmsFieldQuality::Usable);
    EXPECT_EQ(receiver.health(), ActuatorReceiverHealth::Receiving);
}
TEST(BmsReceiver, ChangedCachedSensorAndPhysicalRangeViolationAreRemovedIndependently) {
    BmsReceiver receiver(config(BmsFrameKind::BatteryState)); ASSERT_TRUE(receiver.start_session(1, kStart));
    auto message = sample(BmsFrameKind::BatteryState); BmsTxState tx{message.kind}; receiver.receive(encode(message, tx), kStart);
    advance(message, 20); auto& state = std::get<BmsBatteryState>(message.content);
    state.soc->fraction = 0.5; state.electrical->source_time_ns = message.source_time_ns;
    state.temperature->source_time_ns = message.source_time_ns; state.temperature->celsius = 250;
    const auto result = receiver.receive(encode(message, tx), message.source_time_ns);
    EXPECT_EQ(result.quality[0], BmsFieldQuality::Invalid); EXPECT_EQ(result.quality[1], BmsFieldQuality::Usable); EXPECT_EQ(result.quality[2], BmsFieldQuality::Invalid);
    EXPECT_EQ(receiver.last_usable_rx_time_ns(0), kStart); EXPECT_FALSE(std::get<BmsBatteryState>(receiver.current_sample(message.source_time_ns)->message.content).soc);
}
TEST(BmsReceiver, ModelInputIdentityCannotChangeOrRollBackUnderFreshEnvelope) {
    BmsReceiver receiver(config(BmsFrameKind::PowerLimits)); ASSERT_TRUE(receiver.start_session(1, kStart));
    auto message = sample(BmsFrameKind::PowerLimits); BmsTxState tx{message.kind}; receiver.receive(encode(message, tx), kStart);
    advance(message, 20); std::get<BmsPowerLimits>(message.content).input_time_ns += kMs; // same batch identity, different original input
    EXPECT_EQ(receiver.receive(encode(message, tx), message.source_time_ns).quality[0], BmsFieldQuality::Invalid);
    EXPECT_EQ(receiver.last_usable_rx_time_ns(0), kStart);
    advance(message, 40); message.causal_sequence = 6; std::get<BmsPowerLimits>(message.content).input_time_ns = kStart;
    EXPECT_EQ(receiver.receive(encode(message, tx), message.source_time_ns).quality[1], BmsFieldQuality::Invalid);
}
TEST(BmsReceiver, InitPowerEnableNeedsIndependentMatchingUnexpiredParent) {
    BmsReceiver receiver(config(BmsFrameKind::PowerRequest)); ASSERT_TRUE(receiver.start_session(1, kStart));
    auto message = sample(BmsFrameKind::PowerRequest); message.local_state = ActuatorLocalState::Init;
    BmsTxState tx{message.kind}; const auto root = parent();
    EXPECT_EQ(receiver.receive(encode(message, tx), kStart).issue, BmsReceiveIssue::ParentMissing);
    advance(message, 10); const auto accepted = receiver.receive(encode(message, tx), message.source_time_ns, &root);
    EXPECT_EQ(accepted.decision, ActuatorReceiveDecision::Accepted); EXPECT_EQ(accepted.quality[0], BmsFieldQuality::Usable);
    EXPECT_FALSE(bms_permission_allows_normal(*receiver.current_sample(message.source_time_ns)));
    advance(message, 20); auto mismatch = root; mismatch.sequence = 8;
    EXPECT_EQ(receiver.receive(encode(message, tx), message.source_time_ns, &mismatch).issue, BmsReceiveIssue::ParentMismatch);
    EXPECT_FALSE(receiver.current_sample(message.source_time_ns)); EXPECT_EQ(receiver.last_usable_rx_time_ns(0), kStart+10*kMs);
}
TEST(BmsReceiver, SameParentCannotRenewDeadlineAndStaleParentCannotAuthorizeNewGrant) {
    BmsReceiver receiver(config(BmsFrameKind::DrivePermission)); ASSERT_TRUE(receiver.start_session(1, kStart));
    auto message = sample(BmsFrameKind::DrivePermission); BmsTxState tx{message.kind}; auto root = parent();
    ASSERT_EQ(receiver.receive(encode(message, tx), kStart, &root).decision, ActuatorReceiveDecision::Accepted);
    advance(message, 10); root.expires_at_ns += 10*kMs; std::get<BmsDriveGrant>(message.content).expires_at_ns = root.expires_at_ns;
    EXPECT_EQ(receiver.receive(encode(message, tx), message.source_time_ns, &root).issue, BmsReceiveIssue::ParentRollback);
    EXPECT_FALSE(receiver.current_sample(message.source_time_ns));
    advance(message, 51); root = parent();
    auto& grant = std::get<BmsDriveGrant>(message.content); grant.expires_at_ns = root.expires_at_ns; grant.power_status_source_time_ns = message.source_time_ns; grant.input_time_ns = message.source_time_ns;
    EXPECT_EQ(receiver.receive(encode(message, tx), message.source_time_ns, &root).issue, BmsReceiveIssue::Expired);
    EXPECT_EQ(receiver.last_usable_rx_time_ns(0), kStart);
}
TEST(BmsReceiver, ExplicitInhibitRevokesGrantAndUnknownDoesNotUseOldPermission) {
    BmsReceiver receiver(config(BmsFrameKind::DrivePermission)); ASSERT_TRUE(receiver.start_session(1, kStart));
    auto message = sample(BmsFrameKind::DrivePermission); BmsTxState tx{message.kind}; const auto root = parent();
    receiver.receive(encode(message, tx), kStart, &root); EXPECT_TRUE(bms_permission_allows_normal(*receiver.current_sample(kStart)));
    advance(message, 10); message.origin = ActuatorOrigin::LocalProtection;
    message.content = BmsDriveGrant{BmsDrivePermission::Inhibit, 0, 0, 0, kStart+80*kMs};
    EXPECT_EQ(receiver.receive(encode(message, tx), message.source_time_ns).quality[0], BmsFieldQuality::Usable);
    EXPECT_FALSE(bms_permission_allows_normal(*receiver.current_sample(message.source_time_ns)));
    advance(message, 20); message.content = BmsDriveGrant{};
    EXPECT_EQ(receiver.receive(encode(message, tx), message.source_time_ns).quality[0], BmsFieldQuality::Unavailable);
    EXPECT_EQ(receiver.last_usable_rx_time_ns(0), kStart+10*kMs); EXPECT_FALSE(bms_permission_allows_normal(*receiver.current_sample(message.source_time_ns)));
}
TEST(BmsReceiver, PermissionExpiryBoundaryClosesUseBeforeReceiveTimeout) {
    BmsReceiver receiver(config(BmsFrameKind::DrivePermission)); ASSERT_TRUE(receiver.start_session(1, kStart));
    auto message = sample(BmsFrameKind::DrivePermission); auto root = parent(); root.expires_at_ns = kStart+20*kMs;
    std::get<BmsDriveGrant>(message.content).expires_at_ns = root.expires_at_ns;
    BmsTxState tx{message.kind}; receiver.receive(encode(message, tx), kStart, &root);
    EXPECT_TRUE(bms_permission_allows_normal(*receiver.current_sample(kStart+19*kMs)));
    const auto expired = receiver.current_sample(kStart+20*kMs); ASSERT_TRUE(expired);
    EXPECT_FALSE(bms_permission_allows_normal(*expired)); EXPECT_EQ(expired->quality[0], BmsFieldQuality::Stale);
    EXPECT_EQ(receiver.health(), ActuatorReceiverHealth::Receiving);
}
TEST(BmsReceiver, PowerReadinessIsActualSnapshotAndNeverImplicitNormalPermission) {
    BmsReceiver receiver(config(BmsFrameKind::PowerStatus)); ASSERT_TRUE(receiver.start_session(1, kStart));
    auto message = sample(BmsFrameKind::PowerStatus); message.local_state = ActuatorLocalState::Init; message.origin = ActuatorOrigin::NoAcceptedInput; message.causal_sequence = 0;
    auto& status = std::get<BmsPowerStatus>(message.content); status.accepted_request_source_time_ns = 0;
    BmsTxState tx{message.kind}; receiver.receive(encode(message, tx), kStart);
    const auto ready = receiver.current_sample(kStart); ASSERT_TRUE(ready); EXPECT_TRUE(bms_power_is_ready(*ready)); EXPECT_FALSE(bms_permission_allows_normal(*ready));
    advance(message, 10); status.condition_validity = 15; status.input_time_ns = message.source_time_ns; ++status.input_sequence;
    const auto unknown = receiver.receive(encode(message, tx), message.source_time_ns);
    EXPECT_EQ(unknown.quality[1], BmsFieldQuality::Unavailable); EXPECT_FALSE(bms_power_is_ready(*receiver.current_sample(message.source_time_ns)));
    advance(message, 20); status.condition_validity = 31; status.condition_bits = 23; status.input_time_ns = message.source_time_ns; ++status.input_sequence;
    EXPECT_EQ(receiver.receive(encode(message, tx), message.source_time_ns).quality[1], BmsFieldQuality::Usable);
    EXPECT_FALSE(bms_power_is_ready(*receiver.current_sample(message.source_time_ns))); // known fault is valid observation
}
TEST(BmsReceiver, PowerHeartbeatCannotRefreshCachedPhysicalInputOrChangeItsValues) {
    BmsReceiver receiver(config(BmsFrameKind::PowerStatus)); ASSERT_TRUE(receiver.start_session(1, kStart));
    auto message = sample(BmsFrameKind::PowerStatus); BmsTxState tx{message.kind}; receiver.receive(encode(message, tx), kStart);
    advance(message, 20); EXPECT_EQ(receiver.receive(encode(message, tx), message.source_time_ns).quality[1], BmsFieldQuality::Usable);
    EXPECT_EQ(receiver.last_usable_rx_time_ns(1), kStart);
    advance(message, 40); std::get<BmsPowerStatus>(message.content).hv_bus_voltage_v = 391;
    EXPECT_EQ(receiver.receive(encode(message, tx), message.source_time_ns).quality[1], BmsFieldQuality::Invalid);
    EXPECT_FALSE(bms_power_is_ready(*receiver.current_sample(message.source_time_ns)));
    advance(message, 80); auto& status = std::get<BmsPowerStatus>(message.content); ++status.input_sequence; status.input_time_ns = message.source_time_ns;
    EXPECT_EQ(receiver.receive(encode(message, tx), message.source_time_ns).decision, ActuatorReceiveDecision::Timeout);
}
TEST(BmsReceiver, DegradedPermissionRequiresExplicitValidatedEnvelopeConfiguration) {
    auto message = sample(BmsFrameKind::DrivePermission); message.local_state = ActuatorLocalState::Degraded;
    const auto root = parent(); BmsTxState tx{message.kind}; const auto frame = encode(message, tx);
    BmsReceiver strict(config(message.kind)); ASSERT_TRUE(strict.start_session(1, kStart));
    EXPECT_EQ(strict.receive(frame, kStart, &root).decision, ActuatorReceiveDecision::ModeRejected);
    auto cfg = config(message.kind); cfg.allow_degraded_permission = true; BmsReceiver reviewed(cfg); ASSERT_TRUE(reviewed.start_session(1, kStart));
    EXPECT_EQ(reviewed.receive(frame, kStart, &root).quality[0], BmsFieldQuality::Usable);
}
TEST(BmsReceiver, ClockRollbackAndObservationTimeoutRequireExplicitNewEpoch) {
    BmsReceiver receiver(config(BmsFrameKind::BatteryState)); ASSERT_TRUE(receiver.start_session(1, kStart));
    auto message = sample(BmsFrameKind::BatteryState); BmsTxState tx{message.kind}; receiver.receive(encode(message, tx), kStart);
    EXPECT_EQ(receiver.poll(kStart+50*kMs), ActuatorReceiverHealth::Receiving);
    EXPECT_EQ(receiver.poll(kStart+49*kMs), ActuatorReceiverHealth::ClockError);
    EXPECT_FALSE(receiver.start_session(2, kStart+49*kMs)); ASSERT_TRUE(receiver.start_session(2, kStart+50*kMs));
    EXPECT_EQ(receiver.poll(kStart+350*kMs), ActuatorReceiverHealth::Timeout);
    message.epoch = 2; message.source_time_ns = kStart+350*kMs;
    auto& data = std::get<BmsBatteryState>(message.content); data.soc->source_time_ns = data.electrical->source_time_ns = data.temperature->source_time_ns = message.source_time_ns;
    EXPECT_EQ(receiver.receive(encode(message, tx), message.source_time_ns).decision, ActuatorReceiveDecision::Timeout);
}
TEST(BmsReceiver, ExpiredPhysicalInputsLeaveCanonicalUnknownViewAndRawHistory) {
    BmsReceiver receiver(config(BmsFrameKind::PowerStatus)); ASSERT_TRUE(receiver.start_session(1, kStart));
    auto message = sample(BmsFrameKind::PowerStatus); message.source_time_ns += 60*kMs;
    BmsTxState tx{message.kind}; receiver.receive(encode(message, tx), kStart+60*kMs);
    const auto view = receiver.current_sample(kStart+71*kMs); ASSERT_TRUE(view);
    EXPECT_EQ(view->quality[0], BmsFieldQuality::Stale); EXPECT_EQ(view->quality[1], BmsFieldQuality::Stale);
    const auto& unknown = std::get<BmsPowerStatus>(view->message.content);
    EXPECT_FALSE(unknown.state); EXPECT_EQ(unknown.input_time_ns, 0); EXPECT_EQ(unknown.input_sequence, 0);
    EXPECT_EQ(std::get<BmsPowerStatus>(receiver.last_accepted()->message.content).input_time_ns, kStart);
    BmsTxState other{message.kind}; EXPECT_TRUE(encode_bms_frame(view->message, other));
}

}  // namespace
