// Real native owner and independent blocking adapter IO. No CARLA calls here.
#include "wall_rig.hpp"
#include "wall_mailbox.hpp"
#include "wall_execution_watch.hpp"
#include "native_admission.hpp"
#include "wall_bridge.hpp"
#include "latest_snapshot.hpp"
#include "perception_2k_ipc.hpp"
#include "wall_startup_trace.hpp"
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
#include <limits>
using namespace stratadrive;
using namespace m7_functional;
namespace {
void perception_view(std::ostream& out,const central::PerceptionIpcView& v) {
    out<<"{\"initialized\":"<<v.initialized<<",\"available\":"<<v.available
       <<",\"disconnected\":"<<v.disconnected<<",\"state_fault\":"<<v.state_fault
       <<",\"reason\":"<<static_cast<unsigned>(v.reason)<<",\"transport_fault\":"<<static_cast<unsigned>(v.transport_fault)
       <<",\"received\":"<<v.received<<",\"rejected\":"<<v.rejected<<",\"accepted_results\":"<<v.accepted_results
       <<",\"polls\":"<<v.polls<<",\"unavailable\":"<<v.unavailable<<",\"budget_hits\":"<<v.budget_hits
       <<",\"sequence\":"<<v.sequence<<",\"observed_wall_ns\":"<<v.observed_wall_ns<<",\"state_frame\":"<<v.state_frame
       <<",\"state_source_ns\":"<<v.state_source_ns<<",\"state_received_wall_ns\":"<<v.state_received_wall_ns
       <<",\"source_enable_ns\":"<<v.source_enable_ns<<",\"wall_enable_ns\":"<<v.wall_enable_ns
       <<",\"frame\":"<<v.frame<<",\"source_ns\":"<<v.source_ns<<",\"expires_ns\":"<<v.expires_ns
       <<",\"received_wall_ns\":"<<v.received_wall_ns<<",\"wall_expires_ns\":"<<v.wall_expires_ns
       <<",\"count\":"<<v.count<<",\"tracks\":"<<v.tracks<<'}';
}
struct Telemetry {Report native;std::optional<central::PerceptionIpcView> perception;};
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
void emit(const Report& r,bool ready,const m7_native::Output& out,const std::string& why,
          const std::optional<central::PerceptionIpcView>& perception={}) {
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
    std::cout<<",\"credit\":";packets(p.credit);std::cout<<",\"permission\":";packet(p.permission);std::cout<<'}';
    if(perception){std::cout<<",\"perception\":";perception_view(std::cout,*perception);}
    std::cout<<'}'<<std::endl;
}
}
int main(int argc,char** argv) {
    try {
        if(argc<4 || (argc>6 && argc!=8 && argc!=10))throw std::runtime_error("carla_wall_owner signal-file trace-prefix scenario [5|10] [30|50 HV dependency ms] [--perception-shadow fd:source-clock:wall-clock]");
        const Time model_step=argc>=5?std::stoull(argv[4])*ms:10*ms;
        const Time hv_dependency=argc>=6?std::stoull(argv[5])*ms:30*ms;
        if(model_step!=5*ms && model_step!=10*ms)throw std::runtime_error("wall model step");
        if(hv_dependency!=30*ms && !(model_step==5*ms && hv_dependency==50*ms))throw std::runtime_error("wall HV policy");
        std::unique_ptr<central::PerceptionIpcShadow> perception;
        unsigned endurance=0;
        if(argc==10) {
            if(std::string(argv[8])!="--endurance-seconds")throw std::runtime_error("explicit endurance option");
            const std::string duration(argv[9]);
            if(duration!="30" && duration!="300")throw std::runtime_error("declared endurance duration");
            endurance=duration=="30"?30:300;
            if((endurance!=30 && endurance!=300) || model_step!=5*ms || hv_dependency!=30*ms)throw std::runtime_error("endurance profile");
        }
        const Time diagnostic_horizon=(endurance?endurance+5:19)*1000*ms;
        const auto perception_capacity=static_cast<std::size_t>(endurance?(endurance+5)*50+1:1000);
        if(argc>=8) {
            if(std::string(argv[6])!="--perception-shadow")throw std::runtime_error("shadow-only perception option");
            std::string value=argv[7];std::array<std::uint64_t,3> parts{};std::size_t begin=0;
            for(unsigned i=0;i<3;++i) {
                const auto end=value.find(':',begin);const auto token=value.substr(begin,end==std::string::npos?end:end-begin);
                if(token.empty() || token.find_first_not_of("0123456789")!=std::string::npos || (i<2)==(end==std::string::npos))throw std::runtime_error("shadow IPC identity syntax");
                parts[i]=std::stoull(token);begin=end+1;
            }
            if(parts[0]>static_cast<std::uint64_t>(std::numeric_limits<int>::max()))throw std::runtime_error("shadow IPC descriptor range");
            perception=std::make_unique<central::PerceptionIpcShadow>(static_cast<int>(parts[0]),42,parts[1],parts[2]);
        }
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
        const auto initial=WallExecutionWatch::now()+(endurance?1000:50)*ms;
        bridge->signal={m7_native::wall_signal_magic,initial,42,0};bridge->actor=actor;bridge->model_initial=model;
        bridge->model_step=model_step;
        bridge->session=session;bridge->generation=generation;std::memcpy(bridge->run,run.c_str(),37);
        WallRig rig({1,42,7},actor,initial,model,model_step,hv_dependency,endurance);rig.request_profile(std::move(phases));
        runtime::LatestSnapshot<Telemetry> latest;
        std::atomic<bool> done{false},trip{false};
        WallExecutionWatch watch(initial+ms,diagnostic_horizon);rig.execution_watch(&watch);
        m7_native::SharedReader<m7_native::SharedReceipt> reader;
        m7_native::SharedWriter<m7_native::SharedProof> writer;
        struct Row {Time now,energy,source,protect;bool armed;Time hv_source,hv_dependency;};
        std::vector<Row> rows;rows.reserve(static_cast<std::size_t>(diagnostic_horizon/ms)+1);std::string failure;
        struct PerceptionRow {central::PerceptionIpcView view;Time native_observed,enable,ipc_service_ns;bool armed,failed;std::array<m7_native::Packet,3> actual;};
        std::vector<PerceptionRow> perception_rows;if(perception)perception_rows.reserve(perception_capacity);
        std::optional<central::PerceptionIpcView> perception_latest;
        Time next_perception=0;bool perception_root_error=false;
        simulation::runtime_support::ThreadInfo owner_info,io_info;owner_info.capture();
        simulation::runtime_support::sleep_until(initial);
        std::cout<<"{\"initial\":"<<initial<<",\"bridge_bytes\":"<<sizeof(*bridge)<<",\"model_step_ns\":"<<model_step<<",\"hv_dependency_ns\":"<<hv_dependency<<"}"<<std::endl;
        std::thread io([&] {
            io_info.capture();
            try {
                while(!done.load()) {
                    pollfd input{STDIN_FILENO,POLLIN,0};if(::poll(&input,1,20)<=0)continue;
                    if(!std::getline(std::cin,line))break;
                    if(line=="STOP")break;
                    if(line=="PROTECT"){trip.store(true);std::cout<<"{\"requested\":true}"<<std::endl;continue;}
                    if(line!="GET")throw std::runtime_error("control operation");
                    auto r=latest.read();if(r)emit(r->native,false,{},"",r->perception);else std::cout<<"{\"ready\":false}"<<std::endl;
                }
            }catch(const std::exception& e){std::cerr<<"IO "<<e.what()<<'\n';trip.store(true);}
            __atomic_store_n(&bridge->stop,1ULL,__ATOMIC_RELEASE);done.store(true);
        });
        Time consumed=0;auto wake=initial+ms;
        try {
            while(!done.load() && wake<initial+diagnostic_horizon) {
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
                if(perception && now>=next_perception) {
                    if(in.enable && !perception->observe_native_init(42,in.enable))perception_root_error=true;
                    const auto poll_begin=WallExecutionWatch::now();
                    perception_latest=perception->poll(poll_begin);
                    const auto poll_elapsed=WallExecutionWatch::now()-poll_begin;
                    if(perception_rows.size()<perception_capacity)perception_rows.push_back({*perception_latest,in.observed,in.enable,poll_elapsed,n.armed,r.failed,in.actual});
                    else throw std::runtime_error("bounded native perception trace");
                    next_perception=initial+((WallExecutionWatch::now()-initial)/(20*ms)+1)*(20*ms);
                }
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
                writer.publish(bridge->proof,shared);latest.publish({n,perception_latest});
                rows.push_back({now,shared.energy_end,n.sensor_wheel?n.sensor_wheel->source:0,r.protected_at,n.armed,n.hv_source,n.hv_dependency});
                wake=initial+((WallExecutionWatch::now()-initial)/ms+1)*ms;
            }
        }catch(const std::exception& e){failure=std::string("owner exception: ")+e.what();}
        __atomic_store_n(&bridge->stop,1ULL,__ATOMIC_RELEASE);m7_native::wall_trip(&bridge->signal);done.store(true);io.join();
        watch.write(std::string(argv[2])+"-wall.csv");
        std::ofstream trace(std::string(argv[2])+".csv");trace<<"now,energy_end,wheel_source,protection,armed,hv_source,hv_dependency\n";
        for(const auto& r:rows)trace<<r.now<<','<<r.energy<<','<<r.source<<','<<r.protect<<','<<r.armed<<','<<r.hv_source<<','<<r.hv_dependency<<'\n';
        std::ofstream meta(std::string(argv[2])+".json");meta<<"{\"first_fault\":\""<<failure<<"\",\"initial\":"<<initial<<",\"diagnostic_horizon_ns\":"<<diagnostic_horizon<<",\"hv_dependency_ns\":"<<hv_dependency<<",\"owner\":";
        owner_info.write_json(meta);meta<<",\"io\":";io_info.write_json(meta);meta<<"}\n";
        if(perception) {
            std::ofstream startup(std::string(argv[2])+"-startup.json");write_startup_observations(startup,rig.startup_observations());
            if(!startup)throw std::runtime_error("startup trace write");
            std::ofstream trace(std::string(argv[2])+"-perception.jsonl");trace<<std::setprecision(17);
            for(const auto& row:perception_rows) {
                trace<<"{\"native_observed_ns\":"<<row.native_observed<<",\"native_enable_ns\":"<<row.enable
                     <<",\"ipc_service_ns\":"<<row.ipc_service_ns<<",\"native_armed\":"<<row.armed<<",\"native_failed\":"<<row.failed<<",\"root_error\":"<<perception_root_error
                     <<",\"perception\":";perception_view(trace,row.view);
                trace<<",\"actual\":[";
                for(std::size_t i=0;i<3;++i) {
                    if(i)trace<<',';
                    const auto& p=row.actual[i];
                    if(!p){trace<<"null";continue;}
                    trace<<'"'<<std::hex<<std::setfill('0');
                    for(std::size_t j=0;j<p->size;++j)trace<<std::setw(2)<<unsigned(p->bytes[j]);
                    trace<<std::dec<<'"';
                }
                trace<<"]}\n";
            }
            if(!trace)throw std::runtime_error("shadow trace write");
        }
        munmap(bridge,sizeof(m7_native::WallBridge));return 0;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
