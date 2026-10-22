#include "vehicle_management.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace stratadrive::central {
namespace {
constexpr std::uint64_t kPeriodNs = 10000000ULL;
std::uint64_t add(std::uint64_t value, std::uint64_t delta) {
    return std::numeric_limits<std::uint64_t>::max() - value < delta ?
        std::numeric_limits<std::uint64_t>::max() : value + delta;
}
bool valid_config(const VehicleManagementConfig& c) {
    const auto& t = c.readiness;
    return t.zone_source_age_ns > 0 && t.zone_source_age_ns <= 30000000ULL &&
        t.actual_source_age_ns > 0 && t.actual_source_age_ns <= 30000000ULL &&
        t.bms_source_age_ns > 0 && t.bms_source_age_ns <= 50000000ULL &&
        t.bms_dependency_age_ns > 0 && t.bms_dependency_age_ns <= 70000000ULL &&
        c.max_tick_gap_ns >= kPeriodNs && c.max_tick_gap_ns <= 30000000ULL && c.minimum_tick_interval_ns>0 && c.minimum_tick_interval_ns<=kPeriodNs &&
        c.initial_input_timeout_ns > 0 && c.initial_input_timeout_ns <= 80000000ULL &&
        c.request_source_age_ns > 0 && c.request_source_age_ns <= 50000000ULL &&
        c.output_lifetime_ns > 0 && c.output_lifetime_ns <= can::kBmsMaxLifetimeNs &&
        c.acknowledgement_timeout_ns > 0 && c.acknowledgement_timeout_ns <= 80000000ULL &&
        c.startup_timeout_ns > c.initial_input_timeout_ns && c.shutdown_timeout_ns > 0 &&
        std::isfinite(c.off_bus_max_v) && c.off_bus_max_v >= 0;
}
bool same_request(const LifecycleRequest& a, const LifecycleRequest& b) {
    return a.identity.epoch == b.identity.epoch && a.identity.sequence == b.identity.sequence &&
        a.identity.source_time_ns == b.identity.source_time_ns && a.identity.expires_at_ns == b.identity.expires_at_ns &&
        a.action == b.action;
}
const can::BmsPowerStatus* power_status(const NormalDriveReadinessInputs& in) {
    return in.rear.power_status ? std::get_if<can::BmsPowerStatus>(&in.rear.power_status->message.content) : nullptr;
}
bool power_off(const can::BmsPowerStatus* s, double maximum) {
    return s && s->state == can::BmsPowerState::Off && s->positive_contactor_closed == false &&
        s->negative_contactor_closed == false && s->precharge_contactor_closed == false &&
        s->hv_bus_voltage_v && *s->hv_bus_voltage_v <= maximum;
}
bool power_observed(const NormalDriveReadinessInputs& in, std::uint64_t now, const ReadinessTiming& timing) {
    const auto* status = power_status(in);
    if (!status || !in.rear.power_status) return false;
    const auto& sample = *in.rear.power_status;
    const auto& message = sample.message;
    return message.kind == can::BmsFrameKind::PowerStatus && message.epoch == in.epoch &&
        message.source_time_ns >= in.session_enable_ns && message.source_time_ns <= now &&
        now - message.source_time_ns <= timing.bms_source_age_ns &&
        status->input_time_ns >= in.session_enable_ns && status->input_time_ns <= message.source_time_ns &&
        now - status->input_time_ns <= timing.bms_dependency_age_ns &&
        sample.quality[0] == can::BmsFieldQuality::Usable && sample.quality[1] == can::BmsFieldQuality::Usable &&
        status->hv_bus_voltage_v && std::isfinite(*status->hv_bus_voltage_v) && *status->hv_bus_voltage_v >= 0;
}
template <typename Message>
bool protection(const std::optional<Message>& m) {
    return m && (m->local_state == can::ActuatorLocalState::FailSafe || m->origin == can::ActuatorOrigin::LocalProtection);
}
bool protection(const std::optional<can::BmsCurrentSample>& s) {
    return s && (s->message.local_state == can::ActuatorLocalState::FailSafe ||
                 s->message.origin == can::ActuatorOrigin::LocalProtection);
}
bool source_protection(const NormalDriveReadinessInputs& in) {
    return protection(in.front.health) || protection(in.rear.health) || protection(in.front.steering_actual) ||
        protection(in.front.brake_actual) || protection(in.rear.drive_actual) ||
        protection(in.rear.power_status) || protection(in.rear.power_limits);
}
}  // namespace

VehicleManagement::VehicleManagement(VehicleManagementConfig config) : config_(config) {
    if (!valid_config(config_)) throw std::invalid_argument("invalid vehicle-management configuration");
}
bool VehicleManagement::start_session(std::uint32_t epoch, std::uint64_t enable_ns) {
    if (epoch == 0 || (epoch_ != 0 && (epoch <= epoch_ || enable_ns < last_observed_ns_))) return false;
    epoch_ = epoch; enable_ns_ = last_observed_ns_ = phase_since_ns_ = enable_ns; sequence_ = 0;
    last_tick_ns_.reset(); last_ack_source_ns_.reset(); grant_expiry_ns_.reset(); request_.reset(); issued_ = {};
    inputs_seen_ = stopped_ = false; decision_ = {}; decision_.state = VehicleManagementState::Init;
    return true;
}
void VehicleManagement::fail(VehicleManagementFault fault) {
    if (decision_.fault == VehicleManagementFault::None || fault == VehicleManagementFault::ClockError) decision_.fault = fault;
    decision_.state = VehicleManagementState::FailSafe; decision_.normal_allowed = false;
}
bool VehicleManagement::live_request(std::uint64_t now) const {
    return request_ && now < request_->identity.expires_at_ns &&
        now - request_->identity.source_time_ns <= config_.request_source_age_ns;
}
bool VehicleManagement::advance(std::uint64_t now) {
    if (epoch_ == 0 || stopped_) return false;
    if (now < last_observed_ns_ || now == std::numeric_limits<std::uint64_t>::max()) {
        fail(VehicleManagementFault::ClockError); stopped_ = true; return false;
    }
    last_observed_ns_ = now;
    if (now - last_tick_ns_.value_or(enable_ns_) > config_.max_tick_gap_ns) fail(VehicleManagementFault::ControlDeadline);
    if (decision_.state == VehicleManagementState::Starting || decision_.state == VehicleManagementState::Normal) {
        if (!live_request(now)) fail(VehicleManagementFault::RequestLost);
        else if (decision_.state == VehicleManagementState::Normal && grant_expiry_ns_ && now >= *grant_expiry_ns_) {
            fail(VehicleManagementFault::GrantExpired);
        }
    }
    return true;
}
LifecycleReceiveDecision VehicleManagement::receive_request(const LifecycleRequest& request, std::uint64_t now) {
    if (epoch_ == 0) return LifecycleReceiveDecision::NotInitialized;
    if (!advance(now) || decision_.state == VehicleManagementState::FailSafe) return LifecycleReceiveDecision::Latched;
    if ((decision_.state == VehicleManagementState::Stopping || decision_.state == VehicleManagementState::Stopped) &&
        request.action != can::BmsPowerAction::Shutdown) {
        return LifecycleReceiveDecision::RestartRequired;
    }
    const auto& id = request.identity;
    if (id.epoch != epoch_) return LifecycleReceiveDecision::EpochMismatch;
    if (static_cast<std::uint16_t>(request.action) > 2 || id.source_time_ns < enable_ns_ || id.source_time_ns > now ||
        id.expires_at_ns <= id.source_time_ns || id.expires_at_ns - id.source_time_ns > can::kBmsMaxLifetimeNs) {
        return LifecycleReceiveDecision::Invalid;
    }
    if (now >= id.expires_at_ns || now - id.source_time_ns > config_.request_source_age_ns) return LifecycleReceiveDecision::Expired;
    if (request_ && id.sequence == request_->identity.sequence) {
        return same_request(request, *request_) ? LifecycleReceiveDecision::Unchanged : LifecycleReceiveDecision::MutationRejected;
    }
    const auto previous = request_ ? std::optional<std::uint32_t>{request_->identity.sequence} : std::nullopt;
    if (!can::actuator_sequence_progresses(previous, id.sequence) ||
        (request_ && id.source_time_ns <= request_->identity.source_time_ns)) return LifecycleReceiveDecision::SequenceRejected;
    request_ = request;
    if (request.action != can::BmsPowerAction::Enable) decision_.normal_allowed = false;
    return LifecycleReceiveDecision::Accepted;
}
void VehicleManagement::mark_continuity_lost(std::uint64_t now) {
    if (advance(now)) fail(VehicleManagementFault::ContinuityLost);
}
const VehicleManagement::IssuedRequest* VehicleManagement::acknowledgement(
    const NormalDriveReadinessInputs& in, std::uint64_t now, can::BmsPowerAction action) const {
    const auto* status = power_status(in);
    if (!status || !in.rear.power_status) return nullptr;
    const auto& reply = in.rear.power_status->message;
    for (const auto& issued : issued_) {
        if (!issued) continue;
        const auto& sent = issued->message;
        const auto& body = std::get<can::BmsPowerRequest>(sent.content);
        if (body.action != action || (action == can::BmsPowerAction::Enable && !issued->parent) ||
            (action == can::BmsPowerAction::Enable && last_ack_source_ns_ && sent.source_time_ns < *last_ack_source_ns_) ||
            sent.sequence != reply.causal_sequence ||
            sent.source_time_ns != status->accepted_request_source_time_ns ||
            sent.source_time_ns > reply.source_time_ns || now >= body.expires_at_ns) continue;
        if (issued->parent && (now >= issued->parent->identity.expires_at_ns ||
            now - issued->parent->identity.source_time_ns > config_.request_source_age_ns)) continue;
        return &*issued;
    }
    return nullptr;
}
std::uint64_t VehicleManagement::permission_expiry(
    const NormalDriveReadinessInputs& in, const IssuedRequest& acknowledged, std::uint64_t now) {
    const auto& t = config_.readiness;
    PermissionSupport support{PermissionLimit::OutputLifetime,now,add(now,config_.output_lifetime_ns)};
    const auto limit = [&](PermissionLimit kind,std::uint64_t source,std::uint64_t expiry) {
        if(expiry<support.expiry_ns) support={kind,source,expiry};
    };
    limit(PermissionLimit::LifecycleExpiry,request_->identity.source_time_ns,request_->identity.expires_at_ns);
    limit(PermissionLimit::LifecycleAge,request_->identity.source_time_ns,add(request_->identity.source_time_ns,config_.request_source_age_ns+1));
    limit(PermissionLimit::AcknowledgedPower,acknowledged.message.source_time_ns,std::get<can::BmsPowerRequest>(acknowledged.message.content).expires_at_ns);
    const auto bound = [&](PermissionLimit kind,std::uint64_t source,std::uint64_t age) { limit(kind,source,add(source,age+1)); };
    bound(PermissionLimit::FrontHealth,in.front.health->source_time_ns,t.zone_source_age_ns);
    bound(PermissionLimit::RearHealth,in.rear.health->source_time_ns,t.zone_source_age_ns);
    bound(PermissionLimit::SteeringActual,in.front.steering_actual->source_time_ns,t.actual_source_age_ns);
    bound(PermissionLimit::BrakeActual,in.front.brake_actual->source_time_ns,t.actual_source_age_ns);
    bound(PermissionLimit::DriveActual,in.rear.drive_actual->source_time_ns,t.actual_source_age_ns);
    bound(PermissionLimit::PowerStatus,in.rear.power_status->message.source_time_ns,t.bms_source_age_ns);
    bound(PermissionLimit::PowerLimits,in.rear.power_limits->message.source_time_ns,t.bms_source_age_ns);
    bound(PermissionLimit::PowerInput,power_status(in)->input_time_ns,t.bms_dependency_age_ns);
    bound(PermissionLimit::LimitsInput,std::get<can::BmsPowerLimits>(in.rear.power_limits->message.content).input_time_ns,t.bms_dependency_age_ns);
    decision_.permission_support=support;
    return support.expiry_ns;
}
std::optional<VehicleManagementOutput> VehicleManagement::tick(const NormalDriveReadinessInputs& in, std::uint64_t now) {
    if (!advance(now)) return std::nullopt;
    if (last_tick_ns_ && now - *last_tick_ns_ < config_.minimum_tick_interval_ns) return std::nullopt;
    last_tick_ns_ = now;
    if (in.epoch != epoch_ || in.session_enable_ns != enable_ns_) fail(VehicleManagementFault::SessionMismatch);
    decision_.normal_allowed = false;
    decision_.input_health = evaluate_vehicle_input_health(in, now, config_.readiness);
    decision_.normal_readiness = evaluate_normal_drive_readiness(in, now, config_.readiness);
    const auto* status = power_status(in);
    if (source_protection(in)) fail(VehicleManagementFault::SourceProtection);
    const bool healthy = decision_.input_health.ready();
    if (!healthy && (inputs_seen_ || now - enable_ns_ >= config_.initial_input_timeout_ns)) fail(VehicleManagementFault::InputsUnavailable);
    if (healthy) inputs_seen_ = true;
    const auto* enabled = healthy ? acknowledgement(in, now, can::BmsPowerAction::Enable) : nullptr;
    // Valid physical OFF is independent of vehicle/peer health and never clears
    // the fault latch. A failed sender can still report a usable physical value.
    const bool observed = in.epoch == epoch_ && in.session_enable_ns == enable_ns_ && power_observed(in, now, config_.readiness);
    const auto* shutdown = observed ? acknowledgement(in, now, can::BmsPowerAction::Shutdown) : nullptr;
    const auto* off_ack = shutdown ? shutdown : observed ? acknowledgement(in, now, can::BmsPowerAction::KeepOff) : nullptr;
    decision_.power_off_confirmed = observed && power_off(status, config_.off_bus_max_v) && off_ack;

    if (decision_.state == VehicleManagementState::Init && healthy) {
        if (*status->positive_contactor_closed || *status->negative_contactor_closed || *status->precharge_contactor_closed) {
            fail(VehicleManagementFault::StartupEnergized);
        } else if (power_off(status, config_.off_bus_max_v)) decision_.state = VehicleManagementState::Off;
        else if (now - enable_ns_ >= config_.startup_timeout_ns) fail(VehicleManagementFault::StartupTimeout);
    }
    if (decision_.state == VehicleManagementState::Off && live_request(now) && request_->action == can::BmsPowerAction::Enable) {
        if (status->condition_bits != 7) fail(VehicleManagementFault::UnsafePowerConditions);
        else { decision_.state = VehicleManagementState::Starting; phase_since_ns_ = now; }
    }
    if (decision_.state == VehicleManagementState::Starting || decision_.state == VehicleManagementState::Normal) {
        if (request_->action != can::BmsPowerAction::Enable) {
            decision_.state = VehicleManagementState::Stopping; phase_since_ns_ = now;
        } else if (status->condition_bits != 7) fail(VehicleManagementFault::UnsafePowerConditions);
        else {
            if (enabled) last_ack_source_ns_ = enabled->message.source_time_ns;
            const bool ack_lost = (decision_.state == VehicleManagementState::Normal && !enabled) ||
                now - last_ack_source_ns_.value_or(phase_since_ns_) >= config_.acknowledgement_timeout_ns;
            if (ack_lost) fail(VehicleManagementFault::PowerAcknowledgement);
            else if (decision_.state == VehicleManagementState::Normal && !decision_.normal_readiness.ready()) fail(VehicleManagementFault::PowerNotReady);
            else if (decision_.normal_readiness.ready() && enabled) decision_.state = VehicleManagementState::Normal;
            else if (now - phase_since_ns_ >= config_.startup_timeout_ns) fail(VehicleManagementFault::StartupTimeout);
        }
    }
    if (decision_.state == VehicleManagementState::Stopping) {
        if (decision_.power_off_confirmed && shutdown) decision_.state = VehicleManagementState::Stopped;
        else if (now - phase_since_ns_ >= config_.shutdown_timeout_ns) fail(VehicleManagementFault::ShutdownTimeout);
    }
    if (sequence_ > std::numeric_limits<std::uint32_t>::max()) {
        fail(VehicleManagementFault::SequenceExhausted); stopped_ = true; return std::nullopt;
    }
    VehicleManagementOutput out;
    const bool fault = decision_.state == VehicleManagementState::FailSafe;
    const bool allow = decision_.state == VehicleManagementState::Normal;
    const bool starting = decision_.state == VehicleManagementState::Starting;
    const bool stopping = decision_.state == VehicleManagementState::Stopping;
    auto& power = out.power_request; auto& grant = out.drive_permission;
    power.kind = can::BmsFrameKind::PowerRequest; grant.kind = can::BmsFrameKind::DrivePermission;
    for (auto* message : {&power, &grant}) {
        message->epoch = epoch_; message->sequence = static_cast<std::uint32_t>(sequence_); message->source_time_ns = now;
        message->local_state = fault ? can::ActuatorLocalState::FailSafe : allow ? can::ActuatorLocalState::Normal : can::ActuatorLocalState::Init;
        message->origin = fault ? can::ActuatorOrigin::LocalProtection : can::ActuatorOrigin::NoAcceptedInput;
    }
    const bool root = live_request(now) && (starting || allow || stopping);
    const auto expiry = root ? std::min({add(now, config_.output_lifetime_ns), request_->identity.expires_at_ns,
        add(request_->identity.source_time_ns, config_.request_source_age_ns + 1)}) : add(now, config_.output_lifetime_ns);
    const auto action = fault || stopping ? can::BmsPowerAction::Shutdown :
        starting || allow ? can::BmsPowerAction::Enable : can::BmsPowerAction::KeepOff;
    power.content = can::BmsPowerRequest{action, expiry, root ? request_->identity.source_time_ns : 0};
    if (root) {
        power.origin = can::ActuatorOrigin::NormalPath; power.causal_sequence = request_->identity.sequence;
        out.power_parent = request_->identity;
    } else if (stopping) power.origin = can::ActuatorOrigin::LocalProtection;
    grant.content = can::BmsDriveGrant{can::BmsDrivePermission::Inhibit, 0, 0, 0, add(now, config_.output_lifetime_ns)};
    if (allow && enabled) {
        grant.origin = can::ActuatorOrigin::NormalPath; grant.causal_sequence = request_->identity.sequence;
        const auto oldest = std::min({*decision_.normal_readiness.oldest_input_time_ns,
            request_->identity.source_time_ns, enabled->parent->identity.source_time_ns});
        grant.content = can::BmsDriveGrant{can::BmsDrivePermission::AllowNormal, in.rear.power_status->message.sequence,
            in.rear.power_status->message.source_time_ns, oldest, permission_expiry(in, *enabled, now)};
        out.permission_parent = request_->identity; grant_expiry_ns_ = std::get<can::BmsDriveGrant>(grant.content).expires_at_ns;
        decision_.normal_allowed = true;
    } else grant_expiry_ns_.reset();
    issued_[static_cast<std::size_t>(sequence_ % issued_.size())] = IssuedRequest{power, root ? request_ : std::nullopt};
    ++sequence_;
    return out;
}
}  // namespace stratadrive::central
