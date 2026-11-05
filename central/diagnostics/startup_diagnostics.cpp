#include "startup_diagnostics.hpp"
#include <limits>
#include <stdexcept>

namespace stratadrive::diagnostics {
StartupDiagnostics::StartupDiagnostics(EventQueue& q,ControlContext c,Component actor,unsigned role,bool global)
    :queue_(q),context_(c),actor_(actor),role_(role),global_(global) {
    if(!c.run || !c.producer || !c.clock_instance || !c.profile || role>8 || global!=(role==8) ||
       (c.domain!=Domain::Simulation && c.domain!=Domain::Monotonic)) throw std::invalid_argument("startup diagnostics context");
}
Stamp StartupDiagnostics::stamp(std::uint64_t ns,bool trusted) const noexcept { return {context_.domain,context_.clock_instance,ns,true,trusted}; }
Event StartupDiagnostics::base(const session::Plan& p,std::uint64_t now) const noexcept {
    Event e; e.session={context_.run,p.epoch}; if(p.enable_ns) e.session_enable=stamp(p.enable_ns);
    e.profile=context_.profile; e.requirements=e.interfaces=1; e.times[6]=stamp(now,now>=p.requested_ns);
    e.source={true,context_.producer,p.epoch,p.epoch,stamp(p.requested_ns),stamp(p.prepare_deadline_ns)}; return e;
}
EventId StartupDiagnostics::publish(Event e) noexcept {
    if(!next_) { healthy_=false; return {}; }
    e.id={context_.run,context_.producer,next_};
    if(next_==std::numeric_limits<std::uint64_t>::max()) { next_=0; healthy_=false; e.kind=Kind::Gap; e.key={}; e.occurrence={}; } else ++next_;
    if(e.kind==Kind::Fault) e.occurrence={context_.run,context_.producer,e.session.epoch,e.key.monitor,e.id.sequence};
    if(!queue_.publish(e)) { healthy_=false; }
    if(!clock_recovery_.remember(e)) {
        healthy_=false;
        auto gap=e;gap.kind=Kind::Gap;gap.key={};gap.occurrence={};publish(gap);
    }
    return e.id;
}
void StartupDiagnostics::attempt(const session::Plan& p) noexcept {
    if(!p.epoch || p.epoch<=epoch_) return;
    epoch_=p.epoch; seen_=false;
    if(global_) { auto e=base(p,p.requested_ns); e.kind=Kind::Attempt; e.session_enable={}; publish(e); }
}
void StartupDiagnostics::observe(const std::optional<session::Observation>& fault,const std::optional<session::Observation>& success,
    bool ready,bool released,std::uint64_t now) noexcept {
    if(fault && fault->plan.epoch && (fault->plan.epoch>epoch_ || !seen_)) {
        const auto& o=*fault; attempt(o.plan);
        if(o.plan.epoch==epoch_) {
            seen_=true; bool propagation=false,known=true; Code code=Code::Startup;
            if(global_) {
                known=o.reason && o.reason<=static_cast<unsigned>(session::Fault::Continuity);
                const auto reason=static_cast<session::Fault>(o.reason);
                propagation=reason==session::Fault::Participant || reason==session::Fault::Cancelled;
                if(reason==session::Fault::Clock) code=Code::Clock;
                else if(reason==session::Fault::OwnerGap) code=Code::Deadline;
                else if(reason==session::Fault::None) known=false;
            } else {
                known=o.reason && o.reason<=static_cast<unsigned>(session::ParticipantFault::Continuity);
                const auto reason=static_cast<session::ParticipantFault>(o.reason);
                propagation=reason==session::ParticipantFault::Aborted;
                if(reason==session::ParticipantFault::Clock) code=Code::Clock;
                else if(reason==session::ParticipantFault::OwnerGap) code=Code::Deadline;
                else if(reason==session::ParticipantFault::None) known=false;
            }
            auto e=base(o.plan,now); e.kind=known && !propagation?Kind::Fault:Kind::Observation;
            e.key={e.kind==Kind::Fault?code:Code::None,static_cast<unsigned>(actor_),global_?10U:11U,role_+1};
            e.native_reason=o.reason; e.state_before=o.state; e.state_after=o.accepted_roles; e.received_roles=o.accepted_roles;
            e.expected_roles=global_?255:1U<<role_; e.cause_unknown=propagation; e.unmapped=!known; e.latch=Latch::Set;
            e.times[2]=stamp(o.observed_ns,code!=Code::Clock && o.observed_ns>=o.plan.requested_ns);
            if(o.deadline_ns && o.observed_ns>=o.deadline_ns) e.times[1]=stamp(o.deadline_ns,code!=Code::Clock);
            e.source.expiry=o.deadline_ns?stamp(o.deadline_ns):Stamp{};
            const auto id=publish(e); e.id=id;
            if(e.kind==Kind::Fault) {
                e.occurrence={context_.run,context_.producer,e.session.epoch,e.key.monitor,id.sequence};
                std::optional<Pending>* slot=nullptr;
                for(auto& p:pending_) if(p && p->fault.key==e.key) { slot=&p; break; }
                if(!slot) for(auto& p:pending_) if(!p) { slot=&p; break; }
                if(slot) slot->emplace(Pending{e,false}); else { healthy_=false; e.kind=Kind::Gap; e.key={}; e.occurrence={}; publish(e); }
            }
        }
    }
    if(!healthy_ || !success || !ready || !released || success->reason || !success->plan.epoch) return;
    const auto& o=*success; attempt(o.plan);
    if(o.state!=(global_?static_cast<unsigned>(session::State::Running):static_cast<unsigned>(session::ParticipantState::Ready)) ||
       o.plan.epoch!=epoch_ || o.plan.enable_ns<o.plan.requested_ns || o.plan.commit_deadline_ns>o.plan.prepare_deadline_ns || !o.plan.enable_ns || o.observed_ns<o.plan.enable_ns || o.observed_ns>now ||
       o.observed_ns>=o.plan.commit_deadline_ns || now-o.observed_ns>session::kMessageAgeNs || o.accepted_roles!=(global_?255U:1U<<role_)) return;
    if(global_ && released_!=epoch_) {
        auto e=base(o.plan,now); e.kind=Kind::Session; e.expected_roles=e.received_roles=255; e.source.source=stamp(o.observed_ns); publish(e); released_=epoch_;
    }
    for(auto& p:pending_) if(p && !p->recovered && epoch_>p->fault.session.epoch && p->fault.key.code==Code::Startup) {
        auto e=base(o.plan,now); e.kind=Kind::Observation; e.key=p->fault.key; e.occurrence=p->fault.occurrence; e.related=p->fault.id;
        e.proof=Proof::Control; e.latch=Latch::Clear; e.source.source=stamp(o.observed_ns); e.state_before=o.state;
        e.expected_roles=global_?255:1U<<role_; e.received_roles=o.accepted_roles;
        const auto id=publish(e); e.kind=Kind::Passed; e.proof_event=id; publish(e); p->recovered=true;
    }
}
} // namespace stratadrive::diagnostics
