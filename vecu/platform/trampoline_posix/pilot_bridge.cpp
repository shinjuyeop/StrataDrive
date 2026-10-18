#include "pilot_bridge.h"
#include "actuator_socketcan.hpp"
#include "steering_actuator.hpp"

#include <array>
#include <atomic>
#include <charconv>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <memory>
#include <sched.h>
#include <stdexcept>
#include <string>
#include <sys/socket.h>
#include <unistd.h>

namespace {
using namespace stratadrive;
constexpr std::uint64_t ms=1000000, window=1600*ms, deadline=5*ms;
constexpr std::size_t capacity=256, budget=8;
static_assert(sizeof(PilotSensor)==32 && sizeof(PilotOutput)==40);
static_assert(std::atomic<std::uint64_t>::is_always_lock_free);
std::uint64_t clock_ns() { return socketcan::monotonic_time_ns(); }
std::uint64_t number(const char* text) {
    const std::string value(text); std::uint64_t result=0;
    const auto parsed=std::from_chars(value.data(),value.data()+value.size(),result);
    if(parsed.ec!=std::errc{} || parsed.ptr!=value.data()+value.size()) throw std::invalid_argument("pilot integer");
    return result;
}
struct Job {
    std::atomic<std::uint64_t> release{0},end{0},detected{0};
    std::uint64_t start{0},phase{0},source{0},suspend{0},resume{0},actual_source{0};
    unsigned fault{0}; bool reported{false},actual_valid{false};
};
struct Pilot {
    socketcan::Endpoint endpoint;
    vecu::SteeringActuator ecu{{-.5,.5,-.3,.3,0,1,50*ms,ms}};
    int fd;
    const std::uint64_t enable;
    const std::string scenario;
    const std::filesystem::path directory;
    std::array<Job,capacity> jobs{};
    std::atomic<std::size_t> released{0};
    std::atomic<bool> protection{false};
    std::array<can::SteeringFrame,32> queue{};
    std::size_t head{0},count{0},current{capacity},observed{0};
    std::optional<steering::AngleMeasurement> sensor,current_sensor;
    unsigned os_errors{0},fatal_errors{0},last_os_error{0},accepted{0},rejected{0},rx_calls{0},watch_calls{0},ipc_errors{0};
    bool continuity_lost{false},injected{false};
    std::uint64_t first_guard{0},last_command_ns{0},last_command_source{0};
    Pilot(char** argv):endpoint(argv[1],can::kSteeringCommandId),fd(static_cast<int>(number(argv[2]))),
        enable(number(argv[3])),scenario(argv[4]),directory(argv[5]) {
        if(fd<0 || enable<=clock_ns() || !std::filesystem::is_directory(directory) ||
           (scenario!="normal" && scenario!="command-loss" && scenario!="corrupt" && scenario!="control-stall"))
            throw std::invalid_argument("pilot configuration");
        if(!ecu.start_session({2,1,enable})) throw std::runtime_error("pilot INIT");
    }
    void send_output(bool hold,double target,std::uint64_t issued,std::uint64_t due,std::size_t job,unsigned reason) {
        const PilotOutput packet{issued,due,job,static_cast<std::uint32_t>(hold),reason,target};
        if(send(fd,&packet,sizeof(packet),MSG_DONTWAIT|MSG_NOSIGNAL)!=sizeof(packet)) ++ipc_errors;
    }
    void protect(std::uint64_t now) {
        protection.store(true,std::memory_order_release);
        if(!first_guard) { first_guard=now; send_output(true,0,now,0,capacity,1); }
    }
};
std::unique_ptr<Pilot> pilot;
template<class Function> int checked(Function function) {
    try { return function(); }
    catch(...) { if(pilot) { ++pilot->fatal_errors; pilot->protection.store(true,std::memory_order_release); } return 0; }
}
} // namespace

extern "C" int pilot_open(int argc,char** argv) {
    return checked([&] { if(argc!=6) return 0; pilot=std::make_unique<Pilot>(argv); return 1; });
}
extern "C" void pilot_started(void) {
    checked([] { std::ofstream(pilot->directory/"rtos-start.json") << "{\"rtos_pid\":" << getpid() << "}\n"; return 1; });
}
extern "C" int pilot_release(void) {
    return checked([] {
        auto& p=*pilot; const auto now=clock_ns();
        if(now<p.enable+10*ms || now>p.enable+window) return 0;
        const auto i=p.released.load(std::memory_order_relaxed);
        if(i==capacity) { p.protect(now); return 0; }
        p.jobs[i].release.store(now,std::memory_order_relaxed);
        p.released.store(i+1,std::memory_order_release);
        return 1;
    });
}
extern "C" void pilot_receive(void) {
    checked([] {
        auto& p=*pilot; ++p.rx_calls;
        if(clock_ns()>p.enable+window) return 1;
        for(std::size_t n=0;n<budget;++n) {
            const auto packet=p.endpoint.receive(); if(!packet) break;
            if(packet->dropped_frames) p.continuity_lost=true;
            if(p.count==p.queue.size()) { p.continuity_lost=true; break; }
            p.queue[(p.head+p.count)%p.queue.size()]=socketcan::to_steering(packet->frame); ++p.count;
        }
        for(std::size_t n=0;n<budget;++n) {
            PilotSensor packet{}; const auto received=recv(p.fd,&packet,sizeof(packet),MSG_DONTWAIT|MSG_TRUNC);
            if(received<0 && (errno==EAGAIN || errno==EWOULDBLOCK)) break;
            if(received!=sizeof(packet) || packet.magic!=PILOT_SENSOR_MAGIC || !std::isfinite(packet.angle_rad)) {
                ++p.ipc_errors; p.continuity_lost=true; break;
            }
            if(p.sensor && packet.source_ns<=p.sensor->source_time_ns) { p.continuity_lost=true; break; }
            p.sensor=steering::AngleMeasurement{packet.model_epoch,packet.sequence,packet.source_ns,packet.angle_rad};
        }
        return 1;
    });
}
extern "C" int pilot_control_begin(void) {
    return checked([] {
        auto& p=*pilot; const auto size=p.released.load(std::memory_order_acquire);
        if(size==0 || p.current==size-1) return 0;
        p.current=size-1; auto& row=p.jobs[p.current]; row.start=clock_ns();
        if(p.continuity_lost) p.ecu.mark_continuity_lost(row.start);
        while(p.count) {
            const auto received_ns=clock_ns(); const auto result=p.ecu.receive(p.queue[p.head],received_ns);
            if(result.decision==can::SteeringReceiveDecision::Accepted) {
                p.last_command_ns=received_ns; p.last_command_source=can::decode_steering_frame(p.queue[p.head])->source_time_ns;
            }
            p.head=(p.head+1)%p.queue.size(); --p.count;
            if(result.decision==can::SteeringReceiveDecision::Accepted) ++p.accepted; else ++p.rejected;
        }
        p.current_sensor=p.sensor; row.phase=clock_ns(); row.source=p.sensor ? p.sensor->source_time_ns : 0;
        if(p.protection.load(std::memory_order_acquire)) p.ecu.mark_output_rejected(row.phase);
        p.ecu.prepare(row.phase);
        return 1;
    });
}
extern "C" int pilot_suspend(void) {
    return checked([] {
        auto& p=*pilot;
        if(p.scenario!="control-stall" || p.injected || p.jobs[p.current].phase<p.enable+600*ms) return 0;
        p.injected=true; p.jobs[p.current].suspend=clock_ns(); return 1;
    });
}
extern "C" void pilot_resume(void) { checked([] { pilot->jobs[pilot->current].resume=clock_ns(); return 1; }); }
extern "C" void pilot_control_finish(void) {
    checked([] {
        auto& p=*pilot; auto& row=p.jobs[p.current];
        auto feedback=p.ecu.complete(p.current_sensor,row.phase);
        const auto now=clock_ns(),due=row.release.load()+deadline;
        const bool blocked=p.protection.load(std::memory_order_acquire) || now>due;
        if(blocked) { p.ecu.mark_output_rejected(now); feedback.reset(); }
        const auto output=p.ecu.output();
        p.send_output(blocked || output.mode==steering::ActuationMode::Hold,output.target_rad,now,due,p.current,blocked?1:2);
        if(feedback) {
            const auto message=can::decode_steering_frame(*feedback);
            if(!message) throw std::runtime_error("pilot Actual codec");
            p.endpoint.send(socketcan::to_socketcan(*feedback));
            row.reported=true; row.actual_source=message->source_time_ns; row.actual_valid=message->angle_rad.has_value();
        }
        row.fault=static_cast<unsigned>(p.ecu.fault()); row.end.store(clock_ns(),std::memory_order_release);
        return 1;
    });
}
extern "C" void pilot_watch(void) {
    checked([] {
        auto& p=*pilot; ++p.watch_calls; const auto now=clock_ns();
        const auto size=p.released.load(std::memory_order_acquire);
        while(p.observed<size) {
            auto& row=p.jobs[p.observed]; const auto due=row.release.load()+deadline;
            if(now<due) break;
            const auto end=row.end.load(std::memory_order_acquire);
            if(end==0 || end>due) { row.detected.store(now,std::memory_order_release); p.protect(now); }
            ++p.observed;
        }
        return 1;
    });
}
extern "C" int pilot_done(void) { return checked([] { return clock_ns()>=pilot->enable+window+40*ms ? 1:0; }); }
extern "C" void pilot_os_error(unsigned error) { if(pilot) { ++pilot->os_errors; pilot->last_os_error=error; pilot->protection.store(true); } }
extern "C" void pilot_close(unsigned error) {
    checked([&] {
        auto& p=*pilot;
        std::ofstream csv(p.directory/"rtos-jobs.csv");
        csv << "job,release_ns,deadline_ns,start_ns,phase_ns,end_ns,source_ns,actual_source_ns,reported,fault,detected_ns,suspend_ns,resume_ns,actual_valid\n";
        for(std::size_t i=0;i<p.released.load();++i) { const auto& r=p.jobs[i];
            csv << i << ',' << r.release.load() << ',' << r.release.load()+deadline << ',' << r.start << ',' << r.phase << ',' << r.end.load()
                << ',' << r.source << ',' << r.actual_source << ',' << r.reported << ',' << r.fault << ',' << r.detected.load() << ',' << r.suspend << ',' << r.resume << ',' << r.actual_valid << '\n';
        }
        sched_param priority{}; const int policy=sched_getscheduler(0); sched_getparam(0,&priority);
        cpu_set_t mask; CPU_ZERO(&mask);
        if(sched_getaffinity(0,sizeof(mask),&mask)!=0) throw std::runtime_error("pilot affinity read");
        std::ofstream meta(p.directory/"rtos.json");
        meta << "{\"schema\":1,\"rtos_pid\":" << getpid() << ",\"clock\":\"CLOCK_MONOTONIC\",\"os\":\"Trampoline POSIX\",\"oil_version\":\"2.5\",\"tick_ns\":10000000,"
            << "\"enable_ns\":" << p.enable << ",\"end_ns\":" << clock_ns() << ",\"completion_budget_ns\":" << deadline
            << ",\"released\":" << p.released.load() << ",\"first_guard_ns\":" << p.first_guard << ",\"accepted\":" << p.accepted
            << ",\"rejected\":" << p.rejected << ",\"last_command_accepted_ns\":" << p.last_command_ns << ",\"last_command_source_ns\":" << p.last_command_source
            << ",\"rx_calls\":" << p.rx_calls << ",\"watch_calls\":" << p.watch_calls
            << ",\"os_errors\":" << p.os_errors << ",\"last_os_error\":" << p.last_os_error << ",\"fatal_errors\":" << p.fatal_errors
            << ",\"ipc_errors\":" << p.ipc_errors << ",\"shutdown_status\":" << error << ",\"linux_policy\":" << policy
            << ",\"linux_priority\":" << priority.sched_priority << ",\"linux_cpu\":" << sched_getcpu() << ",\"linux_allowed_cpus\":[";
        bool separator=false;
        for(int cpu=0;cpu<CPU_SETSIZE;++cpu) if(CPU_ISSET(cpu,&mask)) { if(separator) meta << ','; meta << cpu; separator=true; }
        meta << "],\"host_realtime_guarantee\":false}";
        return 1;
    });
}
