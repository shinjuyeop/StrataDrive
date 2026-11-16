#pragma once
#include <array>
#include <cstdint>
#include <time.h>
#include "owner_wait_profile.hpp"

namespace stratadrive::m7_native {
// Diagnostic clocks only. Never substitute these for source/expiry timestamps.
struct PathStamp { std::uint64_t wall=0, cpu=0; };
inline std::uint64_t path_clock(clockid_t clock) noexcept {
    timespec value{};
    return clock_gettime(clock,&value)==0 ? std::uint64_t(value.tv_sec)*1000000000+
           std::uint64_t(value.tv_nsec) : 0;
}
inline PathStamp path_stamp() noexcept {
    return {path_clock(CLOCK_MONOTONIC),path_clock(CLOCK_THREAD_CPUTIME_ID)};
}
enum class OwnerPhase : unsigned {
    Admitted, Staged, BeforeTick, AfterTick, AcquiredBegin, AcquiredEnd,
    WorkBegin, WorkEnd, PublishBegin, PublishEnd, Complete, Count
};
struct OwnerPath {
    std::array<PathStamp,static_cast<unsigned>(OwnerPhase::Count)> phases{};
    std::array<OwnerStamp,static_cast<unsigned>(OwnerPhase::Count)> scheduling{};
    OwnerWait wait{};
    std::uint64_t max_pump_gap=0,max_rpc=0,proof_observed=0,admission_attempts=0;
    void mark(OwnerPhase phase) noexcept {
        const auto stamp=owner_stamp();const auto index=static_cast<unsigned>(phase);
        phases[index]={stamp.wall,stamp.cpu};scheduling[index]=stamp;
    }
    void acquisition(OwnerPhase phase,std::uint64_t original_wall) noexcept {
        const auto stamp=owner_stamp();const auto index=static_cast<unsigned>(phase);
        phases[index]={original_wall,stamp.cpu};scheduling[index]=stamp;
    }
};
struct NativePath {
    std::uint64_t wake=0,read_begin=0,read_end=0,frame=0,acquired_begin=0;
    std::uint64_t service_begin=0,service_end=0,published=0,cpu_begin=0,cpu_end=0;
};
} // namespace stratadrive::m7_native
