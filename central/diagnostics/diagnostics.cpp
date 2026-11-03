#include "diagnostics.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <type_traits>
#include <utility>

namespace stratadrive::diagnostics {
std::uint32_t code_registry_revision(Code code) noexcept {
    switch(code) {
    case Code::Startup: return 3;
    case Code::Gateway: case Code::BmsLocal: case Code::PowerLocal: return 2;
    case Code::None: case Code::SpeedInput: case Code::CentralControl: case Code::BrakingTimeout:
    case Code::Handoff: case Code::StopEvidence: case Code::ShutdownTimeout: case Code::StopRequest:
    case Code::CommandLoss: case Code::FeedbackLoss: case Code::Response: case Code::Clock: case Code::Deadline: case Code::RecordingGap: return 1;
    }
    return std::numeric_limits<std::uint32_t>::max();
}
bool operator==(const EventId& a,const EventId& b) noexcept { return a.run==b.run && a.producer==b.producer && a.sequence==b.sequence; }
bool operator==(const Session& a,const Session& b) noexcept { return a.run==b.run && a.epoch==b.epoch; }
bool operator==(const Key& a,const Key& b) noexcept { return a.code==b.code && a.component==b.component && a.monitor==b.monitor && a.subject==b.subject; }
bool operator==(const Occurrence& a,const Occurrence& b) noexcept { return a.run==b.run && a.producer==b.producer && a.epoch==b.epoch && a.monitor==b.monitor && a.sequence==b.sequence; }
bool comparable(const Stamp& a,const Stamp& b) noexcept {
    return a.present && b.present && a.trusted && b.trusted && a.domain!=Domain::Unknown && a.domain==b.domain && a.instance && a.instance==b.instance;
}
namespace {
bool valid(const EventId& id) { return id.run && id.producer && id.sequence; }
bool valid(const Session& s) { return s.run && s.epoch; }
bool known(Code code) {
    switch(code) {
    case Code::SpeedInput: case Code::CentralControl: case Code::BrakingTimeout: case Code::Handoff:
    case Code::StopEvidence: case Code::ShutdownTimeout: case Code::StopRequest: case Code::CommandLoss:
    case Code::FeedbackLoss: case Code::Gateway: case Code::BmsLocal: case Code::PowerLocal:
    case Code::Response: case Code::Clock: case Code::Deadline: case Code::Startup: case Code::RecordingGap: return true;
    default: return false;
    }
}
bool valid(const Key& k) { return known(k.code) && k.component && k.monitor && k.subject; }
bool valid(const Occurrence& o) { return o.run && o.producer && o.epoch && o.monitor && o.sequence; }
bool valid(const Stamp& s) {
    if(s.domain>Domain::Monotonic) return false;
    if(!s.present) return s.domain==Domain::Unknown && s.instance==0 && s.ns==0 && !s.trusted;
    return s.domain!=Domain::Unknown && s.instance!=0;
}
bool same_stamp(const Stamp& a,const Stamp& b) {
    return a.domain==b.domain && a.instance==b.instance && a.ns==b.ns && a.present==b.present && a.trusted==b.trusted;
}
bool valid(const Identity& i) { return valid(i.source) && valid(i.expiry) && (!i.present || (i.producer && i.epoch)); }
bool valid(const Event& e) {
    if(e.schema!=1 || !valid(e.id) || !valid(e.session) || e.id.run!=e.session.run ||
       e.kind>Kind::Attempt || e.latch>Latch::Clear || e.proof>Proof::Recording ||
       !valid(e.session_enable) || !valid(e.source) || !valid(e.command) || !valid(e.stop_lease) ||
       !std::isfinite(e.measured) || !std::isfinite(e.expected_min) || !std::isfinite(e.expected_max)) return false;
    if(!std::all_of(e.times.begin(),e.times.end(),[](const Stamp& s){return valid(s);})) return false;
    if(e.kind==Kind::Attempt) return e.key.code==Code::None && !e.session_enable.present && e.source.present &&
        e.source.producer==e.id.producer && e.source.epoch==e.session.epoch && comparable(e.source.source,e.source.source);
    if(e.kind==Kind::Session) return e.key.code==Code::None && comparable(e.session_enable,e.session_enable);
    if(e.kind==Kind::Fault || e.kind==Kind::Passed) {
        if(!valid(e.key) || !valid(e.occurrence) || e.occurrence.monitor!=e.key.monitor) return false;
        if(e.kind==Kind::Fault && (e.occurrence.run!=e.id.run || e.occurrence.producer!=e.id.producer || e.occurrence.epoch!=e.session.epoch ||
            !e.times[static_cast<std::size_t>(Time::Detected)].present || !e.native_reason)) return false;
    }
    return e.key.code==Code::None || valid(e.key);
}
Proof required(Code c) {
    switch(c) {
    case Code::SpeedInput: case Code::CommandLoss: case Code::FeedbackLoss: case Code::StopRequest: return Proof::Input;
    case Code::CentralControl: case Code::Clock: case Code::Deadline: case Code::Gateway: case Code::PowerLocal: case Code::Startup: return Proof::Control;
    case Code::BmsLocal: return Proof::Input;
    case Code::BrakingTimeout: return Proof::Stop;
    case Code::Handoff: return Proof::Handoff;
    case Code::StopEvidence: return Proof::Hold;
    case Code::ShutdownTimeout: return Proof::Shutdown;
    case Code::Response: return Proof::Response;
    case Code::RecordingGap: return Proof::Recording;
    default: return Proof::None;
    }
}
// Different producer instances in one epoch have no trusted ordering. A restart
// of a monitored owner requires the existing trusted newer application epoch.
bool later(const Event& e,const Record& r) {
    if(e.session.epoch!=r.state_session.epoch) return e.session.epoch>r.state_session.epoch;
    return e.session.run==r.state_session.run && e.id.producer==r.state_event.producer && e.id.sequence>r.state_event.sequence;
}
bool stationary(const ServiceEvidence& e) {
    if(!e.current_streams_valid || !e.normal_dispatch_inhibited || !comparable(e.now,e.enable) || e.now.ns<e.enable.ns ||
       !std::isfinite(e.wheel_rad_s) || !std::isfinite(e.torque_nm) || !std::isfinite(e.pressure_pa) ||
       e.wheel_rad_s<0 || e.wheel_rad_s>.01 || std::abs(e.torque_nm)>.1 || e.pressure_pa<100000 || e.pressure_pa>1500000) return false;
    std::uint64_t low=e.now.ns,high=0;
    for(const auto& s : {e.wheel,e.drive,e.brake}) {
        if(!comparable(e.now,s) || s.ns<e.enable.ns || s.ns>e.now.ns || e.now.ns-s.ns>30000000) return false;
        low=std::min(low,s.ns); high=std::max(high,s.ns);
    }
    return high-low<=20000000;
}
template<class I> void transfer(I& i,Stamp& v) { i(v.domain,v.instance,v.ns,v.present,v.trusted); }
template<class I> void transfer(I& i,EventId& v) { i(v.run,v.producer,v.sequence); }
template<class I> void transfer(I& i,Session& v) { i(v.run,v.epoch); }
template<class I> void transfer(I& i,Key& v) { i(v.code,v.component,v.monitor,v.subject); }
template<class I> void transfer(I& i,Occurrence& v) { i(v.run,v.producer,v.epoch,v.monitor,v.sequence); }
template<class I> void transfer(I& i,Identity& v) { i(v.present,v.producer,v.sequence,v.epoch,v.source,v.expiry); }
template<class I> void transfer(I& i,Event& v) {
    i(v.schema,v.id,v.related,v.proof_event,v.session,v.key,v.occurrence,v.kind,v.latch,v.proof,
      v.native_reason,v.severity,v.model_epoch,v.state_before,v.state_after,v.profile,v.requirements,v.interfaces,
      v.session_enable,v.source,v.command,v.stop_lease);
    for(auto& s:v.times) i(s);
    i(v.expected_roles,v.received_roles,v.cause_unknown,v.unmapped,v.measured,v.expected_min,v.expected_max);
}
template<class I> void transfer(I& i,ServiceEvidence& v) {
    i(v.now,v.enable,v.wheel,v.drive,v.brake,v.wheel_rad_s,v.torque_nm,v.pressure_pa,v.current_streams_valid,v.normal_dispatch_inhibited);
}
template<class I> void transfer(I&,Clear&);
struct Writer {
    std::vector<std::uint8_t> data;
    template<class... T> void operator()(T&... v) { (field(v),...); }
    template<class T> void field(T& v) {
        if constexpr(std::is_same_v<T,bool>) data.push_back(v?1:0);
        else if constexpr(std::is_enum_v<T>) { auto n=static_cast<std::underlying_type_t<T>>(v); field(n); }
        else if constexpr(std::is_integral_v<T>) { for(std::size_t n=0;n<sizeof(T);++n) data.push_back(static_cast<std::uint8_t>(v>>(n*8))); }
        else if constexpr(std::is_same_v<T,double>) { std::uint64_t n=0; static_assert(sizeof(v)==sizeof(n)); std::memcpy(&n,&v,sizeof(n)); field(n); }
        else transfer(*this,v);
    }
};
struct Reader {
    const std::vector<std::uint8_t>& data; std::size_t cursor{0};
    template<class... T> void operator()(T&... v) { (field(v),...); }
    template<class T> void field(T& v) {
        if constexpr(std::is_same_v<T,bool>) { std::uint8_t n=0; field(n); if(n>1) throw std::runtime_error("diagnostics boolean"); v=n!=0; }
        else if constexpr(std::is_enum_v<T>) { std::underlying_type_t<T> n{}; field(n); v=static_cast<T>(n); }
        else if constexpr(std::is_integral_v<T>) {
            if(data.size()-cursor<sizeof(T)) throw std::runtime_error("diagnostics truncated payload");
            std::uint64_t n=0; for(std::size_t j=0;j<sizeof(T);++j) n|=static_cast<std::uint64_t>(data[cursor++])<<(j*8); v=static_cast<T>(n);
        } else if constexpr(std::is_same_v<T,double>) { std::uint64_t n=0; field(n); std::memcpy(&v,&n,sizeof(n)); }
        else transfer(*this,v);
    }
};
template<class I> void transfer(I& i,Clear& v) {
    i(v.id,v.session,v.evidence,v.all);
    auto size=static_cast<std::uint32_t>(v.targets.size()); i(size);
    if(size==0 || size>4096) throw std::runtime_error("diagnostics clear target count");
    v.targets.resize(size);
    for(auto& t:v.targets) i(t.key,t.revision);
}
} // namespace
void validate(Limits l) {
    for(auto v : {l.events,l.records,l.occurrences,l.clears}) if(v==0 || v>4096) throw std::invalid_argument("diagnostics limits");
}
std::vector<std::uint8_t> encode(const Entry& entry) {
    Writer w; auto tag=static_cast<std::uint8_t>(entry.index()); w(tag);
    if(tag==0) { auto e=std::get<Event>(entry); w(e); }
    else { auto c=std::get<Clear>(entry); w(c); }
    return std::move(w.data);
}
Entry decode(const std::vector<std::uint8_t>& bytes) {
    Reader r{bytes}; std::uint8_t tag=0; r(tag); Entry entry;
    if(tag==0) { Event e; r(e); entry=e; }
    else if(tag==1) { Clear c; r(c); entry=std::move(c); }
    else throw std::runtime_error("diagnostics entry tag");
    if(r.cursor!=bytes.size()) throw std::runtime_error("diagnostics trailing payload");
    return entry;
}
Ledger::Ledger(Limits limits):limits_(limits) {
    validate(limits); events_.reserve(limits.events); records_.reserve(limits.records);
    episodes_.reserve(limits.occurrences); clears_.reserve(limits.clears);
}
const Record* Ledger::find(const Key& key) const noexcept {
    const auto it=std::find_if(records_.begin(),records_.end(),[&](const Record& r){return r.key==key;});
    return it==records_.end()?nullptr:&*it;
}
Record* Ledger::mutable_record(const Key& key) noexcept { return const_cast<Record*>(std::as_const(*this).find(key)); }
void Ledger::restarted() noexcept {
    for(auto& r:records_) { r.condition=Condition::Unknown; r.latch=Latch::Unknown; r.pass_event={}; }
}
void Ledger::recording_gap() noexcept { complete_=false; restarted(); }
Result Ledger::record(const Event& e) {
    const auto old=std::find_if(events_.begin(),events_.end(),[&](const Event& v){return v.id==e.id;});
    if(old!=events_.end()) {
        if(encode(*old)==encode(e)) return Result::Duplicate;
        recording_gap(); return Result::Conflict;
    }
    Ledger next=*this; const auto result=next.apply(e);
    if(result==Result::Accepted) *this=std::move(next); else recording_gap();
    return result;
}
Result Ledger::apply(const Event& e) {
    if(!valid(e)) return Result::Invalid;
    if(events_.size()>=limits_.events || revision_==std::numeric_limits<std::uint64_t>::max()) return Result::Capacity;
    if(e.kind==Kind::Attempt) {
        if(e.session.epoch<=session_.epoch) return Result::Invalid;
        session_=e.session; enable_={}; released_=false; attempt_origin_=e.source.source; attempt_producer_=e.id.producer; restarted();
    } else if(e.kind==Kind::Session) {
        if(e.session.epoch==session_.epoch) {
            if(released_ || e.expected_roles!=255 || e.received_roles!=255 || !(e.session==session_) || e.id.producer!=attempt_producer_ || !comparable(e.session_enable,attempt_origin_) || e.session_enable.ns<attempt_origin_.ns) return Result::Invalid;
        } else {
            if(e.session.epoch<session_.epoch) return Result::Invalid;
            session_=e.session; restarted();
        }
        enable_=e.session_enable; released_=true; attempt_origin_={}; attempt_producer_=0;
    } else if(!valid(session_) || e.session.epoch>session_.epoch || (e.session.epoch==session_.epoch && !(e.session==session_))) return Result::Invalid;
    if(!released_ && (e.kind==Kind::Passed || e.proof!=Proof::None)) return Result::NotReady;
    if(e.kind==Kind::Fault && !mutable_record(e.key) && records_.size()>=limits_.records) return Result::Capacity;
    if((e.kind==Kind::Fault || e.kind==Kind::Passed || e.kind==Kind::Unavailable) && e.session==session_) {
        const auto* current=find(e.key);
        if(current && current->state_session==e.session && valid(current->state_event) && e.id.producer!=current->state_event.producer) return Result::Conflict;
        if(e.kind==Kind::Fault && current && !current->cleared && current->state_session==e.session &&
           current->condition!=Condition::Passed && later(e,*current) &&
           std::none_of(episodes_.begin(),episodes_.end(),[&](const Episode& p){return p.id==e.occurrence;})) return Result::Conflict;
    }
    if(valid(e.occurrence)) {
        const auto old=std::find_if(episodes_.begin(),episodes_.end(),[&](const Episode& p){return p.id==e.occurrence;});
        if(old!=episodes_.end() && !(old->key==e.key)) return Result::Conflict;
        if(old==episodes_.end()) {
            if(episodes_.size()>=limits_.occurrences) return Result::Capacity;
            episodes_.push_back({e.occurrence,e.key,0,false});
        }
    }
    ++revision_; events_.push_back(e);
    unmapped_=unmapped_ || e.unmapped;
    if(e.kind==Kind::Gap) { recording_gap(); return Result::Accepted; }
    if(e.kind==Kind::Fault) project(e);
    if(e.kind==Kind::Unavailable) {
        auto* r=mutable_record(e.key);
        if(r && !r->cleared && e.session==session_ && later(e,*r)) {
            r->condition=Condition::Unknown; r->latch=Latch::Unknown; r->pass_event={};
            r->state_event=e.id; r->state_session=e.session; r->revision=revision_;
        }
    }
    // Resolve late evidence and a pass delivered before its confirmed fault.
    // All storage is bounded; this work is exclusively on the writer thread.
    for(const auto& event:events_) if(event.kind==Kind::Passed) pass(event);
    return Result::Accepted;
}
void Ledger::project(const Event& e) {
    auto episode=std::find_if(episodes_.begin(),episodes_.end(),[&](const Episode& p){return p.id==e.occurrence;});
    if(episode->confirmed) return;
    auto* r=mutable_record(e.key);
    if(!r) {
        Record fresh; fresh.key=e.key; records_.push_back(fresh); r=&records_.back();
    }
    episode->confirmed=true;
    const bool historical=e.session.epoch<session_.epoch || (valid(r->state_event) && !later(e,*r));
    if(r->cleared && historical) { episode->generation=r->generation; return; }
    if(r->cleared) {
        if(r->generation==std::numeric_limits<std::uint64_t>::max()) { recording_gap(); return; }
        const auto generation=r->generation+1; const auto key=r->key;
        *r=Record{}; r->key=key; r->generation=generation;
    }
    episode->generation=r->generation;
    if(r->count==std::numeric_limits<std::uint64_t>::max()) { recording_gap(); return; }
    ++r->count;
    const auto detected=e.times[static_cast<std::size_t>(Time::Detected)];
    if(r->count==1 || e.session.epoch<r->first.epoch ||
       (e.session.epoch==r->first.epoch && e.id.producer==r->first_event.producer && e.id.sequence<r->first_event.sequence)) {
        r->first=e.occurrence; r->first_event=e.id; r->first_detected=detected;
    }
    if(r->count==1 || e.session.epoch>r->last.epoch ||
       (e.session.epoch==r->last.epoch && e.id.producer==r->last_event.producer && e.id.sequence>r->last_event.sequence)) {
        r->last=e.occurrence; r->last_event=e.id; r->last_detected=detected;
    }
    r->revision=revision_;
    if(!historical) {
        r->condition=complete_?Condition::Failed:Condition::Unknown; r->latch=e.latch;
        r->state_event=e.id; r->state_session=e.session; r->pass_event={};
    }
}
bool Ledger::pass(const Event& e) {
    if(!complete_ || !released_ || !(e.session==session_) || e.proof!=required(e.key.code) || e.proof==Proof::None || !valid(e.proof_event)) return false;
    if(e.key.code==Code::Startup && e.session.epoch<=e.occurrence.epoch) return false;
    auto* r=mutable_record(e.key);
    if(!r || r->cleared || !later(e,*r)) return false;
    const auto episode=std::find_if(episodes_.begin(),episodes_.end(),[&](const Episode& p){return p.id==e.occurrence;});
    if(episode==episodes_.end() || !episode->confirmed || episode->generation!=r->generation) return false;
    const auto proof=std::find_if(events_.begin(),events_.end(),[&](const Event& v){return v.id==e.proof_event;});
    if(proof==events_.end() || !(proof->key==e.key) || !(proof->session==e.session) || proof->proof!=e.proof ||
        (proof->kind!=Kind::Actual && proof->kind!=Kind::Observation) || proof->id.producer!=e.id.producer || proof->id.sequence>=e.id.sequence ||
        !later(*proof,*r) || !(proof->occurrence==e.occurrence)) return false;
    r->condition=Condition::Passed; r->latch=e.latch; r->state_session=e.session; r->state_event=e.id;
    r->pass_event=e.id; r->revision=revision_; return true;
}
Result Ledger::clear(const Clear& c) {
    const auto previous=std::find_if(clears_.begin(),clears_.end(),[&](const Clear& v){return v.id==c.id;});
    if(previous!=clears_.end()) {
        if(encode(*previous)==encode(c)) return Result::Duplicate;
        recording_gap(); return Result::Conflict;
    }
    if(!valid(c.id) || !valid(c.session) || c.id.run!=c.session.run || c.targets.empty() || c.targets.size()>limits_.records) return Result::Invalid;
    if(!complete_ || !released_ || unmapped_ || !(c.session==session_) || !same_stamp(c.evidence.enable,enable_) || !stationary(c.evidence)) return Result::NotReady;
    if(clears_.size()>=limits_.clears || revision_==std::numeric_limits<std::uint64_t>::max()) { recording_gap(); return Result::Capacity; }
    if(c.all && c.targets.size()!=static_cast<std::size_t>(std::count_if(records_.begin(),records_.end(),[](const Record& r){return !r.cleared;}))) return Result::NotReady;
    for(std::size_t i=0;i<c.targets.size();++i) {
        const auto& t=c.targets[i]; const auto* r=find(t.key);
        if(!r || r->cleared || r->condition!=Condition::Passed || !valid(r->pass_event) || !(r->state_session==session_) || r->revision!=t.revision) return Result::NotReady;
        for(std::size_t j=0;j<i;++j) if(c.targets[j].key==t.key) return Result::Invalid;
    }
    ++revision_;
    for(const auto& t:c.targets) { auto* r=mutable_record(t.key); r->cleared=true; r->revision=revision_; }
    clears_.push_back(c); return Result::Accepted;
}
EventQueue::EventQueue(std::uint64_t run,std::uint64_t producer):run_(run),producer_(producer) {
    static_assert(std::atomic<std::size_t>::is_always_lock_free && std::atomic<std::uint64_t>::is_always_lock_free && std::atomic<bool>::is_always_lock_free);
    if(!run || !producer) throw std::invalid_argument("diagnostics producer identity");
}
bool EventQueue::publish(const Event& e) noexcept {
    const bool identity=e.id.run==run_ && e.id.producer==producer_ && e.id.sequence!=0;
    const auto write=write_.load(std::memory_order_relaxed),next=(write+1)%entries_.size();
    if(!identity || next==read_.load(std::memory_order_acquire)) {
        if(!identity) identity_error_.store(true,std::memory_order_release);
        if(dropped_.load(std::memory_order_relaxed)==0) first_lost_.store(e.id.sequence,std::memory_order_relaxed);
        const auto old=dropped_.load(std::memory_order_relaxed);
        if(old<std::numeric_limits<std::uint64_t>::max()) dropped_.store(old+1,std::memory_order_release);
        return false;
    }
    entries_[write]=e; write_.store(next,std::memory_order_release); return true;
}
bool EventQueue::pop(Event& e) noexcept {
    const auto read=read_.load(std::memory_order_relaxed);
    if(read==write_.load(std::memory_order_acquire)) return false;
    e=entries_[read]; read_.store((read+1)%entries_.size(),std::memory_order_release); return true;
}
EventQueue::Health EventQueue::health() const noexcept {
    const auto count=dropped_.load(std::memory_order_acquire);
    return {count,first_lost_.load(std::memory_order_relaxed),identity_error_.load(std::memory_order_acquire)};
}
Recorder::Recorder(Journal& journal):journal_(journal),ledger_(journal.limits()) {
    for(const auto& entry:journal.committed()) {
        const auto result=std::holds_alternative<Event>(entry)?ledger_.record(std::get<Event>(entry)):ledger_.clear(std::get<Clear>(entry));
        if(result!=Result::Accepted) throw std::runtime_error("diagnostics invalid journal transaction");
    }
    ledger_.restarted(); if(!journal.writable()) ledger_.recording_gap();
}
Receipt Recorder::record(const Event& event) {
    const auto result=ledger_.record(event);
    if(result==Result::Duplicate) {
        const auto& entries=journal_.committed();
        const bool durable=std::any_of(entries.begin(),entries.end(),[&](const Entry& v){return std::holds_alternative<Event>(v) && std::get<Event>(v).id==event.id;});
        return {result,durable,entries.size()};
    }
    bool durable=false;
    if(result==Result::Accepted && journal_.writable()) {
        try { durable=journal_.append(event); } catch(...) { durable=false; }
    }
    if(!durable) ledger_.recording_gap();
    if(!ledger_.complete()) journal_.invalidate();
    return {result,durable,journal_.committed().size()};
}
Receipt Recorder::clear(const Clear& clear) {
    Ledger next=ledger_; const auto result=next.clear(clear);
    if(result==Result::Duplicate) return {result,true,journal_.committed().size()};
    if(result!=Result::Accepted) {
        if(!next.complete()) { ledger_.recording_gap(); journal_.invalidate(); }
        return {result,false,journal_.committed().size()};
    }
    bool durable=false;
    if(journal_.writable()) {
        try { durable=journal_.append(clear); } catch(...) { durable=false; }
    }
    if(durable) ledger_=std::move(next); else { ledger_.recording_gap(); journal_.invalidate(); }
    return {durable?result:Result::StorageFailure,durable,journal_.committed().size()};
}
std::size_t Recorder::drain(EventQueue& queue,std::size_t budget) {
    const auto check_health=[&] {
        const auto h=queue.health();
        if(h.dropped || h.identity_error) { ledger_.recording_gap(); journal_.invalidate(); }
    };
    check_health(); Event e; std::size_t consumed=0;
    while(consumed<budget && queue.pop(e)) { record(e); ++consumed; }
    check_health(); return consumed;
}
} // namespace stratadrive::diagnostics
