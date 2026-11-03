#include "remote_diagnostics_context.hpp"
#include <algorithm>
#include <stdexcept>
#include <utility>

namespace stratadrive::diagnostics {
ContextualOutbox::ContextualOutbox(FileJournal& j,ControlContext c,std::uint64_t central)
    :ContextualOutbox(j,c,std::vector<CentralIssuer>{{central,1}}) {}
ContextualOutbox::ContextualOutbox(FileJournal& j,ControlContext c,std::vector<CentralIssuer> lineage)
    :outbox_(j),local_(c),issuers_(std::move(lineage)) {
    if(!c.run || !c.producer || !c.clock_instance || !c.profile || c.domain!=Domain::Monotonic)
        throw std::invalid_argument("remote diagnostic manifest");
    if(issuers_.empty() || issuers_.size()>16 || issuers_.front().first_epoch!=1)throw std::invalid_argument("remote Central lineage");
    for(std::size_t i=0;i<issuers_.size();++i) {
        const auto& item=issuers_[i];
        if(!item.producer || item.producer==c.producer || !item.first_epoch ||
           (i && item.first_epoch<=issuers_[i-1].first_epoch) ||
           std::any_of(issuers_.begin(),issuers_.begin()+static_cast<std::ptrdiff_t>(i),[&](const auto& old){return old.producer==item.producer;}))
            throw std::invalid_argument("remote Central lineage");
    }
    pending_.reserve(kPending);
    for(const auto& entry:j.committed()) {
        const auto& e=std::get<Event>(entry);
        if(e.id.run!=c.run || e.profile!=c.profile || !e.session_enable.present ||
           e.session_enable.domain!=c.domain || e.session_enable.instance!=c.clock_instance ||
           (e.kind==Kind::Session?e.id.producer!=issuer(e.session.epoch):e.id.producer!=c.producer))
            throw std::invalid_argument("remote diagnostic store manifest");
        if(e.kind==Kind::Session) retained_context_=e;
    }
}
std::uint64_t ContextualOutbox::issuer(std::uint32_t epoch) const noexcept {
    std::uint64_t producer=0;for(const auto& entry:issuers_)if(epoch>=entry.first_epoch)producer=entry.producer;else break;return producer;
}
Result ContextualOutbox::restore(const remote::RunLeaseEvidence& evidence) {
    return retained_context_?context(*retained_context_,evidence):Result::NotReady;
}
ContextualOutbox::~ContextualOutbox() { if(!pending_.empty()) outbox_.recording_gap(); }
bool ContextualOutbox::matches(const Event& e) const noexcept {
    return context_ && e.session==context_->session && comparable(e.session_enable,context_->session_enable) &&
        e.session_enable.ns==context_->session_enable.ns;
}
Result ContextualOutbox::commit(const Event& e) {
    const auto r=outbox_.record(e);
    if(!r.durable && r.result==Result::Accepted) return Result::StorageFailure;
    return r.result;
}
Result ContextualOutbox::context(const Event& e,const remote::RunLeaseEvidence& evidence) {
    if(!outbox_.healthy()) return Result::NotReady;
    const auto trusted=[&](const Stamp& s) {
        return s.present && s.trusted && s.domain==local_.domain && s.instance==local_.clock_instance;
    };
    if(e.schema!=1 || e.kind!=Kind::Session || e.id.run!=local_.run || e.id.producer!=issuer(e.session.epoch) || !e.id.sequence ||
       e.session.run!=local_.run || !e.session.epoch || e.profile!=local_.profile ||
       e.key.code!=Code::None || e.proof!=Proof::None || e.expected_roles!=255 || e.received_roles!=255 ||
       !trusted(e.session_enable) || !e.source.present || e.source.producer!=issuer(e.session.epoch) ||
       e.source.epoch!=e.session.epoch || e.source.sequence!=e.session.epoch ||
       !trusted(e.source.source) || !trusted(e.source.expiry) || !trusted(e.times[static_cast<std::size_t>(Time::Observed)])) return Result::Invalid;
    const auto& a=evidence.clock;
    if(!a.established || a.local_domain!=local_.clock_instance || a.source_domain!=a.local_domain || a.offset_ns || a.uncertainty_ns)
        return Result::Invalid;
    if(!evidence.accepted) return Result::NotReady;
    const auto& lease=*evidence.accepted; const auto& p=lease.plan;
    if(e.session.epoch!=p.epoch) return Result::NotReady;
    if(e.session_enable.ns!=p.enable_ns || e.source.expiry.ns!=p.prepare_deadline_ns ||
       e.source.source.ns<p.enable_ns || e.source.source.ns>=p.commit_deadline_ns ||
       e.source.source.ns>lease.source_time_ns || e.times[static_cast<std::size_t>(Time::Observed)].ns<e.source.source.ns)
        return Result::Invalid;
    if(context_ && e.session.epoch==context_->session.epoch) {
        if(encode(e)==encode(*context_)) return Result::Duplicate;
        outbox_.recording_gap(); return Result::Conflict;
    }
    if(e.session.epoch<outbox_.ledger().session().epoch || (context_ && e.session.epoch<context_->session.epoch) ||
       std::any_of(pending_.begin(),pending_.end(),[&](const Event& item){return item.session.epoch<e.session.epoch;})) return Result::NotReady;
    const auto result=commit(e);
    if(result!=Result::Accepted && result!=Result::Duplicate) return result;
    // A new trusted issuer may use a fresh replica. Reset delivery only after
    // original context/actual endpoint evidence and durable context commit.
    if(retained_context_ && retained_context_->id.producer!=e.id.producer)outbox_.restart_delivery();
    context_=e;retained_context_=e;
    while(!pending_.empty() && pending_.front().session==e.session) {
        if(!matches(pending_.front())) { outbox_.recording_gap(); return Result::Conflict; }
        const auto r=commit(pending_.front());
        if(r!=Result::Accepted && r!=Result::Duplicate) { outbox_.recording_gap(); return r; }
        pending_.erase(pending_.begin());
    }
    return result;
}
Result ContextualOutbox::submit(const Event& e) {
    if(!outbox_.healthy()) return Result::NotReady;
    if(e.id.run!=local_.run || e.id.producer!=local_.producer || !e.id.sequence || e.session.run!=local_.run || !e.session.epoch ||
       e.profile!=local_.profile || e.kind==Kind::Session || e.kind==Kind::Attempt) return Result::Invalid;
    // A delayed Session may release historical faults, never retroactively
    // qualify recovery produced before this writer admitted the global context.
    if((e.kind==Kind::Passed || e.proof!=Proof::None) && !matches(e)) return Result::NotReady;
    if(context_ && e.session.epoch<=context_->session.epoch) {
        if(!matches(e)) return Result::Invalid;
        return commit(e);
    }
    if(!pending_.empty() && e.session.epoch<pending_.back().session.epoch) return Result::Invalid;
    if(pending_.size()==kPending) { outbox_.recording_gap(); return Result::Capacity; }
    pending_.push_back(e); return Result::Accepted;
}
std::size_t ContextualOutbox::drain(EventQueue& q,std::size_t budget) {
    const auto check=[&] {const auto h=q.health(); if(h.dropped || h.identity_error) outbox_.recording_gap();};
    check(); std::size_t consumed=0; Event e;
    while(consumed<budget && outbox_.healthy() && q.pop(e)) {
        ++consumed; const auto r=submit(e);
        if(r!=Result::Accepted && r!=Result::Duplicate) outbox_.recording_gap();
    }
    check(); return consumed;
}
} // namespace stratadrive::diagnostics
