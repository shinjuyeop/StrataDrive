#pragma once

#include "actuator_receiver_state.hpp"
#include "drive_frame_codec.hpp"

namespace stratadrive::can {
struct DriveReceiverConfig {
    DriveFrameKind kind;
    ActuatorValueRange torque_nm;
    double max_wheel_speed_rad_s;
    double max_regen_torque_nm;
    std::uint64_t max_source_age_ns{30000000ULL};
    std::uint64_t timeout_ns{80000000ULL};
    std::uint64_t max_feedback_age_ns{30000000ULL};
    // Explicit EV dependency budget; nullopt keeps the existing source/input 30 ms policy.
    std::optional<std::uint64_t> max_capability_input_age_ns{};
};
enum class DriveFeedbackQuality { Unavailable, Usable, Stale, Invalid };
struct DriveReceiveResult {
    ActuatorReceiveDecision decision;
    std::optional<e2e::P05Status> e2e_status;
    DriveFeedbackQuality wheel_speed{DriveFeedbackQuality::Unavailable};
    DriveFeedbackQuality regen_capability{DriveFeedbackQuality::Unavailable};
};
struct DriveAcceptedSample { DriveMessage message; std::uint64_t received_time_ns; };

// Torque stream은 critical이다. 보조 speed/capability의 stale/invalid는 별도로 무효화한다.
class DriveReceiver {
public:
    explicit DriveReceiver(const DriveReceiverConfig& config);
    bool start_session(std::uint32_t epoch, std::uint64_t monitoring_enable_ns);
    void mark_continuity_lost(std::uint64_t now_ns) { state_.mark_continuity_lost(now_ns); }
    DriveReceiveResult receive(const DriveFrame& frame, std::uint64_t now_ns);
    ActuatorReceiverHealth poll(std::uint64_t now_ns) { return state_.poll(now_ns); }
    // Torque가 fresh일 때만 반환. 각 optional feedback도 원천 age/quality 검사를 통과해야 존재한다.
    std::optional<DriveMessage> current_sample(std::uint64_t now_ns);
    ActuatorReceiverHealth health() const { return state_.health(); }
    // Raw accepted wire snapshot은 진단용이며 제어 입력이 아니다.
    const std::optional<DriveAcceptedSample>& last_accepted() const { return accepted_; }
    const std::optional<std::uint64_t>& last_raw_rx_time_ns() const { return state_.last_raw_rx_time_ns(); }

private:
    std::uint64_t capability_input_age_ns() const {
        return config_.max_capability_input_age_ns.value_or(config_.max_feedback_age_ns);
    }
    DriveFeedbackQuality check_wheel_speed(const DriveMessage& message, std::uint64_t now_ns) const;
    DriveFeedbackQuality check_capability(const DriveMessage& message, std::uint64_t now_ns) const;
    const DriveReceiverConfig config_;
    DriveRxState e2e_;
    ActuatorReceiverState state_;
    std::uint64_t session_start_ns_{0};
    std::optional<DriveAcceptedSample> accepted_;
    std::optional<DriveMessage> usable_;
    std::optional<DriveWheelSpeed> wheel_cursor_;
    std::optional<DriveRegenCapability> capability_cursor_;
    DriveRegenLimitReason capability_reason_{DriveRegenLimitReason::InputsInvalid};
};
}  // namespace stratadrive::can
