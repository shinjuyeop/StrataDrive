#include "run_lease_gate.hpp"
#include "actuator_receiver_state.hpp"
#include <limits>

namespace stratadrive::remote {
std::optional<TimeBounds> mapped_time(std::uint64_t source,const ClockAgreement& a) {
    if(!a.established || !a.local_domain || !a.source_domain) return std::nullopt;
    auto center=source;
    if(a.offset_ns>=0) {
        const auto delta=static_cast<std::uint64_t>(a.offset_ns);
        if(delta>UINT64_MAX-center) return std::nullopt;
        center+=delta;
    } else {
        const auto delta=static_cast<std::uint64_t>(-(a.offset_ns+1))+1;
        if(delta>center) return std::nullopt;
        center-=delta;
    }
    if(a.uncertainty_ns>center || a.uncertainty_ns>UINT64_MAX-center) return std::nullopt;
    return TimeBounds{center-a.uncertainty_ns,center+a.uncertainty_ns};
}
bool source_and_expiry_current(std::uint64_t source,std::uint64_t expiry,std::uint64_t now,std::uint64_t age,const ClockAgreement& a) {
    const auto s=mapped_time(source,a),e=mapped_time(expiry,a);
    return source<expiry && s && e && s->latest<=now && now-s->earliest<=age && now<e->earliest;
}
bool RunLeaseGate::bind(const session::Plan& plan,const ClockAgreement& a,std::uint64_t now) {
    if(!a.established || !a.local_domain || a.local_domain!=a.source_domain || a.offset_ns || a.uncertainty_ns ||
       !plan.epoch || plan.epoch<=plan_.epoch || now<observed_ || now<plan.enable_ns || now>=plan.commit_deadline_ns ||
       plan.requested_ns>plan.enable_ns || plan.enable_ns>=plan.commit_deadline_ns || plan.commit_deadline_ns>plan.prepare_deadline_ns ||
       plan.commit_deadline_ns>UINT64_MAX-session::kMessageAgeNs) return false;
    plan_=plan;clock_=a;observed_=now;acquisition_deadline_=plan.commit_deadline_ns+session::kMessageAgeNs;
    accepted_.reset();fault_=RunLeaseFault::None;return true;
}
bool RunLeaseGate::observe(const session::SessionParticipant& local,std::uint64_t now) {
    if(!plan_.epoch) return false;
    if(now<observed_) fault_=RunLeaseFault::Clock;
    else observed_=now;
    if(fault_!=RunLeaseFault::None) return false;
    if(local.fault()!=session::ParticipantFault::None) fault_=RunLeaseFault::Session;
    else if(!accepted_ && now>=acquisition_deadline_) fault_=RunLeaseFault::AcquisitionTimeout;
    else if(accepted_ && (now>=accepted_->expires_at_ns || now-accepted_->source_time_ns>session::kMessageAgeNs)) fault_=RunLeaseFault::Expired;
    return fault_==RunLeaseFault::None;
}
bool RunLeaseGate::receive(const RunLease& lease,std::uint64_t domain,const session::SessionParticipant& local,std::uint64_t now) {
    if(!observe(local,now) || !local.run_enabled() || domain!=clock_.source_domain || !session::same_plan(lease.plan,plan_) ||
       lease.source_time_ns<plan_.enable_ns || lease.expires_at_ns<=lease.source_time_ns ||
       lease.expires_at_ns-lease.source_time_ns>kRunLeaseLifetimeNs ||
       !source_and_expiry_current(lease.source_time_ns,lease.expires_at_ns,now,session::kMessageAgeNs,clock_) ||
       !can::actuator_sequence_progresses(accepted_?std::optional<std::uint32_t>{accepted_->sequence}:std::nullopt,lease.sequence) ||
       (accepted_ && lease.source_time_ns<=accepted_->source_time_ns)) return false;
    accepted_=lease;return true;
}
bool RunLeaseGate::allows(const session::SessionParticipant& local,std::uint64_t now) {
    return observe(local,now) && local.run_enabled() && accepted_.has_value();
}
void RunLeaseGate::protect(std::uint32_t epoch) { if(epoch && epoch==plan_.epoch && fault_==RunLeaseFault::None) fault_=RunLeaseFault::Protection; }
bool ProtectionReceipt::expect(const ProtectionRequest& r,session::Role peer,std::uint64_t domain,std::uint64_t now) {
    if(!domain || !r.epoch || !r.token || peer>=session::Role::CentralIngress || r.source_time_ns>now || now>=r.deadline_ns ||
        now-r.source_time_ns>session::kMessageAgeNs || r.deadline_ns<=r.source_time_ns ||
        r.deadline_ns-r.source_time_ns>transport::kResultBudgetNs) return false;
    request_=r;peer_=peer;clock_domain_=domain;selected_ns_.reset();return true;
}
bool ProtectionReceipt::receive(const OwnerMessage& m,std::uint64_t now) {
    const auto* ack=std::get_if<ProtectionAck>(&m.payload);
    if(!request_ || !ack || m.from!=peer_ || m.to!=session::Role::CentralIngress || m.clock_domain!=clock_domain_) return false;
    const auto& a=ack->request;const auto& r=*request_;
    if(a.epoch!=r.epoch || a.token!=r.token || a.source_time_ns!=r.source_time_ns || a.deadline_ns!=r.deadline_ns ||
       !ack->selected || ack->selected_ns<r.source_time_ns || ack->selected_ns>now || now>=r.deadline_ns) return false;
    if(!selected_ns_) selected_ns_=ack->selected_ns;
    return *selected_ns_==ack->selected_ns; // immutable duplicate, not a new selection time
}
} // namespace stratadrive::remote
