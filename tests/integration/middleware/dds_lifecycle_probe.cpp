// Gate-closed optional DDS11.0.1 transport/lifetime diagnostic, not a controller.
#include "owner_wire.hpp"
#include "packet.h"
#include "dds_allocation_trace.hpp"
#include <dds/dds.h>
extern "C" void lifecycle_snapshot(dds_entity_t writer,std::uint64_t out[6]);
extern "C" int lifecycle_proxy_snapshot(dds_entity_t reader,std::uint64_t out[9]);
#include <algorithm>
#include <cassert>
#include <chrono>
#include <cstring>
#include <deque>
#include <filesystem>
#include <iostream>
#include <optional>
#include <thread>
using namespace stratadrive;
namespace {
constexpr std::uint64_t ms=1000000,domain=0x534452564c414231ULL;
std::uint64_t now(){return allocation_trace::now();}
void sleep(){std::this_thread::sleep_for(std::chrono::microseconds(200));}
void mark(const std::string& file){std::ofstream(file)<<now()<<'\n';}
struct Callback {
    std::atomic<unsigned> active{0},calls{0};std::atomic<bool> entered{false};
    bool hold;std::string marker;
};
void available(dds_entity_t,void* arg){
    auto& c=*static_cast<Callback*>(arg);c.active.fetch_add(1,std::memory_order_relaxed);
    const unsigned i=c.calls.fetch_add(1,std::memory_order_relaxed);
    if(c.hold && i==0){mark(c.marker);c.entered.store(true,std::memory_order_relaxed);std::this_thread::sleep_for(std::chrono::milliseconds(50));}
    c.active.fetch_sub(1,std::memory_order_relaxed);
}
void snapshot(dds_entity_t writer,std::ofstream& out,const char* stage){
    std::uint64_t values[6]{};lifecycle_snapshot(writer,values);
    out<<now()<<','<<stage<<",0x"<<std::hex<<values[0]<<",0x"<<values[1]<<std::dec;
    for(unsigned i=2;i<6;++i)out<<','<<values[i];
    out<<'\n';
}
}
int main(int argc,char** argv){
    if(argc!=5)return 2;
    const std::string role=argv[1],folder=argv[2],scenario=argv[3];
    const bool central=role=="central";std::uint32_t epoch=std::stoul(argv[4]);
    const std::string prefix=folder+"/"+role+"-"+std::to_string(epoch);
    const bool observe=!(std::getenv("SD_LIFETIME_TRACE") && std::string(std::getenv("SD_LIFETIME_TRACE"))=="off");
    const bool coordinated=std::getenv("SD_COORDINATED_RESTART")!=nullptr;
    if(observe)allocation_trace::install();
    Callback cb;cb.hold=!central && scenario=="callback-delete";cb.marker=prefix+".callback";
    const auto pp=dds_create_participant(37,nullptr,nullptr);assert(pp>0);
    const auto down=dds_create_topic(pp,&strata_Packet_desc,"sd_lifetime_down",nullptr,nullptr);
    const auto up=dds_create_topic(pp,&strata_Packet_desc,"sd_lifetime_up",nullptr,nullptr);assert(up>0 && down>0);
    auto* qos=dds_create_qos();dds_qset_reliability(qos,DDS_RELIABILITY_RELIABLE,0);
    dds_qset_history(qos,DDS_HISTORY_KEEP_ALL,8);dds_qset_resource_limits(qos,8,1,8);
    dds_qset_durability(qos,DDS_DURABILITY_VOLATILE);
    auto writer=dds_create_writer(pp,central?down:up,qos,nullptr);assert(writer>0);
    auto* listener=dds_create_listener(&cb);dds_lset_data_available(listener,available);
    auto reader=dds_create_reader(pp,central?up:down,qos,listener);assert(reader>0);
    dds_delete_listener(listener);dds_delete_qos(qos);
    assert(dds_set_status_mask(reader,DDS_SAMPLE_REJECTED_STATUS|DDS_SAMPLE_LOST_STATUS)==0);
    std::ofstream events(prefix+".csv"),objects(prefix+".objects.csv"),proxies(prefix+".proxy.csv");
    proxies<<"proxy,participant,lease,mutex,guid_prefix,guid_entity,lease_duration_ns,last_access_ns,scope_end_ns\n";
    events<<"time_ns,event,epoch,token,source_ns,deadline_ns,inner_expiry_ns,accepted\n";
    objects<<"time_ns,stage,writer,whc,seq,min_seq,max_seq,unacked_bytes\n";snapshot(writer,objects,"created");
    auto maps=std::ifstream("/proc/self/maps");std::ofstream(prefix+".maps")<<maps.rdbuf();
    const auto setup=now();
    for(;;){dds_publication_matched_status_t status{};assert(dds_get_publication_matched_status(writer,&status)==0);
        if(status.current_count>0)break;
        if(now()-setup>10000*ms)return 3;
        sleep();}
    mark(prefix+".matched");
    const std::string go=folder+(epoch==43?"/go43":"/go");
    while(!std::filesystem::exists(go)){assert(now()-setup<12000*ms);sleep();}
    const auto start=now();auto next=start;unsigned sent=0,received=0,accepted=0,rejected=0,old=0,stale=0,failures=0,overflows=0;
    std::uint64_t valid_deadline=0,loss=0,delete_begin=0,delete_end=0;bool failed_link=false,deleted=false;
    std::uint32_t previous=0;bool has_previous=false;std::deque<remote::OwnerPacket> ingress,result;
    remote::OwnerPacket saved{};bool saved_valid=false,replayed=false;unsigned max_in=0,max_out=0,proxy_samples=0;std::uint64_t whc_samples=0;
    const auto duration=(scenario=="restart"?4200:1600)*ms;
    auto log=[&](const char* event,const transport::ZoneRequest& q,bool ok){
        const auto* r=std::get_if<central::VehicleRequest>(&q.work);
        events<<now()<<','<<event<<','<<q.epoch<<','<<q.token<<','<<q.sent_ns<<','<<q.deadline_ns<<','<<(r?r->expires_at_ns:0)<<','<<ok<<'\n';events.flush();
    };
    auto send=[&](const remote::OwnerPacket& packet){strata_Packet p{};p.size=packet.size;std::memcpy(p.data,packet.bytes.data(),packet.size);const auto rc=dds_write(writer,&p);if(rc<0){++failures;failed_link=true;}return rc==0;};
    while(now()-start<duration){
        const auto t=now();
        if(central && scenario=="restart" && epoch==42 && std::filesystem::exists(folder+"/epoch43")){epoch=43;sent=0;has_previous=false;next=t;}
        if(central && sent<60 && t>=next && !(coordinated && scenario=="restart" && epoch==42 && std::filesystem::exists(folder+"/quiesce"))){
            central::VehicleRequest request{epoch,sent,t,t+30*ms,.2,.02,0,false};
            transport::ZoneRequest q{epoch,sent,t,t+20*ms,request};
            auto p=remote::encode_owner_message({session::Role::CentralIngress,session::Role::FrontZone,domain,q});assert(p);
            const bool ok=send(*p);log("send",q,ok);if(!saved_valid){saved=*p;saved_valid=true;}
            snapshot(writer,objects,"write");++whc_samples;
            if(scenario=="lifetime" && sent%20==0){std::uint64_t ids[9]{};if(lifecycle_proxy_snapshot(reader,ids)){for(unsigned i=0;i<9;++i)proxies<<(i?",":"")<<ids[i];proxies<<'\n';++proxy_samples;}}
            ++sent;next=t+5*ms;
        }
        if(central && scenario=="restart" && epoch==43 && !replayed && sent>=5){assert(saved_valid);send(saved);replayed=true;}
        if(!central && scenario=="callback-delete" && cb.entered.load(std::memory_order_relaxed) && !deleted){
            delete_begin=now();assert(cb.active.load(std::memory_order_relaxed)>0);
            assert(dds_delete(reader)==0);delete_end=now();assert(cb.active.load(std::memory_order_relaxed)==0);deleted=true;
        }
        const bool blocked=!central && scenario=="overflow" && t-start<400*ms;
        if(!deleted && !blocked)for(unsigned budget=0;budget<8;++budget){
            strata_Packet p{};void* samples[1]={&p};dds_sample_info_t info[1]{};const auto n=dds_take(reader,samples,info,1,1);
            if(n<0){++failures;break;}if(n==0)break;if(!info[0].valid_data)continue;
            remote::OwnerPacket packet{};if(p.size>packet.bytes.size()){++rejected;continue;}
            packet.size=p.size;std::memcpy(packet.bytes.data(),p.data,p.size);
            if(ingress.size()==8){++overflows;failed_link=true;}else ingress.push_back(packet);
            max_in=std::max(max_in,unsigned(ingress.size()));
        }
        while(!ingress.empty()){
            auto packet=ingress.front();ingress.pop_front();auto msg=remote::decode_owner_message(packet.bytes.data(),packet.size);
            if(!msg){++rejected;continue;}const auto* q=std::get_if<transport::ZoneRequest>(&msg->payload);
            if(!q){++rejected;continue;}const auto* r=std::get_if<central::VehicleRequest>(&q->work);if(!r){++rejected;continue;}
            const auto rx=now();const bool ok=msg->from==session::Role::CentralIngress && msg->to==session::Role::FrontZone && msg->clock_domain==domain && q->epoch==epoch && q->token==r->sequence && q->epoch==r->epoch &&
                q->sent_ns==r->source_time_ns && q->deadline_ns>q->sent_ns && q->deadline_ns-q->sent_ns<=20*ms &&
                q->deadline_ns<=r->expires_at_ns && q->sent_ns<=rx && rx<q->deadline_ns && rx<r->expires_at_ns &&
                (!has_previous || r->sequence>previous);
            ++received;if(ok){++accepted;previous=r->sequence;has_previous=true;valid_deadline=q->deadline_ns;}else{++rejected;if(q->epoch!=epoch)++old;if(rx>=q->deadline_ns)++stale;}
            log(central?"result":"ingress",*q,ok);
            if(!central && ok){if(result.size()==8){++overflows;failed_link=true;}else result.push_back(packet);max_out=std::max(max_out,unsigned(result.size()));}
            if(!central && received>=20)mark(prefix+".progress");
        }
        if(!result.empty()){
            if(!central && scenario=="partial" && accepted>=20 && !deleted){assert(dds_delete(writer)==0);deleted=true;}
            if(!failed_link){send(result.front());result.pop_front();}else result.clear();
        }
        if(valid_deadline && t>=valid_deadline && !loss)loss=t; // availability only, never an ECU protection ACK
        if(!central && (scenario=="peer-stop" || (scenario=="restart" && epoch==42 && (!coordinated || std::filesystem::exists(folder+"/close42")))) && received>=20)break;
        sleep();
    }
    if(!deleted || scenario=="callback-delete"){snapshot(writer,objects,"before-delete");(void)dds_wait_for_acks(writer,DDS_MSECS(100));}
    mark(prefix+".delete");assert(dds_delete(pp)==0);assert(cb.active.load(std::memory_order_relaxed)==0);
    const auto cb_calls=cb.calls.load(std::memory_order_relaxed);assert(allocation_trace::save(prefix+".alloc.csv"));
    bool ok=sent>0 || received>0 || scenario=="callback-delete";
    if(scenario=="lifetime" && central)ok=ok && proxy_samples>0;
    if(scenario=="normal")ok=ok && (central?(sent==60 && accepted==60):(accepted==60));
    if(scenario=="restart" && !central && epoch==43)ok=ok && accepted>0 && old>0 && stale>0;
    if(scenario=="callback-delete" && !central)ok=ok && delete_begin && delete_end>delete_begin;
    if(scenario=="partial" && !central)ok=ok && failed_link && failures>0;
    if(scenario=="overflow")ok=ok && (central?accepted<60:stale>0);
    std::cout<<"{\"functional\":"<<(ok?"true":"false")<<",\"control_gate_open\":false,\"epoch\":"<<epoch<<",\"sent\":"<<sent<<",\"received\":"<<received<<",\"accepted\":"<<accepted<<",\"rejected\":"<<rejected<<",\"old\":"<<old<<",\"stale\":"<<stale<<",\"failures\":"<<failures<<",\"overflow\":"<<overflows<<",\"max_ingress\":"<<max_in<<",\"max_result\":"<<max_out<<",\"callback_calls\":"<<cb_calls<<",\"callback_delete_begin_ns\":"<<delete_begin<<",\"callback_delete_end_ns\":"<<delete_end<<",\"availability_loss_ns\":"<<loss<<",\"proxy_snapshots\":"<<proxy_samples<<",\"whc_snapshots\":"<<whc_samples<<"}\n";
    return ok?0:1;
}
