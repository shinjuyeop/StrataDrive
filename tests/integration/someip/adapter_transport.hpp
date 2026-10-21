#pragma once
#include <vsomeip/vsomeip.hpp>
#include "owner_wire.hpp"
#include "binding.hpp"
#include <atomic>
#include <chrono>
#include <deque>
#include <fstream>
#include <mutex>
#include <thread>

namespace stratadrive::someip {
inline constexpr std::uint64_t kDomain=0x53444d4f4e4fULL,kMs=1000000;
inline std::uint64_t now() { return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
inline void check(bool ok,const char* why) { if(!ok) throw std::runtime_error(why); }
inline bool remote_role(session::Role r) { return r==session::Role::FrontZone || r==session::Role::Steering || r==session::Role::Brake; }
inline unsigned method(const remote::OwnerPayload& p) {
    if(std::holds_alternative<session::Control>(p) || std::holds_alternative<session::Ack>(p)) return 0x40;
    if(std::holds_alternative<remote::RunLease>(p)) return 0x50;
    if(std::holds_alternative<remote::ProtectionRequest>(p) || std::holds_alternative<remote::ProtectionAck>(p)) return 0x60;
    if(std::holds_alternative<transport::Feedback>(p)) return 0x70;
    if(std::holds_alternative<transport::TxResult>(p)) return 0x80;
    return 0x20;
}
inline bool authority(unsigned m) { return m==0x40 || m==0x50 || m==0x60; }
// The only application messages permitted across this Central/Front boundary.
inline bool binding(bool front,std::uint16_t sid,std::uint16_t iid,std::uint16_t mid,
                    unsigned type,unsigned version,const remote::OwnerMessage& m) {
    if(version!=1 || iid!=1 || type!=1 || m.clock_domain!=kDomain || mid!=method(m.payload) ||
       sid!=(front?0x5344:0x5346)+(authority(mid)?1:0)) return false;
    if(front) {
        if(m.from!=session::Role::CentralIngress || !remote_role(m.to)) return false;
        if(const auto* c=std::get_if<session::Control>(&m.payload)) return c->role==m.to;
        if(std::holds_alternative<remote::RunLease>(m.payload) || std::holds_alternative<remote::ProtectionRequest>(m.payload)) return true;
        return m.to==session::Role::FrontZone && std::holds_alternative<transport::ZoneRequest>(m.payload);
    }
    if(m.to!=session::Role::CentralIngress || !remote_role(m.from)) return false;
    if(const auto* a=std::get_if<session::Ack>(&m.payload)) return a->role==m.from;
    if(std::holds_alternative<remote::ProtectionAck>(m.payload)) return true;
    return m.from==session::Role::FrontZone && (std::holds_alternative<transport::TxResult>(m.payload) || std::holds_alternative<transport::Feedback>(m.payload));
}
class Transport {
    struct Out { remote::OwnerPacket packet; unsigned method; };
    bool front_; std::shared_ptr<vsomeip::application> app_;
    std::thread dispatch_,sender_; std::mutex mutex_; std::array<std::deque<remote::OwnerMessage>,2> rx_;
    std::array<std::deque<Out>,2> tx_; std::atomic<bool> sending_{false},closing_{false};
    std::ofstream trace_;
    unsigned local(unsigned lane) const { return (front_?0x5344:0x5346)+lane; }
    unsigned peer(unsigned lane) const { return (front_?0x5346:0x5344)+lane; }
public:
    std::array<std::atomic<std::uint64_t>,2> probe_nonce{},probe_sent{};
    std::array<std::atomic<std::uint32_t>,8> initialized_epoch{};
    std::atomic<unsigned> stale_authority_rejected{0};
    std::array<std::atomic<unsigned>,2> probe_responses{};
    std::atomic<unsigned> available{0},ready{0},rejected{0},rx_count{0},send_returned{0};
    std::array<std::atomic<unsigned>,2> highwater{},tx_highwater{};
    std::atomic<bool> overflow{false};
    std::uint64_t stop_return_ns=0,join_return_ns=0;
    explicit Transport(bool front,const std::string& trace):front_(front),app_(vsomeip::runtime::get()->create_application(front?"front":"central")),trace_(trace) {
        trace_<<"ns,event,lane,method,bytes\n";
    }
    void start() {
        check(app_->init(),"SDK init");
        app_->register_state_handler([this](auto s) { if(s==vsomeip::state_type_e::ST_REGISTERED) for(unsigned l=0;l<2;++l) {
            app_->offer_service(local(l),1,1,0);app_->request_service(peer(l),1,1,0);
        }});
        for(unsigned l=0;l<2;++l) {
            app_->register_availability_handler(peer(l),1,[this,l](auto,auto,bool yes){
                if(yes) available.fetch_or(1U<<l);else {available.fetch_and(~(1U<<l));ready.fetch_and(~(1U<<l));}
            },1,0);
            for(const auto sid:{local(l),peer(l)}) app_->register_message_handler(sid,1,vsomeip::ANY_METHOD,[this,l](const auto& message) {
                const auto p=message->get_payload();
                const auto type=message->get_message_type();const auto mid=message->get_method();
                if(p && mid==kReady && message->get_interface_version()==1 &&
                   message->get_service()==local(l) && type==vsomeip::message_type_e::MT_REQUEST_NO_RETURN) {
                    const auto q=decode_probe_v2(p->get_data(),p->get_length());
                    if(q && q->lane==l) {
                        if(q->kind==1 && q->origin!=(front_?1:0)) {
                            if(available.load()&(1U<<l))send_probe(l,{2,q->origin,q->lane,q->nonce});
                            return;
                        }
                        if(q->kind==2 && q->origin==(front_?1:0) && q->nonce==probe_nonce[l].load() &&
                           now()-probe_sent[l].load()<1000*kMs) {
                            ready.fetch_or(1U<<l);++probe_responses[l];return;
                        }
                    }
                }
                const auto decoded=p?remote::decode_owner_message(p->get_data(),p->get_length()):std::nullopt;
                if(!decoded || !binding(front_,message->get_service(),message->get_instance(),mid,static_cast<unsigned>(type),message->get_interface_version(),*decoded)) {++rejected;return;}
                // Prequeue admission only. Publish this cache solely from a real
                // positive local INIT ACK; it grants no Release/credit/arm authority.
                // Disconnected SDK buffering must not fill a fresh process's queue
                // with credit that RunLeaseGate would reject before any INIT.
                if(front_ && authority(mid)) {
                    const auto t=now();bool eligible=true;
                    if(const auto* lease=std::get_if<remote::RunLease>(&decoded->payload))
                        eligible=initialized_epoch[static_cast<unsigned>(decoded->to)].load()==lease->plan.epoch && lease->plan.epoch!=0 &&
                            lease->source_time_ns<=t && t-lease->source_time_ns<=session::kMessageAgeNs && t<lease->expires_at_ns;
                    else if(const auto* c=std::get_if<session::Control>(&decoded->payload))
                        eligible=c->source_ns<=t && t-c->source_ns<=session::kMessageAgeNs &&
                            (c->phase==session::Phase::Abort || t<(c->phase==session::Phase::Prepare?c->plan.prepare_deadline_ns:c->plan.commit_deadline_ns));
                    else if(const auto* p=std::get_if<remote::ProtectionRequest>(&decoded->payload))
                        eligible=p->source_time_ns<=t && t<p->deadline_ns;
                    if(!eligible){++stale_authority_rejected;return;}
                }
                std::lock_guard<std::mutex> lock(mutex_);++rx_count;
                if(rx_[l].size()==8) {overflow=true;return;}
                rx_[l].push_back(*decoded);highwater[l]=std::max(highwater[l].load(),static_cast<unsigned>(rx_[l].size()));
            });
        }
        dispatch_=std::thread([this]{app_->start();});sending_=true;
        sender_=std::thread([this]{
            while(sending_) {
                for(const unsigned l:{1U,0U}) for(unsigned i=0;i<8;++i) {
                    std::optional<Out> o;
                    {std::lock_guard<std::mutex> lock(mutex_);if(!tx_[l].empty()){o=tx_[l].front();tx_[l].pop_front();}}
                    if(!o) break;
                    auto m=vsomeip::runtime::get()->create_request(true);m->set_service(peer(l));m->set_instance(1);m->set_method(o->method);
                    m->set_interface_version(1);m->set_message_type(vsomeip::message_type_e::MT_REQUEST_NO_RETURN);
                    auto p=vsomeip::runtime::get()->create_payload();p->set_data(o->packet.bytes.data(),o->packet.size);m->set_payload(p);
                    app_->send(m);++send_returned;
                    trace_<<now()<<",send-return,"<<l<<','<<o->method<<','<<o->packet.size<<'\n';
                }
                if(closing_) {std::lock_guard<std::mutex> lock(mutex_);if(tx_[0].empty() && tx_[1].empty())break;}
                std::this_thread::sleep_for(std::chrono::microseconds(200));
            }
        });
    }
    void send_probe(unsigned lane,ProbeV2 probe) {
        auto m=vsomeip::runtime::get()->create_request(true);m->set_service(peer(lane));m->set_instance(1);m->set_method(kReady);m->set_interface_version(1);
        m->set_message_type(vsomeip::message_type_e::MT_REQUEST_NO_RETURN);
        const auto bytes=probe_v2(probe);auto p=vsomeip::runtime::get()->create_payload();p->set_data(bytes.data(),bytes.size());m->set_payload(p);app_->send(m);
    }
    void probe_peer(bool force=false) {
        for(unsigned l=0;l<2;++l) if((available.load()&(1U<<l)) && (force || !(ready.load()&(1U<<l)))) {
            const auto stamp=now();probe_sent[l]=stamp;probe_nonce[l]=stamp;
            send_probe(l,{1,static_cast<std::uint8_t>(front_?1:0),static_cast<std::uint8_t>(l),stamp});
        }
    }
    bool send(const remote::OwnerMessage& m) {
        auto p=remote::encode_owner_message(m);if(!p)return false;const auto mid=method(m.payload);const unsigned l=authority(mid)?1:0;
        std::lock_guard<std::mutex> lock(mutex_);
        if(tx_[l].size()==8) {overflow=true;return false;}
        tx_[l].push_back({*p,mid});tx_highwater[l]=std::max(tx_highwater[l].load(),static_cast<unsigned>(tx_[l].size()));return true;
    }
    std::optional<remote::OwnerMessage> pop(unsigned lane) {
        std::lock_guard<std::mutex> lock(mutex_);if(rx_[lane].empty())return {};
        auto m=rx_[lane].front();rx_[lane].pop_front();return m;
    }
    void inject_bad(unsigned mid,unsigned type,unsigned version,const remote::OwnerPacket& packet) {
        auto m=vsomeip::runtime::get()->create_request(true);m->set_service(peer(0));m->set_instance(1);m->set_method(mid);
        m->set_interface_version(version);m->set_message_type(static_cast<vsomeip::message_type_e>(type));
        auto p=vsomeip::runtime::get()->create_payload();p->set_data(packet.bytes.data(),packet.size);m->set_payload(p);app_->send(m);
    }
    std::size_t queued(unsigned lane){std::lock_guard<std::mutex> lock(mutex_);return rx_[lane].size();}
    void stop() {
        closing_=true;if(sender_.joinable())sender_.join();sending_=false;
        if(!dispatch_.joinable())return;
        for(unsigned l=0;l<2;++l){app_->stop_offer_service(local(l),1,1,0);app_->release_service(peer(l),1);}
        app_->clear_all_handler();app_->stop();stop_return_ns=now();dispatch_.join();join_return_ns=now();
        trace_<<stop_return_ns<<",stop-return,0,0,0\n"<<join_return_ns<<",join-return,0,0,0\n";trace_.flush();
    }
    ~Transport(){stop();}
};
}
