#include "native_diagnostics.hpp"
#include "local_safety.hpp"
#include "bms_controller.hpp"
#include "power_controller.hpp"
#include <stdexcept>

namespace stratadrive::diagnostics {
namespace {
Code mapping(NativeMonitor monitor,std::uint32_t reason,std::uint32_t detail,bool& known) {
    known=true;
    if(monitor==NativeMonitor::CommandGateway || monitor==NativeMonitor::RearPowerGateway) {
        switch(static_cast<zone::ProtectionCause>(reason)) {
        case zone::ProtectionCause::CommandExpired: case zone::ProtectionCause::UpstreamLost:
            return monitor==NativeMonitor::RearPowerGateway && (detail&12U)?Code::FeedbackLoss:Code::CommandLoss;
        case zone::ProtectionCause::SendFailure: case zone::ProtectionCause::QueueOverflow:return Code::Gateway;
        case zone::ProtectionCause::ClockError:return Code::Clock;
        case zone::ProtectionCause::CoordinatorRequest: case zone::ProtectionCause::None:return Code::None;
        }
    } else if(monitor==NativeMonitor::Bms) {
        switch(static_cast<vecu::BmsControlFault>(reason)) {
        case vecu::BmsControlFault::InputsInvalid: case vecu::BmsControlFault::Protection:return Code::BmsLocal;
        case vecu::BmsControlFault::ClockError:return Code::Clock;
        case vecu::BmsControlFault::ControlDeadline:return Code::Deadline;
        case vecu::BmsControlFault::None:return Code::None;
        case vecu::BmsControlFault::SequenceExhausted:break;
        }
    } else {
        using F=vecu::PowerControlFault;
        switch(static_cast<F>(reason)) {
        case F::StartupEnergized: case F::InputsUnavailable: case F::RequestLost: case F::ConditionsUnsafe:
        case F::ContactorResponse: case F::PrechargeTimeout: case F::BusNotReady: case F::ShutdownCurrentBlocked: case F::DischargeTimeout:return Code::PowerLocal;
        case F::ClockError:return Code::Clock;
        case F::ControlDeadline:return Code::Deadline;
        case F::BmsInhibit: case F::ContinuityLost: case F::None:return Code::None;
        case F::SequenceExhausted:break;
        }
    }
    known=false; return Code::None;
}
Proof required(Code code) {
    if(code==Code::BmsLocal || code==Code::CommandLoss || code==Code::FeedbackLoss) return Proof::Input;
    if(code==Code::Deadline || code==Code::Gateway || code==Code::PowerLocal) return Proof::Control;
    return Proof::None;
}
}
NativeDiagnostics::NativeDiagnostics(EventQueue& q,ControlContext c,Component actor,std::uint64_t first)
    :publisher_(q,c,first,"native diagnostic context"),actor_(actor) {
    if(actor!=Component::Front && actor!=Component::Rear && actor!=Component::Bms && actor!=Component::Power)
        throw std::invalid_argument("native diagnostic context");
}
Event NativeDiagnostics::base(std::uint64_t now) const noexcept {
    Event e; e.session=session_; e.session_enable=stamp(enable_); e.profile=capture_context().profile; e.requirements=e.interfaces=1; e.times[6]=stamp(now,now>=enable_); return e;
}
bool NativeDiagnostics::start_session(std::uint32_t epoch,std::uint64_t enable) noexcept {
    if(!epoch || epoch<=session_.epoch || (session_.epoch && enable<enable_)) return false;
    session_={capture_context().run,epoch}; enable_=enable; seen_={}; return healthy();
}
void NativeDiagnostics::failure(NativeMonitor monitor,const NativeObservation& o,std::uint64_t now) noexcept {
    if(o.epoch!=session_.epoch || o.enable_ns!=enable_) return;
    const auto index=static_cast<unsigned>(monitor)-6;
    if(seen_[index][o.propagation?1:0]) return;
    seen_[index][o.propagation?1:0]=true;
    bool known=false; const auto code=mapping(monitor,o.reason,o.detail,known); auto e=base(now);
    e.kind=known && !o.propagation && code!=Code::None?Kind::Fault:Kind::Observation;
    e.key={e.kind==Kind::Fault?code:Code::None,static_cast<std::uint32_t>(actor_),static_cast<std::uint32_t>(monitor),o.reason?o.reason:1};
    e.native_reason=o.reason; e.model_epoch=o.model_epoch; e.state_before=o.state; e.state_after=o.detail;
    if(monitor==NativeMonitor::CommandGateway || monitor==NativeMonitor::RearPowerGateway) e.measured=o.writes;
    e.latch=Latch::Set; e.cause_unknown=o.propagation; e.unmapped=!known;
    e.times[2]=stamp(o.observed_ns,code!=Code::Clock && o.observed_ns>=enable_);
    e.source={true,static_cast<std::uint32_t>(actor_),o.observed_ns,o.epoch,stamp(o.observed_ns,code!=Code::Clock),o.valid_until_ns?stamp(*o.valid_until_ns):Stamp{}};
    if(o.violation_ns && *o.violation_ns<=o.observed_ns) e.times[1]=stamp(*o.violation_ns,code!=Code::Clock);
    if(o.root) { const auto& r=*o.root; e.command={true,static_cast<std::uint32_t>(actor_),r.sequence,r.epoch,stamp(r.source_ns),stamp(r.expiry_ns)}; }
    const auto id=publish(e); e.id=id;
    if(e.kind==Kind::Fault) {
        e.occurrence={session_.run,capture_context().producer,session_.epoch,e.key.monitor,id.sequence};
        std::optional<Pending>* slot=nullptr;
        for(auto& p:pending_) if(p && p->event.key==e.key) { slot=&p; break; }
        if(!slot) for(auto& p:pending_) if(!p) { slot=&p; break; }
        if(slot) slot->emplace(Pending{e,false,false}); else { publisher_.incomplete(); auto gap=base(now); gap.kind=Kind::Gap; publish(gap); }
        for(std::size_t i=0;i<o.samples.size();++i) if(o.samples[i].present) {
            const auto& s=o.samples[i]; auto evidence=e; evidence.kind=Kind::Observation; evidence.related=id;
            evidence.source={true,i+1,s.sequence,s.epoch,stamp(s.source_ns),{}}; publish(evidence);
        }
    }
}
void NativeDiagnostics::selection(NativeMonitor monitor,std::optional<std::uint64_t> at,bool acknowledgement) noexcept {
    if(!at) return;
    for(auto& p:pending_) if(p && !p->selected && p->event.session==session_ && p->event.key.monitor==static_cast<std::uint32_t>(monitor) && *at>=p->event.times[2].ns) {
        auto e=p->event; e.kind=acknowledgement?Kind::ProtectionAck:Kind::ProtectionSelected; e.related=p->event.id;
        e.source={true,static_cast<std::uint32_t>(actor_),*at,session_.epoch,stamp(*at),{}};
        e.times[acknowledgement?4:3]=stamp(*at); e.times[6]=stamp(*at); publish(e); p->selected=true;
    }
}
void NativeDiagnostics::observe(NativeMonitor monitor,const std::optional<NativeObservation>& fault,const std::optional<NativeObservation>& propagation,
    const std::optional<NativeObservation>& success,bool currently_healthy,bool gate,std::uint64_t now) noexcept {
    const auto tag=static_cast<unsigned>(monitor);
    if(tag<6 || tag>9 || !session_.epoch ||
       ((monitor==NativeMonitor::CommandGateway || monitor==NativeMonitor::RearPowerGateway) && actor_!=Component::Front && actor_!=Component::Rear) ||
       (monitor==NativeMonitor::RearPowerGateway && actor_!=Component::Rear) ||
       (monitor==NativeMonitor::Bms && actor_!=Component::Bms) || (monitor==NativeMonitor::Power && actor_!=Component::Power)) return;
    if(fault) failure(monitor,*fault,now);
    if(propagation) failure(monitor,*propagation,now);
    if(!healthy() || !gate || !currently_healthy || !success || !success->qualified || success->reason || success->propagation ||
       success->epoch!=session_.epoch || success->enable_ns!=enable_ || success->observed_ns>now) return;
    const auto& good=*success;
    const auto body_age=(monitor==NativeMonitor::Bms || monitor==NativeMonitor::Power)?good.timing[1]:30000000;
    const auto source_age=(monitor==NativeMonitor::Bms || monitor==NativeMonitor::Power)?good.timing[2]:good.timing[0];
    const auto dependency_age=(monitor==NativeMonitor::Bms || monitor==NativeMonitor::Power)?good.timing[3]:good.timing[1];
    if(!body_age || !source_age || !dependency_age || now-good.observed_ns>body_age || (good.valid_until_ns && now>=*good.valid_until_ns)) return;
    if(good.root && (good.root->epoch!=session_.epoch || good.root->source_ns<enable_ || good.root->source_ns>now ||
       good.root->expiry_ns<=now || now-good.root->source_ns>source_age || good.root->dependency_ns<enable_ || good.root->dependency_ns>now || now-good.root->dependency_ns>dependency_age)) return;
    if((monitor==NativeMonitor::CommandGateway || monitor==NativeMonitor::RearPowerGateway || monitor==NativeMonitor::Power) && !good.root) return;
    const auto expected=monitor==NativeMonitor::Bms?5U:monitor==NativeMonitor::Power?2U:monitor==NativeMonitor::RearPowerGateway?4U:0U;
    for(std::size_t i=0;i<expected;++i) {
        const auto& s=good.samples[i];
        if(!s.present || !s.epoch || s.source_ns<enable_ || s.source_ns>now || now-s.source_ns>source_age ||
           s.dependency_ns<enable_ || s.dependency_ns>now || now-s.dependency_ns>dependency_age) return;
        if((monitor==NativeMonitor::Bms || (monitor==NativeMonitor::Power && i==0)) && s.epoch!=good.model_epoch) return;
        if((monitor==NativeMonitor::Power && i==1) || monitor==NativeMonitor::RearPowerGateway) if(s.epoch!=session_.epoch) return;
    }
    for(auto& pending:pending_) if(pending && !pending->recovered && pending->event.key.monitor==tag && session_.epoch>pending->event.session.epoch) {
        auto e=base(now); e.kind=Kind::Observation; e.key=pending->event.key; e.proof=required(e.key.code);
        if(e.proof==Proof::None) continue;
        e.related=pending->event.id; e.occurrence=pending->event.occurrence; e.latch=Latch::Clear;
        e.model_epoch=good.model_epoch; e.state_before=good.state; e.state_after=good.writes;
        e.source={true,static_cast<std::uint32_t>(actor_),good.observed_ns,good.epoch,stamp(good.observed_ns),good.valid_until_ns?stamp(*good.valid_until_ns):Stamp{}};
        if(good.root) { const auto& r=*good.root; e.command={true,static_cast<std::uint32_t>(actor_),r.sequence,r.epoch,stamp(r.source_ns),stamp(r.expiry_ns)}; }
        const auto proof=publish(e); e.kind=Kind::Passed; e.proof_event=proof; publish(e); pending->recovered=true;
    }
}
} // namespace stratadrive::diagnostics
