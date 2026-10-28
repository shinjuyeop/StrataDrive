#include "functional_rig.hpp"
#include "native_admission.hpp"
#include <iomanip>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
using namespace stratadrive::m7_functional;
namespace {
void audit(const std::optional<WheelAudit>& w) {
    if(w)std::cout<<"{\"source_ns\":"<<w->source<<",\"rad_s\":"<<w->rad_s<<'}';
    else std::cout<<"null";
}
void packet(const std::optional<stratadrive::remote::OwnerPacket>& p) {
    if(!p){std::cout<<"null";return;}
    std::cout<<'"'<<std::hex<<std::setfill('0');
    for(std::size_t i=0;i<p->size;++i)std::cout<<std::setw(2)<<unsigned(p->bytes[i]);
    std::cout<<std::dec<<'"';
}
template<std::size_t N> void packets(const std::array<std::optional<stratadrive::remote::OwnerPacket>,N>& values) {
    std::cout<<'[';for(std::size_t i=0;i<N;++i){if(i)std::cout<<',';packet(values[i]);}std::cout<<']';
}
}
int main(int argc,char** argv) {
    try {
        if((argc!=6 && argc!=8) || (std::string(argv[1])!="--wheel-shadow" && std::string(argv[1])!="--external-wheel-plant" && std::string(argv[1])!="--native-actual-export" && std::string(argv[1])!="--native-solver-work"))
            throw std::runtime_error("requires --wheel-shadow or --external-wheel-plant run application plant actor; no general driving acceptance");
        const auto run=std::stoull(argv[2]),app=std::stoull(argv[3]),plant=std::stoull(argv[4]),actor=std::stoull(argv[5]);
        if(!actor || actor>UINT32_MAX || app>UINT32_MAX || plant>UINT32_MAX)throw std::runtime_error("identity range");
        const bool solver_work=std::string(argv[1])=="--native-solver-work";
        const bool exporting=std::string(argv[1])=="--native-actual-export" || solver_work;
        const bool external=std::string(argv[1])=="--external-wheel-plant" || exporting;
        FunctionalRig rig({run,static_cast<std::uint32_t>(app),static_cast<std::uint32_t>(plant)},static_cast<std::uint32_t>(actor),
            solver_work?PlantMode::ExternalSolverWork:(external?PlantMode::ExternalWheelZoh:PlantMode::StationaryFixture),exporting);
        if(argc==8) {
            if(!solver_work || std::string(argv[6])!="--scenario")throw std::runtime_error("scenario requires solver-work mode");
            std::ifstream file(argv[7]);if(!file)throw std::runtime_error("scenario open");
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
        std::cout<<std::setprecision(17);
        std::string line;
        std::unique_ptr<stratadrive::m7_native::Admission> admission;
        std::optional<stratadrive::m7_external::SolverWork> work;
        std::optional<WheelSample> previous_wheel;
        stratadrive::m7_native::Output previous_admission;
        while(std::getline(std::cin,line)) {
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
            if(!admission_good)return 1;
        }
        return 0;
    } catch(const std::exception& e) {
        std::cerr<<e.what()<<'\n';
        std::cout<<"{\"status\":\"FAIL\",\"driving\":false,\"next_frame\":null}"<<std::endl;
        return 1;
    }
}
