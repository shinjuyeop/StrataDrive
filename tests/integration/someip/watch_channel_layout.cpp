// Offline Host ABI verification for saved observation bytes; no SDK/runtime work.
#include "native_execution_watch.hpp"
#include <iostream>
#include <cstddef>
using S=stratadrive::simulation::NativeWatchShared;
static_assert(sizeof(std::atomic<std::uint64_t>)==8);
static_assert(sizeof(std::atomic<std::uint32_t>)==4);
static_assert(offsetof(S,finished)==56 && offsetof(S,detected)==80056);
static_assert(sizeof(S)==160056);
int main(){std::cout<<"{\"size\":"<<sizeof(S)<<",\"finished_offset\":"<<offsetof(S,finished)<<",\"detected_offset\":"<<offsetof(S,detected)<<"}\n";}
