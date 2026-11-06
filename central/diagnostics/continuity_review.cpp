#include "continuity_review.hpp"
#include <algorithm>
#include <limits>
#include <stdexcept>
#include <utility>

namespace stratadrive::diagnostics {
namespace {
std::uint32_t crc(const Entry& entry) {
    std::uint32_t n=0xffffffff;for(auto byte:encode(entry)){n^=byte;for(unsigned bit=0;bit<8;++bit)n=(n>>1)^((n&1)?0xedb88320U:0U);}return ~n;
}
bool same(const Stamp& a,const Stamp& b){return comparable(a,b) && a.ns==b.ns;}
}
std::uint64_t FrozenStream::store_id() const noexcept {return epochs_?epochs_->store_id():journal_->store_id();}
std::uint32_t FrozenStream::registry_revision() const noexcept {return epochs_?epochs_->registry_revision():journal_->registry_revision();}
std::uint64_t FrozenStream::size() const noexcept {return epochs_?epochs_->watermark():journal_->committed().size();}
Entry FrozenStream::committed(std::uint64_t ordinal) const {return epochs_?epochs_->committed(ordinal):journal_->committed().at(static_cast<std::size_t>(ordinal-1));}
bool FrozenStream::verified() const {
    // EpochRecorder verifies every retained segment/checkpoint when acquiring
    // its lifetime lock. Do not flatten that history into a finite Ledger.
    if(epochs_)return epochs_->ledger().complete();
    if(!journal_ || !journal_->writable() || journal_->uncommitted_bytes())return false;
    Ledger checked(journal_->limits());
    for(const auto& entry:journal_->committed()) {
        const auto* e=std::get_if<Event>(&entry);
        if(!e || checked.record(*e)!=Result::Accepted || !checked.complete())return false;
    }
    return true;
}
ContinuityInspector::ContinuityInspector(ControlContext c,std::vector<StreamBinding> manifest):service_(c),manifest_(std::move(manifest)) {
    if(!c.run || !c.producer || !c.profile || !c.clock_instance || c.domain!=Domain::Monotonic || manifest_.empty() || manifest_.size()>32)
        throw std::invalid_argument("continuity service manifest");
    for(std::size_t i=0;i<manifest_.size();++i){const auto& entry=manifest_[i];
        if(!entry.stream || !entry.producer || entry.producer==c.producer || std::any_of(manifest_.begin(),manifest_.begin()+static_cast<std::ptrdiff_t>(i),[&](const StreamBinding& v){return v.stream==entry.stream || v.producer==entry.producer;}))
            throw std::invalid_argument("continuity stream manifest");
    }
}
ReviewPreparation ContinuityInspector::prepare(const Ledger& ledger,EventId identity,const Event& global,const std::vector<StreamState>& streams,
    ContinuityDisposition disposition,const ServiceEvidence& evidence,std::uint64_t sequence) const {
    const auto blocked=[](ReviewBlock reason){return ReviewPreparation{reason,std::nullopt};};
    if(disposition!=ContinuityDisposition::AcceptUnknownHistory || !sequence || sequence>std::numeric_limits<std::uint64_t>::max()-2 || !stationary_evidence(evidence))return blocked(ReviewBlock::Request);
    if(!ledger.complete())return blocked(ReviewBlock::Storage);
    const auto incident=std::find_if(ledger.events().begin(),ledger.events().end(),[&](const Event& e){return e.id==identity;});
    if(incident==ledger.events().end() || !continuity_incident(*incident) || incident->id.run!=service_.run)return blocked(ReviewBlock::Incident);
    const auto* record=ledger.find(incident->key);if(!record || record->cleared)return blocked(ReviewBlock::Incident);
    const auto current=std::find_if(ledger.events().begin(),ledger.events().end(),[&](const Event& e){return e.id==global.id && encode(e)==encode(global);});
    if(current==ledger.events().end() || global.kind!=Kind::Session || !(ledger.session()==global.session) || global.session.run!=service_.run || global.session.epoch<=incident->session.epoch ||
       global.profile!=service_.profile || global.expected_roles!=255 || global.received_roles!=255 || !same(global.session_enable,evidence.enable) ||
       evidence.now.domain!=service_.domain || evidence.now.instance!=service_.clock_instance || !global.source.present || global.source.producer!=global.id.producer ||
       !comparable(global.source.source,global.session_enable) || global.source.source.ns<global.session_enable.ns || global.source.source.ns>evidence.now.ns ||
       incident->profile!=service_.profile || !comparable(incident->session_enable,evidence.now))return blocked(ReviewBlock::Session);
    if(streams.size()!=manifest_.size())return blocked(ReviewBlock::Streams);
    ContinuityPlan plan;auto& approval=plan.review;
    approval.id={service_.run,service_.producer,sequence+1};approval.incident=identity;approval.proof_event={service_.run,service_.producer,sequence};
    approval.session=global.session;approval.revision=record->revision;approval.disposition=disposition;approval.evidence=evidence;
    for(std::size_t i=0;i<streams.size();++i){const auto& state=streams[i];const auto& binding=manifest_[i];
        if(!state.source || !state.replica || state.source==state.replica || state.source.store_id()!=binding.stream || state.replica.store_id()!=binding.stream ||
           state.source.registry_revision()!=state.replica.registry_revision())return blocked(ReviewBlock::Streams);
        if(state.pending || state.queue.dropped || state.queue.identity_error || state.queue.first_lost_sequence)return blocked(ReviewBlock::Pending);
        const auto& source=state.source;const auto& replica=state.replica;
        if(!source.verified() || !replica.verified())return blocked(ReviewBlock::Storage);
        if(!source.size() || source.size()!=replica.size() || state.acknowledged!=source.size())return blocked(ReviewBlock::Pending);
        bool context=false;Session last{};Event tip;
        for(std::uint64_t ordinal=1;ordinal<=source.size();++ordinal){
            const auto entry=source.committed(ordinal);const auto* event=std::get_if<Event>(&entry);
            if(!event || encode(entry)!=encode(replica.committed(ordinal)) || event->id.run!=service_.run || event->profile!=service_.profile ||
               (event->kind!=Kind::Session && event->id.producer!=binding.producer))return blocked(ReviewBlock::Storage);
            if(encode(*event)==encode(global))context=true;
            if(event->kind==Kind::Session || event->kind==Kind::Attempt)last=event->session;
            tip=*event;
        }
        if(!context || !(last==global.session))return blocked(ReviewBlock::Session);
        approval.streams.push_back({binding.stream,binding.producer,source.size(),tip.id,crc(tip)});
    }
    auto& proof=plan.proof;proof=*incident;proof.id=approval.proof_event;proof.related=identity;proof.session=global.session;proof.session_enable=global.session_enable;
    proof.kind=Kind::Observation;proof.proof=Proof::Recording;proof.latch=Latch::Clear;proof.unmapped=false;proof.native_reason=2;
    proof.source={true,service_.producer,sequence,global.session.epoch,evidence.now,{}};proof.times[static_cast<std::size_t>(Time::Observed)]=evidence.now;
    auto& passed=plan.passed;passed=proof;passed.id.sequence=sequence+2;passed.kind=Kind::Passed;passed.proof_event=proof.id;passed.related=approval.id;
    return {ReviewBlock::None,std::move(plan)};
}
} // namespace stratadrive::diagnostics
