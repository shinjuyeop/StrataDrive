#pragma once

#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <functional>
#include <stdexcept>
#include <string_view>
#include <thread>
#include <vector>

namespace stratadrive::someip::test {
// Register each role's reads before startup. Writes remain available for every
// known marker. Reading an unobserved name fails instead of returning stale data.
inline std::vector<std::string> fixture_observations(std::string_view role) {
    if(role=="plant")return {"stop-plant","inject-model-delay","inject","service-stop-ready"};
    if(role=="central")return {"stop-central","inject","rejoin-request","service-collector-freeze",
                              "full-pause-ack","front-protected","queue-full","service-epoch-request"};
    if(role=="front" || role=="rear")return {"stop-"+std::string(role),"inject","full-pause-request",
                                          "service-freeze","service-fault-inject"};
    throw std::invalid_argument("unknown fixture role");
}
// Orchestration only: these files never grant control authority or prove a DTC.
// Register names before starting an owner. Its reads/writes then touch only
// bounded atomics; slow storage cannot stop command renewal or RX consumption.
class FixtureSignals {
    struct Slot {
        std::filesystem::path path;
        std::atomic<bool> present{false};
        std::atomic<std::uint64_t> requested{0};
        bool observed{false}; // immutable after registration
        bool written{false}; // worker only
    };
    std::array<Slot,48> slots_;
    std::size_t count_{0};
    std::atomic<bool> stop_{false},failed_{false};
    std::thread worker_;
    static std::uint64_t now() {
        return std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count();
    }
    Slot& find(const std::filesystem::path& path) {
        for(std::size_t i=0;i<count_;++i)if(slots_[i].path==path)return slots_[i];
        throw std::invalid_argument("unregistered fixture signal");
    }
public:
    using Hook=std::function<void(const std::filesystem::path&)>;
    FixtureSignals(const std::filesystem::path& folder,const std::string& tag,
                   std::function<void()> configure={},Hook before_write={},
                   const std::vector<std::string>& observed={}) {
        std::vector<std::string> names{
            "armed","plant-ready","stop-plant","stop-central","stop-front","stop-rear",
            "inject","inject-model-delay","service-stop-ready","service-fault-inject",
            "service-freeze","service-collector-freeze","service-epoch-ready","service-epoch-request",
            "rejoin-request","rejoined","central-2-rejoined","control-established",
            "central-protected","front-protected","rear-protected","physical-protected",
            "diagnostics-settled","delay-drained","queue-full","full-pause-request","full-pause-ack",
            "central.service-frozen","front.service-frozen","rear.service-frozen",
            tag+".started",tag+".ready",tag+".failed",tag+".quiesced"};
        for(const auto& name:names) {
            auto& s=slots_[count_++];s.path=folder/name;
            s.observed=observed.empty();
        }
        for(const auto& name:observed)find(folder/name).observed=true;
        for(std::size_t i=0;i<count_;++i)if(slots_[i].observed)
            slots_[i].present=std::filesystem::exists(slots_[i].path);
        worker_=std::thread([this,folder,tag,configure,before_write] {
            try {
                if(configure)configure();
                std::ofstream observations(folder/(tag+".signals.observed.txt"));
                for(std::size_t i=0;i<count_;++i)if(slots_[i].observed)observations<<slots_[i].path.filename().string()<<'\n';
                observations.close();if(!observations)throw std::runtime_error("fixture observation manifest failed");
                std::ofstream log(folder/(tag+".signals.csv"));
                log<<"name,requested_ns,write_begin_ns,write_end_ns\n";
                do {
                    const bool final_pass=stop_.load(std::memory_order_acquire);
                    for(std::size_t i=0;i<count_;++i) {
                        auto& s=slots_[i];
                        if(const auto request=s.requested.load(std::memory_order_acquire);request && !s.written) {
                            const auto begin=now();
                            if(before_write)before_write(s.path);
                            std::ofstream out(s.path);out<<request<<'\n';out.close();
                            if(!out)throw std::runtime_error("fixture signal write failed");
                            s.written=true;
                            log<<s.path.filename().string()<<','<<request<<','<<begin<<','<<now()<<'\n';
                        }
                        if(s.observed)s.present.store(std::filesystem::exists(s.path),std::memory_order_release);
                    }
                    log.flush();if(!log)throw std::runtime_error("fixture signal trace failed");
                    if(final_pass)break;
                    std::this_thread::sleep_for(std::chrono::milliseconds(1));
                } while(true);
            } catch(...) {failed_.store(true,std::memory_order_release);}
        });
    }
    bool exists(const std::filesystem::path& path) {
        auto& slot=find(path);
        if(!slot.observed)throw std::invalid_argument("unobserved fixture signal");
        return slot.present.load(std::memory_order_acquire);
    }
    void mark(const std::filesystem::path& path,std::uint64_t source=0) {
        auto& s=find(path);std::uint64_t empty=0;
        s.requested.compare_exchange_strong(empty,source?source:now(),std::memory_order_release,std::memory_order_relaxed);
    }
    bool failed() const {return failed_.load(std::memory_order_acquire);}
    void finish() {stop_.store(true,std::memory_order_release);if(worker_.joinable())worker_.join();}
    ~FixtureSignals(){finish();}
};
} // namespace stratadrive::someip::test
