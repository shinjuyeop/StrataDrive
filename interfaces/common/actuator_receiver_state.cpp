#include "actuator_receiver_state.hpp"

#include <cmath>
#include <limits>

namespace stratadrive::can {
namespace {
constexpr std::uint32_t kSequenceWindow = 10;
}  // namespace

bool actuator_sequence_progresses(std::optional<std::uint32_t> previous, std::uint32_t next) {
    return previous ? next > *previous && next - *previous <= kSequenceWindow : next < kSequenceWindow;
}

bool actuator_mode_allowed(const ActuatorMetadata& metadata, bool command) {
    if (command) {
        return metadata.origin == ActuatorOrigin::NormalPath &&
               (metadata.local_state == ActuatorLocalState::Normal ||
                metadata.local_state == ActuatorLocalState::Degraded);
    }
    // 유효 Actual과 sender health는 별개다. Origin=0은 INIT에서만 허용한다.
    return metadata.origin != ActuatorOrigin::NoAcceptedInput ||
           metadata.local_state == ActuatorLocalState::Init;
}

bool actuator_value_in_range(double value, ActuatorValueRange range) {
    // raw→double의 1 ULP 오차만 허용한다. 다음 wire step은 허용하지 않는다.
    const auto lower = std::nextafter(range.minimum, -std::numeric_limits<double>::infinity());
    const auto upper = std::nextafter(range.maximum, std::numeric_limits<double>::infinity());
    return std::isfinite(value) && value >= lower && value <= upper;
}

ActuatorReceiverState::ActuatorReceiverState(ActuatorReceiverTiming timing) : timing_(timing) {}

bool ActuatorReceiverState::start_session(std::uint32_t epoch, std::uint64_t monitoring_enable_ns) {
    if (timing_.max_source_age_ns == 0 || timing_.max_source_age_ns >= timing_.timeout_ns ||
        timing_.timeout_ns > timing_.timeout_limit_ns ||
        epoch == 0 || (epoch_ != 0 && (epoch <= epoch_ || monitoring_enable_ns < last_observed_ns_))) {
        return false;
    }
    epoch_ = epoch;
    monitoring_enable_ns_ = monitoring_enable_ns;
    last_observed_ns_ = monitoring_enable_ns;
    accepted_.reset();
    last_raw_rx_ns_.reset();
    health_ = ActuatorReceiverHealth::Waiting;
    return true;
}

ActuatorReceiverHealth ActuatorReceiverState::poll(std::uint64_t now_ns) {
    if (health_ == ActuatorReceiverHealth::NotInitialized) return health_;
    if (now_ns < last_observed_ns_) {
        health_ = ActuatorReceiverHealth::ClockError;
        return health_;
    }
    last_observed_ns_ = now_ns;
    if (health_ == ActuatorReceiverHealth::ClockError || health_ == ActuatorReceiverHealth::Timeout ||
        health_ == ActuatorReceiverHealth::ContinuityError) {
        return health_;
    }
    const auto reference_ns = accepted_ ? accepted_->received_time_ns : monitoring_enable_ns_;
    if (now_ns - reference_ns >= timing_.timeout_ns) health_ = ActuatorReceiverHealth::Timeout;
    return health_;
}

void ActuatorReceiverState::mark_continuity_lost(std::uint64_t now_ns) {
    const auto status = poll(now_ns);
    if (status == ActuatorReceiverHealth::Waiting || status == ActuatorReceiverHealth::Receiving) {
        health_ = ActuatorReceiverHealth::ContinuityError;
    }
}

std::optional<ActuatorReceiveDecision> ActuatorReceiverState::begin_receive(std::uint64_t now_ns) {
    const auto status = poll(now_ns);  // late frame보다 timeout을 먼저 검사한다.
    if (status == ActuatorReceiverHealth::NotInitialized) return ActuatorReceiveDecision::NotInitialized;
    if (status == ActuatorReceiverHealth::ClockError) return ActuatorReceiveDecision::ClockError;
    if (status == ActuatorReceiverHealth::ContinuityError) return ActuatorReceiveDecision::ContinuityLost;
    last_raw_rx_ns_ = now_ns;
    if (status == ActuatorReceiverHealth::Timeout) return ActuatorReceiveDecision::Timeout;
    return std::nullopt;
}

std::optional<ActuatorReceiveDecision> ActuatorReceiverState::check_metadata(
    const ActuatorMetadata& metadata, std::uint64_t now_ns) const {
    if (metadata.epoch != epoch_) return ActuatorReceiveDecision::EpochMismatch;
    if (metadata.source_time_ns < monitoring_enable_ns_) return ActuatorReceiveDecision::SourceBeforeSession;
    if (metadata.source_time_ns > now_ns) return ActuatorReceiveDecision::SourceInFuture;
    if (now_ns - metadata.source_time_ns > timing_.max_source_age_ns) return ActuatorReceiveDecision::SourceStale;
    const auto previous = accepted_ ? std::optional<std::uint32_t>{accepted_->metadata.sequence} : std::nullopt;
    if (!actuator_sequence_progresses(previous, metadata.sequence)) return ActuatorReceiveDecision::SequenceRejected;
    if (accepted_ && metadata.source_time_ns <= accepted_->metadata.source_time_ns) {
        return ActuatorReceiveDecision::SourceNotIncreasing;
    }
    return std::nullopt;
}

void ActuatorReceiverState::commit(const ActuatorMetadata& metadata, std::uint64_t now_ns) {
    accepted_ = AcceptedMetadata{metadata, now_ns};
    health_ = ActuatorReceiverHealth::Receiving;
}

bool ActuatorReceiverState::has_current_sample(std::uint64_t now_ns) {
    return poll(now_ns) == ActuatorReceiverHealth::Receiving && accepted_ &&
           now_ns - accepted_->metadata.source_time_ns <= timing_.max_source_age_ns;
}
}  // namespace stratadrive::can
