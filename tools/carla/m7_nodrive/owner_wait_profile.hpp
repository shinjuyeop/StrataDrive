#pragma once
#include <array>
#include <cstdint>
#include <sched.h>
#include <sys/resource.h>
#include <time.h>

namespace stratadrive::m7_native {
// Fixed-size, game-thread-owned diagnostics. No allocation, I/O, authority or
// source timestamp modification. rusage is this thread, not process-wide.
struct OwnerStamp {
    std::uint64_t wall=0,cpu=0,voluntary=0,involuntary=0,minor_faults=0,major_faults=0;
    std::uint64_t processor=0,valid=0;
};
inline OwnerStamp owner_stamp() noexcept {
    timespec wall{},cpu{};rusage usage{};OwnerStamp result;
    const int a=clock_gettime(CLOCK_MONOTONIC,&wall);
    const int b=clock_gettime(CLOCK_THREAD_CPUTIME_ID,&cpu);
    const int c=getrusage(RUSAGE_THREAD,&usage);const int processor=sched_getcpu();
    result.wall=std::uint64_t(wall.tv_sec)*1000000000+wall.tv_nsec;
    result.cpu=std::uint64_t(cpu.tv_sec)*1000000000+cpu.tv_nsec;
    result.voluntary=usage.ru_nvcsw;result.involuntary=usage.ru_nivcsw;
    result.minor_faults=usage.ru_minflt;result.major_faults=usage.ru_majflt;
    result.processor=processor<0?0:processor;result.valid=a==0 && b==0 && c==0 && processor>=0;
    return result;
}
enum class PumpReason : unsigned {
    Unavailable, ProofUnreadable, Settlement, Stopped, Invalid,
    NotDue, Gap, Protection, Ineligible, Staging, Ready, Count
};
struct WaitAggregate {
    std::uint64_t count=0,wall=0,cpu=0,voluntary=0,involuntary=0;
    std::uint64_t minor_faults=0,major_faults=0,errors=0;
    OwnerStamp longest_begin{},longest_end{};
    void add(const OwnerStamp& begin,const OwnerStamp& end) noexcept {
        ++count;
        if(!begin.valid || !end.valid || end.wall<begin.wall || end.cpu<begin.cpu ||
           end.voluntary<begin.voluntary || end.involuntary<begin.involuntary ||
           end.minor_faults<begin.minor_faults || end.major_faults<begin.major_faults) {
            ++errors;return;
        }
        const auto elapsed=end.wall-begin.wall;
        wall+=elapsed;cpu+=end.cpu-begin.cpu;voluntary+=end.voluntary-begin.voluntary;
        involuntary+=end.involuntary-begin.involuntary;
        minor_faults+=end.minor_faults-begin.minor_faults;major_faults+=end.major_faults-begin.major_faults;
        if(!longest_end.valid || elapsed>longest_end.wall-longest_begin.wall) {
            longest_begin=begin;longest_end=end;
        }
    }
};
struct OwnerWait {
    std::array<std::uint64_t,static_cast<unsigned>(PumpReason::Count)> reasons{};
    WaitAggregate active{},idle{},outside{};
    std::uint64_t requested_sleep_ns=0,reason_truncated=0;
    std::array<char,96> last_ineligible{};
    void reason(PumpReason why,const char* detail=nullptr) noexcept {
        ++reasons[static_cast<unsigned>(why)];
        if(why!=PumpReason::Ineligible || !detail)return;
        unsigned i=0;
        for(;i+1<last_ineligible.size() && detail[i];++i)last_ineligible[i]=detail[i];
        last_ineligible[i]=0;if(detail[i])++reason_truncated;
    }
};
} // namespace stratadrive::m7_native
