#include "command_admission.hpp"

#include "actuator_receiver_state.hpp"
#include "steering_angle_codec.hpp"
#include "brake_pressure_codec.hpp"
#include "drive_value_codec.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace stratadrive::zone {
namespace {
std::uint64_t add(std::uint64_t time, std::uint64_t delta) {
    return std::numeric_limits<std::uint64_t>::max()-time < delta ?
        std::numeric_limits<std::uint64_t>::max() : time+delta;
}
bool valid_config(const AdmissionConfig& c) {
    for (const auto value : {c.max_angle_rad, c.max_pressure_pa, c.max_propulsion_nm, c.max_regen_nm}) {
        if (!std::isfinite(value) || value <= 0) return false;
    }
    return c.max_angle_rad <= can::kAngleWireMaxRad && c.max_pressure_pa <= can::kBrakePressureWireMaxPa &&
        c.max_propulsion_nm <= can::kDriveTorqueWireMaxNm && c.max_regen_nm <= can::kDriveTorqueWireMaxNm &&
        c.command_source_age_ns > 0 && c.command_source_age_ns <= 30000000ULL &&
        c.parent_source_age_ns > 0 && c.parent_source_age_ns <= 30000000ULL &&
        c.dependency_age_ns > 0 && c.dependency_age_ns <= 70000000ULL &&
        c.command_timeout_ns > c.command_source_age_ns && c.command_timeout_ns <= 80000000ULL;
}
bool same_meta(const can::ActuatorMetadata& a, const can::ActuatorMetadata& b) {
    return a.sequence == b.sequence && a.epoch == b.epoch && a.source_time_ns == b.source_time_ns &&
        a.causal_sequence == b.causal_sequence && a.local_state == b.local_state && a.origin == b.origin;
}
can::ActuatorMetadata metadata(const can::SteeringMessage& m) {
    return {m.sequence, m.epoch, m.source_time_ns, m.causal_sequence, m.local_state, m.origin};
}
const central::CommandContext& context(const central::ScopedCommands& c) {
    return std::visit([](const auto& scoped) -> const central::CommandContext& { return scoped; }, c);
}
can::ActuatorMetadata metadata(const central::ScopedCommands& c) {
    if (const auto* front = std::get_if<central::FrontCommands>(&c)) return metadata(front->steering);
    return std::get<central::RearCommands>(c).drive;
}
bool same_command(const central::ScopedCommands& a, const central::ScopedCommands& b) {
    const auto& x = context(a); const auto& y = context(b);
    if (a.index() != b.index() || !central::same_vehicle_request(x.parent, y.parent) ||
        x.oldest_input_time_ns != y.oldest_input_time_ns || x.expires_at_ns != y.expires_at_ns ||
        !same_meta(metadata(a), metadata(b))) return false;
    if (const auto* f = std::get_if<central::FrontCommands>(&a)) {
        const auto& g = std::get<central::FrontCommands>(b);
        return f->steering.angle_rad == g.steering.angle_rad && f->brake.pressure_pa == g.brake.pressure_pa;
    }
    return std::get<central::RearCommands>(a).drive.torque_nm == std::get<central::RearCommands>(b).drive.torque_nm;
}
bool fresh(std::uint64_t source, std::uint64_t enable, std::uint64_t now, std::uint64_t age) {
    return source >= enable && source <= now && now-source <= age;
}
bool valid_parent(const central::VehicleRequest& p, std::uint64_t enable, std::uint64_t now, std::uint64_t age) {
    return fresh(p.source_time_ns, enable, now, age) && p.expires_at_ns > now &&
        p.expires_at_ns > p.source_time_ns && p.expires_at_ns-p.source_time_ns <= 60000000ULL &&
        std::isfinite(p.acceleration_mps2) && p.acceleration_mps2 >= -5 && p.acceleration_mps2 <= 2 &&
        std::isfinite(p.curvature_inv_m) && std::abs(p.curvature_inv_m) <= 1 &&
        std::isfinite(p.braking_demand) && p.braking_demand >= 0 && p.braking_demand <= 1;
}
AdmissionResult validate_payload(const central::ScopedCommands& c, const AdmissionConfig& cfg) {
    if (const auto* front = std::get_if<central::FrontCommands>(&c)) {
        if (front->steering.kind != can::SteeringFrameKind::Command || front->brake.kind != can::BrakeFrameKind::Command ||
            !same_meta(metadata(front->steering), front->brake)) return AdmissionResult::InvalidPayload;
        if (!front->steering.angle_rad || !front->brake.pressure_pa) return AdmissionResult::InvalidPayload;
        const auto angle = can::encode_steering_angle(*front->steering.angle_rad);
        const auto pressure = can::encode_brake_pressure(*front->brake.pressure_pa);
        if (!can::actuator_value_in_range(*front->steering.angle_rad, {-cfg.max_angle_rad, cfg.max_angle_rad}) ||
            !can::actuator_value_in_range(*front->brake.pressure_pa, {0, cfg.max_pressure_pa}) || !angle || !pressure ||
            !can::actuator_value_in_range(*can::decode_steering_angle(*angle), {-cfg.max_angle_rad, cfg.max_angle_rad}) ||
            !can::actuator_value_in_range(*can::decode_brake_pressure(*pressure), {0, cfg.max_pressure_pa})) return AdmissionResult::ValueOutOfRange;
    } else {
        const auto& drive = std::get<central::RearCommands>(c).drive;
        if (drive.kind != can::DriveFrameKind::Command || !drive.torque_nm || drive.wheel_speed || drive.regen_capability ||
            drive.regen_limit_reason != can::DriveRegenLimitReason::InputsInvalid) return AdmissionResult::InvalidPayload;
        const auto torque = can::encode_drive_torque(*drive.torque_nm);
        if (!can::actuator_value_in_range(*drive.torque_nm, {-cfg.max_regen_nm, cfg.max_propulsion_nm}) || !torque ||
            !can::actuator_value_in_range(*can::decode_drive_torque(*torque), {-cfg.max_regen_nm, cfg.max_propulsion_nm})) return AdmissionResult::ValueOutOfRange;
    }
    const auto m = metadata(c);
    if (m.origin != can::ActuatorOrigin::NormalPath || m.local_state != can::ActuatorLocalState::Normal) return AdmissionResult::ModeRejected;
    return AdmissionResult::Accepted;
}
}  // namespace

CommandAdmission::CommandAdmission(ZoneScope scope, const AdmissionConfig& config) : scope_(scope), config_(config) {
    if ((scope != ZoneScope::Front && scope != ZoneScope::Rear) || !valid_config(config_)) {
        throw std::invalid_argument("invalid Zone admission configuration");
    }
}
bool CommandAdmission::start_session(std::uint32_t epoch, std::uint64_t enable) {
    if (epoch == 0 || (epoch_ != 0 && (epoch <= epoch_ || enable < last_observed_ns_))) return false;
    epoch_ = epoch; enable_ns_ = last_observed_ns_ = enable; armed_ns_ = 0;
    authorized_.reset(); accepted_.reset(); last_valid_rx_ns_.reset();
    decision_ = {}; decision_.state = AdmissionState::Idle;
    return true;
}
void CommandAdmission::fail(AdmissionFault fault) {
    if (decision_.fault == AdmissionFault::None || fault == AdmissionFault::ClockError) decision_.fault = fault;
    decision_.state = AdmissionState::FailSafe; decision_.protection_required = true;
}
bool CommandAdmission::advance(std::uint64_t now) {
    if (decision_.state == AdmissionState::NotInitialized) return false;
    if (now < last_observed_ns_) fail(AdmissionFault::ClockError);
    else last_observed_ns_ = now;
    if (decision_.state == AdmissionState::FailSafe) return false;
    // Check previous authority before considering a late fresh packet/root.
    if (accepted_ && now >= context(*accepted_).expires_at_ns) fail(AdmissionFault::CommandExpired);
    if (decision_.state == AdmissionState::Waiting && now-armed_ns_ >= config_.command_timeout_ns) fail(AdmissionFault::CommandTimeout);
    return decision_.state != AdmissionState::FailSafe;
}
bool CommandAdmission::arm(std::uint64_t now) {
    if (!advance(now) || decision_.state != AdmissionState::Idle) return false;
    armed_ns_ = now; decision_.state = AdmissionState::Waiting; return true;
}
AdmissionResult CommandAdmission::authorize_request(const central::VehicleRequest& p, std::uint64_t now) {
    if (decision_.state == AdmissionState::NotInitialized) return AdmissionResult::NotInitialized;
    if (!advance(now)) return AdmissionResult::Latched;
    if (p.epoch != epoch_) return AdmissionResult::EpochMismatch;
    if (p.expires_at_ns <= now) return AdmissionResult::Expired;
    if (!valid_parent(p, enable_ns_, now, config_.parent_source_age_ns)) return AdmissionResult::InvalidContext;
    if (authorized_ && p.sequence == authorized_->sequence) {
        return central::same_vehicle_request(p, *authorized_) ? AdmissionResult::Unchanged : AdmissionResult::MutationRejected;
    }
    if (!can::actuator_sequence_progresses(authorized_ ? std::optional<std::uint32_t>{authorized_->sequence} : std::nullopt, p.sequence)) {
        return AdmissionResult::SequenceRejected;
    }
    if (authorized_ && p.source_time_ns <= authorized_->source_time_ns) return AdmissionResult::SourceNotIncreasing;
    authorized_ = p; return AdmissionResult::Accepted;
}
AdmissionResult CommandAdmission::receive(const central::ScopedCommands& c, std::uint64_t now) {
    if (decision_.state == AdmissionState::NotInitialized) return AdmissionResult::NotInitialized;
    if (!advance(now)) return AdmissionResult::Latched;
    if (decision_.state == AdmissionState::Idle) return AdmissionResult::NotArmed;
    if ((scope_ == ZoneScope::Front) != std::holds_alternative<central::FrontCommands>(c)) return AdmissionResult::WrongScope;
    const auto payload = validate_payload(c, config_);
    if (payload != AdmissionResult::Accepted) return payload;
    const auto m = metadata(c); const auto& ctx = context(c); const auto& p = ctx.parent;
    if (m.epoch != epoch_ || p.epoch != epoch_) return AdmissionResult::EpochMismatch;
    if (!authorized_) return AdmissionResult::ParentUnavailable;
    if (!central::same_vehicle_request(p, *authorized_) || m.causal_sequence != p.sequence) return AdmissionResult::ParentMismatch;
    if (ctx.expires_at_ns <= now || p.expires_at_ns <= now) return AdmissionResult::Expired;
    if (!valid_parent(p, enable_ns_, now, config_.parent_source_age_ns) ||
        !fresh(m.source_time_ns, enable_ns_, now, config_.command_source_age_ns) || m.source_time_ns < p.source_time_ns ||
        !fresh(ctx.oldest_input_time_ns, enable_ns_, now, config_.dependency_age_ns) || ctx.oldest_input_time_ns > p.source_time_ns ||
        ctx.expires_at_ns > std::min({p.expires_at_ns, add(p.source_time_ns, config_.parent_source_age_ns+1),
            add(m.source_time_ns, config_.command_source_age_ns+1), add(ctx.oldest_input_time_ns, config_.dependency_age_ns+1)})) {
        return AdmissionResult::InvalidContext;
    }
    const auto previous = accepted_ ? std::optional<can::ActuatorMetadata>{metadata(*accepted_)} : std::nullopt;
    if (previous && m.sequence == previous->sequence) {
        return same_command(c, *accepted_) ? AdmissionResult::Unchanged : AdmissionResult::MutationRejected;
    }
    if (!can::actuator_sequence_progresses(previous ? std::optional<std::uint32_t>{previous->sequence} : std::nullopt, m.sequence)) {
        return AdmissionResult::SequenceRejected;
    }
    if (previous && m.source_time_ns <= previous->source_time_ns) return AdmissionResult::SourceNotIncreasing;
    accepted_ = c; last_valid_rx_ns_ = now; decision_.state = AdmissionState::Active;
    return AdmissionResult::Accepted;
}
AdmissionDecision CommandAdmission::poll(std::uint64_t now) { advance(now); return decision_; }
void CommandAdmission::mark_continuity_lost(std::uint64_t now) {
    if (advance(now)) fail(AdmissionFault::ContinuityLost);
}
std::optional<central::ScopedCommands> CommandAdmission::current_command(std::uint64_t now) {
    if (!advance(now) || decision_.state != AdmissionState::Active) return std::nullopt;
    return accepted_;
}
}  // namespace stratadrive::zone
