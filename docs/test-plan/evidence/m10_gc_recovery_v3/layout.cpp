#include "gc_profile.hpp"
#include "state_path_profile.hpp"
#include <iostream>
using namespace stratadrive::m7_native;
int main(){std::cout<<"{\"gc_profile_bytes\":"<<sizeof(GcProfile)<<",\"purge_profile_bytes\":"<<sizeof(PurgeProfile)<<",\"owner_path_bytes\":"<<sizeof(OwnerPath)<<",\"capacity\":64}\n";}
