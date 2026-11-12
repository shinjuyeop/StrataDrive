// Cross-language process fixture, logical timestamps; no CARLA/vehicle claim.
#include "perception_2k_ipc.hpp"
#include <iostream>
#include <string>
using namespace stratadrive::central;
int main(int argc,char** argv) {
    try {
        if(argc!=2)return 2;
        PerceptionIpcShadow shadow(std::stoi(argv[1]),42,77,88);
        std::string command;std::uint64_t now;
        while(std::cin>>command>>now) {
            if(command=="INIT") {std::cout<<shadow.observe_native_init(42,now)<<std::endl;continue;}
            if(command!="POLL")return 2;
            const auto v=shadow.poll(now);
            std::cout<<"{\"initialized\":"<<v.initialized<<",\"available\":"<<v.available
              <<",\"frame\":"<<v.frame<<",\"source\":"<<v.source_ns<<",\"receipt\":"<<v.received_wall_ns
              <<",\"expiry\":"<<v.expires_ns<<",\"wall_expiry\":"<<v.wall_expires_ns
              <<",\"received\":"<<v.received<<",\"accepted\":"<<v.accepted_results<<",\"rejected\":"<<v.rejected
              <<",\"tracks\":"<<v.tracks<<",\"disconnected\":"<<v.disconnected<<'}'<<std::endl;
        }
    } catch(const std::exception& error) {std::cerr<<error.what()<<'\n';return 1;}
}
