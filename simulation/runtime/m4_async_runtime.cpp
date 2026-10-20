#include "m4_async_runtime.hpp"

#include "async_leaf_owner.hpp"
#include "async_coordinator_port.hpp"
#include "async_zone_owner.hpp"
#include "session_loop.hpp"
#include "ev_power_model.hpp"
#include "drive_sil_plant.hpp"
#include "steering_response.hpp"
#include "brake_pressure_response.hpp"
#include "runtime_support.hpp"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <memory>
#include <thread>
#include <string_view>
#include <new>

namespace stratadrive::simulation {
namespace {
constexpr std::uint64_t kMs=1000000,kIoPoll=200000,kLogicalStart=1000000000;
std::uint64_t cpu_now() { timespec t{}; if(clock_gettime(CLOCK_THREAD_CPUTIME_ID,&t)!=0) throw std::runtime_error("thread CPU clock"); return static_cast<std::uint64_t>(t.tv_sec)*1000000000+static_cast<std::uint64_t>(t.tv_nsec); }
std::uint64_t wall_now() { return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count()); }
class Clock final : public transport::Clock {
public:
    explicit Clock(bool wall):wall_(wall) {}
    std::uint64_t logical{kLogicalStart};
    std::uint64_t now_ns() noexcept override { return wall_?wall_now():logical; }
private: bool wall_;
};
struct Audit {
    std::thread::id owner{}; bool valid{true}; std::uint64_t last_poll{0},last_runnable{0},poll_gap{0},runnable_gap{0};
    std::vector<std::uint64_t> durations;
    void enter(std::uint64_t now) {
        if(owner==std::thread::id{}) owner=std::this_thread::get_id(); else valid=valid && owner==std::this_thread::get_id();
        if(last_poll) poll_gap=std::max(poll_gap,now-last_poll);
        last_poll=now;
    }
    void runnable(std::uint64_t now) { if(now!=0 && now!=last_runnable) { if(last_runnable) runnable_gap=std::max(runnable_gap,now-last_runnable); last_runnable=now; } }
    M4Timing result(std::string name) {
        M4Timing r; r.owner=std::move(name); r.samples=durations.size(); if(durations.empty()) return r;
        std::sort(durations.begin(),durations.end()); double sum=0;
        for(const auto d:durations) { sum+=static_cast<double>(d); if(d>4000000) ++r.body_over_4ms; }
        const auto count=static_cast<double>(durations.size());
        const auto percentile=[&](double p) { return static_cast<double>(durations[static_cast<std::size_t>(std::ceil(p*count))-1])/1000; };
        r.mean_body_us=sum/count/1000; r.p95_body_us=percentile(.95); r.p99_body_us=percentile(.99);
        r.max_body_us=static_cast<double>(durations.back())/1000; r.max_poll_gap_ms=static_cast<double>(poll_gap)/kMs; r.max_runnable_gap_ms=static_cast<double>(runnable_gap)/kMs;
        return r;
    }
};
class PhysicalOwner {
public:
    PhysicalOwner(Clock& clock,transport::RunGate& gate,std::array<runtime::LatestSnapshot<OwnerSensors>,session::kRoleCount>& sensors,
        std::array<runtime::LatestSnapshot<OwnerActuation>,transport::kLeaves>& outputs,std::uint64_t start,std::vector<M4Event>& events,transport::Protection& override_signal,std::uint32_t first_epoch)
        :clock_(clock),gate_(gate),sensors_(sensors),outputs_(outputs),events_(events),override_(override_signal),released_epoch_(first_epoch),start_(start) {}
    void step() {
        const auto released_at_start=gate_.epoch(); if(released_at_start>released_epoch_) released_epoch_=released_at_start;
        const bool force_at_start=override_.pending(released_epoch_);
        const auto now=clock_.now_ns();
        if(!begun_) {
            begun_=true; last_=now; motor_.begin(7,now);
            ok_=angles_.begin(now) && pressure_.begin(now) && energy_.initialize({7,now,.63,25},0); return;
        }
        if(!ok_ || now<=last_) return;
        const battery::ModelIdentity id{7,sequence_++,last_};
        const double old_torque=motor_.actual_nm();
        const auto& p=energy_.power_state();
        const bool inverter=(p.contactors.positive && p.contactors.negative && p.bus_voltage_v>=300) || std::abs(old_torque)>1e-9;
        const EvPowerInputs inputs{battery::ModelMeasurement<double>{old_torque,id,last_},battery::ModelMeasurement<double>{0,id,last_},
            battery::ModelMeasurement<EvElectricalEnvironment>{{.25,inverter},id,last_}};
        const auto stepped=energy_.step({last_,now,inputs,coils_});
        ok_=stepped.fault==EvPowerFault::None && motor_.advance(now,false) && angles_.advance(now) && pressure_.advance(now);
        if(!ok_) return;
        OwnerSensors s; s.source_ns=now; s.angle=angles_.capture(); s.pressure=pressure_.capture(); s.torque=motor_.capture(now);
        s.power=energy_.power_observation(); s.battery=energy_.battery_observation();
        const auto& actual=energy_.power_state();
        s.drive.wheel_speed=battery::ModelMeasurement<double>{0,{7,sequence_,now},now};
        s.drive.hv=battery::ModelMeasurement<drive::HvFeedback>{{actual.bus_voltage_v,actual.contactors.positive && actual.contactors.negative && actual.bus_voltage_v>=300,false},
            {7,sequence_,now},last_};
        for(auto& channel:sensors_) channel.publish(s);
        // Apply new outputs only after advancing the previous interval. The
        // physical application time is distinct from original ECU/CAN source.
        for(std::size_t l=0;l<outputs_.size();++l) {
            const auto out=outputs_[l].read(); if(!out || out->source_ns>now || out->source_ns==applied_[l] || out->epoch>released_epoch_) continue;
            const bool stale=now-out->source_ns>30000000; applied_[l]=out->source_ns; applied_epoch_[l]=out->epoch;
            if(l==4 && out->epoch>power_driver_epoch_ && released_at_start==out->epoch) { watchdog_[4]=false; current_safe_since_=0; driver_shutdown_=false; power_driver_epoch_=0; }
            if(out->steering) ok_=ok_ && (stale || out->steering->mode==steering::ActuationMode::Hold?angles_.hold(now):angles_.set_target(out->steering->target_rad,now));
            if(out->brake) {
                // Trusted new application release clears only the modeled
                // actuator's protection-mode latch/pending demands. begin()
                // preserves pressure, model identity and sensor sequence.
                // A nominal Hold or CAN packet in the old Epoch cannot do so.
                if(out->epoch>brake_release_epoch_ && released_at_start==out->epoch) { ok_=ok_ && pressure_.begin(now); brake_release_epoch_=out->epoch; }
                if(out->brake->mode!=brake::ActuationMode::Protect && brake_release_epoch_!=out->epoch) continue;
                if(stale || out->brake->mode==brake::ActuationMode::Protect) ok_=ok_ && pressure_.request_protection(out->brake->target_pa,now);
                else if(out->brake->mode==brake::ActuationMode::Hold) ok_=ok_ && pressure_.hold(now);
                else ok_=ok_ && pressure_.set_target(out->brake->target_pa,now);
            }
            if(out->drive) { auto application=*out->drive; application.issued_time_ns=now; if(stale) { application.mode=drive::ActuationMode::Zero; application.target_nm=0; } ok_=ok_ && motor_.apply(application); }
            if(out->coils) coils_=*out->coils;
        }
        // Independent application watchdog while a Leaf itself is stopped.
        if(applied_[0] && now-applied_[0]>30000000) ok_=ok_ && angles_.hold(now);
        if(applied_[1] && now-applied_[1]>30000000) ok_=ok_ && pressure_.request_protection(1000000,now);
        if(applied_[2] && now-applied_[2]>30000000) ok_=ok_ && motor_.apply({drive::ActuationMode::Zero,0,std::nullopt,now});
        for(std::size_t l=0;l<5;++l) if(l!=3 && applied_[l] && now-applied_[l]>30000000 && !watchdog_[l]) {
            watchdog_[l]=true; if(l==4) power_driver_epoch_=applied_epoch_[l]; events_.push_back({now,"output-watchdog",8,applied_epoch_[l],applied_[l],applied_[l]+30000000,applied_[l],static_cast<int>(l+2)});
        }
        // A stopped Power ECU cannot run its controlled shutdown. The modeled
        // output driver interlock first forces torque zero, then releases coils
        // only after measured current/torque are safe; this is not an ECU ACK.
        if(watchdog_[4]) {
            ok_=ok_ && motor_.apply({drive::ActuationMode::Zero,0,std::nullopt,now});
            if(std::abs(motor_.actual_nm())<.1 && std::abs(actual.pack_current_a)<vecu::PowerControllerConfig{}.opening_current_max_a) {
                if(!current_safe_since_) current_safe_since_=now;
                if(now-current_safe_since_>=vecu::PowerControllerConfig{}.current_dwell_ns) {
                    coils_={{false,false,false},true};
                    if(!driver_shutdown_) events_.push_back({now,"driver-power-shutdown",8,power_driver_epoch_,applied_[4],applied_[4]+30000000,current_safe_since_,6});
                    driver_shutdown_=true;
                }
            } else current_safe_since_=0;
        }
        if(force_at_start) {
            ok_=ok_ && angles_.hold(now) && pressure_.request_protection(1000000,now) && motor_.apply({drive::ActuationMode::Zero,0,std::nullopt,now});
            if(!override_.acknowledged(released_epoch_)) events_.push_back({now,"override-applied",8,released_epoch_,0,0,0,0});
            override_.selected.store(released_epoch_,std::memory_order_release);
        }
        last_=now;
        if(now-last_trace_>=10000000) {
            last_trace_=now;
            trace.push_back({now-start_,now,0,false,false,false,0,0,0,angles_.actual_angle_rad(),pressure_.actual_pressure_pa(),motor_.actual_nm(),actual.bus_voltage_v,energy_.battery_state().soc});
            trace.back().run_gate=released_at_start!=0; trace.back().epoch=released_at_start;
            trace.back().energy_j=energy_.battery_state().energy_j;
            trace.back().model_epoch=actual.identity.epoch; trace.back().model_sequence=actual.identity.sequence;
            trace.back().contacts=static_cast<unsigned>(actual.contactors.positive)|(static_cast<unsigned>(actual.contactors.negative)<<1U)|(static_cast<unsigned>(actual.contactors.precharge)<<2U);
        }
    }
    bool ok() const { return ok_; }
    int fault_code() const { return static_cast<int>(energy_.fault()); }
    std::vector<M4Trace> trace;
private:
    Clock& clock_; transport::RunGate& gate_; std::array<runtime::LatestSnapshot<OwnerSensors>,session::kRoleCount>& sensors_;
    std::array<runtime::LatestSnapshot<OwnerActuation>,transport::kLeaves>& outputs_;
    std::vector<M4Event>& events_; transport::Protection& override_; std::uint32_t released_epoch_; std::array<bool,5> watchdog_{}; std::array<std::uint32_t,5> applied_epoch_{};
    std::uint64_t current_safe_since_{0}; std::uint32_t power_driver_epoch_{0}; bool driver_shutdown_{false};
    std::uint64_t start_,last_{0},last_trace_{0}; std::uint32_t sequence_{0},brake_release_epoch_{0}; bool begun_{false},ok_{true}; std::array<std::uint64_t,transport::kLeaves> applied_{};
    SteeringResponse angles_{{-.3,.3,.1,1,50000000,7}};
    BrakePressureResponse pressure_{{1500000,200000,5000000,10000000,50000000,7}};
    DriveSilPlant motor_{vecu::DriveControllerConfig{}.response};
    EvPowerModel energy_{{},{180000000,400,.05,200000,20,25,100,.01,1,100000},{.002,50,.02,100,1000,500}};
    power::CoilCommand coils_{};
};
class ZoneSession final : public session::ParticipantPort {
public:
    ZoneSession(zone::AsyncZoneOwner& zone,Clock& clock,runtime::LatestSnapshot<OwnerSensors>& sensors):zone_(zone),clock_(clock),sensors_(sensors) {}
    std::uint64_t now_ns() noexcept override { return clock_.now_ns(); }
    session::Preparation prepare(const session::Plan& plan) noexcept override {
        if(quiesced_!=plan.epoch) { quiesced_=plan.epoch; zone_.quiesce(); }
        const auto s=sensors_.read(); const bool ready=s && session_reset_safe(reset_evidence(*s),7,now_ns());
        if(ready) prepared_=plan.epoch;
        return ready?session::Preparation::Ready:session::Preparation::Pending;
    }
    bool initialize(const session::Plan& p) noexcept override { const auto s=sensors_.read(); const bool ok=s && session_reset_safe(reset_evidence(*s),7,now_ns()) && zone_.initialize(p.epoch,p.enable_ns); if(ok) prepared_=0; return ok; }
    void protect() noexcept override { zone_.protect_local(); }
    void service() noexcept override { if(prepared_<=zone_.epoch()) zone_.service(); }
private: zone::AsyncZoneOwner& zone_; Clock& clock_; runtime::LatestSnapshot<OwnerSensors>& sensors_; std::uint32_t quiesced_{0},prepared_{0};
};
class CentralIngress final : public session::ParticipantPort {
public:
    CentralIngress(central::AsyncCoordinatorPort& port,Clock& clock,runtime::LatestSnapshot<OwnerSensors>& sensors):port_(port),clock_(clock),sensors_(sensors) {}
    std::uint64_t now_ns() noexcept override { return clock_.now_ns(); }
    session::Preparation prepare(const session::Plan& plan) noexcept override {
        const auto s=sensors_.read(); const bool ready=s && session_reset_safe(reset_evidence(*s),7,now_ns()); if(ready) prepared_=plan.epoch;
        return ready?session::Preparation::Ready:session::Preparation::Pending;
    }
    bool initialize(const session::Plan& p) noexcept override { const auto s=sensors_.read(); const bool ok=s && session_reset_safe(reset_evidence(*s),7,now_ns()) && port_.initialize({p.epoch,p.enable_ns}); if(ok) prepared_=0; return ok; }
    void protect() noexcept override { port_.protect(); }
    void service() noexcept override { if(!prepared_) port_.service(); }
private: central::AsyncCoordinatorPort& port_; Clock& clock_; runtime::LatestSnapshot<OwnerSensors>& sensors_; std::uint32_t prepared_{0};
};
struct Network;
class BootPort final : public session::CoordinatorPort {
public:
    explicit BootPort(Network& network):n_(network) {}
    std::uint64_t now_ns() noexcept override;
    bool quiesce_central() noexcept override;
    bool send(const session::Control&) noexcept override { return false; } // SessionCentralLoop supplies the link
    bool commit_central(central::CoordinatorSession session) noexcept override;
    void protect_central() noexcept override;
private: Network& n_;
};
struct Network {
    const M4Config config; Clock clock; std::uint64_t start;
    transport::RunGate gate;
    std::array<transport::ZoneLink,2> zones;
    std::array<transport::LeafLink,transport::kLeaves> leaves;
    std::array<runtime::LatestSnapshot<OwnerSensors>,session::kRoleCount> sensors;
    std::array<runtime::LatestSnapshot<OwnerActuation>,transport::kLeaves> outputs;
    BmsGateChannel bms_gate;
    central::AsyncCoordinatorPort port{clock,gate,zones[0],zones[1]}; central::VehicleCoordinator core{port,{true}};
    std::array<std::unique_ptr<zone::AsyncZoneOwner>,2> zone_owners;
    std::array<std::unique_ptr<ZoneSession>,2> zone_sessions;
    std::array<std::unique_ptr<AsyncLeafOwner>,transport::kLeaves> leaf_owners;
    CentralIngress ingress{port,clock,sensors[7]};
    session::SessionLinks session_links; BootPort boot{*this}; SessionCentralLoop startup{boot,session_links};
    std::array<std::unique_ptr<SessionOwnerLoop>,session::kRoleCount> sessions;
    std::array<std::vector<M4Event>,10> owner_events;
    transport::Protection monitor_override; std::atomic<std::uint32_t> running_epoch{0};
    PhysicalOwner physical{clock,gate,sensors,outputs,start,owner_events[8],monitor_override,config.first_epoch}; std::array<Audit,10> audit;
    std::unique_ptr<M4ExecutionWatch> execution_watch;
    std::vector<std::unique_ptr<FaultEvidence>> filters;
    std::array<bool,10> paused{},overrun{},fault_seen{},selected_seen{},gate_seen{};
    bool restart_pending{false};
    std::array<std::array<std::uint64_t,6>,8> valid_observed{};
    session::State session_seen{session::State::Quiet}; bool armed_seen{false};
    M4Result result; std::vector<M4Trace> central_trace;
    std::uint64_t last_tick{0},last_root{0},last_vehicle{0},last_stop{0},next_management{0},vehicle_release{0},lifecycle_release{0}; std::uint32_t root_seq{0},vehicle_seq{0},stop_seq{0},active_epoch{0};
    bool began{false},rejoined{false},old_replayed{false};
    explicit Network(const M4Config& c):config(c),clock(c.wall_time),start(clock.now_ns()) {
        running_epoch.store(c.first_epoch);
        for(auto& log:owner_events) log.reserve(24000);
        bind_filters();
        std::array<transport::LeafLink*,transport::kLeaves> ptrs{}; for(std::size_t i=0;i<ptrs.size();++i) ptrs[i]=&leaves[i];
        for(std::size_t i=0;i<2;++i) {
            zone_owners[i]=std::make_unique<zone::AsyncZoneOwner>(i==0?zone::ZoneScope::Front:zone::ZoneScope::Rear,clock,gate,zones[i],ptrs);
            zone_sessions[i]=std::make_unique<ZoneSession>(*zone_owners[i],clock,sensors[i]);
            sessions[i]=std::make_unique<SessionOwnerLoop>(static_cast<session::Role>(i),*zone_sessions[i],session_links[i]);
        }
        for(std::size_t i=0;i<transport::kLeaves;++i) {
            leaf_owners[i]=std::make_unique<AsyncLeafOwner>(static_cast<transport::Leaf>(i),clock,gate,leaves[i],sensors[i+2],outputs[i],bms_gate);
            leaf_owners[i]->execution_deadline(config.execution_guards);
            sessions[i+2]=std::make_unique<SessionOwnerLoop>(static_cast<session::Role>(i+2),*leaf_owners[i],session_links[i+2]);
        }
        sessions[7]=std::make_unique<SessionOwnerLoop>(session::Role::CentralIngress,ingress,session_links[7]);
    }
    template<class T,std::size_t N> void bind(session::SessionMailbox<T,N>& mailbox,FaultPath path,std::size_t target) {
        auto filter=std::make_unique<FaultDelivery<T>>(clock,start,config.faults,path,static_cast<M4Owner>(target));
        mailbox.delivery(filter.get()); filters.push_back(std::move(filter));
    }
    void bind_filters() {
        if(config.scenario!=M4Scenario::Fault) return;
        for(std::size_t z=0;z<2;++z) {
            bind(zones[z].work,FaultPath::CentralToZone,z); bind(zones[z].results,FaultPath::ZoneToCentral,z); bind(zones[z].feedback,FaultPath::ZoneToCentral,z);
        }
        for(std::size_t l=0;l<5;++l) { bind(leaves[l].work,FaultPath::ZoneToLeaf,l+2); bind(leaves[l].reports,FaultPath::LeafToZone,l+2); }
        for(std::size_t i=0;i<8;++i) { bind(session_links[i].controls,FaultPath::SessionControl,i); bind(session_links[i].acks,FaultPath::SessionAck,i); }
    }
    void configure_watch(std::uint64_t until) {
        const auto enable=execution_watch?clock.now_ns()+100*kMs:start+100*kMs;
        if(execution_watch) { const auto rows=execution_watch->rows(); result.execution.insert(result.execution.end(),rows.begin(),rows.end()); }
        if(config.execution_guards) execution_watch=std::make_unique<M4ExecutionWatch>(enable,start+until);
    }
    void poll_deadlines(std::size_t observer) {
        if(!execution_watch) return;
        const auto now=clock.now_ns();
        for(const auto& fault:execution_watch->poll(observer,now)) if(fault) {
            const auto epoch=running_epoch.load(std::memory_order_acquire); gate.close(); monitor_override.request(epoch);
            for(auto& zone:zones) zone.protection.request(epoch);
            owner_events[observer].push_back({now,"deadline-detected",observer,epoch,fault->timing.deadline_ns-4000000,fault->timing.deadline_ns,fault->timing.deadline_ns,static_cast<int>(fault->target)});
        }
    }
    void collect_filters() {
        for(const auto& filter:filters) if(!filter->collect(result.events)) result.event_overflow=true;
        filters.clear();
    }
    void replace_joined_links() {
        collect_filters();
        for(auto& link:zones) { link.~ZoneLink(); new(&link) transport::ZoneLink{}; }
        for(auto& link:leaves) { link.~LeafLink(); new(&link) transport::LeafLink{}; }
        for(auto& link:session_links) { link.~SessionLink(); new(&link) session::SessionLink{}; }
        bind_filters();
        for(std::size_t i=0;i<8;++i) {
            auto* actor=i<2?static_cast<session::ParticipantPort*>(zone_sessions[i].get()):i==7?static_cast<session::ParticipantPort*>(&ingress):static_cast<session::ParticipantPort*>(leaf_owners[i-2].get());
            sessions[i]=std::make_unique<SessionOwnerLoop>(static_cast<session::Role>(i),*actor,session_links[i]);
        }
        for(auto& a:audit) a.owner={};
        running_epoch.store(config.rejoin_epoch,std::memory_order_release);
        restart_pending=true; ++result.replaced_links;
        result.events.push_back({clock.now_ns(),"joined-links-replaced",7,config.rejoin_epoch,0,0,0,0});
    }
    void central_step() {
        auto now=clock.now_ns(); const auto elapsed=now-start;
        if(!began) { began=true; startup.begin(config.first_epoch,now); }
        if(!rejoined && ((config.scenario==M4Scenario::Rejoin && elapsed>=config.rejoin_ns) || (config.recovery_ns && elapsed>=config.recovery_ns && (!config.replace_links || restart_pending)))) {
            rejoined=true; gate.close(); startup.cancel(now); startup.begin(config.rejoin_epoch,clock.now_ns());
            owner_events[7].push_back({clock.now_ns(),"recovery-request",7,config.rejoin_epoch,0,0,0,0});
        }
        sessions[7]->step(); startup.step(); now=clock.now_ns();
        if(session_seen!=startup.state()) {
            session_seen=startup.state(); const auto& plan=startup.plan();
            owner_events[7].push_back({now,session_seen==session::State::Failed?"session-failed":"session-phase",7,plan.epoch,plan.requested_ns,plan.enable_ns?plan.commit_deadline_ns:plan.prepare_deadline_ns,plan.enable_ns,session_seen==session::State::Failed?static_cast<int>(startup.fault()):static_cast<int>(session_seen)});
        }
        if(startup.run_enabled()) {
            const auto epoch=startup.plan().epoch;
            if(active_epoch!=epoch) {
                active_epoch=epoch; last_tick=last_root=last_vehicle=last_stop=vehicle_release=0; lifecycle_release=0;
                root_seq=vehicle_seq=stop_seq=0; next_management=startup.plan().enable_ns+14*kMs;
                owner_events[7].push_back({now,"run-released",7,epoch,0,0,0,0});
                running_epoch.store(epoch,std::memory_order_release);
                if(!monitor_override.pending(epoch)) gate.release(epoch); else core.request_protection(now); // Once per fully released session; a closed gate stays closed in this Epoch.
            }
            // Decide the release once. Clock movement during ingress must not
            // execute VM without the root update belonging to that same job.
            const bool management_due=now>=next_management;
            const bool stopping=(config.scenario==M4Scenario::NormalStop || (config.scenario==M4Scenario::Fault && std::any_of(config.faults.begin(),config.faults.end(),[](const auto& f){return f.phase==FaultPhase::Stop;}))) && elapsed>=config.injection_ns;
            if(stopping && (core.decision().normal_armed || core.decision().stopping) && (!last_stop || now-last_stop>=20*kMs)) {
                core.receive_stop({{epoch,stop_seq++,now,now+60*kMs},.02},now); last_stop=now;
            }
            now=clock.now_ns();
            const auto lifecycle_slot=now>=startup.plan().enable_ns+4*kMs?(now-startup.plan().enable_ns-4*kMs)/(20*kMs)+1:0;
            if(!core.decision().stopping && management_due && lifecycle_slot!=lifecycle_release) {
                lifecycle_release=lifecycle_slot;
                core.receive_lifecycle({{epoch,root_seq++,now,now+60*kMs},can::BmsPowerAction::Enable},now); last_root=now;
            }
            now=clock.now_ns();
            const bool lose_command=config.scenario==M4Scenario::CommandLoss && elapsed>=config.injection_ns;
            if(core.decision().normal_armed && !core.decision().stopping && !lose_command && now>=core.next_allocation_ns() && vehicle_release!=core.next_allocation_ns()) {
                vehicle_release=core.next_allocation_ns();
                core.receive_vehicle({epoch,vehicle_seq++,now,now+60*kMs,.2,.02,0,false},now); last_vehicle=now;
            }
            if(config.scenario==M4Scenario::OldEpoch && elapsed>=config.injection_ns && !old_replayed) {
                old_replayed=true;
                zones[0].work.push({epoch-1,999999,now,now+20*kMs,central::VehicleRequest{epoch-1,0,start,start+60*kMs,1,1,0,false}});
            }
            const auto in=port.feedback(); now=clock.now_ns();
            if(management_due) { last_tick=now; next_management=startup.plan().enable_ns+4*kMs+((now-startup.plan().enable_ns-4*kMs)/(10*kMs)+1)*(10*kMs); }
            core.tick(in,now,management_due);
        } else if(startup.state()==session::State::Failed && core.decision().fault!=central::CoordinatorFault::None && (!last_tick || now-last_tick>=10*kMs)) {
            last_tick=now; core.tick(port.feedback(),now);
        }
        const auto d=core.decision(); now=clock.now_ns();
        if(d.normal_armed && !armed_seen) owner_events[7].push_back({now,"normal-authorized",7,active_epoch,0,0,0,0});
        armed_seen=d.normal_armed;
        if(d.fault!=central::CoordinatorFault::None) {
            gate.close();
            if(startup.state()==session::State::Running || startup.state()==session::State::Releasing) startup.cancel(now);
            if(!result.first_fault_ns) result.first_fault_ns=now-start;
        }
        if(startup.state()==session::State::Failed) gate.close();
        const bool protected_all=zones[0].protection.acknowledged(active_epoch) && zones[1].protection.acknowledged(active_epoch);
        if(protected_all && result.first_fault_ns && !result.all_protected_ns) result.all_protected_ns=now-start;
        if(d.normal_armed && gate.allows(active_epoch)) {
            if(!result.first_active_ns) result.first_active_ns=now-start;
            if(rejoined && active_epoch==config.rejoin_epoch && !result.rejoin_active_ns) result.rejoin_active_ns=now-start;
        }
        if(central_trace.empty() || now-central_trace.back().source_ns>=10*kMs) {
            const auto observed=port.feedback();
            central_trace.push_back({now-start,now,active_epoch,gate.allows(active_epoch),d.normal_armed,protected_all,
                static_cast<int>(d.management.state),static_cast<int>(d.fault),static_cast<int>(d.stop.state),0,0,0,0,0,
                observed.front.steering_actual?observed.front.steering_actual->source_time_ns:0,
                observed.front.brake_actual?observed.front.brake_actual->source_time_ns:0,
                observed.rear.drive_actual?observed.rear.drive_actual->source_time_ns:0,port.command_source_ns(),port.command_root_sequence()});
        }
    }
    void step(std::size_t owner) {
        const auto now=clock.now_ns(),body_start=wall_now(); const auto elapsed=now-start;
        bool pause=false; std::uint64_t delay=0;
        for(const auto& f:config.faults) if(f.path==FaultPath::Owner && static_cast<std::size_t>(f.target)==owner && f.active(elapsed)) {
            if(f.kind==FaultKind::Pause) pause=true;
            if(f.kind==FaultKind::Overrun && !overrun[owner]) {
                overrun[owner]=true; owner_events[owner].push_back({now,"overrun-injected",owner,gate.epoch(),0,now+4000000,now,0});
                if(config.wall_time) delay=f.duration_ns;
            }
            if(f.kind==FaultKind::Overrun && !config.wall_time) pause=true;
        }
        const auto job=execution_watch?execution_watch->begin(owner,now,!pause):std::optional<std::size_t>{};
        const auto cpu_start=job?cpu_now():0;
        if(pause!=paused[owner]) { owner_events[owner].push_back({now,pause?"owner-stopped":"owner-resumed",owner,gate.epoch(),0,0,now,0}); paused[owner]=pause; }
        if(pause) return; // No session, control, self-monitor, RX, output or ACK.
        audit[owner].enter(now);
        if(delay) { std::this_thread::sleep_for(std::chrono::nanoseconds(delay)); owner_events[owner].push_back({clock.now_ns(),"overrun-ended",owner,running_epoch.load(),0,now+4000000,now,0}); }
        if(owner==9) poll_deadlines(9);
        else if(owner==8) { poll_deadlines(8); physical.step(); }
        else if(owner==7) { central_step(); audit[owner].runnable(last_tick); }
        else {
            if(owner==0) zone_owners[0]->fail_brake_write=elapsed>=config.injection_ns &&
                (config.scenario==M4Scenario::PartialFront || (config.scenario==M4Scenario::Rejoin && zone_owners[0]->epoch()==config.first_epoch));
            if(owner==2) leaf_owners[0]->drop_actual=config.scenario==M4Scenario::FeedbackLoss && elapsed>=config.injection_ns;
            if(owner==3) leaf_owners[1]->reject_arm=config.scenario==M4Scenario::PartialArm;
            sessions[owner]->step();
            audit[owner].runnable(owner<2?zone_owners[owner]->last_health_ns():leaf_owners[owner-2]->last_body_ns());
        }
        if(owner<2 || owner==7) {
            const auto record=[&](const auto& histories) {
                for(std::size_t i=0;i<histories.size();++i) {
                    const auto& h=histories[i]; if(h.received_ns && h.received_ns!=valid_observed[owner][i]) {
                        valid_observed[owner][i]=h.received_ns;
                        owner_events[owner].push_back({h.received_ns,"valid-feedback",owner,h.epoch,h.source_ns,0,0,static_cast<int>(i)});
                    }
                }
            };
            if(owner==7) record(port.input_history()); else record(zone_owners[owner]->input_history());
        }
        if(owner<8) {
            const auto epoch=owner==7?active_epoch:owner<2?zone_owners[owner]->epoch():leaf_owners[owner-2]->epoch();
            const bool bad=owner==7?core.decision().fault!=central::CoordinatorFault::None:owner<2?zone_owners[owner]->faulted():leaf_owners[owner-2]->faulted();
            if(bad && !fault_seen[owner]) owner_events[owner].push_back({clock.now_ns(),"fault-observed",owner,epoch,0,0,0,owner==7?static_cast<int>(core.decision().fault):owner<2?zone_owners[owner]->rejection():leaf_owners[owner-2]->fault_code()});
            fault_seen[owner]=bad;
            const bool selected=owner<2?zones[owner].protection.acknowledged(epoch):owner<7?leaves[owner-2].protection.acknowledged(epoch):false;
            if(selected && !selected_seen[owner]) owner_events[owner].push_back({clock.now_ns(),owner<2?"zone-protection-ack":"leaf-protection-selected",owner,epoch,0,0,0,0});
            selected_seen[owner]=selected;
            const bool enabled=gate.allows(epoch);
            if(gate_seen[owner] && !enabled) owner_events[owner].push_back({clock.now_ns(),"gate-closed-observed",owner,epoch,0,0,0,0});
            gate_seen[owner]=enabled;
        }
        audit[owner].durations.push_back(wall_now()-body_start);
        if(execution_watch) execution_watch->finish(owner,job,clock.now_ns(),job?cpu_now()-cpu_start:0);
    }
    M4Result finish() {
        collect_filters();
        if(execution_watch) { const auto rows=execution_watch->rows(); result.execution.insert(result.execution.end(),rows.begin(),rows.end()); }
        for(const auto& row:result.execution) {
            if(!row.end_ns || row.end_ns>row.deadline_ns) ++result.deadline_misses;
            if(!row.start_ns) ++result.skipped_opportunities;
        }
        result.timing_ok=result.deadline_misses==0;
        for(const auto& log:owner_events) result.events.insert(result.events.end(),log.begin(),log.end());
        for(const auto& leaf:leaf_owners) result.events.insert(result.events.end(),leaf->input_events().begin(),leaf->input_events().end());
        std::stable_sort(result.events.begin(),result.events.end(),[](const auto& a,const auto& b){ return a.time_ns<b.time_ns; });
        result.physical_ok=physical.ok(); result.completed_batches=port.completed_batches(); result.front_frames=zone_owners[0]->command_frames(); result.rear_frames=zone_owners[1]->command_frames();
        const std::array<const char*,10> names{"FrontZone","RearZone","Steering","Brake","Drive","Bms","Power","Central","Physical","Monitor"};
        for(std::size_t i=0;i<(config.execution_guards?10U:9U);++i) { result.ownership_ok=result.ownership_ok && audit[i].valid; result.timing.push_back(audit[i].result(names[i])); }
        std::size_t c=0;
        for(auto row:physical.trace) {
            while(c+1<central_trace.size() && central_trace[c+1].source_ns<=row.source_ns) ++c;
            if(!central_trace.empty() && central_trace[c].source_ns<=row.source_ns) {
                const auto& s=central_trace[c]; row.central_observation_ns=s.source_ns;
                if(!row.run_gate || row.epoch==s.epoch) { row.epoch=s.epoch; row.normal_armed=s.normal_armed; row.protected_all=s.protected_all;
                row.management=s.management; row.coordinator_fault=s.coordinator_fault; row.stop_state=s.stop_state;
                row.steering_source_ns=s.steering_source_ns; row.brake_source_ns=s.brake_source_ns; row.drive_source_ns=s.drive_source_ns;
                row.command_source_ns=s.command_source_ns; row.command_root_sequence=s.command_root_sequence;
                } // A newer physical gate cannot inherit an older epoch's protection/arm snapshot.
            }
            if(!result.trace.empty()) {
                const auto& old=result.trace.back();
                if(row.source_ns<=old.source_ns || row.model_epoch!=old.model_epoch || row.model_sequence<=old.model_sequence || row.energy_j>old.energy_j+1e-6 || row.soc>old.soc+1e-12) result.model_preserved=false;
            }
            result.trace.push_back(row);
        }
        const auto d=core.decision(); const bool expected_fault=config.scenario==M4Scenario::PartialFront || config.scenario==M4Scenario::FeedbackLoss || config.scenario==M4Scenario::CommandLoss || config.scenario==M4Scenario::PartialArm || config.scenario==M4Scenario::Rejoin;
        bool scenario_ok;
        if(expected_fault) scenario_ok=result.first_fault_ns!=0 && result.all_protected_ns>=result.first_fault_ns && result.all_protected_ns-result.first_fault_ns<=100*kMs;
        else scenario_ok=result.first_fault_ns==0 && d.fault==central::CoordinatorFault::None && result.first_active_ns!=0;
        if(config.scenario==M4Scenario::Rejoin) scenario_ok=scenario_ok && result.rejoin_active_ns>config.rejoin_ns && d.fault==central::CoordinatorFault::None;
        if(expected_fault && config.scenario!=M4Scenario::PartialArm) scenario_ok=scenario_ok && result.first_fault_ns>=config.injection_ns && result.all_protected_ns<=config.injection_ns+100*kMs;
        if(config.scenario==M4Scenario::NormalStop) scenario_ok=scenario_ok && d.stop.state==central::NormalStopState::Complete && d.management.power_off_confirmed;
        if(config.scenario!=M4Scenario::PartialArm) scenario_ok=scenario_ok && result.completed_batches>0;
        if(config.scenario==M4Scenario::PartialArm) scenario_ok=scenario_ok && result.first_active_ns==0 && result.front_frames==0 && result.rear_frames==0;
        if(config.scenario==M4Scenario::Fault) {
            const auto is=[](const M4Event& e,const char* value){ return std::string_view(e.kind)==value; };
            bool affected=false,protected_live=false;
            for(const auto& e:result.events) {
                if(is(e,"owner-stopped") || is(e,"dropped") || is(e,"delayed") || is(e,"overflow") || is(e,"receive-blocked") || is(e,"overrun-injected")) {
                    affected=true; if(!result.effective_injection_ns) result.effective_injection_ns=e.time_ns-start;
                }
                if(result.effective_injection_ns && e.time_ns-start>=result.effective_injection_ns && (is(e,"fault-observed") || is(e,"session-failed") || is(e,"deadline-detected")) && !result.live_fault_ns) result.live_fault_ns=e.time_ns-start;
                if(is(e,"leaf-protection-selected") || is(e,"output-watchdog")) protected_live=true;
                for(const auto& f:config.faults) if(f.path==FaultPath::Owner && f.kind==FaultKind::Pause && e.owner==static_cast<std::size_t>(f.target) && f.active(e.time_ns-start) && (is(e,"fault-observed") || is(e,"leaf-protection-selected") || is(e,"zone-protection-ack"))) ++result.stopped_ack_violations;
            }
            for(const auto& row:result.trace) {
                if(row.protected_all && row.run_gate) result.gate_latched=false;
                if(result.effective_injection_ns && row.elapsed_ns>=result.effective_injection_ns && !row.run_gate && !result.normal_blocked_ns) result.normal_blocked_ns=row.elapsed_ns;
                if(result.normal_blocked_ns && row.elapsed_ns>result.normal_blocked_ns && (!config.recovery_ns || row.elapsed_ns<config.recovery_ns) && row.run_gate) result.gate_latched=false;
            }
            for(const auto& e:result.events) if(is(e,"leaf-protection-selected") && e.epoch==config.first_epoch && result.effective_injection_ns && e.time_ns-start>=result.effective_injection_ns && e.time_ns-start<=result.effective_injection_ns+100*kMs) result.live_selection_mask|=1U<<e.owner;
            result.missing_selection_mask=124U & ~result.live_selection_mask;
            bool early_fault=false;
            for(const auto& e:result.events) if((is(e,"fault-observed") || is(e,"deadline-detected") || is(e,"session-failed")) && e.time_ns-start<result.effective_injection_ns) early_fault=true;
            scenario_ok=affected && !early_fault && result.gate_latched && result.stopped_ack_violations==0 && (protected_live || result.first_active_ns==0) && result.live_fault_ns && result.normal_blocked_ns;
            const bool preparing=std::any_of(config.faults.begin(),config.faults.end(),[](const auto& f){return f.phase==FaultPhase::Prepare;});
            if(!preparing && result.effective_injection_ns) scenario_ok=scenario_ok && result.live_fault_ns<=result.effective_injection_ns+100*kMs && result.normal_blocked_ns<=result.effective_injection_ns+100*kMs;
            if(config.recovery_ns) scenario_ok=scenario_ok && result.rejoin_active_ns>config.recovery_ns && d.fault==central::CoordinatorFault::None;
        }
        if(config.execution_guards && !expected_fault && config.scenario!=M4Scenario::Fault) scenario_ok=scenario_ok && result.timing_ok;
        result.passed=result.startup_ok && scenario_ok && result.physical_ok && result.ownership_ok && !result.event_overflow && result.model_preserved;
        if(!result.passed) result.reason="scenario="+std::string(m4_scenario_name(config.scenario))+" core="+std::to_string(static_cast<int>(d.fault))+" session="+std::to_string(static_cast<int>(startup.fault()))+" management="+std::to_string(static_cast<int>(d.management.state))+" vm_fault="+std::to_string(static_cast<int>(d.management.fault))+" allocation="+std::to_string(static_cast<int>(d.allocation.fault))+" stop="+std::to_string(static_cast<int>(d.stop.state))+" physical="+std::to_string(result.physical_ok)+" active="+std::to_string(result.first_active_ns)+" fault="+std::to_string(result.first_fault_ns)+" selected="+std::to_string(result.all_protected_ns);
        if(!result.passed) { result.reason+=" transport="+std::to_string(static_cast<int>(port.fault()))+" op="+std::to_string(port.failed_operation())+" front="+std::to_string(zone_owners[0]->rejection())+" rear="+std::to_string(zone_owners[1]->rejection())+" energy="+std::to_string(physical.fault_code()); for(const auto& l:leaf_owners) result.reason+=" leaf="+std::to_string(l->fault_code()); }
        return result;
    }
};
std::uint64_t BootPort::now_ns() noexcept { return n_.clock.now_ns(); }
bool BootPort::quiesce_central() noexcept { n_.gate.close(); n_.core.request_protection(now_ns()); n_.port.protect(); return true; }
bool BootPort::commit_central(central::CoordinatorSession s) noexcept { return n_.core.start_session(s); }
void BootPort::protect_central() noexcept { n_.gate.close(); n_.core.request_protection(now_ns()); n_.port.protect(); }
}  // namespace
M4Result run_m4_async(const M4Config& config) {
    if(config.duration_ns==0 || config.first_epoch==0 || (config.scenario==M4Scenario::Rejoin && config.rejoin_epoch<=config.first_epoch)) throw std::invalid_argument("M4 run configuration");
    for(const auto& f:config.faults) {
        validate_fault(f);
        if(f.target==M4Owner::Monitor && !config.execution_guards) throw std::invalid_argument("monitor injection requires execution guards");
    }
    if((!config.wall_time && (config.fifo || config.cpu_a>=0 || config.cpu_b>=0)) || config.cpu_a < -1 || config.cpu_b < -1) throw std::invalid_argument("native placement requires wall clock");
    if(config.duration_ns>10000000000ULL || (config.scenario==M4Scenario::Fault && config.faults.empty()) ||
       (config.recovery_ns && (config.rejoin_epoch<=config.first_epoch || config.recovery_ns>=config.duration_ns))) throw std::invalid_argument("M4 fault/recovery configuration");
    auto network=std::make_unique<Network>(config);
    if(!config.wall_time) {
        if(config.execution_guards) network->configure_watch(config.replace_links && config.recovery_ns?config.recovery_ns:config.duration_ns);
        bool replaced=false;
        for(std::uint64_t t=0;t<=config.duration_ns;t+=kIoPoll) {
            network->clock.logical=kLogicalStart+t;
            if(config.replace_links && config.recovery_ns && !replaced && t>=config.recovery_ns) { network->replace_joined_links(); if(config.execution_guards) network->configure_watch(config.duration_ns); replaced=true; }
            if(t%kMs==0) network->step(8);
            if(config.execution_guards && t%(2*kMs)==0) network->step(9);
            for(std::size_t owner=0;owner<8;++owner) network->step(owner);
        }
    } else {
        const auto count=config.execution_guards?10U:9U;
        runtime_support::ThreadInfo inherited; inherited.capture();
        if(inherited.policy!=SCHED_OTHER || inherited.priority!=0) throw std::invalid_argument("M4 native launcher must be OTHER/0");
        for(const auto cpu:{config.cpu_a,config.cpu_b}) if(cpu>=0 && std::find(inherited.allowed_cpus.begin(),inherited.allowed_cpus.end(),cpu)==inherited.allowed_cpus.end()) throw std::invalid_argument("M4 CPU outside inherited affinity");
        auto segment=[&](std::uint64_t until) {
            if(config.execution_guards) network->configure_watch(until);
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
                    const auto origin=std::chrono::steady_clock::now(); auto release=origin;
                    const auto period=std::chrono::nanoseconds(owner==9?2*kMs:owner==8?kMs:kIoPoll);
                    while(network->clock.now_ns()-network->start<until) {
                        network->step(owner); const auto now=std::chrono::steady_clock::now();
                        release=origin+period*((now-origin)/period+1); std::this_thread::sleep_until(release);
                    }
                } catch(...) { errors[owner]=true; }
            });
            const auto setup_deadline=std::chrono::steady_clock::now()+std::chrono::milliseconds(50);
            while(ready.load(std::memory_order_acquire)!=count && std::chrono::steady_clock::now()<setup_deadline) std::this_thread::sleep_for(std::chrono::microseconds(20));
            if(ready.load(std::memory_order_acquire)!=count) aborted=true;
            else for(std::size_t i=0;i<count;++i) if(observed[i].setup_error) aborted=true;
            go.store(true,std::memory_order_release);
            for(auto& worker:workers) worker.join();
            if(aborted) { network->result.startup_ok=false; network->result.reason="M4 owner configuration/startup rejected"; }
            for(std::size_t i=0;i<count;++i) { network->result.threads.push_back(observed[i]); if(errors[i]) { network->result.startup_ok=false; network->result.reason="M4 owner execution exception"; } }
        };
        if(config.replace_links && config.recovery_ns) { segment(config.recovery_ns); network->replace_joined_links(); }
        if(network->result.startup_ok) segment(config.duration_ns);
    }
    return network->finish();
}
const char* m4_scenario_name(M4Scenario s) {
    switch(s) {
    case M4Scenario::Normal: return "normal"; case M4Scenario::NormalStop: return "normal-stop";
    case M4Scenario::PartialFront: return "partial-front"; case M4Scenario::FeedbackLoss: return "feedback-loss";
    case M4Scenario::CommandLoss: return "command-loss"; case M4Scenario::PartialArm: return "partial-arm";
    case M4Scenario::Rejoin: return "rejoin"; case M4Scenario::OldEpoch: return "old-epoch"; case M4Scenario::Fault: return "fault";
    }
    return "invalid";
}
void write_m4_result(const M4Config& config,const M4Result& r,const std::string& directory) {
    std::filesystem::create_directories(directory); const auto prefix=std::filesystem::path(directory)/(std::string(config.wall_time?"wall-":"logical-")+m4_scenario_name(config.scenario));
    std::ofstream csv(prefix.string()+".csv"); csv<<"elapsed_ms,source_ns,epoch,run_gate,normal_armed,protected_all,management,coordinator_fault,stop_state,angle_rad,pressure_pa,torque_nm,bus_v,soc,steering_source_ns,brake_source_ns,drive_source_ns,command_source_ns,command_root_sequence,central_observation_ns,energy_j,model_epoch,model_sequence,contacts\n"<<std::setprecision(12);
    for(const auto& row:r.trace) csv<<static_cast<double>(row.elapsed_ns)/kMs<<','<<row.source_ns<<','<<row.epoch<<','<<row.run_gate<<','<<row.normal_armed<<','<<row.protected_all<<','<<row.management<<','<<row.coordinator_fault<<','<<row.stop_state<<','<<row.angle_rad<<','<<row.pressure_pa<<','<<row.torque_nm<<','<<row.bus_v<<','<<row.soc<<','<<row.steering_source_ns<<','<<row.brake_source_ns<<','<<row.drive_source_ns<<','<<row.command_source_ns<<','<<row.command_root_sequence<<','<<row.central_observation_ns<<','<<row.energy_j<<','<<row.model_epoch<<','<<row.model_sequence<<','<<row.contacts<<'\n';
    std::ofstream guard(prefix.string()+"-execution.csv"); guard<<"owner,slot,release_ns,deadline_ns,start_ns,end_ns,cpu_ns,detected_ns\n";
    for(const auto& j:r.execution) guard<<j.owner<<','<<j.slot<<','<<j.release_ns<<','<<j.deadline_ns<<','<<j.start_ns<<','<<j.end_ns<<','<<j.cpu_ns<<','<<j.detected_ns<<'\n';
    std::ofstream events(prefix.string()+"-events.csv"); events<<"time_ns,elapsed_ms,kind,owner,epoch,source_ns,deadline_ns,reference_ns,code\n"<<std::setprecision(12);
    const auto origin=r.trace.empty()?0:r.trace.front().source_ns-r.trace.front().elapsed_ns;
    for(const auto& e:r.events) events<<e.time_ns<<','<<static_cast<double>(e.time_ns-origin)/kMs<<','<<e.kind<<','<<e.owner<<','<<e.epoch<<','<<e.source_ns<<','<<e.deadline_ns<<','<<e.reference_ns<<','<<e.code<<'\n';
    std::ofstream summary(prefix.string()+".json"); summary<<std::boolalpha<<std::setprecision(12)<<"{\"passed\":"<<r.passed<<",\"ownership_ok\":"<<r.ownership_ok<<",\"physical_ok\":"<<r.physical_ok<<",\"first_active_ns\":"<<r.first_active_ns<<",\"first_fault_ns\":"<<r.first_fault_ns<<",\"all_protected_ns\":"<<r.all_protected_ns<<",\"rejoin_active_ns\":"<<r.rejoin_active_ns<<",\"completed_batches\":"<<r.completed_batches<<",\"front_frames\":"<<r.front_frames<<",\"rear_frames\":"<<r.rear_frames<<",\"timing\":[";
    for(std::size_t i=0;i<r.timing.size();++i) {
        const auto& t=r.timing[i]; if(i) summary<<',';
        summary<<"{\"owner\":\""<<t.owner<<"\",\"samples\":"<<t.samples<<",\"mean_body_us\":"<<t.mean_body_us<<",\"p95_body_us\":"<<t.p95_body_us<<",\"p99_body_us\":"<<t.p99_body_us<<",\"max_body_us\":"<<t.max_body_us<<",\"body_over_4ms\":"<<t.body_over_4ms<<",\"max_poll_gap_ms\":"<<t.max_poll_gap_ms<<",\"max_runnable_gap_ms\":"<<t.max_runnable_gap_ms<<'}';
    }
    summary<<"],\"threads\":[";
    for(std::size_t i=0;i<r.threads.size();++i) {
        const auto& t=r.threads[i]; if(i) summary<<',';
        summary<<"{\"owner\":"<<t.owner<<",\"policy\":"<<t.policy<<",\"priority\":"<<t.priority<<",\"cpu\":"<<t.cpu<<",\"tid\":"<<t.tid<<",\"requested_cpu\":"<<t.requested_cpu<<",\"setup_error\":"<<t.setup_error<<",\"affinity\":[";
        for(std::size_t k=0;k<t.affinity.size();++k) { if(k) summary<<','; summary<<t.affinity[k]; } summary<<"]}";
    }
    summary<<"],\"guards_enabled\":"<<config.execution_guards<<",\"fifo_requested\":"<<config.fifo<<",\"startup_ok\":"<<r.startup_ok<<",\"timing_ok\":"<<r.timing_ok<<",\"deadline_misses\":"<<r.deadline_misses<<",\"skipped_opportunities\":"<<r.skipped_opportunities;
    summary<<",\"faults\":[";
    for(std::size_t i=0;i<config.faults.size();++i) {
        const auto& f=config.faults[i]; if(i) summary<<',';
        summary<<"{\"path\":\""<<fault_path_name(f.path)<<"\",\"kind\":\""<<fault_kind_name(f.kind)<<"\",\"target\":\""<<m4_owner_name(f.target)<<"\",\"start_ns\":"<<f.start_ns<<",\"duration_ns\":"<<f.duration_ns<<",\"delay_ns\":"<<f.delay_ns<<",\"phase\":"<<static_cast<int>(f.phase)<<'}';
    }
    summary<<"],\"duration_ns\":"<<config.duration_ns<<",\"recovery_ns\":"<<config.recovery_ns<<",\"gate_latched\":"<<r.gate_latched<<",\"stopped_ack_violations\":"<<r.stopped_ack_violations<<",\"replaced_links\":"<<r.replaced_links<<",\"event_overflow\":"<<r.event_overflow<<",\"effective_injection_ns\":"<<r.effective_injection_ns<<",\"live_fault_ns\":"<<r.live_fault_ns<<",\"normal_blocked_ns\":"<<r.normal_blocked_ns<<",\"live_selection_mask\":"<<r.live_selection_mask<<",\"missing_selection_mask\":"<<r.missing_selection_mask<<",\"model_preserved\":"<<r.model_preserved<<",\"reason\":"<<std::quoted(r.reason)<<"}\n";
}
}  // namespace stratadrive::simulation
