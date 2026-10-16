#include "steering_runtime.hpp"
#include "runtime_support.hpp"

#include "periodic_task.hpp"
#include "latest_snapshot.hpp"
#include "steering_actuator.hpp"
#include "steering_response.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <cerrno>
#include <exception>
#include <fstream>
#include <iomanip>
#include <optional>
#include <pthread.h>
#include <sched.h>
#include <stdexcept>
#include <system_error>
#include <thread>
#include <time.h>
#include <vector>

namespace stratadrive::simulation {
namespace {
constexpr std::uint64_t kMs=1000000, kPeriod=10*kMs, kDeadline=5*kMs, kPoll=2*kMs;
constexpr std::size_t kJobs=120, kInjectedJob=20;
using runtime_support::now_ns;
using runtime_support::sleep_until;
using runtime_support::ThreadInfo;
using runtime_support::open_output;
using runtime_support::append_bounded;
std::uint64_t next_poll(std::uint64_t enable, std::uint64_t now) {
    return runtime_support::next_wake(enable,kPoll,now);
}
struct Inputs {
    std::optional<can::SteeringFrame> command;
    std::optional<steering::AngleMeasurement> sensor;
};
struct Output {
    steering::Actuation actuation;
    std::size_t job;
    std::uint64_t deadline_ns;
    std::optional<can::SteeringFrame> feedback;
};
struct Job {
    std::uint64_t start{0},end{0},prepare_begin{0},prepare_end{0},complete_begin{0},complete_end{0};
    std::uint64_t job_time{0},input_source{0},sensor_sequence{0},feedback_source{0},feedback_at{0},command_rx{0},command_source{0};
    std::uint64_t injection_begin{0},injection_end{0};
    std::uint32_t command_sequence{0},causal_sequence{0};
    bool ran{false},prepared{false};
    bool feedback_valid{false},feedback_failsafe{false};
    int fault{0},receive_decision{-1};
};
struct PlantStep {
    std::uint64_t time,begin,end,sensor_source,sensor_sequence;
    double angle;
    bool override_hold;
    std::int64_t last_ecu_applied_job;
    std::uint64_t output_issued,output_applied;
};
struct MonitorStep { std::uint64_t time; bool fault; };
} // namespace

void run_steering_runtime(const std::string& scenario, const std::filesystem::path& directory, bool detailed) {
    if(scenario!="normal" && scenario!="overrun" && scenario!="stall") throw std::invalid_argument("steering-runtime scenario");
    // Refuse to overwrite a previous experiment, even if it failed.
    if(!std::filesystem::create_directories(directory)) throw std::invalid_argument("runtime output directory must be new");
    std::vector<std::uint64_t> clock_probe; clock_probe.reserve(10000);
    for(std::size_t i=0;i<10000;++i) { const auto a=now_ns(); clock_probe.push_back(now_ns()-a); }
    std::sort(clock_probe.begin(),clock_probe.end());
    timespec resolution{};
    if(clock_getres(CLOCK_MONOTONIC,&resolution)!=0) throw std::system_error(errno,std::generic_category(),"clock_getres");
    const auto enable=now_ns()+50*kMs;
    const runtime::TaskSchedule schedule({enable+kPeriod,kPeriod,kDeadline,kJobs});
    runtime::DeadlineMonitor monitor(schedule);
    const auto stop_at=schedule.deadline(kJobs-1)+30*kMs;
    std::array<Job,kJobs> jobs{};
    std::vector<PlantStep> plant_steps; plant_steps.reserve(kJobs*10+128);
    std::vector<MonitorStep> monitor_steps; monitor_steps.reserve(kJobs*10+128);
    std::size_t plant_drops=0,monitor_drops=0,input_read_empty=0,expired_outputs=0;
    std::uint64_t hold_at=0,monitor_started=0,monitor_ended=0;
    runtime::LatestSnapshot<Inputs> input_port; runtime::LatestSnapshot<Output> output_port;
    std::atomic<bool> abort{false};
    std::array<std::exception_ptr,3> errors{};
    std::array<ThreadInfo,3> thread_info{};
    SteeringResponse plant({-.3,.3,0,1,50*kMs});
    if(!plant.begin(enable)) throw std::runtime_error("runtime plant INIT");
    auto watch=[&] {
        try {
            thread_info[1].capture(); sleep_until(enable); monitor_started=now_ns();
            while(!abort.load(std::memory_order_acquire)) {
                const auto now=now_ns(); monitor.poll(now);
                if(detailed) append_bounded(monitor_steps,MonitorStep{now,monitor.faulted()},monitor_drops);
                if(now>=stop_at) break;
                sleep_until(next_poll(enable,now_ns()));
            }
            monitor_ended=now_ns();
        } catch(...) { errors[1]=std::current_exception(); abort.store(true,std::memory_order_release); }
    };
    auto control=[&] {
        try {
            thread_info[0].capture();
            vecu::SteeringActuatorConfig config{-.5,.5,-.3,.3,0,1,50*kMs};
            config.period_ns=kMs; // minimum call guard, distinct from the 10 ms task release
            vecu::SteeringActuator ecu(config);
            if(!ecu.start_session({1,1,enable})) throw std::runtime_error("runtime ECU INIT");
            Inputs cached;
            for(std::size_t next=0;next<kJobs && !abort.load(std::memory_order_acquire);) {
                sleep_until(schedule.release(next));
                const auto actual_start=now_ns();
                const auto selected=schedule.newest_released(actual_start,next);
                if(!selected) continue;
                const auto i=*selected; next=i+1;
                // Expired jobs are still accounted for by the independent monitor.
                if(actual_start>=schedule.deadline(i)) continue;
                auto& row=jobs[i]; row.ran=true; row.start=actual_start;
                if(const auto snapshot=input_port.read()) cached=*snapshot; else ++input_read_empty;
                const bool blocked=monitor.faulted() || monitor.clock_error();
                row.job_time=now_ns();
                if(blocked) ecu.mark_output_rejected(row.job_time);
                if(cached.command) {
                    const auto decoded=can::decode_steering_frame(*cached.command);
                    if(decoded) { row.command_sequence=decoded->sequence; row.command_source=decoded->source_time_ns; }
                    row.receive_decision=static_cast<int>(ecu.receive(*cached.command,row.job_time).decision);
                    if(detailed && row.receive_decision==static_cast<int>(can::SteeringReceiveDecision::Accepted)) row.command_rx=now_ns();
                }
                if(cached.sensor) { row.input_source=cached.sensor->source_time_ns; row.sensor_sequence=cached.sensor->sequence; }
                if(detailed) row.prepare_begin=now_ns();
                row.prepared=ecu.prepare(row.job_time);
                if(detailed) row.prepare_end=now_ns();
                if(i==kInjectedJob && scenario!="normal") {
                    row.injection_begin=now_ns();
                    if(scenario=="stall") sleep_until(row.injection_begin+120*kMs);
                    else while(now_ns()-row.injection_begin<15*kMs) std::atomic_signal_fence(std::memory_order_seq_cst);
                    row.injection_end=now_ns();
                }
                if(detailed) row.complete_begin=now_ns();
                auto feedback=row.prepared ? ecu.complete(cached.sensor,row.job_time) : std::nullopt;
                if(detailed) row.complete_end=now_ns();
                const auto admission=now_ns();
                // Discard late/newly invalidated jobs, but keep timely
                // protected diagnostics once the ECU has latched its fault.
                const bool newly_faulted=monitor.faulted() && ecu.fault()==vecu::SteeringFault::None;
                if(admission>schedule.deadline(i) || newly_faulted || monitor.clock_error()) {
                    ecu.mark_output_rejected(admission); feedback.reset();
                }
                output_port.publish(Output{ecu.output(),i,schedule.deadline(i),feedback});
                if(feedback) {
                    const auto decoded=can::decode_steering_frame(*feedback);
                    if(!decoded) throw std::runtime_error("runtime feedback codec");
                    row.feedback_at=now_ns(); row.feedback_source=decoded->source_time_ns;
                    row.feedback_valid=decoded->angle_rad.has_value();
                    row.feedback_failsafe=decoded->local_state==can::SteeringLocalState::FailSafe && decoded->origin==can::SteeringOrigin::LocalProtection;
                    row.causal_sequence=decoded->causal_sequence;
                }
                row.fault=static_cast<int>(ecu.fault()); row.end=now_ns();
                if(!monitor.finish(i,row.end)) throw std::runtime_error("runtime duplicate completion");
            }
        } catch(...) { errors[0]=std::current_exception(); abort.store(true,std::memory_order_release); }
    };
    std::thread watch_thread(watch);
    std::thread control_thread;
    try { control_thread=std::thread(control); }
    catch(...) { abort.store(true,std::memory_order_release); watch_thread.join(); throw; }
    try {
        thread_info[2].capture(); sleep_until(enable);
        can::SteeringTxState tx{can::SteeringFrameKind::Command};
        std::uint32_t command_sequence=0;
        std::uint64_t next_command=enable;
        Inputs inputs;
        std::optional<std::size_t> applied_job;
        std::int64_t last_ecu_applied_job=-1;
        std::uint64_t output_issued=0,output_applied=0;
        while(!abort.load(std::memory_order_acquire)) {
            const bool forced_hold=monitor.faulted() || monitor.clock_error();
            const auto pending_output=output_port.read();
            const auto now=now_ns();
            const auto begin=detailed ? now_ns() : 0;
            if(!plant.advance(now)) throw std::runtime_error("runtime physical step");
            if(forced_hold) {
                if(!plant.hold(now)) throw std::runtime_error("runtime independent hold");
                if(hold_at==0) hold_at=now;
            } else if(const auto& output=pending_output; output && applied_job!=output->job) {
                applied_job=output->job;
                if(now>output->deadline_ns) ++expired_outputs;
                else if(output->actuation.mode==steering::ActuationMode::Hold) {
                    if(!plant.hold(now)) throw std::runtime_error("runtime ECU hold");
                } else if(!plant.set_target(output->actuation.target_rad,now)) throw std::runtime_error("runtime target application");
                if(now<=output->deadline_ns) {
                    last_ecu_applied_job=static_cast<std::int64_t>(output->job);
                    output_issued=output->actuation.issued_time_ns; output_applied=now;
                }
            }
            inputs.sensor=plant.capture();
            const auto end=detailed ? now_ns() : 0;
            if(!inputs.sensor) throw std::runtime_error("runtime acquisition");
            if(now>=next_command) {
                can::SteeringMessage command;
                command.epoch=1; command.sequence=command_sequence++; command.source_time_ns=now;
                command.angle_rad=.3; command.local_state=can::SteeringLocalState::Normal; command.origin=can::SteeringOrigin::NormalPath;
                inputs.command=can::encode_steering_frame(command,tx);
                if(!inputs.command) throw std::runtime_error("runtime command codec");
                next_command=enable+((now-enable)/kPeriod+1)*kPeriod;
            }
            input_port.publish(inputs);
            if(detailed) append_bounded(plant_steps,PlantStep{now,begin,end,inputs.sensor->source_time_ns,
                inputs.sensor->sequence,inputs.sensor->angle_rad,forced_hold,last_ecu_applied_job,output_issued,output_applied},plant_drops);
            if(now>=stop_at) break;
            sleep_until(next_poll(enable,now_ns()));
        }
    } catch(...) { errors[2]=std::current_exception(); abort.store(true,std::memory_order_release); }
    control_thread.join(); watch_thread.join();
    auto job_file=open_output(directory/"jobs.csv");
    job_file << "job,release_ns,deadline_ns,start_ns,end_ns,ran,detected_ns,job_time_ns,prepare_begin_ns,prepare_end_ns,complete_begin_ns,complete_end_ns,input_source_ns,sensor_sequence,command_sequence,causal_sequence,feedback_source_ns,feedback_publish_ns,injection_begin_ns,injection_end_ns,prepared,fault,receive_decision,command_rx_ns,command_source_ns,feedback_valid,feedback_failsafe\n";
    for(std::size_t i=0;i<kJobs;++i) {
        const auto& r=jobs[i];
        job_file << i << ',' << schedule.release(i) << ',' << schedule.deadline(i) << ',' << r.start << ',' << r.end << ',' << r.ran
            << ',' << monitor.detected(i) << ',' << r.job_time << ',' << r.prepare_begin << ',' << r.prepare_end << ',' << r.complete_begin << ',' << r.complete_end
            << ',' << r.input_source << ',' << r.sensor_sequence << ',' << r.command_sequence << ',' << r.causal_sequence << ',' << r.feedback_source << ',' << r.feedback_at
            << ',' << r.injection_begin << ',' << r.injection_end << ',' << r.prepared << ',' << r.fault << ',' << r.receive_decision
            << ',' << r.command_rx << ',' << r.command_source << ',' << r.feedback_valid << ',' << r.feedback_failsafe << '\n';
    }
    auto plant_file=open_output(directory/"plant.csv");
    plant_file << "time_ns,physics_begin_ns,physics_end_ns,sensor_source_ns,sensor_sequence,angle_rad,override_hold,last_ecu_applied_job,output_issued_ns,output_applied_ns\n";
    for(const auto& r:plant_steps) plant_file << r.time << ',' << r.begin << ',' << r.end << ',' << r.sensor_source << ',' << r.sensor_sequence << ',' << r.angle << ',' << r.override_hold
        << ',' << r.last_ecu_applied_job << ',' << r.output_issued << ',' << r.output_applied << '\n';
    auto monitor_file=open_output(directory/"monitor.csv"); monitor_file << "time_ns,fault\n";
    for(const auto& r:monitor_steps) monitor_file << r.time << ',' << r.fault << '\n';
    auto metadata=open_output(directory/"run.json");
    metadata << "{\n  \"schema\": 1, \"scenario\": " << std::quoted(scenario) << ", \"detailed_trace\": " << (detailed?"true":"false")
        << ",\n  \"clock\": \"CLOCK_MONOTONIC\", \"enable_ns\": " << enable << ", \"stop_ns\": " << stop_at
        << ",\n  \"period_ns\": " << kPeriod << ", \"relative_deadline_ns\": " << kDeadline << ", \"monitor_period_ns\": " << kPoll
        << ", \"plant_period_ns\": " << kPoll << ", \"jobs\": " << kJobs << ", \"injected_job\": " << kInjectedJob
        << ",\n  \"application_epoch\": 1, \"model_epoch\": 1, \"minimum_ecu_call_ns\": " << kMs
        << ",\n  \"monitor_started_ns\": " << monitor_started << ", \"monitor_ended_ns\": " << monitor_ended << ", \"hold_applied_ns\": " << hold_at
        << ",\n  \"clock_resolution_ns\": " << static_cast<std::uint64_t>(resolution.tv_sec)*1000000000+static_cast<std::uint64_t>(resolution.tv_nsec)
        << ", \"clock_pair_samples\": 10000, \"clock_pair_p50_ns\": " << clock_probe[4999] << ", \"clock_pair_p99_ns\": " << clock_probe[9899]
        << ", \"clock_pair_max_ns\": " << clock_probe.back()
        << ",\n  \"input_snapshot_overwrites\": " << input_port.overwrites() << ", \"input_read_empty\": " << input_read_empty
        << ", \"output_snapshot_overwrites\": " << output_port.overwrites() << ", \"expired_outputs\": " << expired_outputs
        << ", \"trace_drops\": " << plant_drops+monitor_drops << ", \"monitor_clock_error\": " << (monitor.clock_error()?"true":"false")
        << ", \"aborted\": " << (abort.load()?"true":"false") << ",\n  \"threads\": [";
    for(std::size_t i=0;i<thread_info.size();++i) {
        if(i!=0) metadata << ',';
        metadata << "{\"role\": " << std::quoted(i==0?"ecu":i==1?"monitor":"plant_fixture") << ", \"policy\": " << thread_info[i].policy
            << ", \"priority\": " << thread_info[i].priority << ", \"observed_cpu\": " << thread_info[i].observed_cpu << ", \"allowed_cpus\": ";
        thread_info[i].write_affinity(metadata); metadata << '}';
    }
    metadata << "]\n}\n";
    metadata.close(); job_file.close(); plant_file.close(); monitor_file.close();
    for(const auto& error:errors) if(error) std::rethrow_exception(error);
    if(abort.load()) throw std::runtime_error("runtime aborted; inspect saved trace");
}
} // namespace stratadrive::simulation
