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
Outbox::Outbox(FileJournal& j):journal_(j),recorder_(j) { event_only(j); }
std::optional<wire::Bytes> Outbox::next() {
    if(!healthy() || acknowledged_>=journal_.committed().size()) return std::nullopt;
    in_flight_=acknowledged_+1;
    return wire::encode(wire::Data{journal_.store_id(),in_flight_,journal_.registry_revision(),std::get<Event>(journal_.committed()[in_flight_-1])});
}
Result Outbox::acknowledge(const wire::Bytes& bytes) {
    wire::Message message;
    try { message=wire::decode(bytes); } catch(const std::exception&) { return Result::Invalid; }
    const auto* a=std::get_if<wire::Ack>(&message);
    if(!a || a->stream!=journal_.store_id() || a->registry!=journal_.registry_revision()) return Result::Invalid;
    if(!healthy()) return Result::NotReady;
    if(a->sequence>journal_.committed().size() || a->sequence>acknowledged_+1 || (a->sequence>acknowledged_ && a->sequence!=in_flight_)) return Result::NotReady;
    const auto& e=std::get<Event>(journal_.committed()[a->sequence-1]);
    if(a->event_crc!=wire::event_crc(e)) return Result::Conflict;
    if(a->sequence<=acknowledged_) return Result::Duplicate;
    acknowledged_=a->sequence; in_flight_=0; return Result::Accepted;
}
Inbox::Inbox(FileJournal& j):journal_(j),recorder_(j) { event_only(j); }
DeliveryReceipt Inbox::receive(const wire::Bytes& bytes) {
    const auto receipt=[&](Result result,std::optional<wire::Bytes> ack=std::nullopt) {return DeliveryReceipt{result,std::move(ack),journal_.committed().size()};};
    wire::Message message;
    try { message=wire::decode(bytes); } catch(const std::exception&) { return receipt(Result::Invalid); }
    const auto* d=std::get_if<wire::Data>(&message);
    if(!d || d->stream!=journal_.store_id() || d->registry!=journal_.registry_revision()) return receipt(Result::Invalid);
    if(!healthy()) return receipt(Result::NotReady);
    const auto& entries=journal_.committed();
    if(d->sequence>entries.size()+1) return receipt(Result::NotReady);
    if(d->sequence<=entries.size()) {
        if(diagnostics::encode(entries[d->sequence-1])!=diagnostics::encode(d->event)) { recorder_.recording_gap(); return receipt(Result::Conflict); }
        return receipt(Result::Duplicate,wire::encode(wire::Ack{d->stream,d->sequence,d->registry,wire::event_crc(d->event)}));
    }
    if(std::any_of(entries.begin(),entries.end(),[&](const Entry& e){return std::get<Event>(e).id==d->event.id;})) {
        recorder_.recording_gap(); return receipt(Result::Conflict);
    }
    const auto recorded=recorder_.record(d->event);
    if(!recorded.durable) return receipt(recorded.result==Result::Accepted?Result::StorageFailure:recorded.result);
    if(recorded.result!=Result::Accepted || recorded.watermark!=d->sequence) { recorder_.recording_gap(); return receipt(Result::Conflict); }
    return receipt(Result::Accepted,wire::encode(wire::Ack{d->stream,d->sequence,d->registry,wire::event_crc(d->event)}));
}
} // namespace stratadrive::diagnostics
