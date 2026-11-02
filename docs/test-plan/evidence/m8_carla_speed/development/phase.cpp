#include "functional_rig.hpp"
#include "native_admission.hpp"
#include <iostream>
using namespace stratadrive;
using namespace m7_functional;
int main(){constexpr Scope scope{1,42,7};for(unsigned phase=0;phase<=100;++phase)for(bool fractional:{false,true}){std::string error;unsigned at=400;
        FunctionalRig rig(scope,99,PlantMode::ExternalSolverWork,true,60000);rig.speed_profile();rig.controller_phase(phase*200000);
        std::unique_ptr<m7_native::Admission> admission;
        m7_native::Output prior;Time previous=0;unsigned steps=0;
        std::optional<SpeedControlAudit> last;
        
        for(unsigned i=0;i<400;++i) {
            const auto seconds=fractional?3.997146773152053+i*.009999999776482582:1+i*.01;
            const auto now=static_cast<Time>(std::llround(seconds*1e9));
            const Observation o{scope,domain,100+i,seconds,.01};const WheelSample wheel{99,100+i,now,{0,0,0,0}};
            Report r;
            
            try {
                if(!i)r=rig.observe(o,wheel);
                else {
                    m7_external::SolverWork w;
                    w.frame=100+i;w.begin=previous;w.end=now;w.oldest=prior.empty?previous:prior.oldest_actuator;
                    w.torque=prior.torque;w.dt=double(.01f*(1.f/320.f));w.wheel={0,{7,99+i,previous},previous};
                    r=rig.observe(o,wheel,w);
                }
            } catch(const std::runtime_error& e) {
                error=e.what();at=i;break;
            }
            if(!admission)admission=std::make_unique<m7_native::Admission>(42,now);
            const auto& e=*r.native_export;m7_native::Input in;
            in.observed=e.observed;in.enable=e.enable;in.normal=e.normal;
            in.actual=e.actual;in.commands=e.commands;in.release=e.release;in.credit=e.credit;in.permission=e.permission;
            in.service_mask=r.service_mask;in.credit_mask=r.credit_mask;in.release_mask=r.release_mask;
            const bool accepted=admission->accept(in,now,prior);
            if(!accepted){error=admission->error();at=i;break;}
            if(r.speed_control && (!last || last->sequence!=r.speed_control->sequence)) {
                const auto& s=*r.speed_control;
                last=s;++steps;
            }
            previous=now;
        }
std::cout<<phase*.2<<","<<fractional<<","<<at<<","<<steps<<","<<error<<"\n";}}
