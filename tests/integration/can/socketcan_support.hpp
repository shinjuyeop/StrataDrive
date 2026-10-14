#pragma once

#include "steering_receiver.hpp"
#include "steering_actuator.hpp"
#include "brake_actuator.hpp"
#include "brake_receiver.hpp"
#include "drive_receiver.hpp"
#include "bms_receiver.hpp"
#include "bounded_rx_queue.hpp"
#include "socketcan_endpoint.hpp"

#include <charconv>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <sstream>
#include <vector>

namespace stratadrive::fixture {
struct TrustedSession { std::uint32_t epoch; std::uint64_t enable_ns; };
inline vecu::SteeringActuatorConfig steering_model_config() {
    return {-0.5, 0.5, -0.3, 0.3, 0, 1, 50000000}; // SIL fixture, not OEM calibration
}
inline vecu::BrakeActuatorConfig brake_model_config() {
    return {2000000, 1500000, 0, 5000000, 10000000, 1000000, 50000000};
}
class RxPump {
public:
    RxPump(socketcan::Endpoint& endpoint, std::string mode) : endpoint_(endpoint), mode_(std::move(mode)) {}
    bool start_session(TrustedSession session) {
        if (!queue_.start_session(session.epoch)) return false;
        enable_ns_ = session.enable_ns; reported_ = false; return true;
    }
    template <typename Receiver> void collect(Receiver& receiver) {
        const auto elapsed = socketcan::monotonic_time_ns() - enable_ns_;
        // Fault fixture suspends ingress OR dispatch, never the timeout monitor.
        if (mode_ == "kernel-overflow" && elapsed >= 10000000 && elapsed < 45000000) return;
        for (unsigned int count = 0; count < 8; ++count) {
            const auto received = endpoint_.receive(); if (!received) break;
            if (!queue_.push(received->frame, received->dropped_frames)) {
                const auto now = socketcan::monotonic_time_ns();
                receiver.mark_continuity_lost(now);
                if (!reported_) {
                    std::cout << "QUEUE_FAULT kind=" << (queue_.fault() == can::RxQueueFault::KernelDrop ? "kernel" : "application")
                              << " at_ns=" << now << " drops=" << received->dropped_frames
                              << " usable=" << receiver.current_sample(now).has_value() << '\n';
                    reported_ = true;
                } else std::cout << "QUEUE_DISCARD at_ns=" << now << '\n';
            }
        }
    }
    std::optional<socketcan::Frame> pop() {
        const auto elapsed = socketcan::monotonic_time_ns() - enable_ns_;
        if (mode_ == "app-overflow" && elapsed >= 10000000 && elapsed < 45000000) return std::nullopt;
        return queue_.pop();
    }
private:
    socketcan::Endpoint& endpoint_;
    const std::string mode_;
    can::BoundedRxQueue<socketcan::Frame, 32> queue_;
    std::uint64_t enable_ns_{0};
    bool reported_{false};
};

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

inline std::optional<can::BmsFrameKind> bms_kind(const std::string& text) {
    if (text == "bms-request") return can::BmsFrameKind::PowerRequest;
    if (text == "bms-power") return can::BmsFrameKind::PowerStatus;
    if (text == "bms-limits") return can::BmsFrameKind::PowerLimits;
    if (text == "bms-battery") return can::BmsFrameKind::BatteryState;
    if (text == "drive-limits") return can::BmsFrameKind::DriveBatteryLimits;
    if (text == "drive-permission") return can::BmsFrameKind::DrivePermission;
    return std::nullopt;
}

inline constexpr std::uint64_t kMs = 1000000ULL;
struct BmsSessionPlan {
    std::uint64_t enable_ns{0};
    std::uint64_t rejoin_ns{0};
    std::vector<can::BmsParentContext> parents;
    const can::BmsParentContext* parent(std::uint32_t epoch, std::uint32_t sequence) const {
        for (const auto& item : parents) {
            if (item.epoch == epoch && item.sequence == sequence) return &item;
        }
        return nullptr;
    }
};

// Harness-provisioned identities/deadlines, independent of CAN. CausalSequence
// only looks up this trusted allowlist; it cannot create or renew a parent.
inline BmsSessionPlan await_bms_start() {
    std::string line;
    if (!std::getline(std::cin, line)) throw std::runtime_error("EV trusted plan missing");
    std::istringstream input(line);
    std::string command;
    std::size_t count = 0;
    BmsSessionPlan plan;
    if (!(input >> command >> plan.enable_ns >> plan.rejoin_ns >> count) || command != "start" ||
        plan.enable_ns == 0 || count > 16 || (plan.rejoin_ns && plan.rejoin_ns <= plan.enable_ns)) {
        throw std::runtime_error("invalid EV trusted start plan");
    }
    for (std::size_t index = 0; index < count; ++index) {
        can::BmsParentContext item{};
        if (!(input >> item.epoch >> item.sequence >> item.source_time_ns >> item.expires_at_ns) ||
            item.epoch == 0 || item.source_time_ns < plan.enable_ns || item.expires_at_ns <= item.source_time_ns ||
            plan.parent(item.epoch, item.sequence)) throw std::runtime_error("invalid EV parent fixture");
        plan.parents.push_back(item);
    }
    if (input >> command) throw std::runtime_error("unexpected EV plan field");
    return plan;
}

inline unsigned int bms_period_ms(can::BmsFrameKind kind) {
    if (kind == can::BmsFrameKind::BatteryState) return 100;
    if (kind == can::BmsFrameKind::PowerStatus || kind == can::BmsFrameKind::DrivePermission) return 10;
    return 20;
}

// Synthetic data only; no battery/controller/contactor response model runs here.
struct BmsSampleIdentity { std::uint32_t epoch; std::uint32_t sequence; std::uint64_t source_ns; };
inline can::BmsMessage bms_message(can::BmsFrameKind kind, BmsSampleIdentity identity,
                                  const can::BmsParentContext* parent) {
    using namespace can;
    const auto epoch = identity.epoch;
    const auto sequence = identity.sequence;
    const auto source_ns = identity.source_ns;
    BmsMessage message;
    message.kind = kind; message.epoch = epoch; message.sequence = sequence;
    message.source_time_ns = source_ns;
    message.local_state = ActuatorLocalState::Normal; message.origin = ActuatorOrigin::NormalPath;
    message.causal_sequence = sequence;
    switch (kind) {
    case BmsFrameKind::PowerRequest:
        message.local_state = ActuatorLocalState::Init;
        message.causal_sequence = parent ? parent->sequence : 900;
        message.content = BmsPowerRequest{BmsPowerAction::Enable,
            parent && parent->expires_at_ns > source_ns ? parent->expires_at_ns : source_ns + 60*kMs,
            parent ? parent->source_time_ns : source_ns};
        break;
    case BmsFrameKind::DrivePermission:
        message.causal_sequence = parent ? parent->sequence : 900;
        message.content = BmsDriveGrant{BmsDrivePermission::AllowNormal, sequence, source_ns,
            source_ns, parent && parent->expires_at_ns > source_ns ? parent->expires_at_ns : source_ns + 60*kMs};
        break;
    case BmsFrameKind::PowerLimits:
    case BmsFrameKind::DriveBatteryLimits:
        message.content = BmsPowerLimits{120000, 200000, BmsLimitReason::Nominal, BmsLimitReason::Nominal, source_ns};
        break;
    case BmsFrameKind::PowerStatus:
        message.content = BmsPowerStatus{BmsPowerState::HvReady, true, true, false, 7, 31,
            400, source_ns, source_ns, sequence};
        break;
    case BmsFrameKind::BatteryState:
        message.content = BmsBatteryState{BmsSocSample{0.75, source_ns},
            BmsElectricalSample{400, -12.3, source_ns}, BmsTemperatureSample{25, source_ns}};
        break;
    }
    return message;
}

inline void clear_bms_content(can::BmsMessage& message) {
    using namespace can;
    switch (message.kind) {
    case BmsFrameKind::PowerRequest: message.content = BmsPowerRequest{}; break;
    case BmsFrameKind::PowerStatus: message.content = BmsPowerStatus{}; break;
    case BmsFrameKind::PowerLimits:
    case BmsFrameKind::DriveBatteryLimits: message.content = BmsPowerLimits{}; break;
    case BmsFrameKind::BatteryState: message.content = BmsBatteryState{}; break;
    case BmsFrameKind::DrivePermission: message.content = BmsDriveGrant{}; break;
    }
}

inline const char* quality_name(can::BmsFieldQuality quality) {
    switch (quality) {
    case can::BmsFieldQuality::NotApplicable: return "NA";
    case can::BmsFieldQuality::Unavailable: return "UNAVAILABLE";
    case can::BmsFieldQuality::Usable: return "USABLE";
    case can::BmsFieldQuality::Stale: return "STALE";
    case can::BmsFieldQuality::Invalid: return "INVALID";
    }
    return "UNKNOWN";
}

inline const char* issue_name(can::BmsReceiveIssue issue) {
    switch (issue) {
    case can::BmsReceiveIssue::None: return "NONE";
    case can::BmsReceiveIssue::Expired: return "EXPIRED";
    case can::BmsReceiveIssue::ParentMissing: return "PARENT_MISSING";
    case can::BmsReceiveIssue::ParentMismatch: return "PARENT_MISMATCH";
    case can::BmsReceiveIssue::ParentRollback: return "PARENT_ROLLBACK";
    }
    return "UNKNOWN";
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
        case SteeringReceiveDecision::ContinuityLost: return "CONTINUITY_LOST";
    }
    return "UNKNOWN";
}
}  // namespace stratadrive::fixture
