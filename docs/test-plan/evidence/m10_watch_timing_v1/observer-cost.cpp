#include "watch_timing.hpp"
#include "runtime_support.hpp"
#include <algorithm>
#include <iostream>
#include <vector>
using namespace stratadrive::m7_functional;
using stratadrive::simulation::runtime_support::now_ns;
int main() {
    std::vector<std::uint64_t> costs;costs.reserve(20000);unsigned errors=0;
    for(unsigned i=0;i<20000;++i) {
        const auto begin=now_ns();WatchTimingRow row;
        row.sleep_cpu=sched_getcpu();row.sleep_begin=now_ns();row.wake=now_ns();
        row.begin=WatchThreadStamp::capture();row.job_end=now_ns();row.poll_end=now_ns();
        row.end=WatchThreadStamp::capture();row.grid_now=now_ns();
        errors+=row.begin.error+row.end.error;costs.push_back(now_ns()-begin);
    }
    std::sort(costs.begin(),costs.end());
    std::cout<<"{\"scope\":\"quiet diagnostic stamps only; no control body or live overhead guarantee\",\"samples\":20000,\"errors\":"<<errors
        <<",\"median_ns\":"<<costs[10000]<<",\"p95_ns\":"<<costs[18999]<<",\"maximum_ns\":"<<costs.back()<<"}\n";
    return errors || costs[18999]>=20000;
}
