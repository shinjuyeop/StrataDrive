#include "wall_rig.hpp"
#include "native_admission.hpp"
#include <iostream>
#include <map>
using namespace stratadrive;
using namespace m7_functional;
int main(){
 const Time start=1000000000000ULL, model=1000000000ULL;
 for(unsigned phase=14;phase<15;++phase){
  WallRig rig({1,42,7},99,start,model,5*ms);
  m7_native::Admission gate(42,start,m7_native::ClockPolicy::HostMonotonic,5*ms);
  std::optional<WallReceipt> pending;Time due=start+5*ms;unsigned frames=0,normal=0;std::map<std::string,unsigned> waits;std::string fail;
  for(unsigned i=1;i<=4000;++i){
   const auto now=start+i*ms+50000+(i*7919U)%20000;
   auto r=rig.service(now,pending);pending.reset();
   if(r.failed){fail=r.reason;break;}
   if(now<due)continue;
   const auto& n=r.native;const auto& e=*n.native_export;
   m7_native::Input in;in.observed=e.observed;in.enable=e.enable;in.normal=e.normal;in.protection_since=e.protection_since;
   in.protection_selected_mask=e.protection_selected_mask;in.service_mask=n.service_mask;in.credit_mask=n.credit_mask;in.release_mask=n.release_mask;
   in.actual=e.actual;in.commands=e.commands;in.release=e.release;in.credit=e.credit;in.permission=e.permission;
   m7_native::Output out;std::string why;
   if(!gate.eligible(in,now,out,&why,4000000)){++waits[why];continue;}
   if(!gate.accept(in,now,out)){fail=gate.error();break;}
   ++frames;normal+=out.normal;due=now+5*ms;
   m7_external::CarlaWork c;auto& w=c.work;
   w.frame=100+frames;w.begin=model+(frames-1)*5*ms;w.end=w.begin+5*ms;w.oldest=w.begin;
   w.dt=double(.005f*(1.f/320.f));w.wheel={0,{7,99+frames,w.begin},w.begin};w.torque=out.torque;
   c.applied=now;c.acquired_begin=now+500000;c.acquired_end=c.acquired_begin+1000;c.oldest=out.oldest_actuator?out.oldest_actuator:now;
   c.coils=n.coils;c.coil_source=n.coil_source;
   pending=WallReceipt{{99,w.frame,c.acquired_begin,{0,0,0,0}},w,wall_domain,c};
  }
  std::cout<<phase<<" frames="<<frames<<" normal="<<normal<<" fail="<<fail;
  for(auto& w:waits)std::cout<<" "<<w.first<<"="<<w.second;
  std::cout<<std::endl;
 }
}
