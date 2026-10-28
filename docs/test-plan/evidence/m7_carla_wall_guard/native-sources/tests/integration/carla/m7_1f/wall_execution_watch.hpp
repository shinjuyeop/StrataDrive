#pragma once
// M7 diagnostic bridge to the ORIGINAL M4 2ms/4ms schedule. Actual owner calls
// publish completions; polling stdin or waiting for CARLA never completes a job.
#include "m4_execution_watch.hpp"
#include "runtime_support.hpp"
#include <atomic>
#include <fstream>
#include <thread>

namespace stratadrive::m7_functional {
class WallExecutionWatch {
public:
    static std::uint64_t now() {return simulation::runtime_support::now_ns();}
    explicit WallExecutionWatch(std::uint64_t first_release)
        :first_(first_release),last_(first_release+2000000000ULL),
         watch_(first_release,last_+20000000ULL) {
        monitor_=std::thread([this] {
            auto release=first_;
            while(!done_.load(std::memory_order_acquire)) {
                simulation::runtime_support::sleep_until(release);
                if(done_.load(std::memory_order_acquire))break;
                const auto started=now();
                const auto job=watch_.begin_requested(9,started,true,release);
                for(const auto& fault:watch_.poll(9,started))if(fault)latched_.store(true,std::memory_order_release);
                watch_.finish(9,job,now(),0);
                for(const auto& fault:watch_.poll(9,now()))if(fault)latched_.store(true,std::memory_order_release);
                if(now()>=last_) {exhausted_.store(true,std::memory_order_release);break;}
                release=simulation::M4ReleaseGrid{first_,2000000}.after(now());
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
private:
    const std::uint64_t first_,last_;
    simulation::M4ExecutionWatch watch_;
    std::atomic<bool> done_{false},latched_{false},exhausted_{false};
    std::thread monitor_;
};
} // namespace stratadrive::m7_functional
