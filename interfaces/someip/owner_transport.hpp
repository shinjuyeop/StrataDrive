#pragma once
#include <vsomeip/vsomeip.hpp>
#include "owner_wire.hpp"
#include "wire_binding.hpp"
#include "owner_message_binding.hpp"
#include <atomic>
#include <chrono>
#include <deque>
#include <fstream>
#include <mutex>
#include <thread>

namespace stratadrive::someip {
inline constexpr std::uint64_t kMs=1000000;
inline std::uint64_t now() { return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
inline void check(bool ok,const char* why) { if(!ok) throw std::runtime_error(why); }
class Transport {
    struct Out { remote::OwnerPacket packet; unsigned method; };
    Ecu ecu_; bool three_; std::shared_ptr<vsomeip::application> app_;
    std::thread dispatch_,sender_; std::mutex mutex_; std::array<std::deque<remote::OwnerMessage>,4> rx_;
    std::array<std::deque<Out>,4> tx_; std::atomic<bool> sending_{false},closing_{false};
    std::ofstream trace_;
    unsigned local(unsigned lane) const { return ecu_==Ecu::Central?(lane<2?0x5346+lane:0x534a+lane-2):(ecu_==Ecu::Front?0x5344:0x5348)+lane; }
    unsigned peer(unsigned lane) const { return ecu_==Ecu::Central?(lane<2?0x5344+lane:0x5348+lane-2):(ecu_==Ecu::Front?0x5346:0x534a)+lane; }
public:
    std::array<std::atomic<std::uint64_t>,4> probe_nonce{},probe_sent{};
    std::array<std::atomic<std::uint32_t>,8> initialized_epoch{};
    std::atomic<unsigned> stale_authority_rejected{0};
    std::array<std::atomic<unsigned>,4> probe_responses{};
    std::atomic<unsigned> available{0},ready{0},rejected{0},rx_count{0},send_returned{0};
    std::array<std::atomic<unsigned>,4> highwater{},tx_highwater{};
    std::atomic<bool> overflow{false};
    std::array<std::atomic<unsigned>,4> rx_rejected{};
    std::atomic<std::uint64_t> rx_overflow_ns{0},rx_overflow_token{0};
    std::array<std::uint64_t,8> full_tokens{},drained_tokens{};unsigned drained_count=0;
    bool fifo_preserved=true; // callback writes full_tokens under mutex; pop uses same mutex

    std::uint64_t stop_return_ns=0,join_return_ns=0;
    Transport(bool front,const std::string& trace):Transport(front?Ecu::Front:Ecu::Central,false,trace) {}
    explicit Transport(Ecu ecu,bool three,const std::string& trace):ecu_(ecu),three_(three),app_(vsomeip::runtime::get()->create_application(ecu==Ecu::Central?"central":ecu==Ecu::Front?"front":"rear")),trace_(trace) {
        trace_<<"ns,event,lane,method,bytes\n";
    }
    unsigned channels() const {return ecu_==Ecu::Central && three_?4:2;}
    unsigned ready_mask() const {return (1U<<channels())-1;}
    void start() {
        check(app_->init(),"SDK init");
        app_->register_state_handler([this](auto s) { if(s==vsomeip::state_type_e::ST_REGISTERED) for(unsigned l=0;l<channels();++l) {
            app_->offer_service(local(l),1,1,0);app_->request_service(peer(l),1,1,0);
        }});
        for(unsigned l=0;l<channels();++l) {
            app_->register_availability_handler(peer(l),1,[this,l](auto,auto,bool yes){
                if(yes) available.fetch_or(1U<<l);else {available.fetch_and(~(1U<<l));ready.fetch_and(~(1U<<l));}
            },1,0);
            for(const auto sid:{local(l),peer(l)}) app_->register_message_handler(sid,1,vsomeip::ANY_METHOD,[this,l](const auto& message) {
                const auto p=message->get_payload();
                const auto type=message->get_message_type();const auto mid=message->get_method();
                if(p && mid==kReady && message->get_interface_version()==1 &&
                   message->get_service()==local(l) && type==vsomeip::message_type_e::MT_REQUEST_NO_RETURN) {
                    const auto q=decode_probe_v2(p->get_data(),p->get_length());
                    if(q && q->lane==l%2) {
                        if(q->kind==1 && q->origin!=(ecu_==Ecu::Central?0:1)) {
                            if(available.load()&(1U<<l))send_probe(l,{2,q->origin,q->lane,q->nonce});
                            return;
                        }
                        if(q->kind==2 && q->origin==(ecu_==Ecu::Central?0:1) && q->nonce==probe_nonce[l].load() &&
                           now()-probe_sent[l].load()<1000*kMs) {
                            ready.fetch_or(1U<<l);++probe_responses[l];return;
                        }
                    }
                }
                const auto decoded=p?remote::decode_owner_message(p->get_data(),p->get_length()):std::nullopt;
                if(!decoded || !binding(ecu_,message->get_service(),message->get_instance(),mid,static_cast<unsigned>(type),message->get_interface_version(),*decoded)) {++rejected;return;}
                // Prequeue admission only. Publish this cache solely from a real
                // positive local INIT ACK; it grants no Release/credit/arm authority.
                // Disconnected SDK buffering must not fill a fresh process's queue
                // with credit that RunLeaseGate would reject before any INIT.
                if(ecu_!=Ecu::Central && authority(mid)) {
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
                if(rx_[l].size()==8) {
                    ++rx_rejected[l];
                    if(!rx_overflow_ns.load()) {
                        for(unsigned j=0;j<8;++j)if(auto* r=std::get_if<transport::ZoneRequest>(&rx_[l][j].payload))full_tokens[j]=r->token;
                        if(auto* r=std::get_if<transport::ZoneRequest>(&decoded->payload))rx_overflow_token=r->token;
                        rx_overflow_ns=now();
                    }
                    overflow=true;return;
                }
                rx_[l].push_back(*decoded);highwater[l]=std::max(highwater[l].load(),static_cast<unsigned>(rx_[l].size()));
            });
        }
        dispatch_=std::thread([this]{app_->start();});sending_=true;
        sender_=std::thread([this]{
            while(sending_) {
                for(const unsigned l:{1U,3U,0U,2U}) for(unsigned i=0;i<8;++i) {
                    if(l>=channels())break;
                    std::optional<Out> o;
                    {std::lock_guard<std::mutex> lock(mutex_);if(!tx_[l].empty()){o=tx_[l].front();tx_[l].pop_front();}}
                    if(!o) break;
                    auto m=vsomeip::runtime::get()->create_request(true);m->set_service(peer(l));m->set_instance(1);m->set_method(o->method);
                    m->set_interface_version(1);m->set_message_type(vsomeip::message_type_e::MT_REQUEST_NO_RETURN);
                    auto p=vsomeip::runtime::get()->create_payload();p->set_data(o->packet.bytes.data(),o->packet.size);m->set_payload(p);
                    app_->send(m);++send_returned;
                    trace_<<now()<<",send-return,"<<l<<','<<o->method<<','<<o->packet.size<<'\n';
                }
                if(closing_) {std::lock_guard<std::mutex> lock(mutex_);if(std::all_of(tx_.begin(),tx_.end(),[](const auto& q){return q.empty();}))break;}
                std::this_thread::sleep_for(std::chrono::microseconds(200));
            }
        });
    }
    void send_probe(unsigned lane,ProbeV2 probe) {
        const auto bytes=probe_v2(probe);remote::OwnerPacket packet;packet.size=bytes.size();std::copy(bytes.begin(),bytes.end(),packet.bytes.begin());
        std::lock_guard<std::mutex> lock(mutex_);
        if(tx_[lane].size()==8){overflow=true;return;}
        tx_[lane].push_back({packet,kReady});
        tx_highwater[lane]=std::max(tx_highwater[lane].load(),static_cast<unsigned>(tx_[lane].size()));
    }
    void probe_peer(bool force=false) {
        for(unsigned l=0;l<channels();++l) if((available.load()&(1U<<l)) && (force || !(ready.load()&(1U<<l)))) {
            const auto stamp=now();probe_sent[l]=stamp;probe_nonce[l]=stamp;
            send_probe(l,{1,static_cast<std::uint8_t>(ecu_==Ecu::Central?0:1),static_cast<std::uint8_t>(l%2),stamp});
        }
    }
    bool send(const remote::OwnerMessage& m) {
        auto p=remote::encode_owner_message(m);if(!p)return false;const auto mid=method(m.payload);const unsigned l=(authority(mid)?1:0)+(ecu_==Ecu::Central && three_ && owns_role(Ecu::Rear,m.to)?2:0);
        std::lock_guard<std::mutex> lock(mutex_);
        if(tx_[l].size()==8) {overflow=true;return false;}
        tx_[l].push_back({*p,mid});tx_highwater[l]=std::max(tx_highwater[l].load(),static_cast<unsigned>(tx_[l].size()));return true;
    }
    std::optional<remote::OwnerMessage> pop(unsigned lane) {
        std::lock_guard<std::mutex> lock(mutex_);if(rx_[lane].empty())return {};
        auto m=rx_[lane].front();rx_[lane].pop_front();
        if(lane==0 && rx_overflow_ns && drained_count<8) {
            if(auto* r=std::get_if<transport::ZoneRequest>(&m.payload))drained_tokens[drained_count]=r->token;
            fifo_preserved=fifo_preserved && drained_tokens[drained_count]==full_tokens[drained_count];++drained_count;
        }
        return m;
    }
#ifdef STRATADRIVE_SOMEIP_TEST_HOOKS
    void inject_bad(unsigned mid,unsigned type,unsigned version,const remote::OwnerPacket& packet) {
        auto m=vsomeip::runtime::get()->create_request(true);m->set_service(peer(0));m->set_instance(1);m->set_method(mid);
        m->set_interface_version(version);m->set_message_type(static_cast<vsomeip::message_type_e>(type));
        auto p=vsomeip::runtime::get()->create_payload();p->set_data(packet.bytes.data(),packet.size);m->set_payload(p);app_->send(m);
    }
#endif
    std::size_t queued(unsigned lane){std::lock_guard<std::mutex> lock(mutex_);return rx_[lane].size();}
    void stop() {
        closing_=true;if(sender_.joinable())sender_.join();sending_=false;
        if(!dispatch_.joinable())return;
        for(unsigned l=0;l<channels();++l){app_->stop_offer_service(local(l),1,1,0);app_->release_service(peer(l),1);}
        app_->clear_all_handler();app_->stop();stop_return_ns=now();dispatch_.join();join_return_ns=now();
        trace_<<stop_return_ns<<",stop-return,0,0,0\n"<<join_return_ns<<",join-return,0,0,0\n";trace_.flush();
    }
    ~Transport(){stop();}
};
}
