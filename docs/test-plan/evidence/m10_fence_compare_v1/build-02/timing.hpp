#pragma once
// Game-thread-only, bounded diagnostic journal. No writes/allocations in record().
// Wall and thread CPU clocks are distinct; only durations within each are used.
#include <array>
#include <cstdint>
#include <cstdio>
#include <ctime>

namespace strata_server_timing {
inline std::uint64_t clock_ns(clockid_t clock) {
    timespec value{};
    if(clock_gettime(clock,&value)!=0)return 0;
    return std::uint64_t(value.tv_sec)*1000000000ULL+std::uint64_t(value.tv_nsec);
}
struct Row {
    const char* stage=nullptr;
    std::uint64_t frame=0,begin=0,end=0,cpu_begin=0,cpu_end=0;
};
template<std::size_t Capacity=8192> class Journal {
public:
    Journal(const char* component,bool enabled):component_(component),enabled_(enabled) {}
    ~Journal() { dump(); }
    bool enabled() const {return enabled_;}
    void record(Row row) {
        if(!enabled_)return;
        if(count_==Capacity){++overflow_;return;}
        rows_[count_++]=row;
    }
    std::size_t size() const {return count_;}
    std::uint64_t overflow() const {return overflow_;}
    const Row& at(std::size_t i) const {return rows_[i];}
    void dump() {
        if(!enabled_ || dumped_)return;
        dumped_=true;
        for(std::size_t i=0;i<count_;++i) {
            const auto& r=rows_[i];
            std::fprintf(stderr,"STRATA_SERVER_TIMING_V1 {\"component\":\"%s\",\"stage\":\"%s\",\"frame\":%llu,\"begin\":%llu,\"end\":%llu,\"cpu_begin\":%llu,\"cpu_end\":%llu}\n",
                component_,r.stage,(unsigned long long)r.frame,(unsigned long long)r.begin,(unsigned long long)r.end,
                (unsigned long long)r.cpu_begin,(unsigned long long)r.cpu_end);
        }
        std::fprintf(stderr,"STRATA_SERVER_TIMING_END_V1 {\"component\":\"%s\",\"rows\":%zu,\"overflow\":%llu}\n",component_,count_,(unsigned long long)overflow_);
    }
private:
    const char* component_;bool enabled_,dumped_=false;
    std::array<Row,Capacity> rows_{};std::size_t count_=0;std::uint64_t overflow_=0;
};
class Scope {
public:
    Scope(Journal<>& journal,const char* stage,std::uint64_t frame):journal_(journal) {
        if(journal_.enabled())row_={stage,frame,clock_ns(CLOCK_MONOTONIC),0,clock_ns(CLOCK_THREAD_CPUTIME_ID),0};
    }
    ~Scope() {
        if(!journal_.enabled())return;
        row_.cpu_end=clock_ns(CLOCK_THREAD_CPUTIME_ID);row_.end=clock_ns(CLOCK_MONOTONIC);journal_.record(row_);
    }
    Scope(const Scope&)=delete;
    Scope& operator=(const Scope&)=delete;
private:
    Journal<>& journal_;Row row_{};
};
} // namespace strata_server_timing
