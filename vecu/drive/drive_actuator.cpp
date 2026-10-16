#include "drive_actuator.hpp"

#include "drive_value_codec.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace stratadrive::vecu {
DriveActuator::DriveActuator(DriveActuatorConfig config)
    : config_(config), receiver_({can::DriveFrameKind::Command, config.command_nm,
          can::kDriveWheelSpeedWireMaxRadS, -config.command_nm.minimum,
          config.max_source_age_ns, config.timeout_ns, std::min<std::uint64_t>(30000000, config.max_source_age_ns)}),
      response_(config.response) {
    if (!std::isfinite(config.command_nm.minimum) || !std::isfinite(config.command_nm.maximum) ||
        config.command_nm.minimum >= 0 || config.command_nm.maximum <= 0 ||
        config.command_nm.minimum < -can::kDriveTorqueWireMaxNm ||
        config.command_nm.maximum > can::kDriveTorqueWireMaxNm ||
        config.response.minimum_nm < config.command_nm.minimum ||
        config.response.maximum_nm > config.command_nm.maximum ||
        config.period_ns < 1000000 || config.period_ns > 100000000 ||
        config.max_tick_gap_ns < config.period_ns || config.max_tick_gap_ns > 1000000000 ||
        config.response.delay_ns > config.period_ns * 100 || config.max_source_age_ns == 0 ||
        config.max_source_age_ns >= config.timeout_ns || config.timeout_ns > 100000000) {
        throw std::invalid_argument("DriveActuator configuration");
    }
}
bool DriveActuator::start_session(std::uint32_t epoch, std::uint64_t enable_ns) {
    if (epoch_ != 0 && enable_ns < last_tick_ns_) return false;
    if (!receiver_.start_session(epoch, enable_ns)) return false;
    epoch_ = epoch; last_tick_ns_ = enable_ns; sequence_ = 0; sequence_exhausted_ = false;
    e2e::p05_protect_init(tx_.protection);
    response_.begin(enable_ns); fault_ = DriveFault::None;
    return true;
}
void DriveActuator::fail(DriveFault fault, std::uint64_t now_ns) {
    if (fault == DriveFault::ClockError) { fault_ = fault; return; }
    if (fault_ == DriveFault::None) {
        fault_ = fault;
        response_.request_zero(now_ns);
    }
}
can::DriveReceiveResult DriveActuator::receive(const can::DriveFrame& frame, std::uint64_t now_ns) {
    const auto previous = receiver_.current_sample(now_ns);
    if (receiver_.health() == can::ActuatorReceiverHealth::ClockError) fail(DriveFault::ClockError, now_ns);
    if (!previous && (receiver_.last_accepted() || receiver_.health() == can::ActuatorReceiverHealth::Timeout)) {
        fail(DriveFault::CommandUnavailable, now_ns);
    }
    if (fault_ != DriveFault::None) {
        return {fault_ == DriveFault::ClockError ? can::ActuatorReceiveDecision::ClockError :
                can::ActuatorReceiveDecision::ModeRejected, std::nullopt};
    }
    return receiver_.receive(frame, now_ns);
}
void DriveActuator::mark_continuity_lost(std::uint64_t now_ns) {
    receiver_.mark_continuity_lost(now_ns);
    if (epoch_ != 0) fail(receiver_.health() == can::ActuatorReceiverHealth::ClockError ?
                         DriveFault::ClockError : DriveFault::ContinuityLost, now_ns);
}
std::optional<can::DriveFrame> DriveActuator::tick(std::uint64_t now_ns) {
    if (epoch_ == 0) return std::nullopt;
    const auto sample = receiver_.current_sample(now_ns);
    if (receiver_.health() == can::ActuatorReceiverHealth::ClockError || now_ns < last_tick_ns_) {
        fail(DriveFault::ClockError, now_ns); return std::nullopt;
    }
    if (fault_ == DriveFault::ClockError || sequence_exhausted_) return std::nullopt;
    if (now_ns - last_tick_ns_ < config_.period_ns) return std::nullopt;
    const bool missed = now_ns - last_tick_ns_ > config_.max_tick_gap_ns;
    if (missed) fail(DriveFault::ControlDeadline, now_ns);
    if (receiver_.health() == can::ActuatorReceiverHealth::ContinuityError) fail(DriveFault::ContinuityLost, now_ns);
    if (!sample && (receiver_.last_accepted() || receiver_.health() == can::ActuatorReceiverHealth::Timeout)) {
        fail(DriveFault::CommandUnavailable, now_ns);
    }
    if (fault_ == DriveFault::None && sample) {
        const auto bounded = std::clamp(*sample->torque_nm, config_.response.minimum_nm, config_.response.maximum_nm);
        if (!response_.set_target(bounded, now_ns)) fail(DriveFault::ControlDeadline, now_ns);
    }
    // Lost intervals are held; a following regular tick can run the zero ramp.
    if (missed) response_.skip_to(now_ns);
    else if (!response_.advance(now_ns)) { fail(DriveFault::ClockError, now_ns); return std::nullopt; }
    last_tick_ns_ = now_ns;
    can::DriveMessage actual;
    actual.kind = can::DriveFrameKind::Actual; actual.epoch = epoch_; actual.sequence = sequence_;
    actual.source_time_ns = now_ns;
    const auto& accepted = receiver_.last_accepted();
    actual.causal_sequence = accepted ? accepted->message.sequence : 0;
    actual.local_state = fault_ != DriveFault::None ? can::ActuatorLocalState::FailSafe :
                         sample ? sample->local_state : can::ActuatorLocalState::Init;
    actual.origin = fault_ != DriveFault::None ? can::ActuatorOrigin::LocalProtection :
                    accepted ? can::ActuatorOrigin::NormalPath : can::ActuatorOrigin::NoAcceptedInput;
    if (fault_ == DriveFault::None || accepted) actual.torque_nm = response_.actual_nm();
    // Speed and regen capability stay unavailable: neither is computed by this plant.
    const auto frame = can::encode_drive_frame(actual, tx_);
    if (frame) {
        if (sequence_ == std::numeric_limits<std::uint32_t>::max()) sequence_exhausted_ = true;
        else ++sequence_;
    }
    return frame;
}
}  // namespace stratadrive::vecu
