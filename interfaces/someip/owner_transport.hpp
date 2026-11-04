#pragma once
#include <vsomeip/vsomeip.hpp>
#include "owner_wire.hpp"
#include "wire_binding.hpp"
#include "owner_message_binding.hpp"
#include "owner_credit_retirement.hpp"
#include "../common/monotonic_condition.hpp"
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <deque>
#include <fstream>
#include <functional>
#include <mutex>
#include <thread>
#include <vector>
#include <pthread.h>
#include <time.h>

namespace stratadrive::someip {
inline constexpr std::uint64_t kMs=1000000;
inline std::uint64_t now() { return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
inline void check(bool ok,const char* why) { if(!ok) throw std::runtime_error(why); }
class Transport {
    using Out=OwnerEgressPacket;
    Ecu ecu_; bool three_;bool transitioning_=false; std::shared_ptr<vsomeip::application> app_;
    std::thread dispatch_,sender_; std::mutex mutex_; std::array<std::deque<remote::OwnerMessage>,4> rx_;
    std::condition_variable tx_ready_;runtime::MonotonicCondition rx_ready_;
    std::array<std::deque<Out>,4> tx_; std::atomic<bool> sending_{false},closing_{false};
    std::ofstream trace_;
    struct TimingRow {std::uint64_t ns;const char* event;unsigned lane,method;std::size_t bytes;std::uint32_t crc;std::uint64_t cpu_ns;};
    std::mutex trace_mutex_;std::vector<TimingRow> timing_;bool trace_overflow_=false;
    static std::uint64_t thread_cpu() {timespec t{};clock_gettime(CLOCK_THREAD_CPUTIME_ID,&t);return std::uint64_t(t.tv_sec)*1000000000+t.tv_nsec;}
    void record(const char* event,unsigned lane,unsigned method,const std::uint8_t* bytes,std::size_t size,std::uint64_t stamp=0,std::uint64_t cpu=0) {
        // The canonical packet's trailing CRC correlates the same immutable
        // bytes at queue, SDK call and callback. No hashing/formatting/file IO.
        std::uint32_t crc=0;
        if(size>=4)for(unsigned i=0;i<4;++i)crc|=std::uint32_t(bytes[size-4+i])<<(8*i);
        const auto ns=stamp?stamp:now();std::lock_guard<std::mutex> lock(trace_mutex_);
        if(timing_.size()==timing_.capacity()){trace_overflow_=true;return;}
        timing_.push_back({ns,event,lane,method,size,crc,cpu?cpu:thread_cpu()});
    }
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
    std::array<std::atomic<unsigned>,4> rx_rejected{},transition_discarded{};
    std::atomic<std::uint64_t> rx_overflow_ns{0},rx_overflow_token{0};
    std::atomic<std::uint64_t> tx_overflow_ns{0};std::atomic<unsigned> tx_overflow_lane{0},tx_overflow_method{0};
    std::atomic<std::uint64_t> retired_run_credits{0};
    std::atomic<std::uint64_t> retired_received_credits{0};
    std::array<std::uint64_t,8> full_tokens{},drained_tokens{};unsigned drained_count=0;
    bool fifo_preserved=true; // callback writes full_tokens under mutex; pop uses same mutex

    std::uint64_t stop_return_ns=0,join_return_ns=0;
    Transport(bool front,const std::string& trace):Transport(front?Ecu::Front:Ecu::Central,false,trace) {}
    explicit Transport(Ecu ecu,bool three,const std::string& trace):ecu_(ecu),three_(three),app_(vsomeip::runtime::get()->create_application(ecu==Ecu::Central?"central":ecu==Ecu::Front?"front":"rear")),trace_(trace) {
        timing_.reserve(131072);trace_<<"ns,event,lane,method,bytes,crc,cpu_ns\n";
    }
    unsigned channels() const {return ecu_==Ecu::Central && three_?4:2;}
    unsigned ready_mask() const {return (1U<<channels())-1;}
    void outbound_full(unsigned lane,unsigned method) {
        if(!tx_overflow_ns.load()){tx_overflow_lane=lane;tx_overflow_method=method;tx_overflow_ns=now();}
        overflow=true;
    }
    void start(const std::function<void(const std::shared_ptr<vsomeip::application>&)>& configure={},std::function<void()> registered={}) {
        check(app_->init(),"SDK init");
        if(configure)configure(app_);
        app_->register_state_handler([this,registered=std::move(registered)](auto s) { if(s==vsomeip::state_type_e::ST_REGISTERED) {for(unsigned l=0;l<channels();++l) {
            app_->offer_service(local(l),1,1,0);app_->request_service(peer(l),1,1,0);
        }if(registered)registered();}});
        for(unsigned l=0;l<channels();++l) {
            app_->register_availability_handler(peer(l),1,[this,l](auto,auto,bool yes){
                if(yes) available.fetch_or(1U<<l);else {available.fetch_and(~(1U<<l));ready.fetch_and(~(1U<<l));}
            },1,0);
            for(const auto sid:{local(l),peer(l)}) app_->register_message_handler(sid,1,vsomeip::ANY_METHOD,[this,l](const auto& message) {
                const auto entered=now(),entered_cpu=thread_cpu();
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
                record("rx-enter",l,mid,p->get_data(),p->get_length(),entered,entered_cpu);
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
                if(transitioning_){++transition_discarded[l];return;}
                // A validated Abort/protection request makes queued credit for
                // that exact role/plan/clock obsolete before the owner sees it.
                // This grants no authority and never removes a command or ACK.
                retired_received_credits+=retire_received_credits(rx_[l],*decoded);
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
                record("rx-queued",l,mid,p->get_data(),p->get_length());
                rx_ready_.notify_one();
            });
        }
        dispatch_=std::thread([this]{app_->start();});sending_=true;
        sender_=std::thread([this]{
            pthread_setname_np(pthread_self(),"sd_owner_tx");
            while(sending_) {
                {std::unique_lock<std::mutex> lock(mutex_);
                    tx_ready_.wait(lock,[this]{return closing_ || std::any_of(tx_.begin(),tx_.end(),[](const auto& q){return !q.empty();});});}
                for(const unsigned l:{1U,3U,0U,2U}) for(unsigned i=0;i<8;++i) {
                    if(l>=channels())break;
                    std::optional<Out> o;
                    {std::lock_guard<std::mutex> lock(mutex_);if(!tx_[l].empty()){o=tx_[l].front();tx_[l].pop_front();}}
                    if(!o) break;
                    auto m=vsomeip::runtime::get()->create_request(true);m->set_service(peer(l));m->set_instance(1);m->set_method(o->method);
                    m->set_interface_version(1);m->set_message_type(vsomeip::message_type_e::MT_REQUEST_NO_RETURN);
                    auto p=vsomeip::runtime::get()->create_payload();p->set_data(o->packet.bytes.data(),o->packet.size);m->set_payload(p);
                    record("send-begin",l,o->method,o->packet.bytes.data(),o->packet.size);
                    app_->send(m);++send_returned;
                    record("send-return",l,o->method,o->packet.bytes.data(),o->packet.size);
                }
                if(closing_) {std::lock_guard<std::mutex> lock(mutex_);if(std::all_of(tx_.begin(),tx_.end(),[](const auto& q){return q.empty();}))break;}
            }
        });
    }
    void send_probe(unsigned lane,ProbeV2 probe) {
        const auto bytes=probe_v2(probe);remote::OwnerPacket packet;packet.size=bytes.size();std::copy(bytes.begin(),bytes.end(),packet.bytes.begin());
        std::lock_guard<std::mutex> lock(mutex_);
        if(tx_[lane].size()==8){outbound_full(lane,kReady);return;}
        tx_[lane].push_back({packet,kReady,std::nullopt});
        tx_highwater[lane]=std::max(tx_highwater[lane].load(),static_cast<unsigned>(tx_[lane].size()));
        tx_ready_.notify_one();
    }
    void probe_peer(bool force=false) {
        for(unsigned l=0;l<channels();++l) if((available.load()&(1U<<l)) && (force || !(ready.load()&(1U<<l)))) {
            const auto stamp=now();probe_sent[l]=stamp;probe_nonce[l]=stamp;
            send_probe(l,{1,static_cast<std::uint8_t>(ecu_==Ecu::Central?0:1),static_cast<std::uint8_t>(l%2),stamp});
        }
    }
    // Call only after Central authority is closed and the old session protected.
    // No command/ACK is accepted while its owning graph is retired and durable
    // Epoch IO runs. Probes continue; discarded old ingress is counted per lane.
    // This never clears overflow or supplies authority. A fresh handshake follows.
    void begin_quiescent_transition() {
        std::lock_guard<std::mutex> lock(mutex_);
        check(ecu_==Ecu::Central && !transitioning_ && !overflow,"invalid ingress transition");
        transitioning_=true;
        for(unsigned l=0;l<channels();++l){transition_discarded[l]+=rx_[l].size();rx_[l].clear();}
    }
    void end_quiescent_transition() {
        std::lock_guard<std::mutex> lock(mutex_);check(transitioning_,"ingress not quiesced");transitioning_=false;
    }
    bool send(const remote::OwnerMessage& m) {
        auto p=owner_egress(m);if(!p)return false;const auto mid=p->method;const unsigned l=(authority(mid)?1:0)+(ecu_==Ecu::Central && three_ && owns_role(Ecu::Rear,m.to)?2:0);
        std::lock_guard<std::mutex> lock(mutex_);
        retired_run_credits+=retire_run_credits(tx_[l],m);
        if(tx_[l].size()==8) {outbound_full(l,mid);return false;}
        tx_[l].push_back(*p);tx_highwater[l]=std::max(tx_highwater[l].load(),static_cast<unsigned>(tx_[l].size()));
        record("tx-queued",l,mid,p->packet.bytes.data(),p->packet.size);tx_ready_.notify_one();return true;
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
    // Host functional owner: wake immediately for actual ingress; a bounded
    // idle wait keeps local clock/expiry/sensor work alive without a busy poll.
    void wait_for_ingress(std::chrono::microseconds maximum) {
        std::unique_lock<std::mutex> lock(mutex_);
        rx_ready_.wait_for(lock,maximum,[this]{return overflow || closing_ || std::any_of(rx_.begin(),rx_.end(),[](const auto& q){return !q.empty();});});
    }
    void stop() {
        {std::lock_guard<std::mutex> lock(mutex_);closing_=true;}
        tx_ready_.notify_one();rx_ready_.notify_one();if(sender_.joinable())sender_.join();sending_=false;
        if(!dispatch_.joinable())return;
        for(unsigned l=0;l<channels();++l){app_->stop_offer_service(local(l),1,1,0);app_->release_service(peer(l),1);}
        app_->clear_all_handler();app_->stop();stop_return_ns=now();dispatch_.join();join_return_ns=now();
        for(const auto& r:timing_)trace_<<r.ns<<','<<r.event<<','<<r.lane<<','<<r.method<<','<<r.bytes<<','<<r.crc<<','<<r.cpu_ns<<'\n';
        trace_<<stop_return_ns<<",stop-return,0,0,0\n"<<join_return_ns<<",join-return,0,0,0\n";trace_.flush();
    }
    bool trace_ok() const {return !trace_overflow_ && static_cast<bool>(trace_);}
    ~Transport(){stop();}
};
}
