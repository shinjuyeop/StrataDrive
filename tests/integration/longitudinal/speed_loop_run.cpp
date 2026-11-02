#include "m4_async_runtime.hpp"
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
using namespace stratadrive::simulation;
int main(int argc,char* const argv[]) {
    try {
        if(argc!=3) throw std::invalid_argument("usage: speed_loop_run nominal|feedback-loss|command-loss NEW_DIRECTORY");
        const std::string mode=argv[1]; const std::filesystem::path directory=argv[2];
        M4Config c; c.speed_loop=true; c.renewal=stratadrive::central::CommandRenewal::Host10ms;
        c.duration_ns=92000000000ULL; c.injection_ns=25000000000ULL;
        if(mode=="feedback-loss") c.scenario=M4Scenario::FeedbackLoss;
        else if(mode=="command-loss") c.scenario=M4Scenario::CommandLoss;
        else if(mode!="nominal") throw std::invalid_argument("unknown mode");
        if(mode!="nominal") c.duration_ns=28000000000ULL;
        if(std::filesystem::exists(directory)) throw std::invalid_argument("output exists");
        std::filesystem::create_directories(directory);
        { std::ofstream plan(directory/"config.json"); plan<<"{\"mode\":"<<std::quoted(mode)<<",\"clock\":\"logical\",\"duration_ns\":"<<c.duration_ns<<",\"injection_ns\":"<<c.injection_ns<<",\"controller_period_ns\":20000000,\"allocation_period_ns\":10000000}\n"; }
        const auto r=run_m4_async(c);
        write_m4_result(c,r,directory.string());
        std::ofstream control(directory/"control.csv"); control<<std::setprecision(17)<<"now_ns,profile_ns,speed_source_ns,request_expiry_ns,epoch,sequence,target_mps,speed_mps,acceleration_mps2,integral\n";
        for(const auto& v:r.speed_trace) control<<v.now_ns<<','<<v.profile_ns<<','<<v.speed_source_ns<<','<<v.request_expiry_ns<<','<<v.epoch<<','<<v.sequence<<','<<v.target_mps<<','<<v.speed_mps<<','<<v.acceleration_mps2<<','<<v.integral<<'\n';
        std::ofstream physical(directory/"physical.csv"); physical<<std::setprecision(17)<<"now_ns,speed_mps,distance_m,torque_nm,pressure_pa,bus_v,balance_j,model_epoch,model_sequence,contacts,command_source_ns,command_root_sequence,run_gate\n";
        for(const auto& v:r.trace) physical<<v.source_ns<<','<<v.speed_mps<<','<<v.distance_m<<','<<v.torque_nm<<','<<v.pressure_pa<<','<<v.bus_v<<','<<v.vehicle_balance_j<<','<<v.model_epoch<<','<<v.model_sequence<<','<<v.contacts<<','<<v.command_source_ns<<','<<v.command_root_sequence<<','<<v.run_gate<<'\n';
        std::ofstream result(directory/"runtime.json"); result<<std::boolalpha<<"{\"passed\":"<<r.passed<<",\"speed_origin_ns\":"<<r.speed_origin_ns<<",\"speed_fault\":"<<r.speed_fault<<",\"reason\":"<<std::quoted(r.reason)<<"}\n";
        std::cout<<mode<<": "<<(r.passed?"PASS":"FAIL")<<" controls="<<r.speed_trace.size()<<" speed_fault="<<r.speed_fault<<' '<<r.reason<<'\n';
        return r.passed?0:1;
    } catch(const std::exception& e) { std::cerr<<e.what()<<'\n'; return 2; }
}
