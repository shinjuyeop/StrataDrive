#include "functional_rig.hpp"
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>

using namespace stratadrive::m7_functional;
int main(int argc,char** argv) {
    try {
        if(argc!=5 || std::string(argv[1])!="--functional-shadow")
            throw std::runtime_error("requires --functional-shadow run application plant; no driving mode");
        const auto run=std::stoull(argv[2]),app=std::stoull(argv[3]),plant=std::stoull(argv[4]);
        if(app>UINT32_MAX || plant>UINT32_MAX)throw std::runtime_error("scope range");
        const Scope scope{run,static_cast<std::uint32_t>(app),static_cast<std::uint32_t>(plant)};
        FunctionalRig rig(scope);
        std::string line;
        while(std::getline(std::cin,line)) {
            if(line.size()>512)throw std::runtime_error("input size");
            Observation o{};std::string operation,extra;std::istringstream input(line);
            if(!(input>>operation>>o.scope.run>>o.scope.application>>o.scope.plant>>o.clock>>o.frame>>o.elapsed_s>>o.delta_s) ||
               operation!="STEP" || (input>>extra))throw std::runtime_error("invalid STEP");
            const auto r=rig.observe(o);
            std::cout<<"{\"status\":\"SHADOW_BARRIER\",\"driving\":false,\"now_ns\":"<<r.now<<",\"next_frame\":"<<r.next_frame
                <<",\"release_mask\":"<<r.release_mask<<",\"credit_mask\":"<<r.credit_mask<<",\"service_mask\":"<<r.service_mask
                <<",\"armed_fixture\":"<<(r.armed?"true":"false")<<",\"actual_interval_fixture\":"<<(r.actual_interval?"true":"false")
                <<",\"lease_source_ns\":"<<r.lease_source<<",\"lease_expiry_ns\":"<<r.lease_expiry<<",\"controller_releases\":"<<r.controller_releases
                <<",\"actual_sources_ns\":["<<r.actual_sources[0]<<','<<r.actual_sources[1]<<','<<r.actual_sources[2]<<"],\"commands\":[";
            for(unsigned i=0;i<5;++i){if(i)std::cout<<',';std::cout<<r.commands[i];}
            std::cout<<"],\"leaf_body_ns\":[";
            for(unsigned i=0;i<5;++i){if(i)std::cout<<',';std::cout<<r.leaf_body[i];}
            std::cout<<"]}"<<std::endl;
        }
        return 0;
    } catch(const std::exception& e) {
        std::cerr<<e.what()<<'\n';
        // Error details remain stderr; stdout is a small unambiguous fatal reply.
        std::cout<<"{\"status\":\"FAIL\",\"driving\":false,\"next_frame\":null}"<<std::endl;return 1;
    }
}
