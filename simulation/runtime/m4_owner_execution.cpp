#include "m4_owner_network.hpp"
#include "runtime_support.hpp"
#include <chrono>

namespace stratadrive::simulation::m4_detail {
void execute_logical(Network& network) {
 const auto& config=network.config;
        if(config.execution_guards) network.configure_watch(config.replace_links && config.recovery_ns?config.recovery_ns:config.duration_ns);
        bool replaced=false;
        for(std::uint64_t t=0;t<=config.duration_ns;t+=kIoPoll) {
            network.clock.logical=kLogicalStart+t;
            if(config.replace_links && config.recovery_ns && !replaced && t>=config.recovery_ns) { network.replace_joined_links(); if(config.execution_guards) network.configure_watch(config.duration_ns); replaced=true; }
            if(t%kMs==0) network.step(8);
            if(config.execution_guards && t%(2*kMs)==0) network.step(9);
            for(std::size_t owner=0;owner<8;++owner) network.step(owner);
        }
    
}
void execute_native(Network& network) {
 const auto& config=network.config;
        const auto count=config.execution_guards?10U:9U;
        runtime_support::ThreadInfo inherited; inherited.capture();
        if(inherited.policy!=SCHED_OTHER || inherited.priority!=0) throw std::invalid_argument("M4 native launcher must be OTHER/0");
        for(const auto cpu:{config.cpu_a,config.cpu_b}) if(cpu>=0 && std::find(inherited.allowed_cpus.begin(),inherited.allowed_cpus.end(),cpu)==inherited.allowed_cpus.end()) throw std::invalid_argument("M4 CPU outside inherited affinity");
        auto segment=[&](std::uint64_t until) {
            if(config.execution_guards) network.configure_watch(until);
            std::atomic<std::size_t> ready{0}; std::atomic<bool> go{false}; bool aborted=false;
            std::array<M4Result::Thread,10> observed{}; std::array<bool,10> errors{};
            std::vector<std::thread> workers;
            const std::array<int,10> priorities{18,18,10,10,10,9,10,11,19,20};
            for(std::size_t owner=0;owner<count;++owner) workers.emplace_back([&,owner] {
                auto& out=observed[owner]; out.owner=owner;
                const int cpu=(owner<2 || owner>=8)?config.cpu_a:config.cpu_b; out.requested_cpu=cpu;
                runtime_support::ThreadInfo info;
                try {
                    info.capture();
                    if(cpu>=0) { cpu_set_t mask; CPU_ZERO(&mask); CPU_SET(cpu,&mask); const int error=pthread_setaffinity_np(pthread_self(),sizeof(mask),&mask); if(error) throw std::system_error(error,std::generic_category(),"M4 affinity"); }
                    if(config.fifo) { sched_param parameter{}; parameter.sched_priority=priorities[owner]; const int error=pthread_setschedparam(pthread_self(),SCHED_FIFO,&parameter); if(error) throw std::system_error(error,std::generic_category(),"M4 FIFO"); }
                    info.capture();
                    if(info.policy!=(config.fifo?SCHED_FIFO:SCHED_OTHER) || info.priority!=(config.fifo?priorities[owner]:0) || (cpu>=0 && info.allowed_cpus!=std::vector<int>{cpu})) throw std::runtime_error("M4 requested setup was not applied");
                } catch(const std::system_error& e) { out.setup_error=e.code().value(); } catch(...) { out.setup_error=-1; }
                out.policy=info.policy; out.priority=info.priority; out.cpu=info.observed_cpu; out.tid=info.tid; out.affinity=info.allowed_cpus;
                // A release/acquire launch gate avoids the GCC 11 TSan timed-CV
                // interceptor gap. Setup writes happen before ready; abort before go.
                ready.fetch_add(1,std::memory_order_release);
                while(!go.load(std::memory_order_acquire)) std::this_thread::sleep_for(std::chrono::microseconds(20));
                if(aborted) return;
                try {
                    const M4ReleaseGrid grid{network.start,owner==9?2*kMs:owner==8?kMs:kIoPoll};
                    auto release=grid.after(network.clock.now_ns());
                    while(network.clock.now_ns()-network.start<until) {
                        std::this_thread::sleep_until(std::chrono::steady_clock::time_point(std::chrono::nanoseconds(release)));
                        if(network.clock.now_ns()-network.start>=until) break;
                        network.step(owner,release);
                        release=grid.after(network.clock.now_ns());
                    }
                } catch(...) { errors[owner]=true; }
            });
            const auto setup_deadline=std::chrono::steady_clock::now()+std::chrono::milliseconds(50);
            while(ready.load(std::memory_order_acquire)!=count && std::chrono::steady_clock::now()<setup_deadline) std::this_thread::sleep_for(std::chrono::microseconds(20));
            if(ready.load(std::memory_order_acquire)!=count) aborted=true;
            else for(std::size_t i=0;i<count;++i) if(observed[i].setup_error) aborted=true;
            go.store(true,std::memory_order_release);
            for(auto& worker:workers) worker.join();
            if(aborted) { network.result.startup_ok=false; network.result.reason="M4 owner configuration/startup rejected"; }
            for(std::size_t i=0;i<count;++i) { network.result.threads.push_back(observed[i]); if(errors[i]) { network.result.startup_ok=false; network.result.reason="M4 owner execution exception"; } }
        };
        if(config.replace_links && config.recovery_ns) { segment(config.recovery_ns); network.replace_joined_links(); }
        if(network.result.startup_ok) segment(config.duration_ns);
    
}
} // namespace stratadrive::simulation::m4_detail
