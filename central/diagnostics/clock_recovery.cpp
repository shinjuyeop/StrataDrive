#include "clock_recovery.hpp"
#include <algorithm>

namespace stratadrive::diagnostics {
bool ClockRecovery::remember(const Event& event) noexcept {
    if(event.kind!=Kind::Fault || event.key.code!=Code::Clock)return true;
    trust_.reset();first_=last_source_=0;
    for(auto& pending:pending_)if(pending && pending->fault.key==event.key){pending=Pending{event};return true;}
    for(auto& pending:pending_)if(!pending){pending=Pending{event};return true;}
    return false;
}
bool ClockRecovery::revalidate(const ClockRevalidation& value,Domain domain,std::uint64_t instance) noexcept {
    const auto& a=value.agreement;const auto& checked=value.checked;
    if(!value.revision || value.revision<=revision_ || !value.recovery_epoch ||
       !a.established || a.local_domain!=instance || a.source_domain!=instance || a.offset_ns || a.uncertainty_ns ||
       !checked.present || !checked.trusted || checked.domain!=domain || !instance || checked.instance!=instance ||
       !checked.ns || checked.ns<last_observed_ ||
       std::none_of(pending_.begin(),pending_.end(),[&](const auto& p){return p && !p->recovered && value.recovery_epoch>p->fault.session.epoch;}))return false;
    trust_=value;revision_=value.revision;first_=last_source_=0;last_observed_=checked.ns;
    for(auto& p:pending_)if(p)p->ready=false;
    return true;
}
void ClockRecovery::observe(const ClockRecoverySample& value) noexcept {
    for(auto& p:pending_)if(p)p->ready=false;
    if(!trust_)return;
    const auto& checked=trust_->checked;const auto& plan=value.released;
    const auto valid_stamp=[&](const Stamp& s){return s.present && s.trusted && s.domain==checked.domain && s.instance==checked.instance;};
    if(!valid_stamp(value.observed) || value.observed.ns<last_observed_) {
        trust_.reset();first_=last_source_=0;return; // another clock fault requires another explicit trust revision
    }
    last_observed_=value.observed.ns;
    const bool released=value.session.run && value.session.epoch==trust_->recovery_epoch && plan.epoch==value.session.epoch &&
        plan.requested_ns>=checked.ns && plan.enable_ns>=plan.requested_ns && plan.enable_ns-plan.requested_ns>=session::kInitLeadNs &&
        plan.prepare_deadline_ns>=plan.requested_ns && plan.prepare_deadline_ns-plan.requested_ns==session::kPrepareBudgetNs &&
        plan.commit_deadline_ns>plan.enable_ns && plan.commit_deadline_ns-plan.enable_ns<=session::kInitWindowNs && plan.commit_deadline_ns<=plan.prepare_deadline_ns &&
        value.release_mask==255 && value.normal_gate && value.native_healthy;
    if(!released || !valid_stamp(value.source) || value.source.ns<plan.enable_ns || value.source.ns>value.observed.ns ||
       value.observed.ns-value.source.ns>max_gap_ns || value.source.ns<last_source_) {
        first_=last_source_=0;return;
    }
    if(last_source_ && (!(current_.session==value.session) || !session::same_plan(current_.released,plan) ||
       value.observed.ns-last_source_>max_gap_ns))first_=0;
    if(value.source.ns==last_source_)return; // cached data cannot extend the uninterrupted window
    if(!first_)first_=value.source.ns;
    last_source_=value.source.ns;current_=value;
    if(last_source_-first_<window_ns)return;
    for(auto& p:pending_)if(p && !p->recovered && p->fault.session.run==value.session.run &&
       value.session.epoch>p->fault.session.epoch)p->ready=true;
}
std::optional<Event> ClockRecovery::take_ready() noexcept {
    if(!trust_)return {};
    for(auto& pending:pending_)if(pending && pending->ready && !pending->recovered) {
        pending->ready=false;pending->recovered=true;
        Event e;e.kind=Kind::Observation;e.key=pending->fault.key;e.occurrence=pending->fault.occurrence;e.related=pending->fault.id;
        e.proof=Proof::Control;e.latch=Latch::Clear;e.session=current_.session;e.session_enable=current_.source;e.session_enable.ns=current_.released.enable_ns;
        e.profile=pending->fault.profile;e.requirements=pending->fault.requirements;e.interfaces=pending->fault.interfaces;
        e.times[1]=current_.source;e.times[1].ns=first_;e.times[6]=current_.observed;e.source={true,e.key.component,revision_,e.session.epoch,current_.source,{}};
        e.expected_roles=e.received_roles=255;e.state_before=revision_;
        e.measured=static_cast<double>(last_source_-first_);e.expected_min=static_cast<double>(window_ns);
        return e;
    }
    return {};
}
} // namespace stratadrive::diagnostics
