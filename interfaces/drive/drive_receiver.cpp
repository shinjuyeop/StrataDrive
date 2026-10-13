#include "drive_receiver.hpp"

#include "drive_value_codec.hpp"

#include <cmath>

namespace stratadrive::can {
DriveReceiver::DriveReceiver(const DriveReceiverConfig& config)
    : config_(config), e2e_{config.kind}, state_({config.max_source_age_ns, config.timeout_ns}) {}

bool DriveReceiver::start_session(std::uint32_t epoch, std::uint64_t monitoring_enable_ns) {
    if (!drive_e2e_config(config_.kind) || !std::isfinite(config_.torque_nm.minimum) ||
        !std::isfinite(config_.torque_nm.maximum) || config_.torque_nm.minimum >= 0 ||
        config_.torque_nm.maximum <= 0 || config_.torque_nm.minimum < -kDriveTorqueWireMaxNm ||
        config_.torque_nm.maximum > kDriveTorqueWireMaxNm ||
        !std::isfinite(config_.max_wheel_speed_rad_s) || config_.max_wheel_speed_rad_s <= 0 ||
        config_.max_wheel_speed_rad_s > kDriveWheelSpeedWireMaxRadS ||
        !std::isfinite(config_.max_regen_torque_nm) || config_.max_regen_torque_nm <= 0 ||
        config_.max_regen_torque_nm > -config_.torque_nm.minimum ||
        config_.max_feedback_age_ns == 0 || config_.max_feedback_age_ns > config_.max_source_age_ns ||
        !state_.start_session(epoch, monitoring_enable_ns)) return false;
    session_start_ns_ = monitoring_enable_ns;
    e2e::p05_check_init(e2e_.check);
    accepted_.reset();
    usable_.reset();
    wheel_cursor_.reset();
    capability_cursor_.reset();
    capability_reason_ = DriveRegenLimitReason::InputsInvalid;
    return true;
}

DriveFeedbackQuality DriveReceiver::check_wheel_speed(
    const DriveMessage& message, std::uint64_t now_ns) const {
    if (!message.wheel_speed) return DriveFeedbackQuality::Unavailable;
    const auto& speed = *message.wheel_speed;
    if (!actuator_value_in_range(speed.value_rad_s, {0, config_.max_wheel_speed_rad_s}) ||
        speed.source_time_ns < session_start_ns_ || speed.source_time_ns > message.source_time_ns ||
        speed.source_time_ns > now_ns ||
        (wheel_cursor_ && (speed.source_time_ns < wheel_cursor_->source_time_ns ||
         (speed.source_time_ns == wheel_cursor_->source_time_ns &&
          speed.value_rad_s != wheel_cursor_->value_rad_s)))) return DriveFeedbackQuality::Invalid;
    if (now_ns - speed.source_time_ns > config_.max_feedback_age_ns) return DriveFeedbackQuality::Stale;
    return DriveFeedbackQuality::Usable;
}

DriveFeedbackQuality DriveReceiver::check_capability(
    const DriveMessage& message, std::uint64_t now_ns) const {
    if (!message.regen_capability) return DriveFeedbackQuality::Unavailable;
    const auto& cap = *message.regen_capability;
    if (!message.wheel_speed ||
        !actuator_value_in_range(cap.torque_limit_nm, {0, config_.max_regen_torque_nm}) ||
        cap.input_time_ns < session_start_ns_ || cap.input_time_ns > cap.source_time_ns ||
        cap.source_time_ns > message.source_time_ns || cap.source_time_ns > now_ns ||
        (capability_cursor_ && (cap.source_time_ns < capability_cursor_->source_time_ns ||
         cap.input_time_ns < capability_cursor_->input_time_ns ||
         (cap.source_time_ns == capability_cursor_->source_time_ns &&
          (cap.torque_limit_nm != capability_cursor_->torque_limit_nm ||
           cap.input_time_ns != capability_cursor_->input_time_ns ||
           message.regen_limit_reason != capability_reason_))))) return DriveFeedbackQuality::Invalid;
    if (now_ns - cap.source_time_ns > config_.max_feedback_age_ns ||
        now_ns - cap.input_time_ns > config_.max_feedback_age_ns) return DriveFeedbackQuality::Stale;
    return DriveFeedbackQuality::Usable;
}

DriveReceiveResult DriveReceiver::receive(const DriveFrame& frame, std::uint64_t now_ns) {
    if (const auto rejected = state_.begin_receive(now_ns)) return {*rejected, std::nullopt};
    const auto e2e_return = check_drive_e2e(&frame, e2e_);
    if (e2e_return != e2e::P05Return::Ok) return {ActuatorReceiveDecision::MalformedEnvelope, std::nullopt};
    const auto result = [this](ActuatorReceiveDecision decision) {
        return DriveReceiveResult{decision, e2e_.check.status};
    };
    if (!e2e::p05_is_ok(e2e_return, e2e_.check.status)) return result(ActuatorReceiveDecision::E2eRejected);
    const auto message = decode_drive_frame(frame);
    if (!message) return result(ActuatorReceiveDecision::MalformedPayload);
    if (const auto rejected = state_.check_metadata(*message, now_ns)) return result(*rejected);
    if (!message->torque_nm) return result(ActuatorReceiveDecision::Unavailable);
    if (!actuator_mode_allowed(*message, message->kind == DriveFrameKind::Command)) {
        return result(ActuatorReceiveDecision::ModeRejected);
    }
    if (!actuator_value_in_range(*message->torque_nm, config_.torque_nm)) {
        return result(ActuatorReceiveDecision::TorqueOutOfRange);
    }
    auto accepted_result = result(ActuatorReceiveDecision::Accepted);
    auto usable = *message;
    if (message->kind == DriveFrameKind::Actual) {
        accepted_result.wheel_speed = check_wheel_speed(*message, now_ns);
        if (accepted_result.wheel_speed == DriveFeedbackQuality::Usable) {
            wheel_cursor_ = message->wheel_speed;
        } else {
            usable.wheel_speed.reset();
        }
        accepted_result.regen_capability = check_capability(usable, now_ns);
        if (accepted_result.regen_capability == DriveFeedbackQuality::Usable) {
            capability_cursor_ = message->regen_capability;
            capability_reason_ = message->regen_limit_reason;
        } else {
            usable.regen_capability.reset();
            usable.regen_limit_reason = DriveRegenLimitReason::InputsInvalid;
        }
    }
    state_.commit(*message, now_ns);
    accepted_ = DriveAcceptedSample{*message, now_ns};
    usable_ = usable;
    return accepted_result;
}

std::optional<DriveMessage> DriveReceiver::current_sample(std::uint64_t now_ns) {
    if (!state_.has_current_sample(now_ns) || !usable_) return std::nullopt;
    auto current = *usable_;
    if (current.wheel_speed && now_ns - current.wheel_speed->source_time_ns > config_.max_feedback_age_ns) {
        current.wheel_speed.reset();
    }
    if (current.regen_capability && (!current.wheel_speed ||
        now_ns - current.regen_capability->source_time_ns > config_.max_feedback_age_ns ||
        now_ns - current.regen_capability->input_time_ns > config_.max_feedback_age_ns)) {
        current.regen_capability.reset();
        current.regen_limit_reason = DriveRegenLimitReason::InputsInvalid;
    }
    return current;
}
}  // namespace stratadrive::can
