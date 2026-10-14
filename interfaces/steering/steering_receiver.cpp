#include "steering_receiver.hpp"

#include "steering_angle_codec.hpp"

#include <cmath>

namespace stratadrive::can {
namespace {
bool valid_config(const SteeringReceiverConfig& config) {
    return steering_e2e_config(config.kind).has_value() &&
           std::isfinite(config.min_angle_rad) && std::isfinite(config.max_angle_rad) &&
           config.min_angle_rad < config.max_angle_rad &&
           config.min_angle_rad >= -kAngleWireMaxRad &&
           config.max_angle_rad <= kAngleWireMaxRad;
}
}  // namespace

bool steering_sequence_progresses(std::optional<std::uint32_t> previous, std::uint32_t next) {
    return actuator_sequence_progresses(previous, next);
}

SteeringReceiver::SteeringReceiver(SteeringReceiverConfig config)
    : config_(config), e2e_{config.kind}, state_({config.max_source_age_ns, config.timeout_ns}) {}

bool SteeringReceiver::start_session(std::uint32_t epoch, std::uint64_t monitoring_enable_ns) {
    if (!valid_config(config_) || !state_.start_session(epoch, monitoring_enable_ns)) {
        return false;
    }
    e2e::p05_check_init(e2e_.check);
    accepted_.reset();
    return true;
}

SteeringReceiveResult SteeringReceiver::receive(const SteeringFrame& frame, std::uint64_t now_ns) {
    if (const auto rejected = state_.begin_receive(now_ns)) return {*rejected, std::nullopt};

    const auto previous_e2e = e2e_.check;
    const auto e2e_return = check_steering_e2e(&frame, e2e_);
    if (e2e_return != e2e::P05Return::Ok) {
        return {SteeringReceiveDecision::MalformedEnvelope, std::nullopt};
    }
    const auto message = decode_steering_frame(frame);
    if (message && message->kind == e2e_.kind && message->epoch != state_.epoch()) {
        const auto status = e2e_.check.status;
        e2e_.check = previous_e2e;
        return {SteeringReceiveDecision::EpochMismatch, status};
    }
    const auto result = [this](SteeringReceiveDecision decision) {
        return SteeringReceiveResult{decision, e2e_.check.status};
    };
    if (!e2e::p05_is_ok(e2e_return, e2e_.check.status)) {
        return result(SteeringReceiveDecision::E2eRejected);
    }
    if (!message) {
        return result(SteeringReceiveDecision::MalformedPayload);
    }
    const ActuatorMetadata metadata{message->sequence, message->epoch, message->source_time_ns,
                                    message->causal_sequence, message->local_state, message->origin};
    if (const auto rejected = state_.check_metadata(metadata, now_ns)) return result(*rejected);
    if (!message->angle_rad) {
        return result(SteeringReceiveDecision::Unavailable);
    }
    if (!actuator_mode_allowed(metadata, message->kind == SteeringFrameKind::Command)) {
        return result(SteeringReceiveDecision::ModeRejected);
    }
    if (!actuator_value_in_range(*message->angle_rad, {config_.min_angle_rad, config_.max_angle_rad})) {
        return result(SteeringReceiveDecision::AngleOutOfRange);
    }
    // 모든 조건을 통과할 때만 application의 수용 기록을 함께 갱신한다.
    state_.commit(metadata, now_ns);
    accepted_ = SteeringAcceptedSample{*message, now_ns};
    return result(SteeringReceiveDecision::Accepted);
}

std::optional<SteeringMessage> SteeringReceiver::current_sample(std::uint64_t now_ns) {
    if (!state_.has_current_sample(now_ns) || !accepted_) {
        return std::nullopt;
    }
    return accepted_->message;
}

}  // namespace stratadrive::can
