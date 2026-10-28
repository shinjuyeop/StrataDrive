// Deterministic scheduling study, synthetic stationary wheel; NEVER CARLA evidence.
#include "functional_rig.hpp"
#include "native_admission.hpp"
#include <iostream>
#include <algorithm>
#include <limits>
namespace native=stratadrive::m7_native;
using namespace stratadrive::m7_functional;
int main() {
    constexpr Scope scope{1,42,7};
    std::cout<<"{\"scope\":\"synthetic wheel phase feasibility; NOT CARLA or wall acceptance\",\"cases\":[";
    bool comma=false;
    for(unsigned phase=0;phase<=20;++phase)for(bool fractional:{false,true}) {
        if(comma)std::cout<<',';
        comma=true;
        Time margin=std::numeric_limits<Time>::max();unsigned normal=0,index=0;
        std::string error;bool accepted=true;
        std::array<Time,3> command_age{},parent_age{},dependency_age{},expiry_margin{};
        try {
            FunctionalRig rig(scope,99,PlantMode::ExternalWheelZoh,true);rig.controller_phase(phase*ms);
            std::unique_ptr<native::Admission> gate;
            for(;index<400;++index) {
                const double seconds=fractional?3.997146773152053+index*.009999999776482582:1+index*.01;
                const auto now=static_cast<Time>(std::llround(seconds*1e9));
                const auto r=rig.observe({scope,domain,100+index,seconds,.01},{99,100+index,now,{0,0,0,0}});
                if(!gate)gate=std::make_unique<native::Admission>(42,now);
                const auto& e=*r.native_export;native::Input input;
                input.observed=e.observed;input.enable=e.enable;input.normal=e.normal;
                input.actual=e.actual;input.commands=e.commands;input.release=e.release;input.credit=e.credit;input.permission=e.permission;
                input.service_mask=r.service_mask;input.credit_mask=r.credit_mask;input.release_mask=r.release_mask;
                native::Output out;
                if(!gate->accept(input,now,out)) {accepted=false;error=gate->error();break;}
                if(out.normal) {
                    ++normal;const auto current=out.exclusive_expiry-now-native::step;
                    if(current<margin) {
                        margin=current;
                        for(unsigned j=0;j<3;++j) {
                            const auto decoded=stratadrive::remote::decode_owner_message(e.commands[j]->bytes.data(),e.commands[j]->size);
                            const auto& q=std::get<stratadrive::transport::LeafRequest>(decoded->payload);
                            const auto& c=*q.command;
                            command_age[j]=now+native::step-c.parent.source_time_ns;
                            parent_age[j]=c.parent.expires_at_ns-(now+native::step);
                            dependency_age[j]=now+native::step-c.oldest_input_time_ns;
                            expiry_margin[j]=c.expires_at_ns-(now+native::step);
                        }
                    }
                }
            }
        } catch(const std::exception& failure) {accepted=false;error=failure.what();}
        std::cout<<"{\"phase_ms\":"<<phase<<",\"fractional\":"<<(fractional?"true":"false")
            <<",\"accepted\":"<<(accepted?"true":"false")<<",\"normal_intervals\":"<<normal
            <<",\"intervals\":"<<index<<",\"min_expiry_margin_ns\":"<<(normal?margin:0)<<",\"error\":\""<<error<<"\",\"limiting_example\":[";
        for(unsigned j=0;j<3;++j) {
            if(j)std::cout<<',';
            std::cout<<"{\"role\":"<<j<<",\"parent_age_at_end_ns\":"<<command_age[j]
                <<",\"parent_expiry_margin_ns\":"<<parent_age[j]<<",\"oldest_age_at_end_ns\":"<<dependency_age[j]
                <<",\"command_expiry_margin_ns\":"<<expiry_margin[j]<<'}';
        }
        std::cout<<"]}";
    }
    std::cout<<"]}\n";
}
