#include "state_path_profile.hpp"
#include <algorithm>
#include <cassert>
#include <iostream>
#include <vector>
using namespace stratadrive::m7_native;
int main(){
 std::vector<std::uint64_t> samples;samples.reserve(10000);
 std::uint64_t sum=0;
 for(unsigned i=0;i<10100;++i){
  const auto begin=path_clock(CLOCK_MONOTONIC);const auto stamp=owner_stamp();
  const auto end=path_clock(CLOCK_MONOTONIC);assert(stamp.valid);
  if(i>=100){samples.push_back(end-begin);sum+=end-begin;}
 }
 std::sort(samples.begin(),samples.end());
 std::cout<<"{\"samples\":10000,\"median_ns\":"<<samples[5000]<<",\"p95_ns\":"<<samples[9500]
 <<",\"maximum_ns\":"<<samples.back()<<",\"mean_ns\":"<<sum/10000
 <<",\"owner_path_bytes\":"<<sizeof(OwnerPath)<<",\"native_path_bytes\":"<<sizeof(NativePath)<<"}\n";
 assert(samples[9500]<5000);
}
