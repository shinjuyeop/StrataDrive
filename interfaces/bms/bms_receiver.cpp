#include "bms_receiver.hpp"

#include <cmath>

namespace stratadrive::can {
namespace {
bool observation(BmsFrameKind kind) { return kind == BmsFrameKind::BatteryState; }
std::size_t groups(BmsFrameKind kind) {
    if (observation(kind)) return 3;
    if (kind == BmsFrameKind::PowerLimits || kind == BmsFrameKind::DriveBatteryLimits || kind == BmsFrameKind::PowerStatus) return 2;
    return 1;
}
bool valid_range(ActuatorValueRange range, double minimum, double maximum) {
    return std::isfinite(range.minimum) && std::isfinite(range.maximum) && range.minimum < range.maximum &&
           range.minimum >= minimum && range.maximum <= maximum;
}
bool valid_config(const BmsReceiverConfig& config) {
    return bms_e2e_config(config.kind) && valid_range(config.physical.voltage_v, 0, 6553.4) &&
           valid_range(config.physical.current_a, -3276.7, 3276.7) &&
           valid_range(config.physical.temperature_c, -3276.7, 3276.7) &&
           std::isfinite(config.physical.max_power_limit_w) && config.physical.max_power_limit_w > 0 &&
           config.physical.max_power_limit_w <= 655340 && config.max_source_age_ns > 0 &&
           config.max_source_age_ns < config.timeout_ns && config.timeout_ns <= 80000000ULL &&
           config.max_dependency_age_ns > 0 && config.max_dependency_age_ns < config.timeout_ns &&
           config.observation_age_ns > 0 && config.observation_age_ns < config.observation_timeout_ns &&
           config.observation_timeout_ns <= 300000000ULL;
}
std::uint64_t group_source(const BmsMessage& message, std::size_t group) {
    if (const auto* value = std::get_if<BmsBatteryState>(&message.content)) {
        if (group == 0) return value->soc ? value->soc->source_time_ns : 0;
        if (group == 1) return value->electrical ? value->electrical->source_time_ns : 0;
        return value->temperature ? value->temperature->source_time_ns : 0;
    }
    return message.source_time_ns;
}
bool needs_parent(const BmsMessage& message) {
    if (const auto* value = std::get_if<BmsPowerRequest>(&message.content)) {
        return value->action && message.origin == ActuatorOrigin::NormalPath;
    }
    if (const auto* value = std::get_if<BmsDriveGrant>(&message.content)) {
        return value->permission == BmsDrivePermission::AllowNormal;
    }
    return false;
}
std::uint64_t expiry(const BmsMessage& message) {
    if (const auto* value = std::get_if<BmsPowerRequest>(&message.content)) return value->expires_at_ns;
    if (const auto* value = std::get_if<BmsDriveGrant>(&message.content)) return value->expires_at_ns;
    return 0;
}
bool mode_allowed(const BmsMessage& message, bool allow_degraded) {
    if (const auto* value = std::get_if<BmsPowerRequest>(&message.content)) {
        if (value->action == BmsPowerAction::Enable && message.local_state == ActuatorLocalState::FailSafe) return false;
    }
    if (const auto* value = std::get_if<BmsDriveGrant>(&message.content)) {
        if (value->permission == BmsDrivePermission::AllowNormal &&
            message.local_state == ActuatorLocalState::Degraded && !allow_degraded) return false;
    }
    return message.origin != ActuatorOrigin::NoAcceptedInput || message.local_state == ActuatorLocalState::Init;
}
void remove_group(BmsMessage& message, std::size_t group) {
    if (auto* value = std::get_if<BmsBatteryState>(&message.content)) {
        if (group == 0) value->soc.reset();
        else if (group == 1) value->electrical.reset();
        else value->temperature.reset();
    } else if (auto* value = std::get_if<BmsPowerLimits>(&message.content)) {
        if (group == 0) { value->charge_power_w.reset(); value->charge_reason = BmsLimitReason::InputsInvalid; }
        else { value->discharge_power_w.reset(); value->discharge_reason = BmsLimitReason::InputsInvalid; }
        if (!value->charge_power_w && !value->discharge_power_w) value->input_time_ns = 0;
    } else if (auto* value = std::get_if<BmsPowerStatus>(&message.content)) {
        if (group == 0) value->state.reset();
        else {
            value->positive_contactor_closed.reset(); value->negative_contactor_closed.reset();
            value->precharge_contactor_closed.reset(); value->condition_bits = value->condition_validity = 0;
            value->hv_bus_voltage_v.reset();
        }
        if (!value->state && !value->positive_contactor_closed && !value->negative_contactor_closed &&
            !value->precharge_contactor_closed && value->condition_validity == 0 && !value->hv_bus_voltage_v) {
            value->input_time_ns = 0; value->input_sequence = 0;
        }
    } else if (auto* value = std::get_if<BmsPowerRequest>(&message.content)) {
        value->action.reset(); value->expires_at_ns = value->parent_source_time_ns = 0;
    } else if (auto* value = std::get_if<BmsDriveGrant>(&message.content)) {
        *value = BmsDriveGrant{};
    }
}
bool model_progress(std::uint32_t next_id, std::uint64_t next_time,
                    std::uint32_t previous_id, std::uint64_t previous_time) {
    return next_id >= previous_id && next_time >= previous_time &&
           (next_id != previous_id || next_time == previous_time);
}
}  // namespace
BmsReceiver::BmsReceiver(const BmsReceiverConfig& config)
    : config_(config), e2e_{config.kind},
      cursor_({observation(config.kind) ? config.observation_age_ns : config.max_source_age_ns,
               observation(config.kind) ? config.observation_timeout_ns : config.timeout_ns,
               observation(config.kind) ? 300000000ULL : 80000000ULL}) {}
bool BmsReceiver::start_session(std::uint32_t epoch, std::uint64_t monitoring_enable_ns) {
    if (!valid_config(config_) || !cursor_.start_session(epoch, monitoring_enable_ns)) return false;
    e2e::p05_check_init(e2e_.check);
    session_start_ns_ = monitoring_enable_ns;
    accepted_.reset(); usable_.reset(); parent_.reset();
    group_cursor_ = {}; last_usable_rx_ = {};
    quality_.fill(BmsFieldQuality::NotApplicable);
    health_ = ActuatorReceiverHealth::Waiting;
    return true;
}
ActuatorReceiverHealth BmsReceiver::poll(std::uint64_t now_ns) {
    const auto base = cursor_.poll(now_ns);
    if (base == ActuatorReceiverHealth::NotInitialized || base == ActuatorReceiverHealth::ClockError) {
        health_ = base; return health_;
    }
    if (health_ == ActuatorReceiverHealth::ClockError || health_ == ActuatorReceiverHealth::Timeout) return health_;
    if (base == ActuatorReceiverHealth::Timeout) { health_ = base; return health_; }
    const auto timeout = observation(config_.kind) ? config_.observation_timeout_ns : config_.timeout_ns;
    for (std::size_t group = 0; !observation(config_.kind) && group < groups(config_.kind); ++group) {
        if (now_ns - last_usable_rx_[group].value_or(session_start_ns_) >= timeout) {
            health_ = ActuatorReceiverHealth::Timeout; return health_;
        }
    }
    health_ = base;
    return health_;
}
BmsFieldQuality BmsReceiver::classify(std::size_t group, const BmsMessage& message, std::uint64_t now_ns) const {
    const auto age = [&](std::uint64_t time, std::uint64_t maximum) {
        if (time < session_start_ns_ || time > message.source_time_ns || time > now_ns) return BmsFieldQuality::Invalid;
        return now_ns - time > maximum ? BmsFieldQuality::Stale : BmsFieldQuality::Usable;
    };
    if (const auto* value = std::get_if<BmsBatteryState>(&message.content)) {
        if (group == 0) return value->soc ? age(value->soc->source_time_ns, config_.observation_age_ns) : BmsFieldQuality::Unavailable;
        if (group == 1) {
            if (!value->electrical) return BmsFieldQuality::Unavailable;
            if (!actuator_value_in_range(value->electrical->voltage_v, config_.physical.voltage_v) ||
                !actuator_value_in_range(value->electrical->current_a, config_.physical.current_a)) return BmsFieldQuality::Invalid;
            return age(value->electrical->source_time_ns, config_.observation_age_ns);
        }
        if (!value->temperature) return BmsFieldQuality::Unavailable;
        if (!actuator_value_in_range(value->temperature->celsius, config_.physical.temperature_c)) return BmsFieldQuality::Invalid;
        return age(value->temperature->source_time_ns, config_.observation_age_ns);
    }
    if (const auto* value = std::get_if<BmsPowerLimits>(&message.content)) {
        const auto limit = group == 0 ? value->charge_power_w : value->discharge_power_w;
        if (!limit) return BmsFieldQuality::Unavailable;
        if (!actuator_value_in_range(*limit, {0, config_.physical.max_power_limit_w})) return BmsFieldQuality::Invalid;
        return age(value->input_time_ns, config_.max_dependency_age_ns);
    }
    if (const auto* value = std::get_if<BmsPowerStatus>(&message.content)) {
        if (group == 0 && !value->state) return BmsFieldQuality::Unavailable;
        if (group == 1) {
            if (!value->positive_contactor_closed || !value->negative_contactor_closed ||
                !value->precharge_contactor_closed || !value->hv_bus_voltage_v || value->condition_validity != 31) return BmsFieldQuality::Unavailable;
            if (!actuator_value_in_range(*value->hv_bus_voltage_v, config_.physical.voltage_v)) return BmsFieldQuality::Invalid;
        }
        return age(value->input_time_ns, config_.max_dependency_age_ns);
    }
    if (const auto* value = std::get_if<BmsPowerRequest>(&message.content)) {
        if (!value->action) return BmsFieldQuality::Unavailable;
        return now_ns >= value->expires_at_ns ? BmsFieldQuality::Stale : BmsFieldQuality::Usable;
    }
    const auto& value = std::get<BmsDriveGrant>(message.content);
    if (!value.permission) return BmsFieldQuality::Unavailable;
    if (now_ns >= value.expires_at_ns) return BmsFieldQuality::Stale;
    if (*value.permission == BmsDrivePermission::Inhibit) return BmsFieldQuality::Usable;
    const auto power_age = age(value.power_status_source_time_ns, config_.max_source_age_ns);
    return power_age == BmsFieldQuality::Usable ? age(value.input_time_ns, config_.max_dependency_age_ns) : power_age;
}
bool BmsReceiver::progresses(const BmsMessage& message, std::size_t group) const {
    if (!group_cursor_[group]) return true;
    const auto& previous = *group_cursor_[group];
    if (const auto* value = std::get_if<BmsPowerStatus>(&message.content); value && group == 1) {
        return value->input_sequence > std::get<BmsPowerStatus>(previous.content).input_sequence;
    }
    return group_source(message, group) > group_source(previous, group);
}
BmsReceiveIssue BmsReceiver::check_parent(const BmsMessage& message, std::uint64_t now_ns,
                                        const BmsParentContext* parent) const {
    if (!needs_parent(message)) return BmsReceiveIssue::None;
    if (!parent) return BmsReceiveIssue::ParentMissing;
    if (parent->epoch != message.epoch || parent->sequence != message.causal_sequence ||
        parent->source_time_ns < session_start_ns_ || parent->source_time_ns > message.source_time_ns ||
        parent->expires_at_ns <= parent->source_time_ns || expiry(message) > parent->expires_at_ns) return BmsReceiveIssue::ParentMismatch;
    if (now_ns >= parent->expires_at_ns || now_ns - parent->source_time_ns > config_.max_source_age_ns) return BmsReceiveIssue::Expired;
    if (const auto* value = std::get_if<BmsPowerRequest>(&message.content);
        value && value->parent_source_time_ns != parent->source_time_ns) return BmsReceiveIssue::ParentMismatch;
    if (parent_ && (parent->sequence < parent_->sequence || parent->source_time_ns < parent_->source_time_ns ||
        (parent->sequence == parent_->sequence && (parent->source_time_ns != parent_->source_time_ns ||
         parent->expires_at_ns > parent_->expires_at_ns)) ||
        (parent->sequence > parent_->sequence && parent->source_time_ns <= parent_->source_time_ns))) return BmsReceiveIssue::ParentRollback;
    return BmsReceiveIssue::None;
}
BmsReceiveResult BmsReceiver::receive(const BmsFrame& frame, std::uint64_t now_ns, const BmsParentContext* parent) {
    const auto health = poll(now_ns); // latch before considering a late valid frame
    if (const auto reject = cursor_.begin_receive(now_ns)) return {*reject, std::nullopt};
    if (health == ActuatorReceiverHealth::Timeout) return {ActuatorReceiveDecision::Timeout, std::nullopt};
    const auto result = check_bms_e2e(&frame, e2e_);
    if (result != e2e::P05Return::Ok) return {ActuatorReceiveDecision::MalformedEnvelope, std::nullopt};
    BmsReceiveResult output{ActuatorReceiveDecision::Accepted, e2e_.check.status};
    if (!e2e::p05_is_ok(result, e2e_.check.status)) { output.decision = ActuatorReceiveDecision::E2eRejected; return output; }
    const auto message = decode_bms_frame(frame);
    if (!message) { output.decision = ActuatorReceiveDecision::MalformedPayload; return output; }
    if (const auto reject = cursor_.check_metadata(*message, now_ns)) { output.decision = *reject; return output; }
    if (!mode_allowed(*message, config_.allow_degraded_permission)) { output.decision = ActuatorReceiveDecision::ModeRejected; return output; }
    output.issue = check_parent(*message, now_ns, parent);
    if (output.issue != BmsReceiveIssue::None) {
        // A verified new normal grant without its parent cannot retain an old usable grant.
        usable_.reset(); output.decision = ActuatorReceiveDecision::Unavailable; return output;
    }
    auto usable = *message;
    for (std::size_t group = 0; group < groups(message->kind); ++group) {
        auto quality = classify(group, *message, now_ns);
        if (quality == BmsFieldQuality::Usable && group_cursor_[group]) {
            const auto& previous = *group_cursor_[group];
            const auto source = group_source(*message, group), old_source = group_source(previous, group);
            if (source < old_source) quality = BmsFieldQuality::Invalid;
            if (const auto* value = std::get_if<BmsBatteryState>(&message->content); value && source == old_source) {
                const auto& old = std::get<BmsBatteryState>(previous.content);
                if ((group == 0 && value->soc->fraction != old.soc->fraction) ||
                    (group == 1 && (value->electrical->voltage_v != old.electrical->voltage_v || value->electrical->current_a != old.electrical->current_a)) ||
                    (group == 2 && value->temperature->celsius != old.temperature->celsius)) quality = BmsFieldQuality::Invalid;
            }
            if (const auto* value = std::get_if<BmsPowerLimits>(&message->content)) {
                const auto& old = std::get<BmsPowerLimits>(previous.content);
                if (!model_progress(message->causal_sequence, value->input_time_ns, previous.causal_sequence, old.input_time_ns)) quality = BmsFieldQuality::Invalid;
            }
            if (const auto* value = std::get_if<BmsPowerStatus>(&message->content)) {
                const auto& old = std::get<BmsPowerStatus>(previous.content);
                if (!model_progress(value->input_sequence, value->input_time_ns, old.input_sequence, old.input_time_ns) ||
                    (group == 1 && value->input_sequence == old.input_sequence &&
                     (value->positive_contactor_closed != old.positive_contactor_closed || value->negative_contactor_closed != old.negative_contactor_closed ||
                      value->precharge_contactor_closed != old.precharge_contactor_closed || value->condition_bits != old.condition_bits ||
                      value->condition_validity != old.condition_validity || value->hv_bus_voltage_v != old.hv_bus_voltage_v))) quality = BmsFieldQuality::Invalid;
            }
            if (const auto* value = std::get_if<BmsDriveGrant>(&message->content)) {
                const auto& old = std::get<BmsDriveGrant>(previous.content);
                if (value->permission == BmsDrivePermission::AllowNormal && old.permission == BmsDrivePermission::AllowNormal &&
                    (!model_progress(value->power_status_sequence, value->power_status_source_time_ns,
                                     old.power_status_sequence, old.power_status_source_time_ns) ||
                     value->input_time_ns < old.input_time_ns)) quality = BmsFieldQuality::Invalid;
            }
        }
        output.quality[group] = quality;
        if (quality == BmsFieldQuality::Usable) {
            if (progresses(*message, group)) last_usable_rx_[group] = now_ns;
            group_cursor_[group] = *message;
        } else remove_group(usable, group);
    }
    if (groups(message->kind) == 1 && expiry(*message) != 0 && now_ns >= expiry(*message)) output.issue = BmsReceiveIssue::Expired;
    if (needs_parent(*message) && output.quality[0] == BmsFieldQuality::Usable && parent) parent_ = *parent;
    cursor_.commit(*message, now_ns); // envelope cursor only; per-field healthy ages are above
    accepted_ = BmsAcceptedSample{*message, now_ns}; usable_ = usable; quality_ = output.quality;
    health_ = ActuatorReceiverHealth::Receiving;
    return output;
}
std::optional<BmsCurrentSample> BmsReceiver::current_sample(std::uint64_t now_ns) {
    if (poll(now_ns) != ActuatorReceiverHealth::Receiving || !cursor_.has_current_sample(now_ns) || !usable_) return std::nullopt;
    BmsCurrentSample current{*usable_, quality_};
    for (std::size_t group = 0; group < groups(config_.kind); ++group) {
        if (current.quality[group] != BmsFieldQuality::Usable) continue;
        auto quality = classify(group, current.message, now_ns);
        if (group == 0 && needs_parent(current.message) &&
            (!parent_ || now_ns >= parent_->expires_at_ns || now_ns - parent_->source_time_ns > config_.max_source_age_ns)) quality = BmsFieldQuality::Stale;
        if (quality != BmsFieldQuality::Usable) { current.quality[group] = quality; remove_group(current.message, group); }
    }
    return current;
}
bool bms_power_is_ready(const BmsCurrentSample& sample) {
    const auto* value = std::get_if<BmsPowerStatus>(&sample.message.content);
    return sample.message.kind == BmsFrameKind::PowerStatus && value &&
           sample.quality[0] == BmsFieldQuality::Usable && sample.quality[1] == BmsFieldQuality::Usable &&
           value->state == BmsPowerState::HvReady && value->positive_contactor_closed == true &&
           value->negative_contactor_closed == true && value->precharge_contactor_closed == false &&
           value->condition_validity == 31 && value->condition_bits == 7 &&
           value->hv_bus_voltage_v && *value->hv_bus_voltage_v > 0;
}
bool bms_permission_allows_normal(const BmsCurrentSample& sample) {
    const auto* value = std::get_if<BmsDriveGrant>(&sample.message.content);
    return sample.message.kind == BmsFrameKind::DrivePermission && value &&
           sample.message.origin == ActuatorOrigin::NormalPath &&
           (sample.message.local_state == ActuatorLocalState::Normal || sample.message.local_state == ActuatorLocalState::Degraded) &&
           sample.quality[0] == BmsFieldQuality::Usable && value->permission == BmsDrivePermission::AllowNormal;
}
}  // namespace stratadrive::can
