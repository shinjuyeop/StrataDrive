#include "control_allocation.hpp"

#include "brake_pressure_codec.hpp"
#include "drive_value_codec.hpp"
#include "steering_angle_codec.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace stratadrive::central {
namespace {
constexpr std::uint64_t kPeriodNs = 20000000ULL, kRequestLifetimeNs = 60000000ULL;
std::uint64_t add(std::uint64_t time, std::uint64_t delta) {
    return std::numeric_limits<std::uint64_t>::max() - time < delta ?
        std::numeric_limits<std::uint64_t>::max() : time + delta;
}
double floor_to(double value, double step) { return std::floor(value/step)*step; }
bool valid_config(const AllocationConfig& c) {
    for (const auto value : {c.mass_kg, c.wheel_radius_m, c.wheelbase_m, c.friction_nm_per_pa,
        c.max_pressure_pa, c.max_steering_rad, c.max_propulsion_nm, c.max_regen_nm,
        c.max_service_braking_nm, c.max_acceleration_mps2, c.max_deceleration_mps2, c.max_curvature_inv_m,
        c.max_wheel_speed_rad_s, c.low_speed_enter_rad_s, c.low_speed_exit_rad_s, c.hold_speed_rad_s,
        c.hold_braking_nm, c.release_friction_nm, c.release_motor_nm, c.response_tolerance_nm,
        c.motoring_efficiency_lower_bound, c.copper_loss_w_per_nm2, c.propulsion_mechanical_power_w, c.regen_mechanical_power_w}) {
        if (!std::isfinite(value) || value <= 0) return false;
    }
    const auto& t = c.readiness;
    return std::isfinite(c.reserve_power_w) && c.reserve_power_w >= 0 && c.motoring_efficiency_lower_bound <= 1 &&
        c.max_pressure_pa <= can::kBrakePressureWireMaxPa && c.max_steering_rad <= can::kAngleWireMaxRad &&
        c.max_propulsion_nm <= can::kDriveTorqueWireMaxNm && c.max_regen_nm <= can::kDriveTorqueWireMaxNm &&
        c.max_wheel_speed_rad_s <= can::kDriveWheelSpeedWireMaxRadS &&
        c.hold_speed_rad_s < c.low_speed_enter_rad_s && c.low_speed_enter_rad_s < c.low_speed_exit_rad_s &&
        c.low_speed_exit_rad_s < c.max_wheel_speed_rad_s &&
        c.hold_braking_nm <= c.friction_nm_per_pa*c.max_pressure_pa &&
        std::isfinite(c.friction_nm_per_pa*c.max_pressure_pa) &&
        std::isfinite(c.mass_kg*c.wheel_radius_m*std::max(c.max_acceleration_mps2, c.max_deceleration_mps2)) &&
        std::isfinite(c.wheelbase_m*c.max_curvature_inv_m) &&
        t.zone_source_age_ns > 0 && t.zone_source_age_ns <= 30000000ULL &&
        t.actual_source_age_ns > 0 && t.actual_source_age_ns <= 30000000ULL &&
        t.bms_source_age_ns > 0 && t.bms_source_age_ns <= 50000000ULL &&
        t.bms_dependency_age_ns > 0 && t.bms_dependency_age_ns <= 70000000ULL &&
        c.max_tick_gap_ns >= kPeriodNs && c.max_tick_gap_ns <= 30000000ULL &&
        c.request_source_age_ns > 0 && c.request_source_age_ns <= 30000000ULL &&
        c.feedback_skew_ns > 0 && c.feedback_skew_ns <= 20000000ULL && c.response_dwell_ns > 0;
}
bool fresh(std::uint64_t time, std::uint64_t start, std::uint64_t now, std::uint64_t age) {
    return time >= start && time <= now && now-time <= age;
}
}  // namespace
ControlAllocation::ControlAllocation(const AllocationConfig& config) : config_(config) {
    if (!valid_config(config_)) throw std::invalid_argument("invalid control-allocation configuration");
}
bool ControlAllocation::start_session(std::uint32_t epoch, std::uint64_t enable) {
    if (epoch == 0 || (epoch_ != 0 && (epoch <= epoch_ || enable < last_observed_ns_))) return false;
    epoch_ = epoch; enable_ns_ = last_observed_ns_ = enable; sequence_ = 0;
    last_tick_ns_.reset(); critical_expiry_ns_.reset(); regen_expiry_ns_.reset(); request_.reset(); deficit_ = {}; excess_ = {};
    armed_ = stopped_ = braking_ = low_speed_ = holding_ = false; episode_regen_nm_ = 0;
    decision_ = {}; decision_.state = AllocationState::Waiting;
    return true;
}
void ControlAllocation::fail(AllocationFault fault) {
    if (decision_.fault == AllocationFault::None || fault == AllocationFault::ClockError) decision_.fault = fault;
    decision_.state = AllocationState::FailSafe; decision_.protection_required = true;
}
bool ControlAllocation::live_request(std::uint64_t now) const {
    return request_ && now < request_->expires_at_ns && now-request_->source_time_ns <= config_.request_source_age_ns;
}
bool ControlAllocation::advance(std::uint64_t now) {
    if (epoch_ == 0 || stopped_) return false;
    if (now < last_observed_ns_ || now == std::numeric_limits<std::uint64_t>::max()) {
        fail(AllocationFault::ClockError); stopped_ = true; return false;
    }
    last_observed_ns_ = now;
    if (now-last_tick_ns_.value_or(enable_ns_) > config_.max_tick_gap_ns) fail(AllocationFault::ControlDeadline);
    if (armed_) {
        if (!live_request(now)) fail(AllocationFault::RequestLost);
        else if (critical_expiry_ns_ && now >= *critical_expiry_ns_) fail(AllocationFault::SupportExpired);
        // Optional capability loss removes regen authority, not fresh critical
        // torque/Brake feedback or the friction-only normal path.
        if (regen_expiry_ns_ && now >= *regen_expiry_ns_) episode_regen_nm_ = 0;
    }
    return true;
}
AllocationReceiveDecision ControlAllocation::receive_request(const VehicleRequest& request, std::uint64_t now) {
    if (epoch_ == 0) return AllocationReceiveDecision::NotInitialized;
    if (!advance(now) || decision_.state == AllocationState::FailSafe) return AllocationReceiveDecision::Latched;
    if (request.epoch != epoch_) return AllocationReceiveDecision::EpochMismatch;
    if (!std::isfinite(request.acceleration_mps2) || !std::isfinite(request.curvature_inv_m) ||
        !std::isfinite(request.braking_demand) || request.acceleration_mps2 < -config_.max_deceleration_mps2 ||
        request.acceleration_mps2 > config_.max_acceleration_mps2 || std::abs(request.curvature_inv_m) > config_.max_curvature_inv_m ||
        request.braking_demand < 0 || request.braking_demand > 1 || request.source_time_ns < enable_ns_ || request.source_time_ns > now ||
        request.expires_at_ns <= request.source_time_ns || request.expires_at_ns-request.source_time_ns > kRequestLifetimeNs) {
        return AllocationReceiveDecision::Invalid;
    }
    if (!fresh(request.source_time_ns, enable_ns_, now, config_.request_source_age_ns) || now >= request.expires_at_ns) return AllocationReceiveDecision::Expired;
    if (request_ && request.sequence == request_->sequence) {
        return same_vehicle_request(request, *request_) ? AllocationReceiveDecision::Unchanged : AllocationReceiveDecision::MutationRejected;
    }
    const auto previous = request_ ? std::optional<std::uint32_t>{request_->sequence} : std::nullopt;
    if (!can::actuator_sequence_progresses(previous, request.sequence) ||
        (request_ && request.source_time_ns <= request_->source_time_ns)) return AllocationReceiveDecision::SequenceRejected;
    request_ = request; return AllocationReceiveDecision::Accepted;
}
void ControlAllocation::mark_continuity_lost(std::uint64_t now) { if (advance(now)) fail(AllocationFault::ContinuityLost); }
bool ControlAllocation::Dwell::observe(bool outside, std::uint64_t source, std::uint64_t duration) {
    if (!outside) { first.reset(); return false; }
    if (!first || source < *first) first = source;
    return source-*first >= duration;
}
bool ControlAllocation::permission_valid(const AllocationInputs& in, std::uint64_t now) const {
    if (in.management.state != VehicleManagementState::Normal || !in.management.normal_allowed ||
        in.management.fault != VehicleManagementFault::None || !in.permission || !in.permission_parent) return false;
    const auto& message = in.permission->message;
    const auto* grant = std::get_if<can::BmsDriveGrant>(&message.content);
    const auto& parent = *in.permission_parent;
    return grant && can::bms_permission_allows_normal(*in.permission) && message.local_state == can::ActuatorLocalState::Normal &&
        message.epoch == epoch_ && fresh(message.source_time_ns, enable_ns_, now, config_.readiness.bms_source_age_ns) &&
        parent.epoch == epoch_ && parent.sequence == message.causal_sequence && parent.source_time_ns <= message.source_time_ns &&
        fresh(parent.source_time_ns, enable_ns_, now, config_.readiness.bms_source_age_ns) && now < parent.expires_at_ns &&
        parent.expires_at_ns-parent.source_time_ns <= can::kBmsMaxLifetimeNs &&
        now < grant->expires_at_ns && grant->expires_at_ns <= parent.expires_at_ns &&
        grant->expires_at_ns-message.source_time_ns <= can::kBmsMaxLifetimeNs &&
        grant->power_status_source_time_ns <= message.source_time_ns &&
        fresh(grant->power_status_source_time_ns, enable_ns_, now, config_.readiness.bms_source_age_ns) &&
        grant->input_time_ns <= grant->power_status_source_time_ns &&
        fresh(grant->input_time_ns, enable_ns_, now, config_.readiness.bms_dependency_age_ns);
}
std::optional<AllocatedCommands> ControlAllocation::tick(const AllocationInputs& in, std::uint64_t now) {
    if (!advance(now)) return std::nullopt;
    if (last_tick_ns_ && now-*last_tick_ns_ < kPeriodNs) return std::nullopt;
    last_tick_ns_ = now;
    if (decision_.state == AllocationState::FailSafe) return std::nullopt;
    if (in.feedback.epoch != epoch_ || in.feedback.session_enable_ns != enable_ns_) fail(AllocationFault::SessionMismatch);
    if (!permission_valid(in, now)) {
        if (armed_ || in.management.state == VehicleManagementState::FailSafe) fail(AllocationFault::PermissionUnavailable);
        return std::nullopt;
    }
    const auto readiness = evaluate_normal_drive_readiness(in.feedback, now, config_.readiness);
    if (!readiness.ready()) fail(AllocationFault::CriticalFeedback);
    if (decision_.state == AllocationState::FailSafe || !live_request(now)) return std::nullopt;
    const auto& drive = *in.feedback.rear.drive_actual; const auto& brake = *in.feedback.front.brake_actual;
    const auto& speed = drive.wheel_speed;
    if (!speed || !std::isfinite(speed->value_rad_s) || speed->value_rad_s < 0 || speed->value_rad_s > config_.max_wheel_speed_rad_s ||
        !fresh(speed->source_time_ns, enable_ns_, now, config_.readiness.actual_source_age_ns)) fail(AllocationFault::WheelSpeedUnavailable);
    if (!can::actuator_value_in_range(*drive.torque_nm, {-config_.max_regen_nm, config_.max_propulsion_nm}) ||
        !can::actuator_value_in_range(*brake.pressure_pa, {0, config_.max_pressure_pa})) fail(AllocationFault::CriticalFeedback);
    const auto oldest_actual = std::min(drive.source_time_ns, brake.source_time_ns);
    const auto newest_actual = std::max(drive.source_time_ns, brake.source_time_ns);
    if (newest_actual-oldest_actual > config_.feedback_skew_ns) fail(AllocationFault::FeedbackSkew);
    if (decision_.state == AllocationState::FailSafe) return std::nullopt;

    decision_ = {}; decision_.state = AllocationState::Active;
    const auto omega = speed->value_rad_s;
    if (omega <= config_.low_speed_enter_rad_s) low_speed_ = true;
    else if (omega >= config_.low_speed_exit_rad_s) low_speed_ = false;
    const auto& limits = std::get<can::BmsPowerLimits>(in.feedback.rear.power_limits->message.content);
    auto expiry = std::min({request_->expires_at_ns, add(request_->source_time_ns, config_.request_source_age_ns+1),
        std::get<can::BmsDriveGrant>(in.permission->message.content).expires_at_ns});
    auto oldest = std::min({*readiness.oldest_input_time_ns, request_->source_time_ns,
        in.permission->message.source_time_ns, in.permission_parent->source_time_ns,
        std::get<can::BmsDriveGrant>(in.permission->message.content).input_time_ns, speed->source_time_ns});
    const auto bound = [&](std::uint64_t source, std::uint64_t age) {
        expiry = std::min(expiry, add(source, age+1)); oldest = std::min(oldest, source);
    };
    const auto& t = config_.readiness;
    bound(in.feedback.front.health->source_time_ns, t.zone_source_age_ns); bound(in.feedback.rear.health->source_time_ns, t.zone_source_age_ns);
    bound(in.feedback.front.steering_actual->source_time_ns, t.actual_source_age_ns);
    bound(drive.source_time_ns, t.actual_source_age_ns); bound(brake.source_time_ns, t.actual_source_age_ns);
    bound(speed->source_time_ns, t.actual_source_age_ns);
    bound(in.feedback.rear.power_status->message.source_time_ns, t.bms_source_age_ns);
    bound(std::get<can::BmsPowerStatus>(in.feedback.rear.power_status->message.content).input_time_ns, t.bms_dependency_age_ns);
    bound(in.feedback.rear.power_limits->message.source_time_ns, t.bms_source_age_ns); bound(limits.input_time_ns, t.bms_dependency_age_ns);
    bound(in.permission->message.source_time_ns, t.bms_source_age_ns);
    bound(in.permission_parent->source_time_ns, t.bms_source_age_ns);
    bound(std::get<can::BmsDriveGrant>(in.permission->message.content).power_status_source_time_ns, t.bms_source_age_ns);
    bound(std::get<can::BmsDriveGrant>(in.permission->message.content).input_time_ns, t.bms_dependency_age_ns);
    const auto critical_expiry = expiry;
    std::optional<std::uint64_t> regen_expiry;

    auto regen_limit = 0.0;
    const auto& capability = drive.regen_capability;
    if (capability) {
        if (!std::isfinite(capability->torque_limit_nm) || capability->torque_limit_nm < 0 ||
            capability->torque_limit_nm > config_.max_regen_nm || capability->input_time_ns > capability->source_time_ns ||
            capability->input_time_ns < enable_ns_ || capability->source_time_ns > now ||
            (drive.regen_limit_reason == can::DriveRegenLimitReason::Disabled && capability->torque_limit_nm != 0) ||
            drive.regen_limit_reason == can::DriveRegenLimitReason::InputsInvalid) decision_.regen = RegenAvailability::Invalid;
        else if (!fresh(capability->source_time_ns, enable_ns_, now, t.actual_source_age_ns) ||
            !fresh(capability->input_time_ns, enable_ns_, now, t.bms_dependency_age_ns)) decision_.regen = RegenAvailability::Stale;
        else if (std::min(add(capability->source_time_ns,t.actual_source_age_ns+1),
            add(capability->input_time_ns,t.bms_dependency_age_ns+1)) <= add(now,kPeriodNs)) {
            // Do not knowingly issue a negative target whose supporting sample
            // expires before the next nominal allocation opportunity.
            decision_.regen = RegenAvailability::Expiring;
        }
        else {
            decision_.regen = RegenAvailability::Usable;
            regen_limit = omega > 0 ? std::min({capability->torque_limit_nm, *limits.charge_power_w/omega,
                config_.regen_mechanical_power_w/omega}) : 0;
        }
    }
    if (low_speed_) { regen_limit = 0; decision_.regen = RegenAvailability::LowSpeed; }
    regen_limit = floor_to(regen_limit, can::kDriveTorqueResolutionNm); decision_.regen_limit_nm = regen_limit;
    const auto mass_radius = config_.mass_kg*config_.wheel_radius_m;
    auto braking = std::max(std::max(0.0, -request_->acceleration_mps2)*mass_radius,
        request_->braking_demand*config_.max_service_braking_nm);
    if (!request_->standstill_hold) holding_ = false;
    else if (omega <= config_.hold_speed_rad_s) holding_ = true;
    // Once entered, a small speed rise/noise must not release an explicit hold.
    if (holding_) braking = std::max(braking, config_.hold_braking_nm);
    decision_.hold_active = holding_;
    const auto actual_friction = *brake.pressure_pa*config_.friction_nm_per_pa;
    const auto actual_regen = std::max(0.0, -*drive.torque_nm);
    const bool released = actual_friction <= config_.release_friction_nm && std::abs(*drive.torque_nm) <= config_.release_motor_nm;
    if (braking == 0 && released) braking_ = false;
    decision_.requested_braking_nm = braking;
    decision_.actual_braking_nm = actual_friction-*drive.torque_nm; // signed; positive residual propulsion is not braking
    decision_.actual_source_time_ns = oldest_actual;
    decision_.deficit_nm = std::max(0.0, braking-*decision_.actual_braking_nm);
    decision_.excess_nm = std::max(0.0, *decision_.actual_braking_nm-braking);
    double motor_target = 0, pressure_target = 0;
    if (braking > 0) {
        decision_.brake_priority = request_->acceleration_mps2 > 0;
        if (!braking_) { episode_regen_nm_ = std::min({braking, regen_limit, std::max(0.0, braking-actual_friction)}); braking_ = true; }
        else episode_regen_nm_ = std::min({episode_regen_nm_, braking, regen_limit});
        motor_target = -episode_regen_nm_;
        if (episode_regen_nm_ > 0) {
            bound(capability->source_time_ns, t.actual_source_age_ns); bound(capability->input_time_ns, t.bms_dependency_age_ns);
            regen_expiry = std::min(add(capability->source_time_ns,t.actual_source_age_ns+1),
                add(capability->input_time_ns,t.bms_dependency_age_ns+1));
        }
        // Reserve the selected regen share while it builds. When it contracts,
        // subtract still-observed residual regen, never count a command as actual.
        pressure_target = std::max(0.0, braking-std::max(episode_regen_nm_, actual_regen))/config_.friction_nm_per_pa;
        decision_.selected_regen_nm = episode_regen_nm_;
        decision_.capacity_deficit_nm = std::max(0.0, braking-episode_regen_nm_-config_.max_pressure_pa*config_.friction_nm_per_pa);
        if (decision_.capacity_deficit_nm > config_.response_tolerance_nm) fail(AllocationFault::BrakingCapacity);
    } else {
        episode_regen_nm_ = 0;
        decision_.propulsion_waiting_release = actual_friction > config_.release_friction_nm || *drive.torque_nm < -config_.release_motor_nm;
        const auto wanted = std::max(0.0, request_->acceleration_mps2)*mass_radius;
        const auto available = std::max(0.0, *limits.discharge_power_w-config_.reserve_power_w);
        const auto b = omega/config_.motoring_efficiency_lower_bound, a = config_.copper_loss_w_per_nm2;
        const auto electrical = available == 0 ? 0 : 2*available/(b+std::sqrt(b*b+4*a*available));
        const auto mechanical = omega > 0 ? config_.propulsion_mechanical_power_w/omega : config_.max_propulsion_nm;
        if (!decision_.propulsion_waiting_release) motor_target = std::min({wanted, electrical, mechanical, config_.max_propulsion_nm});
        decision_.propulsion_deficit_nm = std::max(0.0, wanted-motor_target);
    }
    const bool monitor_braking = braking > 0 || actual_friction > config_.release_friction_nm || actual_regen > config_.release_motor_nm;
    const bool under = monitor_braking && *decision_.deficit_nm > config_.response_tolerance_nm;
    const bool over = monitor_braking && *decision_.excess_nm > config_.response_tolerance_nm;
    decision_.response_pending = under || over;
    if (deficit_.observe(under, oldest_actual, config_.response_dwell_ns)) fail(AllocationFault::BrakingDeficit);
    if (excess_.observe(over, oldest_actual, config_.response_dwell_ns)) fail(AllocationFault::BrakingExcess);
    if (decision_.state == AllocationState::FailSafe) return std::nullopt;
    if (sequence_ > std::numeric_limits<std::uint32_t>::max()) { fail(AllocationFault::SequenceExhausted); stopped_ = true; return std::nullopt; }
    AllocatedCommands out; out.parent = *request_; out.expires_at_ns = expiry; out.oldest_input_time_ns = oldest;
    out.steering.kind = can::SteeringFrameKind::Command; out.brake.kind = can::BrakeFrameKind::Command; out.drive.kind = can::DriveFrameKind::Command;
    for (auto* message : {static_cast<can::ActuatorMetadata*>(&out.brake), static_cast<can::ActuatorMetadata*>(&out.drive)}) {
        message->epoch = epoch_; message->sequence = static_cast<std::uint32_t>(sequence_); message->source_time_ns = now;
        message->causal_sequence = request_->sequence; message->local_state = can::ActuatorLocalState::Normal; message->origin = can::ActuatorOrigin::NormalPath;
    }
    out.steering.epoch = epoch_; out.steering.sequence = static_cast<std::uint32_t>(sequence_); out.steering.source_time_ns = now;
    out.steering.causal_sequence = request_->sequence; out.steering.local_state = can::ActuatorLocalState::Normal; out.steering.origin = can::ActuatorOrigin::NormalPath;
    const auto angle = std::atan(config_.wheelbase_m*request_->curvature_inv_m);
    decision_.steering_limited = std::abs(angle) > config_.max_steering_rad;
    out.steering.angle_rad = std::copysign(floor_to(std::min(std::abs(angle), config_.max_steering_rad), can::kAngleResolutionRad), angle);
    out.brake.pressure_pa = floor_to(std::min(pressure_target, config_.max_pressure_pa), can::kBrakePressureResolutionPa);
    out.drive.torque_nm = std::copysign(floor_to(std::abs(motor_target), can::kDriveTorqueResolutionNm), motor_target);
    critical_expiry_ns_ = critical_expiry; regen_expiry_ns_ = regen_expiry; ++sequence_; armed_ = true;
    return out;
}
}  // namespace stratadrive::central
