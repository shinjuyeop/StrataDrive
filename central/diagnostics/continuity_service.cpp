#include "continuity_service.hpp"
#include <algorithm>
#include <limits>
#include <stdexcept>
#include <sys/socket.h>
#include <sys/un.h>
#include <utility>

namespace stratadrive::diagnostics {
namespace {
constexpr std::size_t request_size=76,reply_size=32;
void put(std::vector<std::uint8_t>& b,std::uint64_t n,unsigned width){for(unsigned i=0;i<width;++i)b.push_back(static_cast<std::uint8_t>(n>>(8*i)));}
std::uint64_t get(const std::vector<std::uint8_t>& b,std::size_t& p,unsigned width){std::uint64_t n=0;for(unsigned i=0;i<width;++i)n|=static_cast<std::uint64_t>(b.at(p++))<<(8*i);return n;}
bool cuts_equal(const std::vector<StreamCut>& a,const std::vector<StreamCut>& b){
    return a.size()==b.size() && std::equal(a.begin(),a.end(),b.begin(),[](const auto& x,const auto& y){return x.stream==y.stream && x.producer==y.producer && x.committed==y.committed && x.tip==y.tip && x.tip_crc==y.tip_crc;});
}
bool fresh(const ServiceEvidence& e,const ServiceEvidence& previous){return stationary_evidence(e) && comparable(e.now,previous.now) && e.now.ns>=previous.now.ns && e.now.ns-previous.now.ns<=30000000 && comparable(e.enable,previous.enable) && e.enable.ns==previous.enable.ns;}
// Passed observes the same immutable recording proof at a later decision time.
void observed(Event& e,const Stamp& s){e.times[static_cast<std::size_t>(Time::Observed)]=s;}
}
std::vector<std::uint8_t> encode_service_request(const ServiceRequest& r){
    std::vector<std::uint8_t> b(20);b[0]='S';b[1]='D';b[2]='S';b[3]=1;
    std::copy(r.capability.begin(),r.capability.end(),b.begin()+4);b.reserve(request_size);put(b,r.number,8);
    put(b,r.session.run,8);put(b,r.session.epoch,4);put(b,r.incident.run,8);put(b,r.incident.producer,8);put(b,r.incident.sequence,8);put(b,r.revision,8);
    put(b,static_cast<unsigned>(r.operation),1);put(b,static_cast<unsigned>(r.disposition),1);put(b,0,2);return b;
}
ServiceRequest decode_service_request(const std::vector<std::uint8_t>& b){
    if(b.size()!=request_size || b[0]!='S' || b[1]!='D' || b[2]!='S' || b[3]!=1)throw std::invalid_argument("local service packet");
    ServiceRequest r;std::copy_n(b.begin()+4,16,r.capability.begin());std::size_t p=20;r.number=get(b,p,8);r.session={get(b,p,8),static_cast<std::uint32_t>(get(b,p,4))};
    r.incident={get(b,p,8),get(b,p,8),get(b,p,8)};r.revision=get(b,p,8);r.operation=static_cast<ServiceOperation>(get(b,p,1));r.disposition=static_cast<ContinuityDisposition>(get(b,p,1));
    if(get(b,p,2) || !r.number || r.number>(std::numeric_limits<std::uint64_t>::max()/4) ||
       (r.operation!=ServiceOperation::Review && r.operation!=ServiceOperation::Clear) ||
       (r.operation==ServiceOperation::Review?r.disposition!=ContinuityDisposition::AcceptUnknownHistory:r.disposition!=ContinuityDisposition::None))throw std::invalid_argument("local service request");
    return r;
}
std::vector<std::uint8_t> encode_service_reply(const ServiceReply& r){std::vector<std::uint8_t> b{'S','D','R',1};put(b,r.number,8);put(b,r.watermark,8);put(b,r.revision,8);put(b,static_cast<unsigned>(r.status),1);put(b,r.stage,1);put(b,static_cast<unsigned>(r.blocked),1);put(b,0,1);return b;}
ServiceReply decode_service_reply(const std::vector<std::uint8_t>& b){
    if(b.size()!=reply_size || b[0]!='S' || b[1]!='D' || b[2]!='R' || b[3]!=1)throw std::invalid_argument("local service reply");
    ServiceReply r;std::size_t p=4;r.number=get(b,p,8);r.watermark=get(b,p,8);r.revision=get(b,p,8);r.status=static_cast<ServiceStatus>(get(b,p,1));r.stage=static_cast<std::uint8_t>(get(b,p,1));r.blocked=static_cast<ReviewBlock>(get(b,p,1));
    if(get(b,p,1) || r.status>ServiceStatus::Transport || r.stage>4 || r.blocked>ReviewBlock::Storage)throw std::invalid_argument("local service reply fields");
    return r;
}
ContinuityService::ContinuityService(Recorder& w,std::vector<StreamBinding> manifest,ServicePermit permit,ContinuityCapture& capture):writer_(w),inspector_(permit.actor,std::move(manifest)),permit_(permit),capture_(capture){
    if(permit.pid<=0 || !permit.actor.run || !permit.actor.producer || permit.session.run!=permit.actor.run || !permit.session.epoch || permit.incident.run!=permit.actor.run || !permit.incident.producer || !permit.incident.sequence ||
       std::all_of(permit.capability.begin(),permit.capability.end(),[](auto b){return b==0;}) ||
       std::any_of(w.ledger().events().begin(),w.ledger().events().end(),[&](const Event& e){return e.id.run==permit.actor.run && e.id.producer==permit.actor.producer;}))throw std::invalid_argument("local service permit / fresh producer");
    replies_.reserve(request_budget);
}
ServiceReply ContinuityService::serve(int fd){
    ServiceReply reply;int type=0;socklen_t length=sizeof(type);sockaddr_un address{};socklen_t address_size=sizeof(address);ucred peer{};socklen_t peer_size=sizeof(peer);
    if(getsockopt(fd,SOL_SOCKET,SO_TYPE,&type,&length) || type!=SOCK_SEQPACKET || getpeername(fd,reinterpret_cast<sockaddr*>(&address),&address_size) || address.sun_family!=AF_UNIX ||
       getsockopt(fd,SOL_SOCKET,SO_PEERCRED,&peer,&peer_size) || peer_size!=sizeof(peer) || peer.uid!=permit_.uid || peer.pid!=permit_.pid){
        reply.status=ServiceStatus::Unauthorized;
        // Retire at most one rejected packet so AF_UNIX can deliver the denial
        // before caller closes this connection. Never wait for an untrusted peer.
        std::array<std::uint8_t,request_size> discard{};(void)recv(fd,discard.data(),discard.size(),MSG_DONTWAIT|MSG_TRUNC);
    }
    else {
        std::vector<std::uint8_t> packet(request_size);const auto n=recv(fd,packet.data(),packet.size(),MSG_DONTWAIT|MSG_TRUNC);
        if(n<0)reply.status=(errno==EAGAIN || errno==EWOULDBLOCK)?ServiceStatus::NoData:ServiceStatus::Transport;
        else if(n!=static_cast<ssize_t>(packet.size()))reply.status=ServiceStatus::Malformed;
        else try {
            const auto request=decode_service_request(packet);reply.number=request.number;
            if(request.capability!=permit_.capability)reply.status=ServiceStatus::Unauthorized;
            else if(const auto old=std::find_if(replies_.begin(),replies_.end(),[&](const Cached& c){return c.reply.number==request.number;});old!=replies_.end()){
                if(old->bytes==packet)reply=old->reply;else reply.status=ServiceStatus::Conflict;
            } else if(replies_.size()==request_budget)reply.status=ServiceStatus::Capacity;
            else if(request.number<=highest_)reply.status=ServiceStatus::Conflict;
            else {
                highest_=request.number;
                try{reply=apply(request);}catch(const std::exception&){failed_=true;reply.status=ServiceStatus::Storage;}
                replies_.push_back({std::move(packet),reply});
            }
        }catch(const std::invalid_argument&){reply.status=ServiceStatus::Malformed;}
    }
    const auto bytes=encode_service_reply(reply);(void)send(fd,bytes.data(),bytes.size(),MSG_DONTWAIT|MSG_NOSIGNAL);return reply;
}
ServiceReply ContinuityService::apply(const ServiceRequest& request){
    ServiceReply reply;reply.number=request.number;
    const auto& ledger=writer_.ledger();
    const auto found=std::find_if(ledger.events().begin(),ledger.events().end(),[&](const Event& e){return e.id==permit_.incident;});
    const auto result=[&](ServiceStatus status){reply.status=status;return reply;};
    if(!(request.session==permit_.session) || !(ledger.session()==permit_.session) || !(request.incident==permit_.incident))return result(ServiceStatus::Scope);
    if(failed_ || !ledger.complete())return result(ServiceStatus::Storage);
    if(found==ledger.events().end())return result(ServiceStatus::Scope);
    const auto key=found->key;const auto* record=ledger.find(key);
    if(!record || record->cleared || request.revision!=record->revision)return result(ServiceStatus::Revision);
    if(request.operation==ServiceOperation::Clear && (approved_.empty() || record->condition!=Condition::Passed || !(record->pass_event==approved_pass_)))return result(ServiceStatus::NotReady);
    auto cut=capture_.acquire();if(!cut)return result(ServiceStatus::Freeze);
    auto evidence=cut->sample();
    const auto sequence=request.number*4-3;
    auto prepared=inspector_.prepare(ledger,request.incident,cut->global(),cut->streams(),ContinuityDisposition::AcceptUnknownHistory,evidence,sequence);
    if(!prepared.plan){reply.blocked=prepared.blocked;return result(ServiceStatus::Inspection);}
    auto plan=std::move(*prepared.plan);
    if(request.operation==ServiceOperation::Clear){
        if(!cuts_equal(plan.review.streams,approved_))return result(ServiceStatus::Inspection);
        evidence=cut->sample();if(!fresh(evidence,plan.review.evidence))return result(ServiceStatus::Physical);
        Clear clear;clear.id={permit_.actor.run,permit_.actor.producer,request.number*4};clear.session=permit_.session;clear.evidence=evidence;clear.targets={{key,request.revision}};
        const auto receipt=writer_.clear(clear);reply.watermark=receipt.watermark;
        if(!receipt.durable){failed_=!writer_.ledger().complete();return result(receipt.result==Result::StorageFailure?ServiceStatus::Storage:ServiceStatus::NotReady);}reply.stage=4;
    }else {
        auto trial=ledger;if(trial.record(plan.proof)!=Result::Accepted || trial.review(plan.review)!=Result::Accepted || trial.record(plan.passed)!=Result::Accepted || trial.find(key)->condition!=Condition::Passed)return result(ServiceStatus::NotReady);
        const auto commit=[&](const Receipt& receipt,std::uint8_t stage){reply.watermark=receipt.watermark;if(!receipt.durable){failed_=true;reply.status=ServiceStatus::Storage;return false;}reply.stage=stage;return true;};
        approved_.clear();approved_pass_={};
        if(!commit(writer_.record(plan.proof),1))return reply;
        evidence=cut->sample();if(!fresh(evidence,plan.review.evidence))return result(ServiceStatus::Physical);plan.review.evidence=evidence;
        if(!commit(writer_.review(plan.review),2))return reply;
        const auto latest=cut->sample();if(!fresh(latest,evidence))return result(ServiceStatus::Physical);observed(plan.passed,latest.now);
        if(!commit(writer_.record(plan.passed),3))return reply;
        approved_=plan.review.streams;approved_pass_=plan.passed.id;
    }
    record=writer_.ledger().find(key);reply.revision=record?record->revision:0;return result(ServiceStatus::Accepted);
}
} // namespace stratadrive::diagnostics
