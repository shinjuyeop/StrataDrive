// Real native owner and independent blocking adapter IO. No CARLA calls here.
#include "wall_rig.hpp"
#include "wall_mailbox.hpp"
#include "wall_execution_watch.hpp"
#include "native_admission.hpp"
#include "wall_bridge.hpp"
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
        if(argc!=4 && argc!=5)throw std::runtime_error("carla_wall_owner signal-file trace-prefix scenario [5|10]");
        const Time model_step=argc==5?std::stoull(argv[4])*ms:10*ms;
        if(model_step!=5*ms && model_step!=10*ms)throw std::runtime_error("wall model step");
        std::ifstream profile(argv[3]);std::vector<RequestPhase> phases;std::string line;
        while(std::getline(profile,line)) {
            if(line.empty() || line[0]=='#')continue;
            RequestPhase p{};unsigned hold=0;std::istringstream in(line);
            if(!(in>>p.end_ms>>p.acceleration>>p.curvature>>p.braking>>hold) || hold>1)throw std::runtime_error("scenario");
            p.hold=hold;phases.push_back(p);
        }
        if(phases.empty())throw std::runtime_error("empty scenario");
        std::uint32_t actor;Time model,session,generation;std::string start,run;
        if(!(std::cin>>start>>actor>>model>>session>>generation>>run) || start!="START" || !session || !generation ||
           run.size()!=36 || run.find_first_not_of("0123456789abcdefABCDEF-")!=std::string::npos)throw std::runtime_error("start protocol");
        std::getline(std::cin,line);
        const int fd=open(argv[1],O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
        if(fd<0)throw std::runtime_error("bridge create");
        if(ftruncate(fd,sizeof(m7_native::WallBridge))) {close(fd);throw std::runtime_error("bridge resize");}
        void* memory=mmap(nullptr,sizeof(m7_native::WallBridge),PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);close(fd);
        if(memory==MAP_FAILED)throw std::runtime_error("bridge map");
        auto* bridge=new(memory) m7_native::WallBridge;
        const auto initial=WallExecutionWatch::now()+50*ms;
        bridge->signal={m7_native::wall_signal_magic,initial,42,0};bridge->actor=actor;bridge->model_initial=model;
        bridge->model_step=model_step;
        bridge->session=session;bridge->generation=generation;std::memcpy(bridge->run,run.c_str(),37);
        WallRig rig({1,42,7},actor,initial,model,model_step);rig.request_profile(std::move(phases));
        runtime::LatestSnapshot<Report> latest;
        std::atomic<bool> done{false},trip{false};
        WallExecutionWatch watch(initial+ms,19000*ms);rig.execution_watch(&watch);
        m7_native::SharedReader<m7_native::SharedReceipt> reader;
        m7_native::SharedWriter<m7_native::SharedProof> writer;
        struct Row {Time now,energy,source,protect;bool armed;};
        std::vector<Row> rows;rows.reserve(20000);std::string failure;
        simulation::runtime_support::ThreadInfo owner_info,io_info;owner_info.capture();
        simulation::runtime_support::sleep_until(initial);
        std::cout<<"{\"initial\":"<<initial<<",\"bridge_bytes\":"<<sizeof(*bridge)<<",\"model_step_ns\":"<<model_step<<"}"<<std::endl;
        std::thread io([&] {
            io_info.capture();
            try {
                while(!done.load()) {
                    pollfd input{STDIN_FILENO,POLLIN,0};if(::poll(&input,1,20)<=0)continue;
                    if(!std::getline(std::cin,line))break;
                    if(line=="STOP")break;
                    if(line=="PROTECT"){trip.store(true);std::cout<<"{\"requested\":true}"<<std::endl;continue;}
                    if(line!="GET")throw std::runtime_error("control operation");
                    auto r=latest.read();if(r)emit(*r,false,{},"");else std::cout<<"{\"ready\":false}"<<std::endl;
                }
            }catch(const std::exception& e){std::cerr<<"IO "<<e.what()<<'\n';trip.store(true);}
            __atomic_store_n(&bridge->stop,1ULL,__ATOMIC_RELEASE);done.store(true);
        });
        Time consumed=0;auto wake=initial+ms;
        try {
            while(!done.load() && wake<initial+19000*ms) {
                simulation::runtime_support::sleep_until(wake);auto now=WallExecutionWatch::now();
                if(__atomic_load_n(&bridge->server_trip,__ATOMIC_ACQUIRE))rig.protect("physics completed after authority expiry");
                if(trip.load())rig.protect("trusted adapter safety request");
                std::optional<WallReceipt> receipt;m7_native::SharedReceipt value;
                if(reader.read(bridge->receipt,value) && value.frame!=consumed) {
                    m7_external::CarlaWork c;auto& w=c.work;
                    w.frame=value.frame;w.begin=value.begin;w.end=value.end;w.oldest=w.begin;w.torque=value.torque;w.dt=value.dt;w.sleeping=value.sleeping;
                    w.wheel={value.wheel_begin,{7,static_cast<std::uint32_t>(w.frame-1),w.begin},w.begin};
                    std::copy(std::begin(value.means),std::end(value.means),w.rear_mean.begin());
                    c.applied=value.applied;c.acquired_begin=value.acquired_begin;c.acquired_end=value.acquired_end;c.oldest=value.oldest;c.coil_source=value.coil_source;
                    c.coils={{bool(value.coils&1),bool(value.coils&2),bool(value.coils&4)},bool(value.coils&8)};
                    if(value.coils>15 || value.sleeping>1)rig.protect("shared receipt encoding");
                    receipt=WallReceipt{{actor,w.frame,c.acquired_begin,{value.omega[0],value.omega[1],value.omega[2],value.omega[3]}},w,wall_domain,c};
                    consumed=w.frame;
                }
                now=WallExecutionWatch::now();
                auto r=rig.service(now,receipt);
                if(r.failed){m7_native::wall_trip(&bridge->signal);if(failure.empty())failure=r.reason;}
                const auto& n=r.native;const auto in=proof(n);
                m7_native::SharedProof shared;
                shared.observed=in.observed;shared.enable=in.enable;shared.protection_since=in.protection_since;shared.normal=in.normal;
                shared.selected=in.protection_selected_mask;shared.service=in.service_mask;shared.credit_mask=in.credit_mask;shared.release_mask=in.release_mask;
                for(unsigned i=0;i<3;++i){shared.actual[i]=m7_native::shared_packet(in.actual[i]);shared.commands[i]=m7_native::shared_packet(in.commands[i]);}
                for(unsigned i=0;i<8;++i)shared.release[i]=m7_native::shared_packet(in.release[i]);
                for(unsigned i=0;i<7;++i)shared.credit[i]=m7_native::shared_packet(in.credit[i]);
                shared.permission=m7_native::shared_packet(in.permission);
                shared.coil_source=n.coil_source;shared.coils=unsigned(n.coils.close.positive)|unsigned(n.coils.close.negative)*2|unsigned(n.coils.close.precharge)*4|unsigned(n.coils.discharge_bus)*8;
                if(n.electrical){shared.energy_end=n.electrical->end;shared.total_mechanical=n.electrical->total_mechanical_j;shared.balance=n.electrical->balance_j;
                    const auto& e=*n.electrical;shared.soc=e.soc;shared.chemical=e.chemical_j;shared.motor_loss=e.motor_loss_j;
                    shared.auxiliary=e.auxiliary_j;shared.ohmic=e.ohmic_j;shared.capacitor=e.capacitor_delta_j;shared.circuit=e.circuit_loss_j;}
                writer.publish(bridge->proof,shared);latest.publish(n);
                rows.push_back({now,shared.energy_end,n.sensor_wheel?n.sensor_wheel->source:0,r.protected_at,n.armed});
                wake=initial+((WallExecutionWatch::now()-initial)/ms+1)*ms;
            }
        }catch(const std::exception& e){failure=std::string("owner exception: ")+e.what();}
        __atomic_store_n(&bridge->stop,1ULL,__ATOMIC_RELEASE);m7_native::wall_trip(&bridge->signal);done.store(true);io.join();
        watch.write(std::string(argv[2])+"-wall.csv");
        std::ofstream trace(std::string(argv[2])+".csv");trace<<"now,energy_end,wheel_source,protection,armed\n";
        for(const auto& r:rows)trace<<r.now<<','<<r.energy<<','<<r.source<<','<<r.protect<<','<<r.armed<<'\n';
        std::ofstream meta(std::string(argv[2])+".json");meta<<"{\"first_fault\":\""<<failure<<"\",\"initial\":"<<initial<<",\"owner\":";
        owner_info.write_json(meta);meta<<",\"io\":";io_info.write_json(meta);meta<<"}\n";
        munmap(bridge,sizeof(m7_native::WallBridge));return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
