#include "producer_lifecycle.hpp"
#include <limits>
#include <stdexcept>

namespace stratadrive::diagnostics {
namespace {
Stamp stamp(ControlContext c,std::uint64_t ns) {return {c.domain,c.clock_instance,ns,true,true};}
Event lifecycle_event(ControlContext c,std::uint32_t generation,bool closing,std::uint64_t ns) {
    Event e;e.id={c.run,c.producer,2ULL*generation-(closing?0:1)};e.session={c.run,generation};e.profile=c.profile;
    e.kind=closing?Kind::Observation:Kind::Attempt;
    e.source={true,c.producer,generation,generation,stamp(c,ns),{}};
    e.times[static_cast<std::size_t>(Time::Observed)]=stamp(c,ns);return e;
}
}
ProducerLifecycle::ProducerLifecycle(const std::string& directory,ControlContext c,std::uint64_t started)
    :journal_(directory),recorder_(journal_),identity_(c),started_(started) {
    if(journal_.store_id()!=c.producer || journal_.registry_revision()!=3 || !c.run || !c.producer || !c.clock_instance || !c.profile || c.domain!=Domain::Monotonic || !started)
        throw std::invalid_argument("diagnostic producer lifecycle manifest");
    std::uint32_t generation=0;bool open=false;std::uint64_t last_time=0;
    for(const auto& entry:journal_.committed()) {
        const auto* e=std::get_if<Event>(&entry);
        if(!e || (e->kind!=Kind::Attempt && e->kind!=Kind::Observation))throw std::invalid_argument("diagnostic lifecycle event");
        const bool closing=e->kind==Kind::Observation;
        if((closing && !open) || (!closing && generation==std::numeric_limits<std::uint32_t>::max()))throw std::invalid_argument("diagnostic lifecycle order");
        const auto expected_generation=closing?generation:generation+1;
        const auto ns=e->times[static_cast<std::size_t>(Time::Observed)].ns;
        if(ns<last_time || encode(*e)!=encode(lifecycle_event(c,expected_generation,closing,ns)))throw std::invalid_argument("diagnostic lifecycle identity/time");
        generation=expected_generation;open=!closing;last_time=ns;
    }
    if(!journal_.writable() || !recorder_.ledger().complete())throw std::runtime_error("diagnostic lifecycle incomplete");
    if(generation==std::numeric_limits<std::uint32_t>::max())throw std::overflow_error("diagnostic producer generation exhausted");
    if(started<last_time)throw std::invalid_argument("diagnostic lifecycle clock regressed");
    generation_=generation+1;previous_unclean_=open;
    if(!recorder_.record(lifecycle_event(c,generation_,false,started)).durable)throw std::runtime_error("diagnostic producer generation commit");
}
std::uint64_t ProducerLifecycle::producer(std::uint32_t logical) const {
    if(!logical)throw std::invalid_argument("diagnostic logical producer");
    return (static_cast<std::uint64_t>(generation_-1)<<32)|logical;
}
Result ProducerLifecycle::close(std::uint64_t stopped) {
    if(closed_)return Result::Duplicate;
    if(stopped<started_)return Result::Invalid;
    const auto r=recorder_.record(lifecycle_event(identity_,generation_,true,stopped));
    if(r.durable && r.result==Result::Accepted)closed_=true;
    return r.durable?r.result:Result::StorageFailure;
}
Event continuity_fault(ControlContext c,std::uint32_t logical,std::uint32_t generation,Component actor,
    std::uint32_t epoch,std::uint64_t enable,std::uint64_t boot,std::uint64_t observed) {
    if(!c.run || !c.clock_instance || !c.profile || c.domain!=Domain::Monotonic || !static_cast<unsigned>(actor) || generation<2 || !logical || !epoch || !boot || boot>observed || enable>observed ||
       c.producer!=((static_cast<std::uint64_t>(generation-1)<<32)|logical))throw std::invalid_argument("diagnostic continuity manifest");
    Event e;e.id={c.run,c.producer,1};e.session={c.run,epoch};e.profile=c.profile;
    e.session_enable=stamp(c,enable);e.kind=Kind::Fault;e.key={Code::RecordingGap,static_cast<std::uint32_t>(actor),10,logical};
    e.occurrence={c.run,c.producer,epoch,10,1};e.native_reason=1;e.latch=Latch::Unknown;
    e.state_before=generation-1;e.state_after=generation;e.cause_unknown=true;e.unmapped=true;
    e.times[static_cast<std::size_t>(Time::Detected)]=stamp(c,boot);e.times[static_cast<std::size_t>(Time::Observed)]=stamp(c,observed);return e;
}
} // namespace stratadrive::diagnostics
