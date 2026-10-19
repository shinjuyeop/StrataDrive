#include "normal_stop.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace stratadrive::central {
namespace {
constexpr std::uint64_t kMs=1000000;
std::uint64_t add(std::uint64_t a,std::uint64_t b) { return std::numeric_limits<std::uint64_t>::max()-a<b?std::numeric_limits<std::uint64_t>::max():a+b; }
bool same(const NormalStopRequest& a,const NormalStopRequest& b) {
    const auto& x=a.identity; const auto& y=b.identity;
    return x.epoch==y.epoch && x.sequence==y.sequence && x.source_time_ns==y.source_time_ns && x.expires_at_ns==y.expires_at_ns && a.curvature_inv_m==b.curvature_inv_m;
}
bool fresh(std::uint64_t source,std::uint64_t enable,std::uint64_t now) { return source>=enable && source<=now && now-source<=30*kMs; }
}
NormalStop::NormalStop(const NormalStopConfig& config):config_(config) {
    if(!std::isfinite(config.deceleration_mps2) || config.deceleration_mps2<=0 || config.deceleration_mps2>5 ||
        config.confirmation_ns<20*kMs || config.confirmation_ns>1000*kMs || config.braking_timeout_ns<=config.confirmation_ns ||
        config.shutdown_timeout_ns==0 || config.minimum_tick_interval_ns==0 || config.minimum_tick_interval_ns>10*kMs) throw std::invalid_argument("NormalStop configuration");
}
bool NormalStop::start_session(std::uint32_t epoch,std::uint64_t enable) {
    if(epoch==0 || epoch<=epoch_ || (epoch_!=0 && enable<observed_)) return false;
    epoch_=epoch; enable_=observed_=enable; decision_={NormalStopState::Waiting,NormalStopFault::None,false};
    request_.reset(); pending_request_.reset(); pending_.reset(); last_tick_.reset(); confirmation_start_.reset(); last_evidence_.reset(); return true;
}
void NormalStop::fail(NormalStopFault fault) {
    if(decision_.fault==NormalStopFault::None || fault==NormalStopFault::ClockError) decision_.fault=fault;
    decision_.state=NormalStopState::FailSafe; decision_.protection_required=true;
}
bool NormalStop::advance(std::uint64_t now) {
    if(epoch_==0) return false;
    if(now<observed_) { fail(NormalStopFault::ClockError); return false; }
    observed_=now;
    if(decision_.state==NormalStopState::FailSafe) return false;
    if(request_ && (now>=request_->identity.expires_at_ns || now-request_->identity.source_time_ns>50*kMs)) fail(NormalStopFault::RequestLost);
    if(last_tick_ && now-*last_tick_>30*kMs) fail(NormalStopFault::ControlDeadline);
    if(pending_ && decision_.state==NormalStopState::HandoffPending && now>=pending_->expires_at_ns) fail(NormalStopFault::HandoffExpired);
    return decision_.state!=NormalStopState::FailSafe;
}
bool NormalStop::begin(const NormalStopRequest& request,StopIssuerSeed seed,std::uint64_t now) {
    if(decision_.state!=NormalStopState::Waiting || receive_request(request,now)!=StopReceiveResult::Accepted) return false;
    lifecycle_next_=seed.lifecycle_next; vehicle_next_=seed.vehicle_next; phase_start_=now; decision_.state=NormalStopState::Braking; return true;
}
StopReceiveResult NormalStop::receive_request(const NormalStopRequest& request,std::uint64_t now) {
    if(!advance(now)) return StopReceiveResult::Latched;
    const auto& p=request.identity;
    if(p.epoch!=epoch_ || p.source_time_ns<enable_ || p.source_time_ns>now || now-p.source_time_ns>50*kMs ||
        p.expires_at_ns<=now || p.expires_at_ns<=p.source_time_ns || p.expires_at_ns-p.source_time_ns>80*kMs ||
        !std::isfinite(request.curvature_inv_m) || std::abs(request.curvature_inv_m)>1) return StopReceiveResult::Rejected;
    if(request_ && p.sequence==request_->identity.sequence) return same(request,*request_)?StopReceiveResult::Unchanged:StopReceiveResult::Rejected;
    if(!can::actuator_sequence_progresses(request_?std::optional<std::uint32_t>{request_->identity.sequence}:std::nullopt,p.sequence) ||
        (request_ && p.source_time_ns<=request_->identity.source_time_ns)) return StopReceiveResult::Rejected;
    request_=request; return StopReceiveResult::Accepted;
}
bool NormalStop::acknowledge_handoff(const ActuatorStopLease& lease,std::uint64_t now) {
    if(!advance(now) || decision_.state!=NormalStopState::HandoffPending || !pending_ || !same_stop_lease(lease,*pending_)) return false;
    decision_.state=NormalStopState::PowerDown; phase_start_=now; return true;
}
std::optional<NormalStopPlan> NormalStop::tick(const NormalDriveReadinessInputs& in,const VehicleManagementDecision& management,std::uint64_t now) {
    if(!advance(now) || decision_.state==NormalStopState::Waiting) return std::nullopt;
    if(last_tick_ && now-*last_tick_<config_.minimum_tick_interval_ns) return std::nullopt;
    last_tick_=now;
    const bool power_down=decision_.state==NormalStopState::PowerDown || decision_.state==NormalStopState::Complete;
    if(in.epoch!=epoch_ || in.session_enable_ns!=enable_ || !(power_down?evaluate_vehicle_input_health(in,now):evaluate_normal_drive_readiness(in,now)).ready()) fail(NormalStopFault::FeedbackUnavailable);
    if(management.fault!=VehicleManagementFault::None || (!power_down && !management.normal_allowed)) fail(NormalStopFault::UpstreamProtection);
    if(decision_.state==NormalStopState::FailSafe) return std::nullopt;
    const auto& d=*in.rear.drive_actual; const auto& b=*in.front.brake_actual;
    if(!d.wheel_speed || !fresh(d.wheel_speed->source_time_ns,enable_,now) || !std::isfinite(d.wheel_speed->value_rad_s) ||
        d.wheel_speed->value_rad_s<0 || d.wheel_speed->value_rad_s>100 || !d.torque_nm || !b.pressure_pa ||
        !can::actuator_value_in_range(*d.torque_nm,{-200,300}) || !can::actuator_value_in_range(*b.pressure_pa,{0,1500000})) {
        fail(NormalStopFault::FeedbackUnavailable); return std::nullopt;
    }
    const auto oldest=std::min({d.wheel_speed->source_time_ns,d.source_time_ns,b.source_time_ns});
    if(std::max({d.wheel_speed->source_time_ns,d.source_time_ns,b.source_time_ns})-oldest>20*kMs || (last_evidence_ && oldest<*last_evidence_)) {
        fail(NormalStopFault::FeedbackUnavailable); return std::nullopt;
    }
    const bool stopped=d.wheel_speed->value_rad_s<=kStopSpeedRadS && std::abs(*d.torque_nm)<=kStopTorqueNm && *b.pressure_pa>=kStopPressurePa;
    if(decision_.state==NormalStopState::Braking) {
        if(!stopped) confirmation_start_.reset();
        else if(!confirmation_start_) confirmation_start_=oldest;
        if(stopped && confirmation_start_ && oldest-*confirmation_start_>=config_.confirmation_ns) decision_.state=NormalStopState::HandoffPending;
        if(now-phase_start_>=config_.braking_timeout_ns) fail(NormalStopFault::BrakingTimeout);
    } else if(!stopped) fail(NormalStopFault::StopEvidenceLost);
    last_evidence_=oldest;
    if(decision_.state==NormalStopState::PowerDown) {
        const auto& p=std::get<can::BmsPowerStatus>(in.rear.power_status->message.content);
        if(management.state==VehicleManagementState::Stopped && management.power_off_confirmed && p.state==can::BmsPowerState::Off &&
            p.positive_contactor_closed==false && p.negative_contactor_closed==false && p.precharge_contactor_closed==false &&
            p.hv_bus_voltage_v && *p.hv_bus_voltage_v<=30) decision_.state=NormalStopState::Complete;
        else if(now-phase_start_>=config_.shutdown_timeout_ns) fail(NormalStopFault::ShutdownTimeout);
    }
    if(lifecycle_next_>std::numeric_limits<std::uint32_t>::max() || vehicle_next_>std::numeric_limits<std::uint32_t>::max()) fail(NormalStopFault::SequenceExhausted);
    if(decision_.state==NormalStopState::FailSafe) return std::nullopt;
    if(decision_.state==NormalStopState::HandoffPending && !pending_request_) pending_request_=request_;
    const auto& authority=decision_.state==NormalStopState::HandoffPending?*pending_request_:*request_;
    const auto& root=authority.identity;
    const auto expiry=std::min(root.expires_at_ns,add(root.source_time_ns,50*kMs+1));
    ActuatorStopLease lease{epoch_,root.sequence,root.source_time_ns,expiry};
    if(decision_.state==NormalStopState::HandoffPending) { if(!pending_) pending_=lease; lease=*pending_; }
    const bool shutdown=decision_.state==NormalStopState::PowerDown || decision_.state==NormalStopState::Complete;
    NormalStopPlan plan{decision_.state,authority,{{epoch_,static_cast<std::uint32_t>(lifecycle_next_++),now,expiry},shutdown?can::BmsPowerAction::Shutdown:can::BmsPowerAction::Enable},std::nullopt,lease,decision_.state!=NormalStopState::Braking};
    if(!shutdown) plan.vehicle=VehicleRequest{epoch_,static_cast<std::uint32_t>(vehicle_next_++),now,expiry,
        d.wheel_speed->value_rad_s>kStopSpeedRadS?-config_.deceleration_mps2:0,authority.curvature_inv_m,0,true};
    return plan;
}
} // namespace stratadrive::central
