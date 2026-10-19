#include "normal_stop_control.hpp"

#include <algorithm>

namespace stratadrive::simulation {
std::uint64_t NormalStopControl::observed(std::uint64_t now) const {
    return std::max({now,p_.front.observed_time_ns(),p_.rear.observed_time_ns(),p_.power.observed_time_ns()});
}
void NormalStopControl::protect(std::uint64_t now) {
    const auto time=observed(now);
    p_.steering.request_local_protection(time); p_.brake.request_local_protection(time); p_.drive.request_local_protection(time);
    p_.front.request_protection(); p_.rear.request_protection(); p_.power.mark_continuity_lost();
}
bool NormalStopControl::select(const central::NormalStopPlan& plan,std::uint64_t now) {
    if(!plan.handoff_required || (plan.state!=central::NormalStopState::HandoffPending && plan.state!=central::NormalStopState::PowerDown && plan.state!=central::NormalStopState::Complete)) return false;
    const auto& lease=plan.lease; const auto epoch=lease.epoch;
    const auto& ancestor=plan.ancestor.identity;
    if(lease.epoch!=ancestor.epoch || lease.sequence!=ancestor.sequence || lease.source_time_ns!=ancestor.source_time_ns ||
        lease.expires_at_ns>ancestor.expires_at_ns) return false;
    if(epoch==0 || p_.front.scope()!=zone::ZoneScope::Front || p_.rear.scope()!=zone::ZoneScope::Rear ||
        epoch!=p_.front.application_epoch() || epoch!=p_.rear.application_epoch() || epoch!=p_.power.application_epoch() ||
        epoch!=p_.steering.application_epoch() || epoch!=p_.brake.application_epoch() || epoch!=p_.drive.application_epoch() ||
        (allocation_ && epoch!=allocation_->application_epoch())) return false;
    const auto time=observed(now);
    // Leaves select first, before gateway callbacks can advance their clock.
    if(!p_.steering.select_normal_stop(lease,time) || !p_.brake.select_normal_stop(lease,time) || !p_.drive.select_normal_stop(lease,time) ||
        (allocation_ && !allocation_->select_normal_stop(lease,time)) || !p_.front.select_normal_stop(lease) || !p_.rear.select_normal_stop(lease) || !p_.power.select_normal_stop(lease) ||
        observed(time)>=lease.expires_at_ns) { protect(time); return false; }
    return true;
}
} // namespace stratadrive::simulation
