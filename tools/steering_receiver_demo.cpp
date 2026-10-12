#include "steering_receiver.hpp"

#include <exception>
#include <iostream>
#include <stdexcept>

namespace {
using namespace stratadrive::can;
constexpr std::uint64_t kStart = 1000000000ULL;
constexpr std::uint64_t kMs = 1000000ULL;

const char* decision_name(SteeringReceiveDecision decision) {
    switch (decision) {
        case SteeringReceiveDecision::Accepted: return "ACCEPTED";
        case SteeringReceiveDecision::NotInitialized: return "NOT_INITIALIZED";
        case SteeringReceiveDecision::ClockError: return "CLOCK_ERROR";
        case SteeringReceiveDecision::Timeout: return "TIMEOUT";
        case SteeringReceiveDecision::MalformedEnvelope: return "MALFORMED_ENVELOPE";
        case SteeringReceiveDecision::E2eRejected: return "E2E_REJECTED";
        case SteeringReceiveDecision::MalformedPayload: return "MALFORMED_PAYLOAD";
        case SteeringReceiveDecision::EpochMismatch: return "EPOCH_MISMATCH";
        case SteeringReceiveDecision::SourceBeforeSession: return "SOURCE_BEFORE_SESSION";
        case SteeringReceiveDecision::SourceInFuture: return "SOURCE_IN_FUTURE";
        case SteeringReceiveDecision::SourceStale: return "SOURCE_STALE";
        case SteeringReceiveDecision::SequenceRejected: return "SEQUENCE_REJECTED";
        case SteeringReceiveDecision::SourceNotIncreasing: return "SOURCE_NOT_INCREASING";
        case SteeringReceiveDecision::Unavailable: return "UNAVAILABLE";
        case SteeringReceiveDecision::ModeRejected: return "MODE_REJECTED";
        case SteeringReceiveDecision::AngleOutOfRange: return "ANGLE_OUT_OF_RANGE";
    }
    return "UNKNOWN";
}

SteeringFrame encode(const SteeringMessage& message, SteeringTxState& tx) {
    const auto frame = encode_steering_frame(message, tx);
    if (!frame) {
        throw std::runtime_error("fixture encode 실패");
    }
    return *frame;
}

void show(const char* label, const SteeringFrame& frame, SteeringReceiver& receiver,
          std::uint64_t now_ns, SteeringReceiveDecision expected) {
    const auto result = receiver.receive(frame, now_ns);
    if (result.decision != expected) {
        throw std::runtime_error("예상한 receiver 결과와 다름");
    }
    std::cout << label << " -> " << decision_name(result.decision);
    if (result.e2e_status) {
        std::cout << " (E2E status=" << static_cast<unsigned int>(*result.e2e_status) << ')';
    }
    if (receiver.last_accepted()) {
        std::cout << " last-valid RX=" << receiver.last_accepted()->received_time_ns;
    }
    std::cout << '\n';
}
}  // namespace

int main() {
    try {
        // 수동 timestamp를 쓰는 Host fixture. +/-0.5 rad는 시험용 설정이다.
        SteeringReceiver receiver({SteeringFrameKind::Command, -0.5, 0.5});
        if (!receiver.start_session(1, kStart)) {
            throw std::runtime_error("session 설정 실패");
        }
        SteeringTxState tx{SteeringFrameKind::Command};
        SteeringMessage message;
        message.angle_rad = 0.2;
        message.epoch = 1;
        message.source_time_ns = kStart;
        message.local_state = SteeringLocalState::Normal;
        message.origin = SteeringOrigin::NormalPath;

        std::cout << "Host Receiver fixture (수동 시계, socket/actuator 실행 아님)\n";
        const auto first = encode(message, tx);
        show("정상 첫 frame", first, receiver, kStart, SteeringReceiveDecision::Accepted);
        show("같은 frame 반복", first, receiver, kStart + 5 * kMs, SteeringReceiveDecision::E2eRejected);
        show("cached sample 재포장", encode(message, tx), receiver, kStart + 10 * kMs,
             SteeringReceiveDecision::SequenceRejected);
        message.sequence = 1;
        message.source_time_ns = kStart + kMs;
        show("오래된 sample", encode(message, tx), receiver, kStart + 40 * kMs,
             SteeringReceiveDecision::SourceStale);
        message.source_time_ns = kStart + 50 * kMs;
        show("새 정상 sample", encode(message, tx), receiver, message.source_time_ns,
             SteeringReceiveDecision::Accepted);
        if (receiver.current_sample(kStart + 80 * kMs + 1)) {
            throw std::runtime_error("source age가 끝난 sample이 사용 가능함");
        }
        std::cout << "source age 30 ms 초과 -> current sample 없음\n";
        message.sequence = 2;
        message.source_time_ns = kStart + 90 * kMs;
        message.angle_rad.reset();
        show("invalid sample", encode(message, tx), receiver, message.source_time_ns,
             SteeringReceiveDecision::Unavailable);
        message.angle_rad = 0.2;
        message.epoch = 2;
        message.source_time_ns = kStart + 100 * kMs;
        show("다른 Epoch", encode(message, tx), receiver, message.source_time_ns,
             SteeringReceiveDecision::EpochMismatch);
        if (receiver.poll(kStart + 130 * kMs) != SteeringReceiverHealth::Timeout) {
            throw std::runtime_error("마지막 valid RX +80 ms에서 timeout이 검출되지 않음");
        }
        std::cout << "last-valid RX +80 ms -> TIMEOUT\n";
        message.epoch = 1;
        message.source_time_ns = kStart + 140 * kMs;
        show("timeout 뒤 정상 frame", encode(message, tx), receiver, message.source_time_ns,
             SteeringReceiveDecision::Timeout);
        if (!receiver.start_session(2, kStart + 150 * kMs)) {
            throw std::runtime_error("새 Epoch의 explicit INIT 실패");
        }
        SteeringTxState restarted{SteeringFrameKind::Command};
        message.epoch = 2;
        message.sequence = 0;
        message.source_time_ns = kStart + 150 * kMs;
        show("새 Epoch + explicit INIT", encode(message, restarted), receiver, message.source_time_ns,
             SteeringReceiveDecision::Accepted);
    } catch (const std::exception& error) {
        std::cerr << "REJECT: " << error.what() << '\n';
        return 1;
    }
    return 0;
}
