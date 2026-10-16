#pragma once

#include "steering_receiver.hpp"
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>

namespace stratadrive::demo {
using namespace stratadrive::can;
inline constexpr std::uint64_t kStart=1000000000ULL, kMs=1000000ULL;

inline double parse_angle(const std::string& input) {
    std::size_t consumed = 0;
    const double angle = std::stod(input, &consumed);
    if (consumed != input.size()) throw std::invalid_argument("rad 숫자만 입력하세요.");
    return angle;
}

inline double parse_pressure(const std::string& input) {
    std::size_t consumed = 0;
    const double value = std::stod(input, &consumed);
    if (consumed != input.size()) throw std::invalid_argument("Pa 숫자만 입력하세요.");
    return value;
}

inline const char* decision_name(ActuatorReceiveDecision decision, bool pressure = false) {
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
        case SteeringReceiveDecision::ValueOutOfRange: return pressure ? "PRESSURE_OUT_OF_RANGE" : "ANGLE_OUT_OF_RANGE";
        case SteeringReceiveDecision::ContinuityLost: return "CONTINUITY_LOST";
    }
    return "UNKNOWN";
}

inline SteeringFrame encode(const SteeringMessage& message, SteeringTxState& tx) {
    const auto frame = encode_steering_frame(message, tx);
    if (!frame) {
        throw std::runtime_error("fixture encode 실패");
    }
    return *frame;
}

template <typename Frame, typename Receiver>
void show_receive(const char* label, const Frame& frame, Receiver& receiver,
          std::uint64_t now_ns, ActuatorReceiveDecision expected, bool pressure = false) {
    const auto result = receiver.receive(frame, now_ns);
    if (result.decision != expected) {
        throw std::runtime_error("예상한 receiver 결과와 다름");
    }
    std::cout << label << " -> " << decision_name(result.decision, pressure);
    if (result.e2e_status) {
        std::cout << " (E2E status=" << static_cast<unsigned int>(*result.e2e_status) << ')';
    }
    if (receiver.last_accepted()) {
        std::cout << " last-valid RX=" << receiver.last_accepted()->received_time_ns;
    }
    std::cout << '\n';
}

} // namespace stratadrive::demo
