// Retained original wall service timestamps and solver receipts, no live claim.
#include "wall_rig.hpp"
#include "wall_startup_trace.hpp"
#include <fstream>
#include <iostream>
#include <sstream>
using namespace stratadrive;
using namespace m7_functional;
int main(int argc,char** argv) {
    try {
        if(argc!=4)throw std::runtime_error("input scenario output-prefix");
        std::ifstream input(argv[1]),scenario(argv[2]);Time initial,model;std::uint32_t actor;
        if(!(input>>initial>>model>>actor))throw std::runtime_error("replay identity");
        WallRig rig({1,42,7},actor,initial,model);
        std::vector<RequestPhase> phases;std::string line;
        while(std::getline(scenario,line)) {
            if(line.empty() || line[0]=='#')continue;
            RequestPhase p{};unsigned hold;std::istringstream s(line);
            if(!(s>>p.end_ms>>p.acceleration>>p.curvature>>p.braking>>hold))throw std::runtime_error("profile");
            p.hold=hold;phases.push_back(p);
        }
        rig.request_profile(phases);
        std::ofstream csv(std::string(argv[3])+".csv");
        csv<<"now,energy_end,wheel_source,protection,armed,hv_source,hv_dependency\n";
        Time now;unsigned present;WallReport r;std::size_t calls=0;
        while(input>>now>>present) {
            if(present>1)throw std::runtime_error("presence");
            std::optional<WallReceipt> receipt;
            if(present) {
                m7_external::CarlaWork c;auto& w=c.work;unsigned sleeping,coils;std::array<double,4> omega;
                if(!(input>>w.frame>>w.begin>>w.end>>c.applied>>c.acquired_begin>>c.acquired_end>>c.oldest>>c.coil_source
                    >>coils>>sleeping>>w.torque>>w.dt>>w.wheel.value))throw std::runtime_error("receipt");
                if(coils>15 || sleeping>1)throw std::runtime_error("receipt flags");
                for(auto& value:omega)if(!(input>>value))throw std::runtime_error("omega");
                for(auto& value:w.rear_mean)if(!(input>>value))throw std::runtime_error("means");
                c.coils={{bool(coils&1),bool(coils&2),bool(coils&4)},bool(coils&8)};
                w.sleeping=sleeping;w.oldest=w.begin;w.wheel.identity={7,static_cast<std::uint32_t>(w.frame-1),w.begin};w.wheel.input_time_ns=w.begin;
                receipt=WallReceipt{{actor,w.frame,c.acquired_begin,omega},w,wall_domain,c};
            }
            r=rig.service(now,receipt);++calls;const auto& n=r.native;
            csv<<now<<','<<(n.electrical?n.electrical->end:0)<<','<<(n.sensor_wheel?n.sensor_wheel->source:0)
               <<','<<r.protected_at<<','<<n.armed<<','<<n.hv_source<<','<<n.hv_dependency<<'\n';
        }
        if(!input.eof())throw std::runtime_error("replay parse");
        std::ofstream out(std::string(argv[3])+".json");
        out<<"{\"calls\":"<<calls<<",\"first_fault\":\""<<r.reason<<"\",\"protected_at\":"<<r.protected_at<<",\"startup\":";
        write_startup_observations(out,rig.startup_observations());out<<"}\n";
        if(!out || !csv)throw std::runtime_error("replay output");
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
