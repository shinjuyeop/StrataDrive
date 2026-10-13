#pragma once

#include "steering_receiver.hpp"
#include "brake_receiver.hpp"
#include "drive_receiver.hpp"

#include <charconv>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>

namespace stratadrive::fixture {
inline std::uint32_t positive_number(const std::string& text) {
    std::uint32_t value{};
    const auto result = std::from_chars(text.data(), text.data() + text.size(), value);
    if (result.ec != std::errc{} || result.ptr != text.data() + text.size() || value == 0) {
        throw std::invalid_argument("positive integer required");
    }
    return value;
}

inline can::SteeringFrameKind kind(const std::string& text) {
    if (text == "cmd") return can::SteeringFrameKind::Command;
    if (text == "actual") return can::SteeringFrameKind::Actual;
    throw std::invalid_argument("kind must be cmd or actual");
}

inline void await_start() {
    std::string line;
    if (!std::getline(std::cin, line) || line != "start") {
        throw std::runtime_error("trusted fixture start handshake required on stdin");
    }
}

inline const char* decision_name(can::ActuatorReceiveDecision decision, bool pressure = false, bool torque = false) {
    using can::SteeringReceiveDecision;
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
        case SteeringReceiveDecision::ValueOutOfRange:
            return torque ? "TORQUE_OUT_OF_RANGE" : pressure ? "PRESSURE_OUT_OF_RANGE" : "ANGLE_OUT_OF_RANGE";
    }
    return "UNKNOWN";
}
}  // namespace stratadrive::fixture
