#include "multirate_runtime.hpp"
#include "multirate_fixture.hpp"
#include "runtime_support.hpp"
#include "latest_snapshot.hpp"
#include "periodic_task.hpp"
#include "receive_watch.hpp"
#include "actuator_socketcan.hpp"
#include "brake_actuator.hpp"
#include "brake_pressure_response.hpp"
#include "drive_controller.hpp"
#include "drive_sil_plant.hpp"
#include "ev_power_model.hpp"
#include "power_controller.hpp"

#include <array>
#include <atomic>
#include <exception>
#include <memory>
#include <thread>

namespace stratadrive::simulation {
namespace {
using namespace runtime_support;
using multirate_fixture::TrustedHistory;
constexpr std::uint64_t kMs=1000000,kPoll=2*kMs,kWindow=2400*kMs,kInjection=1100*kMs;
constexpr std::size_t kBrake=0,kDrive=1,kBms=2,kPower=3,kRx=4,kStreams=5;
constexpr std::array<const char*,5> kNames{"brake","drive","bms","power","rx"};
constexpr std::array<std::uint16_t,kStreams> kIds{0x181,0x182,0x193,0x194,0x183};
constexpr std::array<const char*,kStreams> kStreamNames{"brake_command","drive_command","drive_limits","drive_permission","power_request"};
struct Job {
    std::uint64_t start{0},end{0},phase{0},ecu_ns{0},source{0},input_sequence{0},report_source{0};
    std::uint64_t injected_begin{0},injected_end{0};
    unsigned accepted{0},rejected{0},raw{0};
    bool ran{false},prepared{false},reported{false},valid{false},active{false},inhibit{true};
    int fault{0},state{0};
    double selected{0};
};
struct Task {
    std::size_t role;
    runtime::TaskSchedule schedule;
    runtime::DeadlineMonitor monitor;
    std::vector<Job> rows;
    ThreadInfo thread;
    Task(std::size_t id, runtime::TaskScheduleConfig config)
        : role(id),schedule(config),monitor(schedule),rows(schedule.config().jobs) {}
};
struct PhysicalInputs {
    std::optional<brake::PressureMeasurement> pressure;
    std::optional<drive::TorqueMeasurement> torque;
    drive::LocalSensors local;
    battery::SensorSnapshot battery;
    std::optional<power::SensorSnapshot> power;
};
struct WireSample { socketcan::Frame frame; std::uint64_t arrival; };
struct RxInputs { std::array<std::optional<WireSample>,kStreams> stream{}; bool continuity_lost{false}; };
struct BrakeOutput { brake::Actuation actuation; std::uint64_t deadline; std::size_t job; std::optional<can::BrakeFrame> report; };
struct DriveOutput { drive::Actuation actuation; std::uint64_t deadline; std::size_t job; std::optional<can::DriveFrame> report; };
struct BmsOutput { std::optional<can::BmsMessage> message; bool active; };
struct PowerOutput { vecu::PowerControlOutput output; std::optional<can::BmsMessage> message; std::uint64_t deadline; std::size_t job; };
struct PhysicalRow {
    std::uint64_t time,begin,end,brake_source,torque_source;
    double pressure,torque,bus,current,soc,balance;
    bool floor,zero,bms_inhibit,positive,negative;
    int power_phase;
};
struct MonitorRow { std::uint64_t time; unsigned tasks,streams; bool floor,zero,bms_inhibit; };
struct RawRow { std::uint64_t time,source; std::size_t stream; std::uint32_t drops; bool crc_ok; };

template<class Body> void execute(Task& task, std::atomic<bool>& abort, Body body) {
    task.thread.capture();
    for(std::size_t next=0;next<task.rows.size() && !abort.load(std::memory_order_acquire);) {
        sleep_until(task.schedule.release(next)); const auto start=now_ns();
        const auto selected=task.schedule.newest_released(start,next);
        if(!selected) continue;
        const auto i=*selected; next=i+1;
        if(start>=task.schedule.deadline(i)) continue;
        auto& row=task.rows[i]; row.ran=true; row.start=start;
        body(row,i); row.end=now_ns();
        if(!task.monitor.finish(i,row.end)) throw std::runtime_error("multirate duplicate completion");
    }
}
void inject(Job& row, const Task& task, bool enabled, std::size_t i, std::uint64_t enable) {
    if(!enabled ||
        i!=static_cast<std::size_t>((kInjection-(task.schedule.release(0)-enable))/task.schedule.config().period_ns)) return;
    row.injected_begin=now_ns(); sleep_until(row.injected_begin+120*kMs); row.injected_end=now_ns();
}
bool timely(const Task& task, std::size_t job) { return now_ns()<=task.schedule.deadline(job); }
template<class Result> void accepted(const Result& result, std::size_t stream, Job& row,
        std::array<std::atomic<std::uint64_t>,kStreams>& valid_rx) {
    if(result.decision==can::ActuatorReceiveDecision::Accepted) {
        valid_rx[stream].store(now_ns(),std::memory_order_release); row.accepted|=1U<<stream;
    } else ++row.rejected;
}
std::optional<can::BmsParentContext> parent_for(const TrustedHistory& history, const can::BmsFrame& frame) {
    const auto entry=history.find(frame); return entry ? entry->parent : std::nullopt;
}
} // namespace

void run_multirate_runtime(const MultirateRuntimeOptions& options) {
    const auto& scenario=options.scenario;
    const auto& interface_name=options.interface_name;
    const auto& directory=options.directory;
    const bool detailed=options.detailed_trace;
    if(scenario!="normal" && scenario!="brake-stall" && scenario!="drive-stall" && scenario!="bms-stall" &&
        scenario!="power-stall" && scenario!="rx-stall" && scenario!="rx-corrupt") throw std::invalid_argument("multirate-runtime scenario");
    if(!std::filesystem::create_directories(directory)) throw std::invalid_argument("runtime output directory must be new");
    socketcan::Endpoint tx(interface_name);
    std::array<std::unique_ptr<socketcan::Endpoint>,kStreams> sockets;
    for(std::size_t i=0;i<kStreams;++i) sockets[i]=std::make_unique<socketcan::Endpoint>(interface_name,kIds[i]);
    const auto enable=now_ns()+100*kMs,stop_at=enable+kWindow+40*kMs;
    Task brake_task(kBrake,{enable+10*kMs,10*kMs,5*kMs,240}),drive_task(kDrive,{enable+10*kMs,10*kMs,5*kMs,240}),
         bms_task(kBms,{enable+5*kMs,20*kMs,8*kMs,120}),power_task(kPower,{enable+8*kMs,10*kMs,5*kMs,240}),
         rx_task(kRx,{enable+2*kMs,2*kMs,3*kMs,1200});
    const std::array<Task*,5> tasks{&brake_task,&drive_task,&bms_task,&power_task,&rx_task};
    const std::array<bool,5> stalls{scenario=="brake-stall",scenario=="drive-stall",scenario=="bms-stall",scenario=="power-stall",scenario=="rx-stall"};
    std::array<runtime::LatestSnapshot<PhysicalInputs>,4> physical_ports;
    std::array<runtime::LatestSnapshot<RxInputs>,3> rx_ports; // Brake, Drive, Power: never multiple readers of one port
    runtime::LatestSnapshot<BrakeOutput> brake_output;
    runtime::LatestSnapshot<DriveOutput> drive_output;
    runtime::LatestSnapshot<BmsOutput> bms_output;
    runtime::LatestSnapshot<PowerOutput> power_output;
    runtime::LatestSnapshot<std::optional<power::BmsSafetyGate>> bms_to_power;
    runtime::LatestSnapshot<TrustedHistory> request_context,permission_context;
    std::array<std::atomic<std::uint64_t>,kStreams> valid_rx{};
    for(auto& value:valid_rx) value.store(0,std::memory_order_relaxed);
    std::array<runtime::ReceiveWatch,kStreams> receive_watches{
        runtime::ReceiveWatch(enable,80*kMs),runtime::ReceiveWatch(enable,80*kMs),runtime::ReceiveWatch(enable,80*kMs),
        runtime::ReceiveWatch(enable,80*kMs),runtime::ReceiveWatch(enable,80*kMs)};
    std::atomic<bool> abort{false},floor_override{false},zero_override{false},bms_inhibit{false};
    std::array<std::exception_ptr,7> errors{};
    ThreadInfo monitor_thread_info,plant_thread_info;
    std::uint64_t floor_at=0,zero_at=0,monitor_end=0;
    std::size_t physical_drops=0,monitor_drops=0,raw_drops=0,expired_outputs=0;
    std::vector<PhysicalRow> physical_rows; physical_rows.reserve(2600);
    std::vector<MonitorRow> monitor_rows; monitor_rows.reserve(2600);
    std::vector<RawRow> raw_rows; raw_rows.reserve(4000);
    std::optional<PhysicalRow> final_physical;
    auto watch=[&] {
        monitor_thread_info.capture(); sleep_until(enable);
        while(!abort.load(std::memory_order_acquire)) {
            std::array<std::optional<std::uint64_t>,kStreams> captures{};
            for(std::size_t i=0;i<kStreams;++i) { const auto value=valid_rx[i].load(std::memory_order_acquire); if(value!=0) captures[i]=value; }
            const auto now=now_ns(); unsigned task_bits=0,stream_bits=0;
            for(std::size_t i=0;i<tasks.size();++i) {
                tasks[i]->monitor.poll(now);
                if(tasks[i]->monitor.faulted() || tasks[i]->monitor.clock_error()) task_bits|=1U<<i;
            }
            for(std::size_t i=0;i<kStreams;++i) {
                const auto state=receive_watches[i].poll(captures[i],now);
                if(state==runtime::ReceiveHealth::Timeout || state==runtime::ReceiveHealth::ClockError) stream_bits|=1U<<i;
            }
            if((task_bits & ((1U<<kBrake)|(1U<<kRx))) || (stream_bits&1U)) floor_override.store(true,std::memory_order_release);
            if((task_bits & ((1U<<kDrive)|(1U<<kBms)|(1U<<kPower)|(1U<<kRx))) || (stream_bits&30U)) zero_override.store(true,std::memory_order_release);
            if(task_bits & (1U<<kBms)) bms_inhibit.store(true,std::memory_order_release);
            if(detailed) append_bounded(monitor_rows,MonitorRow{now,task_bits,stream_bits,floor_override.load(),zero_override.load(),bms_inhibit.load()},monitor_drops);
            if(now>=stop_at) break;
            sleep_until(next_wake(enable,kPoll,now_ns()));
        }
        monitor_end=now_ns();
    };
    auto brake=[&] {
        vecu::BrakeActuatorConfig config{2000000,1500000,0,5000000,10000000,1000000,50*kMs}; config.period_ns=kMs;
        vecu::BrakeActuator ecu(config); if(!ecu.start_session({1,7,enable})) throw std::runtime_error("Brake INIT");
        execute(brake_task,abort,[&](Job& row,std::size_t i) {
            const auto physical=physical_ports[kBrake].read(); const auto rx=rx_ports[0].read(); const bool blocked=floor_override.load(); row.phase=now_ns();
            if(blocked) ecu.mark_output_rejected(row.phase);
            if(rx && rx->continuity_lost) ecu.mark_continuity_lost(row.phase);
            if(rx && rx->stream[0]) accepted(ecu.receive(socketcan::to_brake(rx->stream[0]->frame),row.phase),0,row,valid_rx);
            const auto sensor=physical ? physical->pressure : std::nullopt;
            if(sensor) { row.source=sensor->source_time_ns; row.input_sequence=sensor->sequence; }
            auto begin=now_ns(); row.prepared=ecu.prepare(row.phase); row.ecu_ns+=now_ns()-begin;
            inject(row,brake_task,stalls[kBrake],i,enable);
            begin=now_ns(); const auto message=row.prepared ? ecu.complete(sensor,row.phase) : std::nullopt; row.ecu_ns+=now_ns()-begin;
            const bool on_time=timely(brake_task,i);
            const bool newly_faulted=floor_override.load() && ecu.fault()==vecu::BrakeFault::None;
            if(!on_time || floor_override.load()) ecu.mark_output_rejected(now_ns());
            row.reported=message.has_value() && on_time && !newly_faulted;
            brake_output.publish({ecu.output(),brake_task.schedule.deadline(i),i,row.reported ? message : std::nullopt});
            if(row.reported) { const auto m=can::decode_brake_frame(*message); if(!m) throw std::runtime_error("Brake report"); row.report_source=m->source_time_ns; row.valid=m->pressure_pa.has_value(); }
            row.fault=static_cast<int>(ecu.fault()); row.selected=ecu.output().target_pa;
        });
    };
    auto drive=[&] {
        vecu::DriveControllerConfig config; config.period_ns=kMs; config.fixed_power_reserve_w=500;
        vecu::DriveController ecu(config); if(!ecu.start_session({1,7,enable})) throw std::runtime_error("Drive INIT");
        execute(drive_task,abort,[&](Job& row,std::size_t i) {
            const auto physical=physical_ports[kDrive].read(); const auto rx=rx_ports[1].read(); const auto history=permission_context.read(); const bool blocked=zero_override.load(); row.phase=now_ns();
            if(blocked) ecu.mark_output_rejected(row.phase);
            if(rx && rx->continuity_lost) ecu.mark_continuity_lost(row.phase);
            if(rx && rx->stream[1]) accepted(ecu.receive_command(socketcan::to_drive(rx->stream[1]->frame),row.phase),1,row,valid_rx);
            if(rx && rx->stream[2]) accepted(ecu.receive_limits(socketcan::to_bms(rx->stream[2]->frame),row.phase),2,row,valid_rx);
            if(rx && rx->stream[3]) {
                const auto f=socketcan::to_bms(rx->stream[3]->frame); const auto parent=history ? parent_for(*history,f) : std::nullopt;
                accepted(ecu.receive_permission(f,row.phase,parent ? &*parent : nullptr),3,row,valid_rx);
            }
            if(physical) ecu.observe_local(physical->local,row.phase);
            const auto sensor=physical ? physical->torque : std::nullopt;
            if(sensor) { row.source=sensor->source_time_ns; row.input_sequence=sensor->sequence; }
            auto begin=now_ns(); row.prepared=ecu.prepare(row.phase); row.ecu_ns+=now_ns()-begin;
            inject(row,drive_task,stalls[kDrive],i,enable);
            begin=now_ns(); const auto message=row.prepared ? ecu.complete(sensor,row.phase) : std::nullopt; row.ecu_ns+=now_ns()-begin;
            const bool on_time=timely(drive_task,i);
            const bool newly_faulted=zero_override.load() && ecu.decision().fault==vecu::DriveGateFault::None;
            if(!on_time || zero_override.load()) ecu.mark_output_rejected(now_ns());
            row.reported=message.has_value() && on_time && !newly_faulted;
            drive_output.publish({ecu.output(),drive_task.schedule.deadline(i),i,row.reported ? message : std::nullopt});
            if(row.reported) { const auto m=can::decode_drive_frame(*message); if(!m) throw std::runtime_error("Drive report"); row.report_source=m->source_time_ns; row.valid=m->torque_nm.has_value(); }
            row.fault=static_cast<int>(ecu.decision().fault); row.active=ecu.decision().active; row.selected=ecu.output().target_nm;
        });
    };
    auto bms=[&] {
        vecu::BmsController ecu(multirate_fixture::bms_config()); if(!ecu.start_session(1,7,enable)) throw std::runtime_error("BMS INIT");
        execute(bms_task,abort,[&](Job& row,std::size_t i) {
            const auto input=physical_ports[kBms].read(); row.phase=now_ns();
            if(input) { row.source=input->battery.batch.source_time_ns; row.input_sequence=input->battery.batch.sequence; }
            inject(row,bms_task,stalls[kBms],i,enable);
            const auto begin=now_ns(); const auto m=ecu.tick(input ? input->battery : battery::SensorSnapshot{},row.phase); row.ecu_ns=now_ns()-begin;
            row.reported=m.has_value() && timely(bms_task,i);
            if(row.reported) { bms_output.publish({m,ecu.decision().state==vecu::BmsControlState::Active}); bms_to_power.publish(ecu.power_gate()); row.report_source=m->source_time_ns; }
            row.fault=static_cast<int>(ecu.decision().fault); row.state=static_cast<int>(ecu.decision().state); row.inhibit=ecu.decision().inhibit_requested;
        });
    };
    auto power=[&] {
        vecu::PowerControllerConfig config; config.period_ns=kMs; config.opening_current_max_a=.5;
        vecu::PowerController ecu(config); if(!ecu.start_session(1,7,enable)) throw std::runtime_error("Power INIT");
        execute(power_task,abort,[&](Job& row,std::size_t i) {
            const auto input=physical_ports[kPower].read(); const auto rx=rx_ports[2].read(); const auto history=request_context.read(); const auto gate=bms_to_power.read(); const bool inhibited=bms_inhibit.load(); row.phase=now_ns();
            if(rx && rx->continuity_lost) ecu.mark_continuity_lost(row.phase);
            if(rx && rx->stream[4]) {
                const auto f=socketcan::to_bms(rx->stream[4]->frame); const auto parent=history ? parent_for(*history,f) : std::nullopt;
                accepted(ecu.receive(f,row.phase,parent ? &*parent : nullptr),4,row,valid_rx);
            }
            const auto sensor=input ? input->power : std::nullopt;
            if(sensor) { row.source=sensor->identity.source_time_ns; row.input_sequence=sensor->identity.sequence; }
            inject(row,power_task,stalls[kPower],i,enable);
            const auto begin=now_ns(); const auto m=ecu.tick(sensor,inhibited ? std::nullopt : gate.value_or(std::nullopt),row.phase); row.ecu_ns=now_ns()-begin;
            row.reported=m.has_value() && timely(power_task,i);
            if(row.reported) { power_output.publish({ecu.output(),m,power_task.schedule.deadline(i),i}); row.report_source=m->source_time_ns; }
            row.fault=static_cast<int>(ecu.output().fault); row.state=static_cast<int>(ecu.output().phase); row.inhibit=ecu.output().inhibit_drive;
        });
    };
    auto receive=[&] {
        RxInputs latest; std::size_t cursor=0;
        execute(rx_task,abort,[&](Job& row,std::size_t i) {
            row.phase=now_ns(); inject(row,rx_task,stalls[kRx],i,enable);
            unsigned empty=0;
            while(row.raw<8 && empty<kStreams) {
                const auto stream=cursor; cursor=(cursor+1)%kStreams;
                const auto packet=sockets[stream]->receive();
                if(!packet) { ++empty; continue; }
                empty=0; ++row.raw; const auto arrival=now_ns();
                latest.stream[stream]=WireSample{packet->frame,arrival};
                if(packet->dropped_frames) latest.continuity_lost=true;
                std::uint64_t source=0; bool crc=false;
                if(stream==0) { const auto m=can::decode_brake_frame(socketcan::to_brake(packet->frame)); if(m) { source=m->source_time_ns; crc=true; } }
                else if(stream==1) { const auto m=can::decode_drive_frame(socketcan::to_drive(packet->frame)); if(m) { source=m->source_time_ns; crc=true; } }
                else { const auto m=can::decode_bms_frame(socketcan::to_bms(packet->frame)); if(m) { source=m->source_time_ns; crc=true; } }
                if(detailed) append_bounded(raw_rows,RawRow{arrival,source,stream,packet->dropped_frames,crc},raw_drops);
            }
            if(row.raw) for(auto& port:rx_ports) port.publish(latest);
        });
    };
    std::vector<std::thread> threads; threads.reserve(6);
    auto launch=[&](std::size_t owner,auto body) {
        threads.emplace_back([&,owner,body] { try { body(); } catch(...) { errors[owner]=std::current_exception(); abort.store(true,std::memory_order_release); } });
    };
    try { launch(5,watch); launch(0,brake); launch(1,drive); launch(2,bms); launch(3,power); launch(4,receive); }
    catch(...) { abort.store(true,std::memory_order_release); for(auto& t:threads) t.join(); throw; }
    try {
        plant_thread_info.capture();
        BrakePressureResponse pressure({1500000,0,5000000,10000000,50*kMs,7}); if(!pressure.begin(enable)) throw std::runtime_error("pressure INIT");
        DriveSilPlant torque({-200,300,0,1000,2000,50*kMs}); torque.begin(7,enable);
        EvPowerModel electrical({}, {180000000,400,.05,200000,20,25,100,.01,1,100000}, {.002,50,.02,100,1000,500});
        if(!electrical.initialize({7,enable,.5,25},0)) throw std::runtime_error("EV INIT");
        can::BrakeTxState brake_tx{can::BrakeFrameKind::Command}; can::DriveTxState drive_tx{can::DriveFrameKind::Command};
        can::BmsTxState limits_tx{can::BmsFrameKind::DriveBatteryLimits},request_tx{can::BmsFrameKind::PowerRequest},permission_tx{can::BmsFrameKind::DrivePermission};
        TrustedHistory requests,permissions; std::optional<std::uint32_t> forwarded_limits;
        std::uint32_t sequence=0,physical_sequence=0; std::uint64_t begin=enable,next_command=enable;
        std::optional<std::size_t> brake_applied,drive_applied,power_applied;
        vecu::PowerControlOutput power_state; std::optional<can::BmsMessage> power_status; bool bms_active=false;
        auto send=[&](socketcan::Frame frame) { frame.fd_flags|=4; if(scenario=="rx-corrupt" && now_ns()-enable>=kInjection) frame.payload[7]^=1; tx.send(frame); };
        sleep_until(enable);
        while(!abort.load(std::memory_order_acquire)) {
            // Acquire every external decision before its application clock.
            // A flag published during physics belongs to the NEXT interval.
            const bool floor=floor_override.load(std::memory_order_acquire),zero=zero_override.load(std::memory_order_acquire);
            const bool captured_bms_inhibit=bms_inhibit.load(std::memory_order_acquire);
            const auto brake_request=brake_output.read(); const auto drive_request=drive_output.read();
            const auto power_request=power_output.read(); const auto limits=bms_output.read();
            const auto now=now_ns(),cost_begin=now_ns();
            const double old_torque=torque.actual_nm(); const battery::ModelIdentity id{7,physical_sequence++,begin};
            const bool inverter=old_torque!=0 || (power_state.phase==vecu::PowerPhase::Ready && !power_state.inhibit_drive);
            const EvPowerInputs inputs{battery::ModelMeasurement<double>{old_torque,id,begin},battery::ModelMeasurement<double>{20,id,begin},
                battery::ModelMeasurement<EvElectricalEnvironment>{{.375,inverter},id,begin}};
            const auto energy=electrical.step({begin,now,inputs,power_state.coils.value_or(power::CoilCommand{})});
            if(energy.fault!=EvPowerFault::None) throw std::runtime_error("multirate EV physical fault="+std::to_string(static_cast<int>(energy.fault)));
            if(!pressure.advance(now) || !torque.advance(now,false)) throw std::runtime_error("multirate actuator physical step");
            if(floor) { if(!pressure.request_protection(1000000,now)) throw std::runtime_error("independent brake floor"); if(!floor_at) floor_at=now; }
            else if(const auto& out=brake_request; out && brake_applied!=out->job) {
                brake_applied=out->job;
                if(now>out->deadline) ++expired_outputs;
                else if(out->actuation.mode==brake::ActuationMode::Protect) { if(!pressure.request_protection(out->actuation.target_pa,now)) throw std::runtime_error("brake protection output"); }
                else if(out->actuation.mode==brake::ActuationMode::Target) { if(!pressure.set_target(out->actuation.target_pa,now)) throw std::runtime_error("brake target output"); }
            }
            if(zero) { if(!torque.apply({drive::ActuationMode::Zero,0,drive::TorqueEnvelope{0,0},now})) throw std::runtime_error("independent torque zero"); if(!zero_at) zero_at=now; }
            else if(const auto& out=drive_request; out && drive_applied!=out->job) {
                drive_applied=out->job;
                if(now>out->deadline) ++expired_outputs;
                else { auto request=out->actuation; request.issued_time_ns=now; if(!torque.apply(request)) throw std::runtime_error("drive output"); }
            }
            if(const auto& out=power_request; out && power_applied!=out->job) {
                power_applied=out->job;
                if(now<=out->deadline) { power_state=out->output; power_status=out->message; }
                else ++expired_outputs;
            }
            const auto& state=electrical.power_state();
            PhysicalInputs snapshot; snapshot.pressure=pressure.capture(); snapshot.torque=torque.capture(now);
            snapshot.battery=electrical.battery_observation(); snapshot.power=electrical.power_observation();
            snapshot.local={battery::ModelMeasurement<double>{20,state.identity,begin},battery::ModelMeasurement<drive::HvFeedback>{{state.bus_voltage_v,
                state.bus_voltage_v>=300 && state.contactors.positive && state.contactors.negative,false},state.identity,begin}};
            if(!snapshot.pressure || !snapshot.torque) throw std::runtime_error("multirate acquisition");
            for(auto& port:physical_ports) port.publish(snapshot);
            const auto cost_end=now_ns();
            if(limits) {
                bms_active=limits->active;
                if(limits->message && forwarded_limits!=limits->message->sequence) {
                    const auto frame=can::forward_bms_limits(*limits->message,limits_tx); if(!frame) throw std::runtime_error("limits relay");
                    send(socketcan::to_socketcan(*frame)); forwarded_limits=limits->message->sequence;
                }
            }
            if(now>=next_command) {
                can::BrakeMessage brake_message; brake_message.epoch=1; brake_message.sequence=sequence; brake_message.source_time_ns=now;
                brake_message.origin=can::ActuatorOrigin::NormalPath; brake_message.local_state=can::ActuatorLocalState::Normal;
                brake_message.pressure_pa=now-enable<1000*kMs ? 300000 : 1300000;
                const auto bf=can::encode_brake_frame(brake_message,brake_tx); if(!bf) throw std::runtime_error("brake TX"); send(socketcan::to_socketcan(*bf));
                can::DriveMessage drive_message; drive_message.epoch=1; drive_message.sequence=sequence; drive_message.source_time_ns=now;
                drive_message.origin=can::ActuatorOrigin::NormalPath; drive_message.local_state=can::ActuatorLocalState::Normal;
                drive_message.torque_nm=now-enable<800*kMs ? 0 : now-enable<1000*kMs ? 150 : 250;
                const auto df=can::encode_drive_frame(drive_message,drive_tx); if(!df) throw std::runtime_error("drive TX"); send(socketcan::to_socketcan(*df));
                const can::BmsParentContext request_parent{1,10000+sequence,now,now+60*kMs};
                can::BmsMessage request; request.kind=can::BmsFrameKind::PowerRequest; request.epoch=1; request.sequence=sequence;
                request.source_time_ns=now; request.causal_sequence=request_parent.sequence; request.origin=can::ActuatorOrigin::NormalPath;
                request.content=can::BmsPowerRequest{can::BmsPowerAction::Enable,request_parent.expires_at_ns,now};
                auto rf=can::encode_bms_frame(request,request_tx); if(!rf) throw std::runtime_error("power request TX"); rf->fd_flags|=4;
                requests.issue(*rf,request_parent); request_context.publish(requests); send(socketcan::to_socketcan(*rf));
                const bool allow=power_status && power_state.phase==vecu::PowerPhase::Ready && !power_state.inhibit_drive && bms_active &&
                    now-power_status->source_time_ns<=50*kMs;
                const can::BmsParentContext grant_parent{1,100000+sequence,now,now+60*kMs};
                can::BmsMessage grant; grant.kind=can::BmsFrameKind::DrivePermission; grant.epoch=1; grant.sequence=sequence;
                grant.source_time_ns=now; grant.causal_sequence=grant_parent.sequence; grant.origin=can::ActuatorOrigin::NormalPath; grant.local_state=can::ActuatorLocalState::Normal;
                const auto status=power_status ? std::get<can::BmsPowerStatus>(power_status->content) : can::BmsPowerStatus{};
                grant.content=can::BmsDriveGrant{allow ? can::BmsDrivePermission::AllowNormal : can::BmsDrivePermission::Inhibit,
                    allow ? power_status->sequence : 0,allow ? power_status->source_time_ns : 0,allow ? status.input_time_ns : 0,now+60*kMs};
                auto gf=can::encode_bms_frame(grant,permission_tx); if(!gf) throw std::runtime_error("permission TX"); gf->fd_flags|=4;
                permissions.issue(*gf,allow ? std::optional<can::BmsParentContext>{grant_parent} : std::nullopt); permission_context.publish(permissions); send(socketcan::to_socketcan(*gf));
                ++sequence; next_command=next_wake(enable,10*kMs,now);
            }
            final_physical=PhysicalRow{now,cost_begin,cost_end,snapshot.pressure->source_time_ns,snapshot.torque->source_time_ns,
                snapshot.pressure->pressure_pa,snapshot.torque->torque_nm,state.bus_voltage_v,snapshot.power && snapshot.power->pack_current_a ? *snapshot.power->pack_current_a : 0,
                electrical.battery_state().soc,electrical.diagnostic_state().balance_error_j,floor,zero,captured_bms_inhibit,state.contactors.positive,state.contactors.negative,
                static_cast<int>(power_state.phase)};
            if(detailed) append_bounded(physical_rows,*final_physical,physical_drops);
            begin=now;
            if(now>=stop_at) break;
            sleep_until(next_wake(enable,kPoll,now_ns()));
        }
    } catch(...) { errors[6]=std::current_exception(); abort.store(true,std::memory_order_release); }
    for(auto& thread:threads) thread.join();
    for(const auto* task:tasks) {
        auto out=open_output(directory/(std::string(kNames[task->role])+"-jobs.csv"));
        out << "job,release_ns,deadline_ns,start_ns,end_ns,ran,detected_ns,phase_ns,ecu_elapsed_ns,input_source_ns,input_sequence,report_source_ns,reported,value_valid,accepted_mask,rejected,raw_frames,injection_begin_ns,injection_end_ns,prepared,fault,state,active,inhibit,selected\n";
        for(std::size_t i=0;i<task->rows.size();++i) { const auto& r=task->rows[i];
            out << i << ',' << task->schedule.release(i) << ',' << task->schedule.deadline(i) << ',' << r.start << ',' << r.end << ',' << r.ran << ',' << task->monitor.detected(i)
                << ',' << r.phase << ',' << r.ecu_ns << ',' << r.source << ',' << r.input_sequence << ',' << r.report_source << ',' << r.reported << ',' << r.valid
                << ',' << r.accepted << ',' << r.rejected << ',' << r.raw << ',' << r.injected_begin << ',' << r.injected_end << ',' << r.prepared << ',' << r.fault
                << ',' << r.state << ',' << r.active << ',' << r.inhibit << ',' << r.selected << '\n'; }
    }
    auto p=open_output(directory/"physical.csv"); p << "time_ns,physics_begin_ns,physics_end_ns,brake_source_ns,torque_source_ns,pressure_pa,torque_nm,bus_v,current_a,soc,balance_j,independent_floor,independent_zero,bms_inhibit,positive,negative,power_phase\n";
    for(const auto& r:physical_rows) p << r.time << ',' << r.begin << ',' << r.end << ',' << r.brake_source << ',' << r.torque_source << ',' << r.pressure << ',' << r.torque << ',' << r.bus << ',' << r.current << ',' << r.soc << ',' << r.balance << ',' << r.floor << ',' << r.zero << ',' << r.bms_inhibit << ',' << r.positive << ',' << r.negative << ',' << r.power_phase << '\n';
    auto w=open_output(directory/"monitor.csv"); w << "time_ns,task_fault_mask,stream_fault_mask,floor,zero,bms_inhibit\n";
    for(const auto& r:monitor_rows) w << r.time << ',' << r.tasks << ',' << r.streams << ',' << r.floor << ',' << r.zero << ',' << r.bms_inhibit << '\n';
    auto raw=open_output(directory/"can-rx.csv"); raw << "time_ns,source_ns,stream,kernel_drops,crc_ok\n";
    for(const auto& r:raw_rows) raw << r.time << ',' << r.source << ',' << r.stream << ',' << r.drops << ',' << r.crc_ok << '\n';
    auto meta=open_output(directory/"run.json");
    meta << "{\n\"schema\": 2, \"family\": \"multirate\", \"scenario\": " << std::quoted(scenario) << ", \"detailed_trace\": " << (detailed?"true":"false")
        << ", \"clock\": \"CLOCK_MONOTONIC\", \"enable_ns\": " << enable << ", \"stop_ns\": " << stop_at << ", \"injection_offset_ns\": " << kInjection
        << ", \"monitor_period_ns\": " << kPoll << ", \"plant_period_ns\": " << kPoll << ", \"monitor_ended_ns\": " << monitor_end
        << ", \"floor_applied_ns\": " << floor_at << ", \"zero_applied_ns\": " << zero_at << ", \"expired_outputs\": " << expired_outputs
        << ", \"trace_drops\": " << physical_drops+monitor_drops+raw_drops << ", \"aborted\": " << (abort.load()?"true":"false")
        << ", \"drive_torque_wire\": \"unavailable for asynchronous acquisition; original P05/ICD unchanged\""
        << ", \"monitor_policy\": " << monitor_thread_info.policy << ", \"plant_policy\": " << plant_thread_info.policy
        << ", \"rx_budget\": 8, \"final_physical\": ";
    if(final_physical) meta << "{\"pressure_pa\":" << final_physical->pressure << ",\"torque_nm\":" << final_physical->torque
        << ",\"bus_v\":" << final_physical->bus << ",\"soc\":" << final_physical->soc << ",\"balance_j\":" << final_physical->balance << '}';
    else meta << "null";
    meta << ", \"tasks\": [";
    for(std::size_t i=0;i<tasks.size();++i) { if(i) meta << ','; const auto& t=*tasks[i]; const auto& c=t.schedule.config();
        meta << "{\"name\":" << std::quoted(kNames[i]) << ",\"period_ns\":" << c.period_ns << ",\"deadline_ns\":" << c.relative_deadline_ns
            << ",\"first_release_ns\":" << c.first_release_ns << ",\"jobs\":" << c.jobs << ",\"policy\":" << t.thread.policy << ",\"priority\":" << t.thread.priority << '}'; }
    meta << "],\n\"threads\": {";
    for(std::size_t i=0;i<tasks.size();++i) { if(i) meta << ','; meta << std::quoted(kNames[i]) << ':'; tasks[i]->thread.write_json(meta); }
    meta << ",\"monitor\":"; monitor_thread_info.write_json(meta);
    meta << ",\"plant_fixture\":"; plant_thread_info.write_json(meta);
    meta << "},\n\"streams\": [";
    for(std::size_t i=0;i<kStreams;++i) { if(i) meta << ','; meta << "{\"name\":" << std::quoted(kStreamNames[i]) << ",\"last_valid_ns\":" << receive_watches[i].last_valid().value_or(0)
        << ",\"detected_ns\":" << receive_watches[i].detected().value_or(0) << ",\"health\":" << static_cast<int>(receive_watches[i].health()) << '}'; }
    meta << "],\n\"input_snapshot_overwrites\": [";
    for(std::size_t i=0;i<physical_ports.size();++i) { if(i) meta << ','; meta << physical_ports[i].overwrites(); }
    meta << "],\"rx_snapshot_overwrites\": [";
    for(std::size_t i=0;i<rx_ports.size();++i) { if(i) meta << ','; meta << rx_ports[i].overwrites(); }
    meta << "]\n}\n";
    meta.close(); p.close(); w.close(); raw.close();
    for(const auto& error:errors) if(error) std::rethrow_exception(error);
}
} // namespace stratadrive::simulation
