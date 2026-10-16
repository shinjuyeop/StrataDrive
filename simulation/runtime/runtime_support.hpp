#pragma once

#include <cerrno>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <pthread.h>
#include <sched.h>
#include <system_error>
#include <time.h>
#include <vector>

namespace stratadrive::simulation::runtime_support {
inline std::uint64_t now_ns() {
    timespec value{};
    if(clock_gettime(CLOCK_MONOTONIC,&value)!=0) throw std::system_error(errno,std::generic_category(),"clock_gettime");
    return static_cast<std::uint64_t>(value.tv_sec)*1000000000+static_cast<std::uint64_t>(value.tv_nsec);
}
inline void sleep_until(std::uint64_t until) {
    const timespec value{static_cast<time_t>(until/1000000000),static_cast<long>(until%1000000000)};
    int result=0;
    do { result=clock_nanosleep(CLOCK_MONOTONIC,TIMER_ABSTIME,&value,nullptr); } while(result==EINTR);
    if(result!=0) throw std::system_error(result,std::generic_category(),"clock_nanosleep");
}
inline std::uint64_t next_wake(std::uint64_t enable, std::uint64_t period, std::uint64_t now) {
    return enable+((now-enable)/period+1)*period;
}
struct ThreadInfo {
    int policy{-1},priority{-1},observed_cpu{-1};
    void capture() {
        sched_param parameter{};
        const int result=pthread_getschedparam(pthread_self(),&policy,&parameter);
        if(result!=0) throw std::system_error(result,std::generic_category(),"pthread_getschedparam");
        priority=parameter.sched_priority; observed_cpu=sched_getcpu();
    }
};
inline std::ofstream open_output(const std::filesystem::path& path) {
    std::ofstream stream;
    stream.exceptions(std::ios::failbit|std::ios::badbit); stream.open(path);
    stream << std::setprecision(17); return stream;
}
template<class T> void append_bounded(std::vector<T>& values, const T& value, std::size_t& drops) {
    if(values.size()==values.capacity()) ++drops;
    else values.push_back(value);
}
} // namespace stratadrive::simulation::runtime_support
