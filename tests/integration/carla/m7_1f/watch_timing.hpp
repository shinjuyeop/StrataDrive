#pragma once
#include <cstdint>
#include <sched.h>
#include <sys/resource.h>
#include <time.h>

namespace stratadrive::m7_functional {
// Thread-local diagnostic observations; never a source/expiry or scheduling input.
struct WatchThreadStamp {
    std::uint64_t cpu_ns{0};
    std::int64_t voluntary{0},involuntary{0},minor_faults{0};
    int cpu{-1},error{0};
    static WatchThreadStamp capture() noexcept {
        WatchThreadStamp result;timespec cpu{};rusage usage{};
        const int clock_error=clock_gettime(CLOCK_THREAD_CPUTIME_ID,&cpu);
        const int usage_error=getrusage(RUSAGE_THREAD,&usage);
        result.cpu_ns=static_cast<std::uint64_t>(cpu.tv_sec)*1000000000ULL+static_cast<std::uint64_t>(cpu.tv_nsec);
        result.cpu=sched_getcpu();result.voluntary=usage.ru_nvcsw;result.involuntary=usage.ru_nivcsw;
        result.minor_faults=usage.ru_minflt;
        result.error=clock_error!=0 || usage_error!=0 || result.cpu<0;
        return result;
    }
};
struct WatchTimingRow {
    std::uint64_t release{0},sleep_begin{0},wake{0},job_end{0},poll_end{0},grid_now{0},next_release{0};
    int sleep_cpu{-1};
    WatchThreadStamp begin,end;
};
} // namespace stratadrive::m7_functional
