#pragma once
// Linux Host execution bridge. No scenario, fault injection or test verdict here.
#include "m4_execution_watch.hpp"
#include "runtime_support.hpp"
#include <atomic>
#include <functional>
#include <memory>
#include <thread>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>

namespace stratadrive::simulation {
inline constexpr std::size_t kNativeWatchSlots=10000;
struct NativeWatchShared {
    std::atomic<std::uint64_t> generation{0},enable{0},stop{0},quiesced{0};
    std::atomic<std::uint32_t> epoch{0},fault_epoch{0};
    std::atomic<std::uint64_t> fault_ns{0},fault_deadline{0};
    std::array<std::atomic<std::uint64_t>,kNativeWatchSlots> finished{},detected{};
};
// One writer per progress slot; atomic, lock-free Linux mmap observations. No
// cross-process C++ ownership or controller state. This is a Host-only contract.
class NativeWatchChannel {
    int fd_=-1;NativeWatchShared* data_=nullptr;
public:
    explicit NativeWatchChannel(const std::string& path,bool create=false) {
        fd_=::open(path.c_str(),O_RDWR|O_CLOEXEC|(create?(O_CREAT|O_EXCL):0),0600);
        if(fd_<0)throw std::system_error(errno,std::generic_category(),"watch channel open");
        if(create && ftruncate(fd_,sizeof(NativeWatchShared)))throw std::system_error(errno,std::generic_category(),"watch channel size");
        auto* p=mmap(nullptr,sizeof(NativeWatchShared),PROT_READ|PROT_WRITE,MAP_SHARED,fd_,0);
        if(p==MAP_FAILED)throw std::system_error(errno,std::generic_category(),"watch mmap");
        data_=static_cast<NativeWatchShared*>(p);
        if(create)new(data_)NativeWatchShared{};
        if(!data_->generation.is_lock_free() || !data_->epoch.is_lock_free())throw std::runtime_error("watch channel needs lock-free Host atomics");
    }
    NativeWatchShared& get(){return *data_;}
    ~NativeWatchChannel(){if(data_)munmap(data_,sizeof(*data_));if(fd_>=0)close(fd_);}
    NativeWatchChannel(const NativeWatchChannel&)=delete;
};
class NativeMonitorObserver {
    NativeWatchChannel channel_;std::uint64_t generation_=0;std::size_t cursor_=0;
    std::unique_ptr<runtime::TaskSchedule> schedule_;std::unique_ptr<runtime::DeadlineMonitor> monitor_;
public:
    explicit NativeMonitorObserver(const std::string& path):channel_(path){}
    std::uint32_t poll(std::uint64_t now) {
        auto& s=channel_.get();const auto gen=s.generation.load(std::memory_order_acquire);
        if(!gen)return 0;
        if(gen!=generation_) {
            const auto enable=s.enable.load(),stop=s.stop.load();
            if(stop<enable+20000000)return 0;
            schedule_=std::make_unique<runtime::TaskSchedule>(runtime::TaskScheduleConfig{enable,2000000,4000000,static_cast<std::size_t>((stop-enable-20000000)/2000000+1)});
            monitor_=std::make_unique<runtime::DeadlineMonitor>(*schedule_);generation_=gen;cursor_=0;
        }
        const auto quiesced=s.quiesced.load();const auto until=quiesced?std::min(now,quiesced):now;
        const auto begin=cursor_;
        while(cursor_<schedule_->config().jobs && schedule_->deadline(cursor_)<=until) {
            const auto finished=s.finished[cursor_].load(std::memory_order_acquire);
            if(finished)monitor_->finish(cursor_,finished);
            ++cursor_;
        }
        monitor_->poll(until);
        if(gen!=s.generation.load(std::memory_order_acquire))return 0;
        for(auto i=begin;i<cursor_;++i)if(const auto detected=monitor_->detected(i))s.detected[i]=detected;
        if(const auto fault=monitor_->first_fault()) {
            const auto epoch=s.epoch.load();
            if(!s.fault_ns.load()){s.fault_deadline=fault->deadline_ns;s.fault_ns=fault->detected_ns;}
            s.fault_epoch=epoch;return epoch;
        }
        return s.fault_epoch.load();
    }
};
class NativeExecutionWatch {
    NativeWatchChannel channel_;M4ExecutionWatch watch_;std::thread monitor_thread_;
    std::atomic<bool> done_{false},ready_{false};std::atomic<int> setup_error_{0};
    std::function<void(std::uint32_t)> protect_;
    std::function<void()> monitor_checkpoint_;
    std::size_t owner_;std::uint64_t origin_,stop_;bool fifo_;
public:
    runtime_support::ThreadInfo monitor_info,owner_info;
    NativeExecutionWatch(const std::string& channel,std::size_t owner,std::uint64_t origin,std::uint64_t duration,bool fifo,std::function<void(std::uint32_t)> protect,std::function<void()> checkpoint={})
      :channel_(channel),watch_(origin+100000000,origin+duration,(1U<<owner)|(1U<<9)),protect_(std::move(protect)),monitor_checkpoint_(std::move(checkpoint)),owner_(owner),origin_(origin),stop_(origin+duration),fifo_(fifo) {
        auto& s=channel_.get();s.generation=0;s.enable=origin+100000000;s.stop=stop_;s.quiesced=0;s.epoch=0;s.fault_epoch=0;s.fault_ns=0;s.fault_deadline=0;
        for(std::size_t i=0;i<kNativeWatchSlots;++i){s.finished[i]=0;s.detected[i]=0;}
        s.generation.store(origin,std::memory_order_release);
        monitor_thread_=std::thread([this]{
            try{configure_thread(0,fifo_?20:0);monitor_info.capture();}catch(const std::system_error& e){setup_error_=e.code().value();}catch(...){setup_error_=-1;}
            ready_.store(true,std::memory_order_release);
            if(setup_error_)return;
            auto release=M4ReleaseGrid{origin_,2000000}.after(runtime_support::now_ns());
            while(!done_.load()) {
                runtime_support::sleep_until(release);if(done_)break;
                const auto start=runtime_support::now_ns();const auto cpu=m4_cpu();
                const auto job=watch_.begin_requested(9,start,true,release);
                if(monitor_checkpoint_)monitor_checkpoint_();
                for(const auto& fault:watch_.poll(9,runtime_support::now_ns()))if(fault) {
                    auto& s=channel_.get();const auto e=s.epoch.load();
                    if(!s.fault_ns.load()){s.fault_deadline=fault->timing.deadline_ns;s.fault_ns=fault->timing.detected_ns;}
                    s.fault_epoch=e;protect_(e);
                }
                const auto end=runtime_support::now_ns();watch_.finish(9,job,end,m4_cpu()-cpu);
                if(job)channel_.get().finished[*job].store(end,std::memory_order_release);
                release=M4ReleaseGrid{origin_,2000000}.after(end);
            }
        });
        while(!ready_.load(std::memory_order_acquire))std::this_thread::yield();
        if(setup_error_){stop();throw std::system_error(setup_error_.load(),std::generic_category(),"native monitor setup");}
    }
    static void configure_thread(int cpu,int priority) {
        cpu_set_t mask;CPU_ZERO(&mask);CPU_SET(cpu,&mask);
        int e=pthread_setaffinity_np(pthread_self(),sizeof(mask),&mask);if(e)throw std::system_error(e,std::generic_category(),"native affinity");
        sched_param p{};p.sched_priority=priority;e=pthread_setschedparam(pthread_self(),priority?SCHED_FIFO:SCHED_OTHER,&p);if(e)throw std::system_error(e,std::generic_category(),"native policy");
        runtime_support::ThreadInfo actual;actual.capture();
        if(actual.policy!=(priority?SCHED_FIFO:SCHED_OTHER) || actual.priority!=priority || actual.allowed_cpus!=std::vector<int>{cpu})throw std::runtime_error("native setup readback mismatch");
    }
    static std::uint64_t m4_cpu(){timespec t{};clock_gettime(CLOCK_THREAD_CPUTIME_ID,&t);return std::uint64_t(t.tv_sec)*1000000000+t.tv_nsec;}
    std::uint64_t next_wake(std::uint64_t now)const{return M4ReleaseGrid{origin_,200000}.after(now);}
    void epoch(std::uint32_t value){channel_.get().epoch=value;}
    bool faulted(){return channel_.get().fault_ns.load()!=0;}
    std::optional<std::size_t> begin(std::uint64_t requested){return watch_.begin_requested(owner_,runtime_support::now_ns(),true,requested);}
    void finish(std::optional<std::size_t> job,std::uint64_t cpu){watch_.finish(owner_,job,runtime_support::now_ns(),m4_cpu()-cpu);}
    void stop(){if(!done_.exchange(true))channel_.get().quiesced=runtime_support::now_ns();if(monitor_thread_.joinable())monitor_thread_.join();}
    void write(const std::string& prefix) {
        stop();std::ofstream out(prefix+".watch.csv");out<<"owner,slot,release,deadline,start,end,cpu,detected,requested\n";
        for(auto r:watch_.rows()){if(r.owner==9)r.detected_ns=channel_.get().detected[r.slot].load();out<<r.owner<<','<<r.slot<<','<<r.release_ns<<','<<r.deadline_ns<<','<<r.start_ns<<','<<r.end_ns<<','<<r.cpu_ns<<','<<r.detected_ns<<','<<r.requested_wake_ns<<'\n';}
        std::ofstream info(prefix+".watch.json");auto& s=channel_.get();info<<"{\"origin\":"<<origin_<<",\"stop\":"<<stop_<<",\"quiesced\":"<<s.quiesced<<",\"fault_ns\":"<<s.fault_ns<<",\"fault_deadline\":"<<s.fault_deadline<<",\"fault_epoch\":"<<s.fault_epoch<<",\"monitor\":";monitor_info.write_json(info);info<<",\"owner\":";owner_info.write_json(info);info<<"}\n";
    }
    ~NativeExecutionWatch(){stop();}
};
}
