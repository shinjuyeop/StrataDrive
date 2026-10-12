#include "steering_receiver.hpp"

#include "steering_angle_codec.hpp"

#include <cmath>
#include <limits>

namespace stratadrive::can {
namespace {
constexpr std::uint32_t kSequenceWindow = 10;
// 기존 100 ms 검출 budget에서 polling/dispatch/jitter 20 ms를 남기는 설정 상한.
constexpr std::uint64_t kMaxTimeoutNs = 80000000ULL;

bool valid_config(const SteeringReceiverConfig& config) {
    return steering_e2e_config(config.kind).has_value() &&
           std::isfinite(config.min_angle_rad) && std::isfinite(config.max_angle_rad) &&
           config.min_angle_rad < config.max_angle_rad &&
           config.min_angle_rad >= -kAngleWireMaxRad &&
           config.max_angle_rad <= kAngleWireMaxRad &&
           config.max_source_age_ns > 0 && config.max_source_age_ns < config.timeout_ns &&
           config.timeout_ns <= kMaxTimeoutNs;
}

bool allowed_mode(const SteeringMessage& message) {
    if (message.kind == SteeringFrameKind::Command) {
        return message.origin == SteeringOrigin::NormalPath &&
               (message.local_state == SteeringLocalState::Normal ||
                message.local_state == SteeringLocalState::Degraded);
    }
    // Actual의 유효 sample과 sender health는 별개다. Origin=0은 INIT에서만 허용한다.
    return message.origin != SteeringOrigin::NoAcceptedInput ||
           message.local_state == SteeringLocalState::Init;
}
}  // namespace

bool steering_sequence_progresses(std::optional<std::uint32_t> previous, std::uint32_t next) {
    return previous ? next > *previous && next - *previous <= kSequenceWindow : next < kSequenceWindow;
}

SteeringReceiver::SteeringReceiver(SteeringReceiverConfig config)
    : config_(config), e2e_{config.kind} {}

bool SteeringReceiver::start_session(std::uint32_t epoch, std::uint64_t monitoring_enable_ns) {
    if (!valid_config(config_) || epoch == 0 ||
        (epoch_ != 0 && (epoch <= epoch_ || monitoring_enable_ns < last_observed_ns_))) {
        return false;
    }
    epoch_ = epoch;
    monitoring_enable_ns_ = monitoring_enable_ns;
    last_observed_ns_ = monitoring_enable_ns;
    e2e::p05_check_init(e2e_.check);
    accepted_.reset();
    last_raw_rx_ns_.reset();
    health_ = SteeringReceiverHealth::Waiting;
    return true;
}

SteeringReceiverHealth SteeringReceiver::poll(std::uint64_t now_ns) {
    if (health_ == SteeringReceiverHealth::NotInitialized) {
        return health_;
    }
    if (now_ns < last_observed_ns_) {
        health_ = SteeringReceiverHealth::ClockError;
        return health_;
    }
    last_observed_ns_ = now_ns;
    if (health_ == SteeringReceiverHealth::ClockError || health_ == SteeringReceiverHealth::Timeout) {
        return health_;
    }
    const auto reference_ns = accepted_ ? accepted_->received_time_ns : monitoring_enable_ns_;
    if (now_ns - reference_ns >= config_.timeout_ns) {
        health_ = SteeringReceiverHealth::Timeout;
    }
    return health_;
}

SteeringReceiveResult SteeringReceiver::receive(const SteeringFrame& frame, std::uint64_t now_ns) {
    const auto status = poll(now_ns);  // late frame보다 먼저 timeout을 검사한다.
    if (status == SteeringReceiverHealth::NotInitialized) {
        return {SteeringReceiveDecision::NotInitialized, std::nullopt};
    }
    if (status == SteeringReceiverHealth::ClockError) {
        return {SteeringReceiveDecision::ClockError, std::nullopt};
    }
    last_raw_rx_ns_ = now_ns;
    if (status == SteeringReceiverHealth::Timeout) {
        return {SteeringReceiveDecision::Timeout, std::nullopt};
    }

    const auto e2e_return = check_steering_e2e(&frame, e2e_);
    if (e2e_return != e2e::P05Return::Ok) {
        return {SteeringReceiveDecision::MalformedEnvelope, std::nullopt};
    }
    const auto result = [this](SteeringReceiveDecision decision) {
        return SteeringReceiveResult{decision, e2e_.check.status};
    };
    if (!e2e::p05_is_ok(e2e_return, e2e_.check.status)) {
        return result(SteeringReceiveDecision::E2eRejected);
    }
    const auto message = decode_steering_frame(frame);
    if (!message) {
        return result(SteeringReceiveDecision::MalformedPayload);
    }
    if (message->epoch != epoch_) {
        return result(SteeringReceiveDecision::EpochMismatch);
    }
    if (message->source_time_ns < monitoring_enable_ns_) {
        return result(SteeringReceiveDecision::SourceBeforeSession);
    }
    if (message->source_time_ns > now_ns) {
        return result(SteeringReceiveDecision::SourceInFuture);
    }
    if (now_ns - message->source_time_ns > config_.max_source_age_ns) {
        return result(SteeringReceiveDecision::SourceStale);
    }
    const auto previous = accepted_ ? std::optional<std::uint32_t>{accepted_->message.sequence}
                                    : std::nullopt;
    if (!steering_sequence_progresses(previous, message->sequence)) {
        return result(SteeringReceiveDecision::SequenceRejected);
    }
    if (accepted_ && message->source_time_ns <= accepted_->message.source_time_ns) {
        return result(SteeringReceiveDecision::SourceNotIncreasing);
    }
    if (!message->angle_rad) {
        return result(SteeringReceiveDecision::Unavailable);
    }
    if (!allowed_mode(*message)) {
        return result(SteeringReceiveDecision::ModeRejected);
    }
    // raw * resolution의 double 반올림 오차만 허용한다. 다음 wire step은 허용하지 않는다.
    const auto lower = std::nextafter(config_.min_angle_rad, -std::numeric_limits<double>::infinity());
    const auto upper = std::nextafter(config_.max_angle_rad, std::numeric_limits<double>::infinity());
    if (*message->angle_rad < lower || *message->angle_rad > upper) {
        return result(SteeringReceiveDecision::AngleOutOfRange);
    }
    // 모든 조건을 통과할 때만 application의 수용 기록을 함께 갱신한다.
    accepted_ = SteeringAcceptedSample{*message, now_ns};
    health_ = SteeringReceiverHealth::Receiving;
    return result(SteeringReceiveDecision::Accepted);
}

std::optional<SteeringMessage> SteeringReceiver::current_sample(std::uint64_t now_ns) {
    if (poll(now_ns) != SteeringReceiverHealth::Receiving || !accepted_ ||
        now_ns - accepted_->message.source_time_ns > config_.max_source_age_ns) {
        return std::nullopt;
    }
    return accepted_->message;
}

}  // namespace stratadrive::can
