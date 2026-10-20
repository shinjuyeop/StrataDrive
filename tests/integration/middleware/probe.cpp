#include "channel.h"
#include "owner_wire.hpp"
#include <chrono>
#include <thread>
#include <fstream>
#include <iostream>
#include <cstring>
#include <sched.h>
#include <map>
#include <tuple>

using namespace stratadrive;
namespace {
std::uint64_t now() {return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());}
constexpr std::uint64_t ms=1000000,domain=0x534452564c414231ULL;
}
int main(int argc,char** argv) {
    if(argc!=5)return 2;
    const bool central=std::string(argv[1])=="central";const auto epoch=static_cast<std::uint32_t>(std::stoul(argv[3]));
    const bool pause=std::string(argv[4])=="overflow";
    std::ofstream csv(argv[2]);csv<<"time_ns,event,epoch,sequence,source_ns,expiry_ns,accepted\n";
    if(!csv || !probe_open(central)) {std::cerr<<"channel setup failed\n";probe_close();return 3;}
    const auto start=now();std::uint64_t next=start+1500*ms;unsigned sent=0,received=0,accepted=0,rejected=0;std::optional<std::uint32_t> previous;unsigned mismatch=0;
    std::map<std::tuple<std::uint32_t,std::uint32_t,std::uint64_t>,remote::OwnerPacket> expected;
    auto send=[&](central::VehicleRequest r) {
        remote::OwnerMessage m{session::Role::CentralIngress,session::Role::FrontZone,domain,transport::ZoneRequest{r.epoch,r.sequence,r.source_time_ns,r.expires_at_ns,r}};
        const auto p=remote::encode_owner_message(m);if(!p)return false;expected[{r.epoch,r.sequence,r.source_time_ns}]=*p;const bool ok=probe_send(p->bytes.data(),static_cast<std::uint32_t>(p->size));
        csv<<now()<<",send,"<<r.epoch<<','<<r.sequence<<','<<r.source_time_ns<<','<<r.expires_at_ns<<','<<ok<<'\n';return ok;
    };
    while(now()-start<4200*ms) {
        const auto t=now();
        if(central && sent<100 && t>=next) {
            const central::VehicleRequest r{epoch,sent,t,t+30*ms,.2,.02,0,false};send(r);
            if(sent==10)send(r); // duplicate, not a new input
            if(sent==20){auto old=r;old.epoch=epoch-1;send(old);}
            if(sent==30){auto stale=r;stale.source_time_ns-=100*ms;stale.expires_at_ns-=100*ms;send(stale);}
            ++sent;next+=20*ms;
        }
        const bool blocked=pause && !central && t-start>=2200*ms && t-start<2500*ms;
        if(!blocked) for(unsigned budget=0;budget<8;++budget) {
            std::array<std::uint8_t,remote::kOwnerWireCapacity> data{};const auto size=probe_take(data.data());if(!size)break;
            const auto message=remote::decode_owner_message(data.data(),size);if(!message) {++rejected;continue;}
            const auto* q=std::get_if<transport::ZoneRequest>(&message->payload);if(!q) {++rejected;continue;}
            const auto* r=std::get_if<central::VehicleRequest>(&q->work);if(!r){++rejected;continue;}
            if(central) {const auto it=expected.find({r->epoch,r->sequence,r->source_time_ns});if(it==expected.end() || it->second.size!=size || std::memcmp(it->second.bytes.data(),data.data(),size)!=0)++mismatch;}
            const auto rx=now();const bool valid=r->epoch==epoch && r->source_time_ns<=rx && rx-r->source_time_ns<=30*ms && rx<r->expires_at_ns &&
                (!previous || r->sequence>*previous);
            if(!central && valid){previous=r->sequence;++accepted;}else if(!central)++rejected;
            // Echo unchanged bytes even for rejected packets: this is an API/
            // queue probe, never a control ACK, Actual source or authority grant.
            if(!central)probe_send(data.data(),size);
            ++received;csv<<rx<<','<<(central?"echo":"receive")<<','<<r->epoch<<','<<r->sequence<<','<<r->source_time_ns<<','<<r->expires_at_ns<<','<<valid<<'\n';
        }
        std::this_thread::sleep_for(std::chrono::microseconds(200));
    }
    cpu_set_t affinity;CPU_ZERO(&affinity);sched_getaffinity(0,sizeof affinity,&affinity);
    std::cout<<"{\"cpu\":"<<sched_getcpu()<<",\"affinity_count\":"<<CPU_COUNT(&affinity)<<",\"cpu1\":"<<CPU_ISSET(1,&affinity)<<",\"policy\":"<<sched_getscheduler(0)<<",\"sent\":"<<sent<<",\"received\":"<<received<<",\"accepted\":"<<accepted<<",\"rejected\":"<<rejected<<",\"echo_mismatch\":"<<mismatch<<",\"channel_failures\":"<<probe_overflow()<<"}\n";
    probe_close();return 0;
}
