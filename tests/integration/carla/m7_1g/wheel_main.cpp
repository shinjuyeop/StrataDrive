#include "functional_rig.hpp"
#include "native_admission.hpp"
#include "wall_execution_watch.hpp"
#include <cerrno>
#include <poll.h>
#include <unistd.h>
#include <iomanip>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
using namespace stratadrive::m7_functional;
namespace {
// Bounded, interruptible input; std::getline can hide buffered WORK/WHEEL lines
// from poll(). Waiting here is NOT an owner execution opportunity.
class Input {
    std::string pending_;
    bool eof_=false;
public:
    enum class Result {Line,Wait,End};
    Result read(std::string& line) {
        auto take=[&] {
            const auto end=pending_.find('\n');
            if(end==std::string::npos)return false;
            if(end>20000)throw std::runtime_error("input line bound");
            line=pending_.substr(0,end);pending_.erase(0,end+1);return true;
        };
        if(take())return Result::Line;
        if(pending_.size()>20000)throw std::runtime_error("input line bound");
        if(eof_) {
            if(!pending_.empty())throw std::runtime_error("unterminated input");
            return Result::End;
        }
        pollfd fd{STDIN_FILENO,POLLIN,0};
        const int ready=::poll(&fd,1,1);
        if(ready<0 && errno!=EINTR)throw std::runtime_error("input poll");
        if(ready<=0)return Result::Wait;
        char bytes[4096];const auto size=::read(STDIN_FILENO,bytes,sizeof(bytes));
        if(size<0) {if(errno==EINTR)return Result::Wait;throw std::runtime_error("input read");}
        if(!size)eof_=true;else pending_.append(bytes,static_cast<std::size_t>(size));
        return take()?Result::Line:Result::Wait;
    }
};
void audit(const std::optional<WheelAudit>& w) {
    if(w)std::cout<<"{\"source_ns\":"<<w->source<<",\"rad_s\":"<<w->rad_s<<'}';
    else std::cout<<"null";
}
void packet(const std::optional<stratadrive::remote::OwnerPacket>& p,std::ostream& out=std::cout) {
    if(!p){out<<"null";return;}
    out<<'"'<<std::hex<<std::setfill('0');
    for(std::size_t i=0;i<p->size;++i)out<<std::setw(2)<<unsigned(p->bytes[i]);
    out<<std::dec<<'"';
}
template<std::size_t N> void packets(const std::array<std::optional<stratadrive::remote::OwnerPacket>,N>& values,std::ostream& out=std::cout) {
    out<<'[';for(std::size_t i=0;i<N;++i){if(i)out<<',';packet(values[i],out);}out<<']';
}
}
int main(int argc,char** argv) {
    std::unique_ptr<WallExecutionWatch> wall_watch;
    std::string wall_path,response_path;
    try {
        if((argc<6 || argc>12 || argc%2!=0) || (std::string(argv[1])!="--wheel-shadow" && std::string(argv[1])!="--external-wheel-plant" && std::string(argv[1])!="--native-actual-export" && std::string(argv[1])!="--native-solver-work"))
            throw std::runtime_error("requires --wheel-shadow or --external-wheel-plant run application plant actor; no general driving acceptance");
        const auto run=std::stoull(argv[2]),app=std::stoull(argv[3]),plant=std::stoull(argv[4]),actor=std::stoull(argv[5]);
        if(!actor || actor>UINT32_MAX || app>UINT32_MAX || plant>UINT32_MAX)throw std::runtime_error("identity range");
        const bool solver_work=std::string(argv[1])=="--native-solver-work";
        const bool exporting=std::string(argv[1])=="--native-actual-export" || solver_work;
        const bool external=std::string(argv[1])=="--external-wheel-plant" || exporting;
        FunctionalRig rig({run,static_cast<std::uint32_t>(app),static_cast<std::uint32_t>(plant)},static_cast<std::uint32_t>(actor),
            solver_work?PlantMode::ExternalSolverWork:(external?PlantMode::ExternalWheelZoh:PlantMode::StationaryFixture),exporting);
        bool scenario_loaded=false;
        for(int arg=6;arg<argc;arg+=2) {
            if(!solver_work)throw std::runtime_error("options require solver-work mode");
            if(std::string(argv[arg])=="--wall-response") {
                if(!response_path.empty())throw std::runtime_error("duplicate wall response");
                response_path=argv[arg+1];continue;
            }
            if(std::string(argv[arg])=="--wall-watch") {
                if(!wall_path.empty())throw std::runtime_error("duplicate wall watch");
                wall_path=argv[arg+1];continue;
            }
            if(std::string(argv[arg])!="--scenario" || scenario_loaded)throw std::runtime_error("invalid/duplicate scenario");
            scenario_loaded=true;
            std::ifstream file(argv[arg+1]);if(!file)throw std::runtime_error("scenario open");
            std::vector<RequestPhase> phases;std::string row;
            while(std::getline(file,row)) {
                if(row.empty() || row[0]=='#')continue;
                RequestPhase phase{};unsigned hold;std::string extra;std::istringstream input(row);
                if(!(input>>phase.end_ms>>phase.acceleration>>phase.curvature>>phase.braking>>hold) || hold>1 || (input>>extra))
                    throw std::runtime_error("invalid scenario row");
                phase.hold=hold!=0;phases.push_back(phase);
            }
            rig.request_profile(std::move(phases));
        }
        if(!response_path.empty() && wall_path.empty())throw std::runtime_error("wall response requires wall watch");
        std::cout<<std::setprecision(17);
        std::string line;
        std::unique_ptr<stratadrive::m7_native::Admission> admission;
        std::optional<stratadrive::m7_external::SolverWork> work;
        std::optional<WheelSample> previous_wheel;
        stratadrive::m7_native::Output previous_admission;
        Input lines;
        const auto stop_if_fault=[&] {
            if(wall_watch && wall_watch->faulted()) {
                BarrierStop selected{};
                Time selected_wall=0;
                const auto emit_stop=[&] {
                std::cout<<"{\"status\":\"WALL_GUARD_STOP\",\"next_frame\":null,\"normal\":"<<(selected.normal?"true":"false")
                    <<",\"credit_mask\":"<<selected.credit_mask<<",\"selected_mask\":"<<selected.selected_mask
                    <<",\"logical_barrier_ns\":"<<selected.logical_ns<<",\"wall_selected_ns\":"<<selected_wall
                    <<",\"actual_exported\":false,\"physical_braking_accepted\":false}"<<std::endl;
                };
                if(response_path.empty()) {
                    selected=rig.stop_at_barrier();selected_wall=WallExecutionWatch::now();
                } else {
                    // Bounded terminal probe, no input/read or synchronous trace
                    // writes on this service path. Never sends these branch-local
                    // timestamps to CARLA or requests another physics tick.
                    struct Record {Time wall;Report report;};
                    std::vector<Record> records;records.reserve(1024);
                    const auto anchor=WallExecutionWatch::now();
                    rig.begin_terminal_response(anchor);
                    auto wake=anchor+ms;
                    do {
                        stratadrive::simulation::runtime_support::sleep_until(wake);
                        const auto now=WallExecutionWatch::now();
                        auto r=rig.service_terminal_response(now);
                        if(records.empty()) {
                            selected_wall=WallExecutionWatch::now();
                            selected={r.now-(now-anchor),r.native_export->protection_selected_mask,r.credit_mask,r.armed};
                            emit_stop(); // Let adapter contain immediately, before the probe completes.
                        }
                        records.push_back({now,std::move(r)});
                        const auto finished=WallExecutionWatch::now();
                        wake=anchor+((finished-anchor)/ms+1)*ms;
                    } while(WallExecutionWatch::now()-anchor<300*ms && records.size()<1024);
                    std::ofstream trace(response_path);trace<<std::setprecision(17);
                    for(const auto& v:records) {
                        const auto& r=v.report;const auto& e=*r.native_export;
                        trace<<"{\"clock\":\"LOCAL_TERMINAL_RESPONSE_NOT_CARLA\",\"wall_ns\":"<<v.wall
                            <<",\"wall_anchor_ns\":"<<anchor<<",\"barrier_ns\":"<<selected.logical_ns
                            <<",\"local_ns\":"<<r.now<<",\"next_frame\":null,\"normal\":false,\"credit_mask\":"<<r.credit_mask
                            <<",\"service_mask\":"<<r.service_mask<<",\"selected_mask\":"<<e.protection_selected_mask
                            <<",\"selection_ns\":"<<e.protection_since<<",\"controller_releases\":"<<r.controller_releases
                            <<",\"energy_end_ns\":"<<r.electrical->end<<",\"mechanical_j\":"<<r.electrical->total_mechanical_j
                            <<",\"soc\":"<<r.electrical->soc<<",\"wheel_source_ns\":"<<r.sensor_wheel->source
                            <<",\"actual\":";packets(e.actual,trace);trace<<"}\n";
                    }
                    if(!trace)throw std::runtime_error("terminal response trace write");
                }
                wall_watch->write(wall_path);
                if(response_path.empty())emit_stop();
                return true;
            }
            return false;
        };
        for(;;) {
            if(stop_if_fault())return 2;
            const auto read=lines.read(line);
            if(stop_if_fault())return 2;
            if(read==Input::Result::End)break;
            if(read==Input::Result::Wait)continue;
            if(line=="WALL_ARM") {
                if(wall_path.empty() || wall_watch || work || !previous_admission.normal)
                    throw std::runtime_error("wall arm requires settled normal barrier and opt-in output");
                // Declared diagnostic window; preceding INIT is NOT monitored.
                wall_watch=std::make_unique<WallExecutionWatch>(WallExecutionWatch::now()+100000000);
                rig.execution_watch(wall_watch.get());
                std::cout<<"{\"status\":\"WALL_GUARD_ARMED\",\"first_release_ns\":"<<wall_watch->first_release()
                    <<",\"period_ns\":2000000,\"deadline_ns\":4000000}"<<std::endl;
                continue;
            }
            if(line=="PROTECT") {
                if(!solver_work || !previous_admission.normal)throw std::runtime_error("protection request context");
                rig.request_protection();continue;
            }
            if(line.size()>(solver_work?20000U:1024U))throw std::runtime_error("input size");
            if(line.rfind("WORK ",0)==0) {
                if(!solver_work || work || !previous_wheel || !admission)throw std::runtime_error("unexpected work");
                stratadrive::m7_external::SolverWork v;unsigned sleeping=0,count=0;
                std::string op,extra;std::istringstream input(line);
                if(!(input>>op>>v.frame>>v.begin>>v.end>>v.dt>>sleeping>>count) || sleeping>1 ||
                   count!=(sleeping?0U:320U))throw std::runtime_error("work header");
                v.sleeping=sleeping!=0;
                for(unsigned k=0;k<count;++k)if(!(input>>v.rear_mean[k]))throw std::runtime_error("missing work substep");
                if(input>>extra)throw std::runtime_error("extra work substep");
                v.torque=double(float((previous_admission.torque*.5)*10000))*2/10000;
                v.oldest=previous_admission.empty?v.begin:previous_admission.oldest_actuator;
                const auto& w=*previous_wheel;
                v.wheel={(w.omega[2]+w.omega[3])/2,{7,static_cast<std::uint32_t>(w.frame),w.source},w.source};
                if(v.frame!=w.frame+1 || v.begin!=w.source || !v.valid())throw std::runtime_error("invalid work binding/value");
                work=v;continue;
            }
            Observation o{};WheelSample w{};std::string op,extra;std::istringstream in(line);
            if(!(in>>op>>o.scope.run>>o.scope.application>>o.scope.plant>>o.clock>>o.frame>>o.elapsed_s>>o.delta_s
                 >>w.actor>>w.frame>>w.source>>w.omega[0]>>w.omega[1]>>w.omega[2]>>w.omega[3]) ||
               op!="WHEEL" || (in>>extra))throw std::runtime_error("invalid WHEEL");
            if(solver_work && previous_wheel && !work)throw std::runtime_error("missing solver work receipt");
            const auto r=work?rig.observe(o,w,*work):rig.observe(o,w);
            if(stop_if_fault())return 2;
            const bool settled=bool(work);
            work.reset();previous_wheel=w;
            bool admission_good=true;
            std::cout<<"{\"status\":\"WHEEL_SHADOW_BARRIER\",\"driving\":false,\"normal_apply\":\""
                <<(exporting?"REQUIRES_SERVER_ADMISSION":"BLOCKED_CALIBRATION_AND_PLANT_OWNERSHIP")<<"\""
                <<",\"now_ns\":"<<r.now<<",\"next_frame\":"<<r.next_frame<<",\"armed_fixture\":"<<(r.armed?"true":"false")
                <<",\"release_mask\":"<<r.release_mask<<",\"credit_mask\":"<<r.credit_mask<<",\"service_mask\":"<<r.service_mask
                <<",\"sensor_wheel\":";audit(r.sensor_wheel);
            std::cout<<",\"returned_wheel\":";audit(r.returned_wheel);
            std::cout<<",\"fixture_torque_nm\":";
            if(r.returned_torque)std::cout<<*r.returned_torque;else std::cout<<"null";
            std::cout<<",\"regen_oldest_ns\":";
            if(r.regen_oldest)std::cout<<*r.regen_oldest;else std::cout<<"null";
            if(r.native_export) {
                const auto& e=*r.native_export;
                std::cout<<",\"native_export\":{\"observed_ns\":\""<<e.observed<<"\",\"enable_ns\":\""<<e.enable
                    <<"\",\"normal\":"<<(e.normal?"true":"false")<<",\"actual\":";packets(e.actual);
                std::cout<<",\"commands\":";packets(e.commands);
                std::cout<<",\"release\":";packets(e.release);
                std::cout<<",\"credit\":";packets(e.credit);
                std::cout<<",\"permission\":";packet(e.permission);
                std::cout<<",\"protection_since_ns\":\""<<e.protection_since<<"\",\"protection_selected_mask\":"<<e.protection_selected_mask<<'}';
                if(!admission)admission=std::make_unique<stratadrive::m7_native::Admission>(static_cast<std::uint32_t>(app),r.now);
                stratadrive::m7_native::Input input;
                input.observed=e.observed;input.enable=e.enable;input.normal=e.normal;
                input.protection_since=e.protection_since;input.protection_selected_mask=e.protection_selected_mask;
                input.actual=e.actual;input.commands=e.commands;input.release=e.release;input.credit=e.credit;input.permission=e.permission;
                input.service_mask=r.service_mask;input.credit_mask=r.credit_mask;input.release_mask=r.release_mask;
                stratadrive::m7_native::Output out;
                const bool good=admission->accept(input,r.now,out);
                admission_good=good;
                previous_admission=out;
                std::cout<<",\"admission\":{\"ok\":"<<(good?"true":"false")<<",\"reason\":\""<<admission->error()
                    <<"\",\"empty\":"<<(out.empty?"true":"false")<<",\"normal\":"<<(out.normal?"true":"false")
                    <<",\"protection\":"<<(out.protection?"true":"false")<<",\"angle_rad\":"<<out.angle<<",\"torque_nm\":"<<out.torque<<",\"pressure_pa\":"<<out.pressure
                    <<",\"oldest_actuator_ns\":\""<<out.oldest_actuator<<"\",\"oldest_dependency_ns\":\""<<out.oldest_dependency
                    <<"\",\"exclusive_expiry_ns\":\""<<out.exclusive_expiry<<"\"}";
            }
            if(external) {
                std::cout<<",\"energy_basis\":\""<<(solver_work?"OBSERVED_SOLVER_WORK_SINGLE_EV":(exporting?"MODEL_ZOH_PREDICTION_NOT_CARLA_WORK":"MODEL_ZOH_UNAPPLIED"))
                    <<"\",\"carla_work_valid\":"<<(settled?"true":"false")<<",\"electrical_steps\":[";
                for(unsigned j=0;j<r.electrical_count;++j) {
                    const auto& e=r.electrical_steps[j];if(j)std::cout<<',';
                    std::cout<<"{\"begin_ns\":"<<e.begin<<",\"end_ns\":"<<e.end<<",\"wheel_source_ns\":"<<e.wheel_source
                        <<",\"wheel_oldest_ns\":"<<e.wheel_oldest<<",\"wheel_rad_s\":"<<e.wheel_rad_s
                        <<",\"actual_torque_nm\":"<<e.torque_nm<<",\"mechanical_j\":"<<e.mechanical_j
                        <<",\"total_mechanical_j\":"<<e.total_mechanical_j<<",\"soc\":"<<e.soc<<",\"balance_j\":"<<e.balance_j<<'}';
                }
                std::cout<<']';
                if(solver_work && settled && r.electrical)std::cout<<",\"settlement\":{\"frame\":"<<o.frame
                    <<",\"end_ns\":"<<r.now<<",\"total_mechanical_j\":"<<r.electrical->total_mechanical_j
                    <<",\"soc\":"<<r.electrical->soc<<",\"balance_j\":"<<r.electrical->balance_j
                    <<",\"motor_loss_j\":"<<r.electrical->motor_loss_j<<",\"auxiliary_j\":"<<r.electrical->auxiliary_j
                    <<",\"ohmic_j\":"<<r.electrical->ohmic_j<<",\"capacitor_delta_j\":"<<r.electrical->capacitor_delta_j
                    <<",\"circuit_loss_j\":"<<r.electrical->circuit_loss_j<<",\"chemical_j\":"<<r.electrical->chemical_j<<'}';
            }
            std::cout<<"}"<<std::endl;
            if(!admission_good) {if(wall_watch)wall_watch->write(wall_path);return 1;}
        }
        if(wall_watch)wall_watch->write(wall_path);
        return 0;
    } catch(const std::exception& e) {
        if(wall_watch) {
            try {wall_watch->write(wall_path);}catch(const std::exception& failure) {std::cerr<<failure.what()<<'\n';}
        }
        std::cerr<<e.what()<<'\n';
        std::cout<<"{\"status\":\"FAIL\",\"driving\":false,\"next_frame\":null}"<<std::endl;
        return 1;
    }
}
