#include "functional_rig.hpp"
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
using namespace stratadrive::m7_functional;
namespace {
void audit(const std::optional<WheelAudit>& w) {
    if(w)std::cout<<"{\"source_ns\":"<<w->source<<",\"rad_s\":"<<w->rad_s<<'}';
    else std::cout<<"null";
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=6 || (std::string(argv[1])!="--wheel-shadow" && std::string(argv[1])!="--external-wheel-plant"))
            throw std::runtime_error("requires --wheel-shadow or --external-wheel-plant run application plant actor; no driving mode");
        const auto run=std::stoull(argv[2]),app=std::stoull(argv[3]),plant=std::stoull(argv[4]),actor=std::stoull(argv[5]);
        if(!actor || actor>UINT32_MAX || app>UINT32_MAX || plant>UINT32_MAX)throw std::runtime_error("identity range");
        const bool external=std::string(argv[1])=="--external-wheel-plant";
        FunctionalRig rig({run,static_cast<std::uint32_t>(app),static_cast<std::uint32_t>(plant)},static_cast<std::uint32_t>(actor),
            external?PlantMode::ExternalWheelZoh:PlantMode::StationaryFixture);
        std::cout<<std::setprecision(17);
        std::string line;
        while(std::getline(std::cin,line)) {
            if(line.size()>1024)throw std::runtime_error("input size");
            Observation o{};WheelSample w{};std::string op,extra;std::istringstream in(line);
            if(!(in>>op>>o.scope.run>>o.scope.application>>o.scope.plant>>o.clock>>o.frame>>o.elapsed_s>>o.delta_s
                 >>w.actor>>w.frame>>w.source>>w.omega[0]>>w.omega[1]>>w.omega[2]>>w.omega[3]) ||
               op!="WHEEL" || (in>>extra))throw std::runtime_error("invalid WHEEL");
            const auto r=rig.observe(o,w);
            std::cout<<"{\"status\":\"WHEEL_SHADOW_BARRIER\",\"driving\":false,\"normal_apply\":\"BLOCKED_CALIBRATION_AND_PLANT_OWNERSHIP\""
                <<",\"now_ns\":"<<r.now<<",\"next_frame\":"<<r.next_frame<<",\"armed_fixture\":"<<(r.armed?"true":"false")
                <<",\"release_mask\":"<<r.release_mask<<",\"credit_mask\":"<<r.credit_mask<<",\"service_mask\":"<<r.service_mask
                <<",\"sensor_wheel\":";audit(r.sensor_wheel);
            std::cout<<",\"returned_wheel\":";audit(r.returned_wheel);
            std::cout<<",\"fixture_torque_nm\":";
            if(r.returned_torque)std::cout<<*r.returned_torque;else std::cout<<"null";
            std::cout<<",\"regen_oldest_ns\":";
            if(r.regen_oldest)std::cout<<*r.regen_oldest;else std::cout<<"null";
            if(external) {
                std::cout<<",\"energy_basis\":\"MODEL_ZOH_UNAPPLIED\",\"carla_work_valid\":false,\"electrical_steps\":[";
                for(unsigned j=0;j<r.electrical_count;++j) {
                    const auto& e=r.electrical_steps[j];if(j)std::cout<<',';
                    std::cout<<"{\"begin_ns\":"<<e.begin<<",\"end_ns\":"<<e.end<<",\"wheel_source_ns\":"<<e.wheel_source
                        <<",\"wheel_oldest_ns\":"<<e.wheel_oldest<<",\"wheel_rad_s\":"<<e.wheel_rad_s
                        <<",\"actual_torque_nm\":"<<e.torque_nm<<",\"mechanical_j\":"<<e.mechanical_j
                        <<",\"total_mechanical_j\":"<<e.total_mechanical_j<<",\"soc\":"<<e.soc<<",\"balance_j\":"<<e.balance_j<<'}';
                }
                std::cout<<']';
            }
            std::cout<<"}"<<std::endl;
        }
        return 0;
    } catch(const std::exception& e) {
        std::cerr<<e.what()<<'\n';
        std::cout<<"{\"status\":\"FAIL\",\"driving\":false,\"next_frame\":null}"<<std::endl;
        return 1;
    }
}
