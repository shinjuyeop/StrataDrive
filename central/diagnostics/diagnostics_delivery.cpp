#include "diagnostics_delivery.hpp"
#include <algorithm>
#include <stdexcept>

namespace stratadrive::diagnostics {
namespace {
void event_only(const FileJournal& j) {
    if(std::any_of(j.committed().begin(),j.committed().end(),[](const Entry& e){return !std::holds_alternative<Event>(e);}))
        throw std::invalid_argument("diagnostic delivery requires event-only store");
}
}
DeliveryStore::DeliveryStore(FileJournal& j):journal_(&j),recorder_(std::make_unique<Recorder>(j)) {event_only(j);}
DeliveryStore::DeliveryStore(EpochRecorder& epochs):epochs_(&epochs) {
    for(std::uint64_t ordinal=1;ordinal<=size();++ordinal)
        if(!std::holds_alternative<Event>(epochs.committed(ordinal)))throw std::invalid_argument("diagnostic delivery requires event-only family");
}
std::uint64_t DeliveryStore::store_id() const noexcept {return epochs_?epochs_->store_id():journal_->store_id();}
std::uint32_t DeliveryStore::registry_revision() const noexcept {return epochs_?epochs_->registry_revision():journal_->registry_revision();}
std::uint64_t DeliveryStore::size() const noexcept {return epochs_?epochs_->watermark():journal_->committed().size();}
Event DeliveryStore::event(std::uint64_t ordinal) const {
    return std::get<Event>(epochs_?epochs_->committed(ordinal):journal_->committed().at(static_cast<std::size_t>(ordinal-1)));
}
Receipt DeliveryStore::record(const Event& e) {return epochs_?epochs_->record(e):recorder_->record(e);}
std::size_t DeliveryStore::drain(EventQueue& q,std::size_t budget) {return epochs_?epochs_->drain(q,budget):recorder_->drain(q,budget);}
bool DeliveryStore::healthy() const noexcept {return epochs_?epochs_->ledger().complete():journal_->writable() && recorder_->ledger().complete();}
const Ledger& DeliveryStore::ledger() const noexcept {return epochs_?epochs_->ledger():recorder_->ledger();}
void DeliveryStore::recording_gap() noexcept {if(epochs_)epochs_->recording_gap();else recorder_->recording_gap();}
Outbox::Outbox(FileJournal& j):store_(j) {}
Outbox::Outbox(EpochRecorder& j):store_(j) {}
std::optional<wire::Bytes> Outbox::next() {
    if(!healthy() || acknowledged_>=store_.size()) return std::nullopt;
    in_flight_=acknowledged_+1;
    return wire::encode(wire::Data{store_.store_id(),in_flight_,store_.registry_revision(),store_.event(in_flight_)});
}
namespace {
template<class Read>
Result accept_ack(std::uint64_t stream,std::uint32_t registry,std::uint64_t size,Read read,
    const wire::Bytes& bytes,bool ready,std::uint64_t& acknowledged,std::uint64_t& in_flight) {
    wire::Message message;
    try { message=wire::decode(bytes); } catch(const std::exception&) { return Result::Invalid; }
    const auto* a=std::get_if<wire::Ack>(&message);
    if(!a || a->stream!=stream || a->registry!=registry) return Result::Invalid;
    if(!ready) return Result::NotReady;
    if(a->sequence>size || a->sequence>acknowledged+1 || (a->sequence>acknowledged && a->sequence!=in_flight)) return Result::NotReady;
    if(a->event_crc!=wire::event_crc(read(a->sequence))) return Result::Conflict;
    if(a->sequence<=acknowledged) return Result::Duplicate;
    acknowledged=a->sequence; in_flight=0; return Result::Accepted;
}
}
Result Outbox::acknowledge(const wire::Bytes& bytes) {
    return accept_ack(store_.store_id(),store_.registry_revision(),store_.size(),
        [&](std::uint64_t n){return store_.event(n);},bytes,healthy(),acknowledged_,in_flight_);
}
Inbox::Inbox(FileJournal& j):store_(j) {}
Inbox::Inbox(EpochRecorder& j):store_(j) {}
DeliveryReceipt Inbox::receive(const wire::Bytes& bytes) {
    const auto receipt=[&](Result result,std::optional<wire::Bytes> ack=std::nullopt) {return DeliveryReceipt{result,std::move(ack),store_.size()};};
    wire::Message message;
    try { message=wire::decode(bytes); } catch(const std::exception&) { return receipt(Result::Invalid); }
    const auto* d=std::get_if<wire::Data>(&message);
    if(!d || d->stream!=store_.store_id() || d->registry!=store_.registry_revision()) return receipt(Result::Invalid);
    if(!healthy()) return receipt(Result::NotReady);
    if(d->sequence>store_.size()+1) return receipt(Result::NotReady);
    if(d->sequence<=store_.size()) {
        if(diagnostics::encode(store_.event(d->sequence))!=diagnostics::encode(d->event)) { store_.recording_gap(); return receipt(Result::Conflict); }
        return receipt(Result::Duplicate,wire::encode(wire::Ack{d->stream,d->sequence,d->registry,wire::event_crc(d->event)}));
    }
    const auto recorded=store_.record(d->event);
    if(!recorded.durable) return receipt(recorded.result==Result::Accepted?Result::StorageFailure:recorded.result);
    // A durable duplicate under a NEW stream ordinal is an identity conflict,
    // never another commit. This includes IDs in archived epoch segments.
    if(recorded.result!=Result::Accepted || recorded.watermark!=d->sequence) { store_.recording_gap(); return receipt(Result::Conflict); }
    return receipt(Result::Accepted,wire::encode(wire::Ack{d->stream,d->sequence,d->registry,wire::event_crc(d->event)}));
}
CommittedReplay::CommittedReplay(const FileJournal& journal):journal_(journal),checked_(journal.limits()) {
    event_only(journal);
    for(const auto& entry:journal.committed())if(checked_.record(std::get<Event>(entry))!=Result::Accepted)
        throw std::invalid_argument("diagnostic replay prefix semantics");
    checked_.restarted();
}
bool CommittedReplay::source_complete() const noexcept {return journal_.writable() && checked_.complete();}
std::optional<wire::Bytes> CommittedReplay::next() {
    if(acknowledged_>=journal_.committed().size())return std::nullopt;
    in_flight_=acknowledged_+1;
    return wire::encode(wire::Data{journal_.store_id(),in_flight_,journal_.registry_revision(),std::get<Event>(journal_.committed()[in_flight_-1])});
}
Result CommittedReplay::acknowledge(const wire::Bytes& bytes) {return accept_ack(journal_.store_id(),journal_.registry_revision(),journal_.committed().size(),
    [&](std::uint64_t n){return std::get<Event>(journal_.committed()[n-1]);},bytes,true,acknowledged_,in_flight_);}
MergedCollector::MergedCollector(FileJournal& merged,const std::vector<FileJournal*>& replicas,const std::vector<const FileJournal*>& predecessors)
    :merged_(merged),recorder_(merged) {
    event_only(merged);
    for(std::size_t i=0;i<replicas.size();++i) {
        const auto* journal=replicas[i];
        if(!journal || journal->store_id()==merged.store_id() || journal->registry_revision()!=merged.registry_revision() ||
           std::any_of(replicas.begin(),replicas.begin()+static_cast<std::ptrdiff_t>(i),[&](const auto* old){return old->store_id()==journal->store_id();}))
            throw std::invalid_argument("diagnostic collector manifest");
        event_only(*journal);
        if(!journal->writable()) throw std::runtime_error("diagnostic replica incomplete");
    }
    for(const auto* history:predecessors) {
        if(!history || history==&merged || history->registry_revision()!=merged.registry_revision())throw std::invalid_argument("diagnostic predecessor manifest");
        // Validate before mutating destination; an uncommitted suffix is never
        // imported or repaired. Caller must report unverified continuity.
        const CommittedReplay checked(*history);(void)checked;
    }
    for(const auto* history:predecessors)for(const auto& entry:history->committed())
        if(!recorder_.record(std::get<Event>(entry)).durable)throw std::runtime_error("diagnostic predecessor import");
    for(auto* journal:replicas) replicas_.push_back({journal,std::make_unique<Inbox>(*journal)});
    if(!healthy()) throw std::runtime_error("diagnostic collector incomplete");
    for(const auto& replica:replicas_)for(const auto& entry:replica.journal->committed()) {
        if(!recorder_.record(std::get<Event>(entry)).durable) throw std::runtime_error("diagnostic merged reconciliation");
    }
    recorder_.restarted();
}
bool MergedCollector::healthy() const noexcept {
    return merged_.writable() && recorder_.ledger().complete() &&
        std::all_of(replicas_.begin(),replicas_.end(),[](const Replica& r){return r.inbox->healthy();});
}
DeliveryReceipt MergedCollector::receive(const wire::Bytes& bytes) {
    wire::Message message;
    try {message=wire::decode(bytes);} catch(const std::exception&) {return {Result::Invalid,std::nullopt,0};}
    const auto* data=std::get_if<wire::Data>(&message);
    if(!data) return {Result::Invalid,std::nullopt,0};
    const auto replica=std::find_if(replicas_.begin(),replicas_.end(),[&](const Replica& r){return r.journal->store_id()==data->stream;});
    if(replica==replicas_.end()) return {Result::Invalid,std::nullopt,0};
    if(!healthy()) return {Result::NotReady,std::nullopt,replica->journal->committed().size()};
    auto receipt=replica->inbox->receive(bytes);
    if(!receipt.ack) return receipt;
    const auto merged=recorder_.record(data->event);
    if(!merged.durable) {receipt.result=merged.result==Result::Accepted?Result::StorageFailure:merged.result;receipt.ack.reset();}
    return receipt;
}
} // namespace stratadrive::diagnostics
