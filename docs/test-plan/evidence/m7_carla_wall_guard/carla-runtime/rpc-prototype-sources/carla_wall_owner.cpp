// Real native owner and independent blocking adapter IO. No CARLA calls here.
#include "wall_rig.hpp"
#include "wall_mailbox.hpp"
#include "wall_execution_watch.hpp"
#include "native_admission.hpp"
#include "wall_signal.hpp"
#include "latest_snapshot.hpp"
#include <atomic>
#include <fcntl.h>
#include <poll.h>
#include <sys/mman.h>
#include <unistd.h>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <thread>
using namespace stratadrive;
using namespace m7_functional;
namespace {
void packet(const m7_native::Packet& p) {
    if(!p){std::cout<<"null";return;}
    std::cout<<'"'<<std::hex<<std::setfill('0');
    for(std::size_t i=0;i<p->size;++i)std::cout<<std::setw(2)<<unsigned(p->bytes[i]);
    std::cout<<std::dec<<'"';
}
template<std::size_t N> void packets(const std::array<m7_native::Packet,N>& p) {
    std::cout<<'[';for(unsigned i=0;i<N;++i){if(i)std::cout<<',';packet(p[i]);}std::cout<<']';
}
m7_native::Input proof(const Report& r) {
    m7_native::Input in;
    if(r.native_export) {
        const auto& e=*r.native_export;in.observed=e.observed;in.enable=e.enable;in.normal=e.normal;
        in.protection_since=e.protection_since;in.protection_selected_mask=e.protection_selected_mask;
        in.actual=e.actual;in.commands=e.commands;in.release=e.release;in.credit=e.credit;in.permission=e.permission;
    }
    in.service_mask=r.service_mask;in.credit_mask=r.credit_mask;in.release_mask=r.release_mask;return in;
}
void emit(const Report& r,bool ready,const m7_native::Output& out,const std::string& why) {
    const auto p=proof(r);
    std::cout<<std::setprecision(17)<<"{\"ready\":"<<ready<<",\"eligibility_error\":\""<<why<<"\",\"now_ns\":"<<r.now<<",\"armed\":"<<r.armed
      <<",\"protection_ns\":"<<p.protection_since<<",\"energy_end\":"<<(r.electrical?r.electrical->end:0)
      <<",\"energy_acquired\":"<<r.electrical_acquired<<",\"coil_source\":"<<r.coil_source
      <<",\"coils\":["<<r.coils.close.positive<<','<<r.coils.close.negative<<','<<r.coils.close.precharge<<','<<r.coils.discharge_bus<<']'
      <<",\"settlement\":{\"mechanical_j\":"<<(r.electrical?r.electrical->total_mechanical_j:0)
      <<",\"balance_j\":"<<(r.electrical?r.electrical->balance_j:0)<<"},\"admission\":{\"empty\":"<<out.empty
      <<",\"torque\":"<<out.torque<<",\"pressure\":"<<out.pressure<<",\"oldest\":"<<out.oldest_actuator
      <<",\"expiry\":"<<out.exclusive_expiry<<"},\"native\":{\"observed\":\""<<p.observed<<"\",\"enable\":\""<<p.enable
      <<"\",\"normal\":"<<(p.normal?"true":"false")<<",\"protection_since\":\""<<p.protection_since
      <<"\",\"protection_selected_mask\":"<<p.protection_selected_mask<<",\"service_mask\":"<<p.service_mask
      <<",\"credit_mask\":"<<p.credit_mask<<",\"release_mask\":"<<p.release_mask<<",\"actual\":";
    packets(p.actual);std::cout<<",\"commands\":";packets(p.commands);std::cout<<",\"release\":";packets(p.release);
    std::cout<<",\"credit\":";packets(p.credit);std::cout<<",\"permission\":";packet(p.permission);std::cout<<"}}"<<std::endl;
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=4)throw std::runtime_error("carla_wall_owner signal-file trace-prefix scenario");
        std::ifstream profile(argv[3]);std::vector<RequestPhase> phases;std::string line;
        while(std::getline(profile,line)) {
            if(line.empty() || line[0]=='#')continue;
            RequestPhase p{};unsigned hold=0;std::istringstream in(line);
            if(!(in>>p.end_ms>>p.acceleration>>p.curvature>>p.braking>>hold) || hold>1)throw std::runtime_error("scenario");
            p.hold=hold;phases.push_back(p);
        }
        // Extend the last declared request over the finite wall test horizon;
        // release periods and request values remain the declared scenario.
        if(phases.empty())throw std::runtime_error("empty scenario");

        std::uint32_t actor;Time model;std::string start;
        if(!(std::cin>>start>>actor>>model) || start!="START")throw std::runtime_error("start protocol");
        std::getline(std::cin,line);
        const int fd=open(argv[1],O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
        if(fd<0 || ftruncate(fd,sizeof(m7_native::WallSignal)))throw std::runtime_error("signal create");
        auto* signal=static_cast<m7_native::WallSignal*>(mmap(nullptr,sizeof(m7_native::WallSignal),PROT_READ|PROT_WRITE,MAP_SHARED,fd,0));close(fd);
        if(signal==MAP_FAILED)throw std::runtime_error("signal map");
        const auto initial=WallExecutionWatch::now()+50*ms;
        *signal={m7_native::wall_signal_magic,initial,42,0};
        WallRig rig({1,42,7},actor,initial,model);rig.request_profile(std::move(phases));
        WallMailbox<WallReceipt,8> inbox;runtime::LatestSnapshot<Report> latest;
        std::atomic<bool> done{false},trip{false};
        WallExecutionWatch watch(initial+ms,19000*ms);rig.execution_watch(&watch);
        simulation::runtime_support::sleep_until(initial);
        std::cout<<"{\"initial\":"<<initial<<"}"<<std::endl;
        std::thread io([&] {
            try {
                m7_native::Admission gate(42,initial,m7_native::ClockPolicy::HostMonotonic);
                std::optional<m7_native::Input> selected;Time selected_time=0;
                while(!done.load()) {
                    pollfd input{STDIN_FILENO,POLLIN,0};
                    if(::poll(&input,1,20)<=0)continue;
                    if(!std::getline(std::cin,line))break;
                    if(line.size()>20000)throw std::runtime_error("input bound");
                    std::istringstream in(line);std::string op;in>>op;
                    if(op=="STOP")break;
                    if(op=="PROTECT") {trip.store(true);std::cout<<"{\"requested\":true}"<<std::endl;continue;}
                    if(op=="GET") {
                        const auto r=latest.read();
                        if(!r){std::cout<<"{\"ready\":false}"<<std::endl;continue;}
                        m7_native::Output out;const auto now=WallExecutionWatch::now();
                        std::string why;const bool ready=gate.eligible(proof(*r),now+2000000,out,&why);
                        // COMMIT is sent only after server confirms the staged
                        // proof, so skipped snapshots do not advance RX cursors.
                        if(ready){selected=proof(*r);selected_time=now+2000000;}
                        emit(*r,ready,out,why);continue;
                    }
                    if(op=="COMMIT") {
                        // The adapter echoes the selected sequence's report by
                        // requesting one at a time. Cursor consumption belongs
                        // exclusively to the SERVER; local preview is stateless.
                        m7_native::Output out;
                        if(!selected || !gate.accept(*selected,selected_time,out))throw std::runtime_error("preview commit");
                        selected.reset();std::cout<<"{\"committed\":true}"<<std::endl;continue;
                    }
                    if(op!="FRAME")throw std::runtime_error("input operation");
                    WallReceipt r;r.clock=wall_domain;r.wheel.actor=actor;r.carla.emplace();
                    auto& c=*r.carla;auto& w=c.work;unsigned sleeping;unsigned a,b,d,e;
                    in>>w.frame>>w.begin>>w.end>>c.applied>>c.acquired_begin>>c.acquired_end>>c.oldest>>c.coil_source
                      >>a>>b>>d>>e>>w.torque>>w.dt>>sleeping>>w.wheel.value;
                    if(a>1 || b>1 || d>1 || e>1 || sleeping>1)throw std::runtime_error("frame booleans");
                    c.coils={{bool(a),bool(b),bool(d)},bool(e)};w.sleeping=sleeping;w.oldest=w.begin;
                    w.wheel.identity={7,static_cast<std::uint32_t>(w.frame-1),w.begin};w.wheel.input_time_ns=w.begin;
                    r.wheel.frame=w.frame;r.wheel.source=c.acquired_begin;
                    for(auto& omega:r.wheel.omega)in>>omega;
                    for(auto& omega:w.rear_mean)in>>omega;
                    std::string extra;if(!in || (in>>extra))throw std::runtime_error("frame parse");
                    r.work=w;if(!inbox.push(r))throw std::runtime_error("receipt overflow");
                    std::cout<<"{\"received\":"<<w.frame<<"}"<<std::endl;
                }
            }catch(const std::exception& e){std::cerr<<"IO "<<e.what()<<'\n';inbox.fail();}
            done.store(true);
        });

        std::ofstream trace(std::string(argv[2])+".csv");
        // Trace is buffered in memory; filesystem IO happens after owner stop.
        struct Row {Time now,energy,source,protect;bool armed;};
        std::vector<Row> rows;rows.reserve(30001);std::string failure;
        auto wake=initial+ms;
        try {
        while(!done.load() && wake<initial+19000*ms) {
            simulation::runtime_support::sleep_until(wake);const auto now=WallExecutionWatch::now();
            if(inbox.failed() || trip.load())rig.protect("adapter/receipt fault");
            auto r=rig.service(now,inbox.pop());
            if(r.failed) {m7_native::wall_trip(signal);if(failure.empty())failure=r.reason;}
            latest.publish(r.native);
            rows.push_back({now,r.native.electrical?r.native.electrical->end:0,r.native.sensor_wheel?r.native.sensor_wheel->source:0,r.protected_at,r.native.armed});
            wake=initial+((WallExecutionWatch::now()-initial)/ms+1)*ms;
        }
        } catch(const std::exception& e) {failure=std::string("owner exception: ")+e.what();}
        m7_native::wall_trip(signal);done.store(true);io.join();watch.write(std::string(argv[2])+"-wall.csv");
        trace<<"now,energy_end,wheel_source,protection,armed\n";
        for(const auto& r:rows)trace<<r.now<<','<<r.energy<<','<<r.source<<','<<r.protect<<','<<r.armed<<'\n';
        std::ofstream meta(std::string(argv[2])+".json");meta<<"{\"first_fault\":\""<<failure<<"\",\"initial\":"<<initial<<"}\n";
        munmap(signal,sizeof(m7_native::WallSignal));return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
