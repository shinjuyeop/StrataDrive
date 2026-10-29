#include "wall_rig.hpp"
#include <iostream>
using namespace stratadrive;using namespace m7_functional;
int main(){
 Time initial,model,now;unsigned actor;std::cin>>initial>>model>>actor;
 WallRig rig({1,42,7},actor,initial,model,5*ms);
 rig.request_profile({{3500,1,.02,0,false},{4500,-.3,0,0,false},{6500,0,0,.5,true},{9500,1,-.02,0,false}});
 unsigned yes;while(std::cin>>now>>yes){std::optional<WallReceipt> receipt;
 if(yes){m7_external::CarlaWork c;auto& w=c.work;unsigned coils;double omega[4];
 std::cin>>w.frame>>w.begin>>w.end>>c.applied>>c.acquired_begin>>c.acquired_end>>c.oldest>>c.coil_source>>coils>>w.torque>>w.wheel.value>>w.dt>>w.sleeping;
 w.dt=double(.005f*(1.f/320.f));w.oldest=w.begin;w.wheel.identity={7,static_cast<std::uint32_t>(w.frame-1),w.begin};w.wheel.input_time_ns=w.begin;
 for(auto& v:omega)std::cin>>v;for(auto& v:w.rear_mean)std::cin>>v;
 c.coils={{bool(coils&1),bool(coils&2),bool(coils&4)},bool(coils&8)};
 receipt=WallReceipt{{actor,w.frame,c.acquired_begin,{omega[0],omega[1],omega[2],omega[3]}},w,wall_domain,c};}
 auto r=rig.service(now,receipt);if(r.failed){std::cout<<"first_failure "<<now-initial<<" "<<r.reason<<std::endl;return 0;}
 }std::cout<<"no failure\n";}
