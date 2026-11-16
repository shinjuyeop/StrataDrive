#include "state_path_profile.hpp"
#include <algorithm>
#include <iostream>
#include <vector>
using namespace stratadrive::m7_native;
int main(){
 std::vector<unsigned long long> cpu,wall;cpu.reserve(20000);wall.reserve(20000);
 for(unsigned i=0;i<20000;++i){auto a=path_stamp();OwnerPath p;
  for(unsigned j=0;j<static_cast<unsigned>(OwnerPhase::Count);++j)p.mark(static_cast<OwnerPhase>(j));
  auto b=path_stamp();cpu.push_back(b.cpu-a.cpu);wall.push_back(b.wall-a.wall);
 }
 std::sort(cpu.begin(),cpu.end());std::sort(wall.begin(),wall.end());
 std::cout<<"{\"samples\":20000,\"scope\":\"11 paired diagnostic clocks plus two benchmark stamps; no control body\",\"cpu_median_ns\":"<<cpu[10000]<<",\"cpu_p95_ns\":"<<cpu[18999]<<",\"wall_median_ns\":"<<wall[10000]<<",\"wall_p95_ns\":"<<wall[18999]<<"}\n";
 return cpu[18999]<50000?0:1;
}
