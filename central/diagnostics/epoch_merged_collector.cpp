#include "diagnostics_delivery.hpp"
#include <algorithm>
#include <limits>
#include <stdexcept>

namespace stratadrive::diagnostics {
namespace {
bool boundary(const Event& e) {return e.kind==Kind::Session || e.kind==Kind::Attempt;}
}
EpochMergedCollector::EpochMergedCollector(EpochRecorder& merged,const std::vector<EpochRecorder*>& replicas):merged_(merged) {
    if(replicas.empty() || replicas.size()>kSources)throw std::invalid_argument("epoch collector source count");
    std::vector<std::uint64_t> streams;
    for(auto* source:replicas) {
        if(!source || source==&merged || source->store_id()==merged.store_id() ||
           std::find(streams.begin(),streams.end(),source->store_id())!=streams.end())
            throw std::invalid_argument("epoch collector manifest");
        streams.push_back(source->store_id());
    }
    const DeliveryStore event_only(merged);(void)event_only;
    for(auto* source:replicas)replicas_.push_back({source,std::make_unique<Inbox>(*source),0,std::nullopt});
    std::sort(replicas_.begin(),replicas_.end(),[](const auto& a,const auto& b){return a.store->store_id()<b.store->store_id();});
    if(!healthy())throw std::runtime_error("epoch collector incomplete");
    merged_.bind_merge_sources(std::move(streams));
    const auto result=reconcile();
    if((result!=Result::Accepted && result!=Result::NotReady) || !healthy())
        throw std::runtime_error("epoch collector reconciliation failed");
    // Replaying a replica-only commit after a crash is historical evidence,
    // never fresh proof that the current physical condition has recovered.
    merged_.restarted();
}
bool EpochMergedCollector::healthy() const noexcept {
    return merged_.ledger().complete() && std::all_of(replicas_.begin(),replicas_.end(),[](const auto& r){return r.inbox->healthy();});
}
Result EpochMergedCollector::reconcile() {
    try {
        for(;;) {
            bool all=true;std::uint32_t next=std::numeric_limits<std::uint32_t>::max();Replica* eligible=nullptr;
            for(auto& r:replicas_) {
                if(!r.head && r.consumed<r.store->watermark()) {
                    r.head=std::get<Event>(r.store->committed(r.consumed+1));
                    const auto& e=*r.head;
                    const auto prior=r.consumed?std::get<Event>(r.store->committed(r.consumed)).session.epoch:0;
                    if(!run_)run_=e.session.run;
                    if(e.session.run!=run_ || e.id.run!=run_ || e.session.epoch<prior ||
                       (e.session.epoch>prior && !boundary(e))) {
                        r.store->recording_gap();merged_.recording_gap();return Result::Conflict;
                    }
                }
                if(!r.head){all=false;continue;}
                next=std::min(next,r.head->session.epoch);
                if(r.head->session.epoch==epoch_ && (!eligible || r.head->kind==Kind::Attempt))eligible=&r;
            }
            if(eligible) {
                const auto receipt=merged_.record(*eligible->head);
                if(!receipt.durable || !healthy())return receipt.result==Result::Accepted?Result::StorageFailure:receipt.result;
                ++eligible->consumed;eligible->head.reset();continue;
            }
            if(!all)return Result::NotReady;
            // Every ordered prefix has reached a real later boundary. No
            // unreceived old tail can be hidden by advancing the checkpoint.
            if(next<=epoch_){merged_.recording_gap();return Result::Conflict;}
            epoch_=next;
        }
    }catch(...){merged_.recording_gap();return Result::StorageFailure;}
}
DeliveryReceipt EpochMergedCollector::receive(const wire::Bytes& bytes) {
    wire::Message message;
    try{message=wire::decode(bytes);}catch(const std::exception&){return {Result::Invalid,std::nullopt,0};}
    const auto* data=std::get_if<wire::Data>(&message);
    if(!data)return {Result::Invalid,std::nullopt,0};
    const auto found=std::find_if(replicas_.begin(),replicas_.end(),[&](const auto& r){return r.store->store_id()==data->stream;});
    if(found==replicas_.end() || data->registry!=EpochRecorder::registry_revision())return {Result::Invalid,std::nullopt,0};
    auto& r=*found;const auto count=r.store->watermark();
    if(!healthy() || data->sequence>r.consumed+1)return {Result::NotReady,std::nullopt,count};
    // Validate new stream order before its replica can rotate. Retransmissions
    // are compared by Inbox against exact historical bytes instead.
    if(data->sequence==count+1) {
        try {
            const auto previous=count?std::get<Event>(r.store->committed(count)).session.epoch:0;
            if(data->event.session.epoch<previous || (data->event.session.epoch>previous && !boundary(data->event)) ||
               (run_ && data->event.session.run!=run_)) {
                r.store->recording_gap();merged_.recording_gap();return {Result::Conflict,std::nullopt,count};
            }
        }catch(...){merged_.recording_gap();return {Result::StorageFailure,std::nullopt,count};}
    }
    auto receipt=r.inbox->receive(bytes);
    if(!receipt.ack)return receipt;
    const auto result=reconcile();
    if(!healthy() || r.consumed<data->sequence) {
        receipt.ack.reset();receipt.result=result==Result::Accepted?Result::NotReady:result;
    }
    return receipt;
}
} // namespace stratadrive::diagnostics
