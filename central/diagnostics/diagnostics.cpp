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
template<class I> void transfer(I& i,Record& v) {
    i(v.key,v.generation,v.revision,v.count,v.first,v.last,v.first_event,v.last_event,
      v.first_detected,v.last_detected,v.state_session,v.state_event,v.condition,v.latch,v.cleared,v.pass_event);
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
template<class I> void transfer(I& i,ContinuityReview& v) {
    i(v.id,v.incident,v.proof_event,v.session,v.revision,v.disposition,v.evidence);
    auto size=static_cast<std::uint32_t>(v.streams.size());i(size);
    if(!size || size>32)throw std::runtime_error("diagnostics review stream count");
    v.streams.resize(size);for(auto& cut:v.streams)i(cut.stream,cut.producer,cut.committed,cut.tip,cut.tip_crc);
}
} // namespace
bool stationary_evidence(const ServiceEvidence& e) noexcept {return stationary(e);}
void validate(Limits l) {
    for(auto v : {l.events,l.records,l.occurrences,l.clears}) if(v==0 || v>4096) throw std::invalid_argument("diagnostics limits");
}
std::vector<std::uint8_t> encode(const Entry& entry) {
    Writer w; auto tag=static_cast<std::uint8_t>(entry.index()); w(tag);
    if(tag==0) { auto e=std::get<Event>(entry); w(e); }
    else if(tag==1) { auto c=std::get<Clear>(entry); w(c); }
    else {auto review=std::get<ContinuityReview>(entry);w(review);}
    return std::move(w.data);
}
Entry decode(const std::vector<std::uint8_t>& bytes) {
    Reader r{bytes}; std::uint8_t tag=0; r(tag); Entry entry;
    if(tag==0) { Event e; r(e); entry=e; }
    else if(tag==1) { Clear c; r(c); entry=std::move(c); }
    else if(tag==2) {ContinuityReview review;r(review);entry=std::move(review);}
    else throw std::runtime_error("diagnostics entry tag");
    if(r.cursor!=bytes.size()) throw std::runtime_error("diagnostics trailing payload");
    return entry;
}
Ledger::Ledger(Limits limits):limits_(limits) {
    validate(limits); events_.reserve(limits.events); records_.reserve(limits.records);
    episodes_.reserve(limits.occurrences); clears_.reserve(limits.clears);approvals_.reserve(limits.clears);
}
std::vector<std::uint8_t> encode_checkpoint(const EpochCheckpoint& checkpoint) {
    Writer w;std::uint32_t schema=1;w(schema);
    auto c=checkpoint;w(c.previous,c.revision);
    auto records=static_cast<std::uint32_t>(c.records.size()),faults=static_cast<std::uint32_t>(c.faults.size());
    if(records>4096 || faults>4096) throw std::invalid_argument("checkpoint bounds");
    w(records);for(auto& r:c.records)w(r);
    w(faults);for(auto& e:c.faults)w(e);
    return std::move(w.data);
}
EpochCheckpoint decode_checkpoint(const std::vector<std::uint8_t>& bytes) {
    Reader r{bytes};EpochCheckpoint c;std::uint32_t schema=0,count=0;r(schema);
    if(schema!=1)throw std::runtime_error("checkpoint schema");
    r(c.previous,c.revision,count);if(count>4096)throw std::runtime_error("checkpoint records");
    c.records.resize(count);for(auto& v:c.records)r(v);
    r(count);if(count>4096)throw std::runtime_error("checkpoint faults");
    c.faults.resize(count);for(auto& v:c.faults)r(v);
    if(r.cursor!=bytes.size())throw std::runtime_error("checkpoint trailing bytes");
    return c;
}
EpochCheckpoint Ledger::checkpoint() const {
    if(!complete_ || unmapped() || !valid(session_))throw std::runtime_error("checkpoint incomplete history");
    EpochCheckpoint c{session_,revision_,records_,{}};
    for(auto& r:c.records) {
        r.condition=Condition::Unknown;r.latch=Latch::Unknown;r.pass_event={};
        if(r.cleared)continue;
        const auto fault=std::find_if(events_.begin(),events_.end(),[&](const Event& e){
            return e.kind==Kind::Fault && e.occurrence==r.last && e.key==r.key;
        });
        if(fault==events_.end() || continuity_incident(*fault))throw std::runtime_error("checkpoint needs continuity review/clear");
        c.faults.push_back(*fault);
    }
    return c;
}
Ledger::Ledger(const EpochCheckpoint& c,Limits limits):Ledger(limits) {
    if(!valid(c.previous) || !c.revision || c.records.size()>limits.records || c.faults.size()>limits.occurrences ||
       c.faults.size()>=limits.events)throw std::invalid_argument("checkpoint bounds/session");
    session_=c.previous;revision_=c.revision;historical_epoch_floor_=c.previous.epoch;
    for(const auto& r:c.records) {
        if(!valid(r.key) || !r.generation || !r.count || !r.revision || r.revision>c.revision ||
           !valid(r.first) || !valid(r.last) || !valid(r.first_event) || !valid(r.last_event) ||
           ((!valid(r.state_session) || !valid(r.state_event)) && (!(r.state_session==Session{}) || !(r.state_event==EventId{}))) ||
           r.state_session.epoch>session_.epoch ||
           !valid(r.first_detected) || !valid(r.last_detected) || r.condition!=Condition::Unknown || r.latch!=Latch::Unknown ||
           !(r.pass_event==EventId{}) || find(r.key))throw std::invalid_argument("checkpoint record");
        records_.push_back(r);
    }
    for(const auto& e:c.faults) {
        const auto* r=find(e.key);
        if(!valid(e) || e.kind!=Kind::Fault || e.unmapped || continuity_incident(e) || e.session.epoch>session_.epoch ||
           !r || r->cleared || !(r->last==e.occurrence) || !(r->last_event==e.id) ||
           std::any_of(events_.begin(),events_.end(),[&](const Event& old){return old.key==e.key || old.id==e.id;}))
            throw std::invalid_argument("checkpoint fault");
        events_.push_back(e);episodes_.push_back({e.occurrence,e.key,r->generation,true});
    }
    if(c.faults.size()!=static_cast<std::size_t>(std::count_if(records_.begin(),records_.end(),[](const Record& r){return !r.cleared;})))
        throw std::invalid_argument("checkpoint missing fault");
    restarted();
}
const Record* Ledger::find(const Key& key) const noexcept {
    const auto it=std::find_if(records_.begin(),records_.end(),[&](const Record& r){return r.key==key;});
    return it==records_.end()?nullptr:&*it;
}
Record* Ledger::mutable_record(const Key& key) noexcept { return const_cast<Record*>(std::as_const(*this).find(key)); }
void Ledger::restarted() noexcept {
    approval_floor_=approvals_.size();recording_floor_=events_.size();
    for(auto& r:records_) { r.condition=Condition::Unknown; r.latch=Latch::Unknown; r.pass_event={}; }
}
void Ledger::recording_gap() noexcept { complete_=false; restarted(); }
Result Ledger::record(const Event& e) {
    const auto old=std::find_if(events_.begin(),events_.end(),[&](const Event& v){return v.id==e.id;});
    if(old!=events_.end()) {
        if(encode(*old)==encode(e)) return Result::Duplicate;
        recording_gap(); return Result::Conflict;
    }
    if(std::any_of(approvals_.begin(),approvals_.end(),[&](const Approval& a){return a.review.id==e.id;})){recording_gap();return Result::Conflict;}
    Ledger next=*this; const auto result=next.apply(e);
    if(result==Result::Accepted) *this=std::move(next); else recording_gap();
    return result;
}
Result Ledger::apply(const Event& e) {
    if(!valid(e)) return Result::Invalid;
    if(e.session.epoch<=historical_epoch_floor_)return Result::NotReady;
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
    unmapped_=unmapped_ || (e.unmapped && !continuity_incident(e));
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
    const auto incident=std::find_if(events_.begin(),events_.end(),[&](const Event& v){return v.kind==Kind::Fault && v.occurrence==e.occurrence && v.key==e.key;});
    if(incident!=events_.end() && continuity_incident(*incident)) {
        const auto approval=std::find_if(approvals_.begin()+static_cast<std::ptrdiff_t>(approval_floor_),approvals_.end(),[&](const Approval& a){
            return a.review.id==e.related && a.review.incident==incident->id && a.review.proof_event==e.proof_event && a.review.session==e.session;
        });
        if(approval==approvals_.end() || approval->review.id.producer!=e.id.producer || approval->review.id.sequence>=e.id.sequence ||
           static_cast<std::size_t>(&e-events_.data())<approval->event_floor || !comparable(e.times[static_cast<std::size_t>(Time::Observed)],approval->review.evidence.now) ||
           e.times[static_cast<std::size_t>(Time::Observed)].ns<approval->review.evidence.now.ns)return false;
    }
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
    if(std::any_of(approvals_.begin(),approvals_.end(),[&](const Approval& a){return a.review.id==c.id;}))return Result::Invalid;
    if(!valid(c.id) || !valid(c.session) || c.id.run!=c.session.run || c.targets.empty() || c.targets.size()>limits_.records) return Result::Invalid;
    if(!complete_ || !released_ || unmapped() || !(c.session==session_) || !same_stamp(c.evidence.enable,enable_) || !stationary(c.evidence)) return Result::NotReady;
    if(clears_.size()+approvals_.size()>=limits_.clears || revision_==std::numeric_limits<std::uint64_t>::max()) { recording_gap(); return Result::Capacity; }
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
bool continuity_incident(const Event& e) noexcept {
    const auto& detected=e.times[static_cast<std::size_t>(Time::Detected)];const auto& observed=e.times[static_cast<std::size_t>(Time::Observed)];
    return e.kind==Kind::Fault && e.key.code==Code::RecordingGap && e.key.monitor==10 && e.key.subject &&
        e.id.sequence==1 && e.occurrence.sequence==1 && e.occurrence.producer==e.id.producer && e.occurrence.epoch==e.session.epoch &&
        e.native_reason==1 && e.state_before && e.state_before<std::numeric_limits<std::uint32_t>::max() && e.state_after==e.state_before+1 &&
        e.id.producer==((static_cast<std::uint64_t>(e.state_before)<<32)|e.key.subject) && e.cause_unknown && e.unmapped &&
        e.latch==Latch::Unknown && detected.domain==Domain::Monotonic && comparable(detected,observed) && detected.ns<=observed.ns &&
        comparable(e.session_enable,observed) && e.session_enable.ns<=observed.ns;
}
bool Ledger::unmapped() const noexcept {
    if(unmapped_)return true;
    return std::any_of(events_.begin(),events_.end(),[&](const Event& e){
        return continuity_incident(e) && std::none_of(approvals_.begin(),approvals_.end(),[&](const Approval& a){return a.review.incident==e.id;});
    });
}
Result Ledger::review(const ContinuityReview& c) {
    const auto old=std::find_if(approvals_.begin(),approvals_.end(),[&](const Approval& a){return a.review.id==c.id;});
    if(old!=approvals_.end()){if(encode(old->review)==encode(c))return Result::Duplicate;recording_gap();return Result::Conflict;}
    if(!valid(c.id) || !valid(c.session) || c.id.run!=c.session.run || c.disposition!=ContinuityDisposition::AcceptUnknownHistory ||
       c.streams.empty() || c.streams.size()>32 || !valid(c.incident) || !valid(c.proof_event) || c.id.producer!=c.proof_event.producer || c.id.sequence<=c.proof_event.sequence ||
       std::any_of(events_.begin(),events_.end(),[&](const Event& e){return e.id==c.id;}) || std::any_of(clears_.begin(),clears_.end(),[&](const Clear& e){return e.id==c.id;}))return Result::Invalid;
    if(!complete_ || !released_ || !(c.session==session_) || !same_stamp(c.evidence.enable,enable_) || !stationary(c.evidence))return Result::NotReady;
    const auto incident=std::find_if(events_.begin(),events_.end(),[&](const Event& e){return e.id==c.incident;});
    const auto proof=std::find_if(events_.begin(),events_.end(),[&](const Event& e){return e.id==c.proof_event;});
    const auto global=std::find_if(events_.begin(),events_.end(),[&](const Event& e){return e.kind==Kind::Session && e.session==session_;});
    if(incident==events_.end() || !continuity_incident(*incident) || !(incident->session.run==c.session.run) || !comparable(incident->session_enable,c.evidence.now) || c.session.epoch<=incident->session.epoch ||
       global==events_.end() || proof==events_.end() || static_cast<std::size_t>(proof-events_.begin())<recording_floor_ || proof->kind!=Kind::Observation || proof->proof!=Proof::Recording || !(proof->related==incident->id) || !(proof->key==incident->key) ||
       !(proof->occurrence==incident->occurrence) || !(proof->session==session_) || !same_stamp(proof->session_enable,enable_) || proof->unmapped || !proof->cause_unknown || proof->latch!=Latch::Clear || proof->profile!=incident->profile || proof->profile!=global->profile ||
       !proof->source.present || proof->source.producer!=proof->id.producer || proof->source.epoch!=session_.epoch || !same_stamp(proof->source.source,proof->times[static_cast<std::size_t>(Time::Observed)]) ||
       !comparable(c.evidence.now,proof->times[static_cast<std::size_t>(Time::Observed)]) || proof->times[static_cast<std::size_t>(Time::Observed)].ns>c.evidence.now.ns ||
       c.evidence.now.ns-proof->times[static_cast<std::size_t>(Time::Observed)].ns>30000000 || global->expected_roles!=255 || global->received_roles!=255)return Result::NotReady;
    auto* r=mutable_record(incident->key);
    const auto episode=std::find_if(episodes_.begin(),episodes_.end(),[&](const Episode& p){return p.id==incident->occurrence;});
    if(!r || r->cleared || r->revision!=c.revision || episode==episodes_.end() || !episode->confirmed || episode->generation!=r->generation)return Result::NotReady;
    for(std::size_t i=0;i<c.streams.size();++i){const auto& cut=c.streams[i];
        if(!cut.stream || !cut.producer || !cut.committed || !valid(cut.tip) || cut.tip.run!=session_.run ||
           std::any_of(c.streams.begin(),c.streams.begin()+static_cast<std::ptrdiff_t>(i),[&](const StreamCut& v){return v.stream==cut.stream || v.producer==cut.producer;}))return Result::Invalid;
        const auto tip=std::find_if(events_.begin(),events_.end(),[&](const Event& e){return e.id==cut.tip;});
        if(tip==events_.end())return Result::NotReady;
        const auto bytes=encode(*tip);std::uint32_t crc=0xffffffff;
        for(auto byte:bytes){crc^=byte;for(unsigned bit=0;bit<8;++bit)crc=(crc>>1)^((crc&1)?0xedb88320U:0U);}
        if((~crc)!=cut.tip_crc)return Result::Conflict;
    }
    if(clears_.size()+approvals_.size()>=limits_.clears || revision_==std::numeric_limits<std::uint64_t>::max()){recording_gap();return Result::Capacity;}
    approvals_.push_back({c,events_.size()});r->revision=++revision_;return Result::Accepted;
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
    replay();
}
Recorder::Recorder(Journal& journal,const EpochCheckpoint& checkpoint):journal_(journal),ledger_(checkpoint,journal.limits()) {
    replay();
}
void Recorder::replay() {
    for(const auto& entry:journal_.committed()) {
        const auto result=std::holds_alternative<Event>(entry)?ledger_.record(std::get<Event>(entry)):std::holds_alternative<Clear>(entry)?ledger_.clear(std::get<Clear>(entry)):ledger_.review(std::get<ContinuityReview>(entry));
        if(result!=Result::Accepted) throw std::runtime_error("diagnostics invalid journal transaction");
    }
    ledger_.restarted(); if(!journal_.writable()) ledger_.recording_gap();
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
void Recorder::recording_gap() noexcept { ledger_.recording_gap(); journal_.invalidate(); }
Receipt Recorder::review(const ContinuityReview& review) {
    Ledger next=ledger_;const auto result=next.review(review);
    if(result==Result::Duplicate)return {result,true,journal_.committed().size()};
    if(result!=Result::Accepted){if(!next.complete()){ledger_.recording_gap();journal_.invalidate();}return {result,false,journal_.committed().size()};}
    bool durable=false;if(journal_.writable()){try{durable=journal_.append(review);}catch(...){durable=false;}}
    if(durable)ledger_=std::move(next);else{ledger_.recording_gap();journal_.invalidate();}
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
