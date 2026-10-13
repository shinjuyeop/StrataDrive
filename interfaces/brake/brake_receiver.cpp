#include "brake_receiver.hpp"

#include "brake_pressure_codec.hpp"

#include <cmath>

namespace stratadrive::can {
BrakeReceiver::BrakeReceiver(BrakeReceiverConfig config)
    : config_(config), e2e_{config.kind}, state_({config.max_source_age_ns, config.timeout_ns}) {}

bool BrakeReceiver::start_session(std::uint32_t epoch, std::uint64_t monitoring_enable_ns) {
    if (!brake_e2e_config(config_.kind) || !std::isfinite(config_.min_pressure_pa) ||
        !std::isfinite(config_.max_pressure_pa) || config_.min_pressure_pa < 0 ||
        config_.min_pressure_pa >= config_.max_pressure_pa || config_.max_pressure_pa > kBrakePressureWireMaxPa ||
        !state_.start_session(epoch, monitoring_enable_ns)) {
        return false;
    }
    e2e::p05_check_init(e2e_.check);
    accepted_.reset();
    return true;
}

BrakeReceiveResult BrakeReceiver::receive(const BrakeFrame& frame, std::uint64_t now_ns) {
    if (const auto rejected = state_.begin_receive(now_ns)) return {*rejected, std::nullopt};
    const auto e2e_return = check_brake_e2e(&frame, e2e_);
    if (e2e_return != e2e::P05Return::Ok) return {BrakeReceiveDecision::MalformedEnvelope, std::nullopt};
    const auto result = [this](BrakeReceiveDecision decision) {
        return BrakeReceiveResult{decision, e2e_.check.status};
    };
    if (!e2e::p05_is_ok(e2e_return, e2e_.check.status)) return result(BrakeReceiveDecision::E2eRejected);
    const auto message = decode_brake_frame(frame);
    if (!message) return result(BrakeReceiveDecision::MalformedPayload);
    if (const auto rejected = state_.check_metadata(*message, now_ns)) return result(*rejected);
    if (!message->pressure_pa) return result(BrakeReceiveDecision::Unavailable);
    if (!actuator_mode_allowed(*message, message->kind == BrakeFrameKind::Command)) {
        return result(BrakeReceiveDecision::ModeRejected);
    }
    if (!actuator_value_in_range(*message->pressure_pa, {config_.min_pressure_pa, config_.max_pressure_pa})) {
        return result(BrakeReceiveDecision::PressureOutOfRange);
    }
    // domain 검사까지 모두 통과해야 application cursor/valid RX/snapshot을 함께 갱신한다.
    state_.commit(*message, now_ns);
    accepted_ = BrakeAcceptedSample{*message, now_ns};
    return result(BrakeReceiveDecision::Accepted);
}

std::optional<BrakeMessage> BrakeReceiver::current_sample(std::uint64_t now_ns) {
    if (!state_.has_current_sample(now_ns) || !accepted_) return std::nullopt;
    return accepted_->message;
}
}  // namespace stratadrive::can
