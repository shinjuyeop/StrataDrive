#include "epoch_local_spool.hpp"
#include <algorithm>
#include <stdexcept>
#include <utility>

namespace stratadrive::diagnostics {
EpochLocalSpool::EpochLocalSpool(EpochRecorder& store,std::uint64_t startup,std::uint64_t control)
    :EpochLocalSpool(store,startup,control,{{startup,control,1}}) {}
EpochLocalSpool::EpochLocalSpool(EpochRecorder& store,std::uint64_t startup,std::uint64_t control,std::vector<EpochPublishers> lineage)
    :out_(store),startup_(startup),control_(control),lineage_(std::move(lineage)) {
    if(!startup || !control || startup==control)throw std::invalid_argument("Central spool publishers");
    if(lineage_.empty() || lineage_.size()>16 || lineage_.front().first_epoch!=1 ||
       std::none_of(lineage_.begin(),lineage_.end(),[&](const auto& p){return p.startup==startup && p.control==control;}))
        throw std::invalid_argument("Central spool lineage");
    std::vector<std::uint64_t> ids;std::uint32_t epoch=0;
    for(const auto& pair:lineage_) {
        if(!pair.startup || !pair.control || pair.startup==pair.control || pair.first_epoch<=epoch ||
           std::find(ids.begin(),ids.end(),pair.startup)!=ids.end() || std::find(ids.begin(),ids.end(),pair.control)!=ids.end())
            throw std::invalid_argument("Central spool lineage");
        ids.push_back(pair.startup);ids.push_back(pair.control);epoch=pair.first_epoch;
    }
    for(std::uint64_t ordinal=1;ordinal<=out_.size();++ordinal) {
        const auto e=out_.event(ordinal);
        if(!bound(e,true) && (!bound(e,false) || e.kind==Kind::Session || e.kind==Kind::Attempt))
            throw std::invalid_argument("Central spool history publisher");
    }
    pending_.reserve(2*EventQueue::kCapacity);
}
bool EpochLocalSpool::bound(const Event& e,bool startup) const noexcept {
    const EpochPublishers* binding=nullptr;
    for(const auto& pair:lineage_)if(e.session.epoch>=pair.first_epoch)binding=&pair;else break;
    return binding && e.id.producer==(startup?binding->startup:binding->control);
}
EpochLocalSpool::~EpochLocalSpool(){if(!pending_.empty())out_.recording_gap();}
std::size_t EpochLocalSpool::drain(EventQueue& startup,EventQueue& control,std::uint32_t retired) {
    if(retired<retired_){out_.recording_gap();return 0;}
    retired_=retired;std::size_t consumed=0;
    for(auto* queue:{&startup,&control}) {
        const auto health=queue->health();
        if(health.dropped || health.identity_error)out_.recording_gap();
        Event e;
        for(std::size_t n=0;n<EventQueue::kCapacity && out_.healthy() && queue->pop(e);++n) {
            ++consumed;
            if(pending_.size()==2*EventQueue::kCapacity || e.id.producer!=(queue==&startup?startup_:control_) || !bound(e,queue==&startup) ||
               (queue==&control && (e.kind==Kind::Session || e.kind==Kind::Attempt))) {out_.recording_gap();break;}
            pending_.push_back(e);
        }
        const auto after=queue->health();if(after.dropped || after.identity_error)out_.recording_gap();
    }
    std::stable_sort(pending_.begin(),pending_.end(),[&](const auto& a,const auto& b) {
        if(a.session.epoch!=b.session.epoch)return a.session.epoch<b.session.epoch;
        if(a.id.producer!=b.id.producer)return a.id.producer==startup_;
        return a.id.sequence<b.id.sequence;
    });
    std::size_t committed=0;
    for(const auto& e:pending_) {
        if(!out_.healthy())break;
        const auto epoch=out_.ledger().session().epoch;
        if(e.session.epoch>epoch && epoch && retired_<epoch)break;
        if(e.session.epoch<epoch){out_.recording_gap();break;}
        if(!out_.record(e).durable){out_.recording_gap();break;}
        ++committed;
    }
    pending_.erase(pending_.begin(),pending_.begin()+static_cast<std::ptrdiff_t>(committed));
    return consumed;
}
} // namespace stratadrive::diagnostics
