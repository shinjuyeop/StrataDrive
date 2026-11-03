#include "owner_diagnostics.hpp"
#include <limits>
#include <stdexcept>

namespace stratadrive::diagnostics {
namespace {
std::uint32_t number(Component c) { return static_cast<std::uint32_t>(c); }
std::uint32_t reason(zone::ZoneFeedbackFault f) {
    using F=zone::ZoneFeedbackFault;
    switch(f) {
    case F::None:return 0; case F::ClockError:return 1; case F::ControlDeadline:return 2;
    case F::InputsUnavailable:return 3; case F::SourceProtection:return 4;
    case F::GatewayProtection:return 5; case F::SequenceExhausted:return 6;
    }
    return 0;
}
can::ActuatorMetadata metadata(const zone::ZoneFeedbackInputs& in,unsigned i) {
    switch(i) {
    case 0: if(in.steering) {
        can::ActuatorMetadata m; m.epoch=in.steering->epoch; m.sequence=in.steering->sequence;
        m.source_time_ns=in.steering->source_time_ns; return m;
    } break;
    case 1: if(in.brake) return *in.brake; break;
    case 2: if(in.drive) return *in.drive; break;
    case 3: if(in.power_status) return in.power_status->message; break;
    case 4: if(in.power_limits) return in.power_limits->message; break;
    default:break;
    }
    return {};
}
std::uint64_t component(unsigned stream) {
    constexpr std::uint64_t ids[]{9,5,4,6,10}; return ids[stream];
}
}
OwnerDiagnostics::OwnerDiagnostics(EventQueue& q,ControlContext c,Component actor):queue_(q),context_(c),actor_(actor) {
    if(!c.run || !c.producer || !c.clock_instance || !c.profile ||
       (c.domain!=Domain::Simulation && c.domain!=Domain::Monotonic) ||
       (actor!=Component::Front && actor!=Component::Rear && actor!=Component::Steering && actor!=Component::Brake && actor!=Component::Drive))
        throw std::invalid_argument("owner diagnostics context");
}
Stamp OwnerDiagnostics::stamp(std::uint64_t ns,bool trusted) const noexcept { return {context_.domain,context_.clock_instance,ns,true,trusted}; }
Event OwnerDiagnostics::base(std::uint64_t now) const noexcept {
    Event e; e.session=session_; e.session_enable=stamp(enable_); e.profile=context_.profile; e.requirements=e.interfaces=1;
    e.times[6]=stamp(now,now>=enable_ && now!=std::numeric_limits<std::uint64_t>::max()); return e;
}
EventId OwnerDiagnostics::publish(Event e) noexcept {
    if(!next_) { healthy_=false; return {}; }
    e.id={context_.run,context_.producer,next_};
    if(next_==std::numeric_limits<std::uint64_t>::max()) { healthy_=false; next_=0; e.kind=Kind::Gap; e.key={}; e.occurrence={}; }
    else ++next_;
    if(e.kind==Kind::Fault) e.occurrence={session_.run,context_.producer,session_.epoch,e.key.monitor,e.id.sequence};
    if(!queue_.publish(e)) healthy_=false;
    return e.id;
}
bool OwnerDiagnostics::start_session(std::uint32_t epoch,std::uint64_t enable) noexcept {
    if(!epoch || epoch<=session_.epoch || (session_.epoch && enable<enable_)) return false;
    session_={context_.run,epoch}; enable_=enable; seen_=selected_=false; return healthy_;
}
void OwnerDiagnostics::selection(std::optional<std::uint64_t> at,bool ack) noexcept {
    if(selected_ || !at || !target_ || target_->session.epoch!=session_.epoch || *at<target_->times[2].ns) return;
    selected_=true; auto e=*target_; e.kind=ack?Kind::ProtectionAck:Kind::ProtectionSelected; e.related=target_->id;
    e.source={true,number(actor_),*at,session_.epoch,stamp(*at),{}}; e.times[ack?4:3]=stamp(*at); e.times[6]=stamp(*at); publish(e);
}
void OwnerDiagnostics::passed(Event e) noexcept {
    const auto proof=publish(e); e.kind=Kind::Passed; e.proof_event=proof; publish(e); recovered_=true;
}
void OwnerDiagnostics::zone(const stratadrive::zone::ZoneFeedbackMonitor& source,bool normal_gate,
    std::optional<std::uint64_t> ack,std::uint64_t now) noexcept {
    if(actor_!=Component::Front && actor_!=Component::Rear) return;
    const auto& fault=source.fault_observation();
    const auto required=actor_==Component::Front?3U:28U;
    if(!seen_ && fault && fault->epoch==session_.epoch && fault->enable_ns==enable_ &&
       (fault->scope==stratadrive::zone::ZoneScope::Front)==(actor_==Component::Front)) {
        seen_=true; const auto& o=*fault; auto e=base(now); e.native_reason=reason(o.fault); e.latch=Latch::Set;
        using F=stratadrive::zone::ZoneFeedbackFault;
        const auto code=o.fault==F::InputsUnavailable?Code::FeedbackLoss:o.fault==F::ClockError?Code::Clock:o.fault==F::ControlDeadline?Code::Deadline:Code::None;
        // The snapshot retains all missing streams; one detector occurrence,
        // not a fabricated root per missing field or upstream FailSafe report.
        e.key={code,number(actor_),4,(required&~o.healthy_mask)?required&~o.healthy_mask:required};
        e.state_before=required; e.state_after=o.healthy_mask&required; e.kind=code==Code::None?Kind::Observation:Kind::Fault;
        e.cause_unknown=code==Code::None; e.unmapped=o.fault==F::SequenceExhausted;
        e.times[2]=stamp(o.observed_ns,o.fault!=F::ClockError && o.observed_ns>=enable_);
        if(o.violation_ns) e.times[1]=stamp(*o.violation_ns);
        const auto id=publish(e); e.id=id;
        if(e.kind==Kind::Fault) {
            e.occurrence={session_.run,context_.producer,session_.epoch,4,id.sequence}; target_=e; recovered_=false;
            std::optional<Pending>* slot=nullptr;
            for(auto& pending:zone_pending_) if(pending && pending->event.key==e.key) { slot=&pending; break; }
            if(!slot) for(auto& pending:zone_pending_) if(!pending) { slot=&pending; break; }
            if(!slot) { healthy_=false; auto gap=base(now); gap.kind=Kind::Gap; publish(gap); }
            else slot->emplace(Pending{e,false});
            for(unsigned i=0;i<5;++i) if((e.key.subject&(1U<<i))!=0) {
                const auto m=metadata(o.last_healthy,i); if(!m.epoch) continue;
                auto history=e; history.kind=Kind::Observation; history.related=id;
                history.source={true,component(i),m.sequence,m.epoch,stamp(m.source_time_ns),{}}; publish(history);
            }
        }
    }
    selection(ack,true);
    const auto& good=source.success_observation();
    if(!healthy_ || !normal_gate || source.fault()!=stratadrive::zone::ZoneFeedbackFault::None || !good ||
       good->epoch!=session_.epoch || good->enable_ns!=enable_ || (good->healthy_mask&required)!=required ||
       now<good->observed_ns || now-good->observed_ns>30000000 ||
       (good->scope==stratadrive::zone::ZoneScope::Front)!=(actor_==Component::Front)) return;
    const feedback::SourceContext context{session_.epoch,enable_,now};
    if(actor_==Component::Front?
       (!feedback::steering_available(good->inputs.steering,context) || !feedback::brake_available(good->inputs.brake,context)):
       (!feedback::drive_available(good->inputs.drive,context) || !feedback::power_available(good->inputs.power_status,context,false) ||
        !feedback::limits_available(good->inputs.power_limits,context,false))) return;
    for(unsigned i=0;i<5;++i) if((required&(1U<<i))!=0) {
        const auto m=metadata(good->inputs,i);
        const auto max_age=i<3?30000000ULL:50000000ULL;
        if(m.epoch!=session_.epoch || m.source_time_ns<enable_ || m.source_time_ns>now || now-m.source_time_ns>max_age) return;
    }
    for(auto& pending:zone_pending_) {
        if(!pending || pending->recovered || session_.epoch<=pending->event.session.epoch ||
           (pending->event.key.code!=Code::FeedbackLoss && pending->event.key.code!=Code::Deadline)) continue;
        const auto& target=pending->event; Event proof;
        for(unsigned i=0;i<5;++i) if((required&(1U<<i))!=0) {
            const auto m=metadata(good->inputs,i); auto e=base(now); e.kind=Kind::Observation;
            e.proof=target.key.code==Code::Deadline?Proof::Control:Proof::Input;
            e.key=target.key; e.occurrence=target.occurrence; e.related=target.id; e.latch=Latch::Clear;
            e.state_before=required; e.state_after=required;
            // Metadata/predicate evidence; scalar physical measurements are not
            // synthesized from a readiness flag or an unpopulated measured=0.
            e.source={true,component(i),m.sequence,m.epoch,stamp(m.source_time_ns),{}};
            if(i==(actor_==Component::Front?1U:4U)) proof=e; else publish(e);
        }
        passed(proof); pending->recovered=true;
    }
}
void OwnerDiagnostics::leaf(const std::optional<transport::LeafAuthorityObservation>& expired,
    const std::optional<transport::LeafAuthorityObservation>& success,bool native_healthy,bool normal_gate,
    std::optional<std::uint64_t> selected,std::uint64_t now) noexcept {
    const auto role=actor_==Component::Steering?transport::Leaf::Steering:actor_==Component::Brake?transport::Leaf::Brake:transport::Leaf::Drive;
    if(actor_!=Component::Steering && actor_!=Component::Brake && actor_!=Component::Drive) return;
    if(!seen_ && expired && expired->leaf==role && expired->epoch==session_.epoch && expired->enable_ns==enable_ && expired->accepted.command) {
        seen_=true; const auto& o=*expired; const auto& c=*o.accepted.command; const auto& p=c.parent; auto e=base(now);
        e.kind=o.independently_expired?Kind::Fault:Kind::Observation; e.native_reason=1; e.latch=Latch::Set;
        e.key={o.independently_expired?Code::CommandLoss:Code::None,number(actor_),5,1}; e.cause_unknown=!o.independently_expired;
        e.times[1]=stamp(c.expires_at_ns); e.times[2]=stamp(o.observed_ns,o.observed_ns>=c.expires_at_ns);
        e.command={true,3,p.sequence,p.epoch,stamp(p.source_time_ns),stamp(c.expires_at_ns)};
        e.source={true,number(actor_),o.accepted.token,o.epoch,stamp(o.accepted.sent_ns),stamp(o.accepted.deadline_ns)};
        const auto id=publish(e); e.id=id;
        if(e.kind==Kind::Fault) { e.occurrence={session_.run,context_.producer,session_.epoch,5,id.sequence}; target_=e; recovered_=false; }
    }
    selection(selected,false);
    if(!healthy_ || recovered_ || !target_ || target_->key.code!=Code::CommandLoss || !native_healthy || !normal_gate || !success ||
       session_.epoch<=target_->session.epoch || success->epoch!=session_.epoch || success->enable_ns!=enable_ || success->leaf!=role ||
       !success->accepted.command || success->observed_ns>now || now-success->observed_ns>30000000) return;
    const auto& c=*success->accepted.command; const auto& p=c.parent;
    if(p.epoch!=session_.epoch || p.source_time_ns<enable_ || p.source_time_ns>success->observed_ns ||
       success->accepted.epoch!=session_.epoch || success->accepted.sent_ns>success->observed_ns ||
       c.oldest_input_time_ns<enable_ || c.oldest_input_time_ns>now || now-c.oldest_input_time_ns>70000000 ||
       c.expires_at_ns<=now || c.expires_at_ns>p.expires_at_ns) return;
    auto e=base(now); e.kind=Kind::Observation; e.proof=Proof::Input; e.key=target_->key; e.occurrence=target_->occurrence;
    e.related=target_->id; e.latch=Latch::Clear;
    e.command={true,3,p.sequence,p.epoch,stamp(p.source_time_ns),stamp(c.expires_at_ns)};
    e.source={true,number(actor_),success->accepted.token,session_.epoch,stamp(c.oldest_input_time_ns),{}};
    // Successful input/control-body evidence is not a physical Actual sample.
    e.times[6]=stamp(success->observed_ns); e.state_after=1; passed(e);
}
} // namespace stratadrive::diagnostics
