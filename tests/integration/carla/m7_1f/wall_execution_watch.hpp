#pragma once
// M7 diagnostic bridge to the ORIGINAL M4 2ms/4ms schedule. Actual owner calls
// publish completions; polling stdin or waiting for CARLA never completes a job.
#include "m4_execution_watch.hpp"
#include "runtime_support.hpp"
#include "watch_timing.hpp"
#include <atomic>
#include <fstream>
#include <thread>

namespace stratadrive::m7_functional {
class WallExecutionWatch {
public:
    static std::uint64_t now() {return simulation::runtime_support::now_ns();}
    explicit WallExecutionWatch(std::uint64_t first_release,std::uint64_t horizon=2000000000ULL,bool profile=false)
        :first_(first_release),last_(first_release+horizon),
         watch_(first_release,last_+20000000ULL,0x3ff,horizon==35000000000ULL || horizon==305000000000ULL),
         timing_capacity_(profile?static_cast<std::size_t>(horizon/2000000+1):0),
         timings_(profile?std::make_unique<WatchTimingRow[]>(timing_capacity_):nullptr) {
        monitor_=std::thread([this] {
            if(timings_)monitor_info_.capture();
            auto release=first_;
            while(!done_.load(std::memory_order_acquire)) {
                WatchTimingRow timing;
                if(timings_) {timing.release=release;timing.sleep_cpu=sched_getcpu();timing.sleep_begin=now();}
                simulation::runtime_support::sleep_until(release);
                if(done_.load(std::memory_order_acquire))break;
                const auto started=now();
                if(timings_) {timing.wake=started;timing.begin=WatchThreadStamp::capture();}
                const auto job=watch_.begin_requested(9,started,true,release);
                for(const auto& fault:watch_.poll(9,started))if(fault)latched_.store(true,std::memory_order_release);
                const auto completed=now();watch_.finish(9,job,completed,0);
                for(const auto& fault:watch_.poll(9,now()))if(fault)latched_.store(true,std::memory_order_release);
                if(timings_) {timing.job_end=completed;timing.poll_end=now();timing.end=WatchThreadStamp::capture();}
                if(now()>=last_) {exhausted_.store(true,std::memory_order_release);break;}
                const auto grid_now=now();release=simulation::M4ReleaseGrid{first_,2000000}.after(grid_now);
                if(timings_) {
                    timing.grid_now=grid_now;timing.next_release=release;
                    if(timing_count_==timing_capacity_) {timing_overflow_=true;exhausted_.store(true,std::memory_order_release);break;}
                    timings_[timing_count_++]=timing;
                }
            }
        });
    }
    ~WallExecutionWatch(){stop();}
    WallExecutionWatch(const WallExecutionWatch&)=delete;
    std::optional<std::size_t> begin(unsigned owner) {
        return watch_.begin(owner,now(),true);
    }
    void finish(unsigned owner,std::optional<std::size_t> job) {
        watch_.finish(owner,job,now(),0);
        if(owner==8)for(const auto& fault:watch_.poll(8,now()))if(fault)latched_.store(true,std::memory_order_release);
    }
    bool faulted() const {return latched_.load(std::memory_order_acquire)||exhausted_.load(std::memory_order_acquire);}
    std::uint64_t first_release() const {return first_;}
    void stop() {done_.store(true,std::memory_order_release);if(monitor_.joinable())monitor_.join();}
    std::vector<simulation::M4ExecutionRow> rows() {stop();return watch_.rows();}
    void write(const std::string& path) {
        const auto stopped=now();stop();
        std::ofstream out(path);out<<"owner,slot,release_ns,deadline_ns,start_ns,end_ns,detected_ns\n";
        for(const auto& row:watch_.rows())if(row.release_ns<=stopped)
            out<<row.owner<<','<<row.slot<<','<<row.release_ns<<','<<row.deadline_ns<<','
               <<row.start_ns<<','<<row.end_ns<<','<<row.detected_ns<<'\n';
        if(!out)throw std::runtime_error("wall watch evidence write");
    }
    void write_profile(const std::string& prefix) {
        stop();if(!timings_)return;
        std::ofstream meta(prefix+".json");
        meta<<"{\"scope\":\"monitor diagnostic only; original release/deadline/skip policy unchanged\",\"first_release_ns\":"<<first_
            <<",\"last_release_ns\":"<<last_<<",\"capacity\":"<<timing_capacity_<<",\"count\":"<<timing_count_
            <<",\"overflow\":"<<(timing_overflow_?"true":"false")<<",\"thread\":";
        monitor_info_.write_json(meta);meta<<"}\n";
        std::ofstream out(prefix+".csv");
        out<<"release_ns,sleep_begin_ns,wake_ns,job_end_ns,poll_end_ns,grid_now_ns,next_release_ns,sleep_cpu,wake_cpu,end_cpu,begin_cpu_ns,end_cpu_ns,begin_voluntary,end_voluntary,begin_involuntary,end_involuntary,begin_minor_faults,end_minor_faults,begin_error,end_error\n";
        for(std::size_t i=0;i<timing_count_;++i) {
            const auto& r=timings_[i];
            out<<r.release<<','<<r.sleep_begin<<','<<r.wake<<','<<r.job_end<<','<<r.poll_end<<','<<r.grid_now<<','<<r.next_release<<','
               <<r.sleep_cpu<<','<<r.begin.cpu<<','<<r.end.cpu<<','<<r.begin.cpu_ns<<','<<r.end.cpu_ns<<','
               <<r.begin.voluntary<<','<<r.end.voluntary<<','<<r.begin.involuntary<<','<<r.end.involuntary<<','
               <<r.begin.minor_faults<<','<<r.end.minor_faults<<','<<r.begin.error<<','<<r.end.error<<'\n';
        }
        if(!meta || !out)throw std::runtime_error("monitor profile write");
    }
private:
    const std::uint64_t first_,last_;
    simulation::M4ExecutionWatch watch_;
    const std::size_t timing_capacity_;
    std::unique_ptr<WatchTimingRow[]> timings_;
    std::size_t timing_count_{0};bool timing_overflow_{false};
    simulation::runtime_support::ThreadInfo monitor_info_;
    std::atomic<bool> done_{false},latched_{false},exhausted_{false};
    std::thread monitor_;
};
} // namespace stratadrive::m7_functional
