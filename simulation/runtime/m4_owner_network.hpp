#pragma once
// Internal M4 harness state. Adapters consume interfaces/zone/owner_messages.hpp.
#include "m4_async_runtime.hpp"
#include "async_leaf_owner.hpp"
#include "async_coordinator_port.hpp"
#include "async_zone_owner.hpp"
#include "session_loop.hpp"
#include "ev_power_model.hpp"
#include "drive_sil_plant.hpp"
#include "steering_response.hpp"
#include "brake_pressure_response.hpp"
#include <algorithm>
#include <memory>
#include <thread>

namespace stratadrive::simulation::m4_detail {
inline constexpr std::uint64_t kMs=1000000,kIoPoll=200000,kLogicalStart=1000000000;
std::uint64_t cpu_now();
std::uint64_t wall_now();
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
    std::size_t buffer_growths{0};
    void record(std::uint64_t duration) { if(durations.size()==durations.capacity()) ++buffer_growths; durations.push_back(duration); }
    void enter(std::uint64_t now) {
        if(owner==std::thread::id{}) owner=std::this_thread::get_id(); else valid=valid && owner==std::this_thread::get_id();
        if(last_poll) poll_gap=std::max(poll_gap,now-last_poll);
        last_poll=now;
    }
    void runnable(std::uint64_t now) { if(now!=0 && now!=last_runnable) { if(last_runnable) runnable_gap=std::max(runnable_gap,now-last_runnable); last_runnable=now; } }
    M4Timing result(std::string name);
};
struct PhysicalFailure {
    const char* model="none";const char* site="none";
    std::uint64_t call_ns=0,previous_call_ns=0,last_success_ns=0,input_ns=0,dt_ns=0;
    std::uint32_t epoch=0;bool protection=false;
    std::array<OwnerActuation,5> outputs{};
    std::uint64_t return_ns=0,component_last_success_ns=0;
};
class PhysicalOwner {
public:
    PhysicalOwner(Clock& clock,transport::RunGate& gate,std::array<runtime::LatestSnapshot<OwnerSensors>,session::kRoleCount>& sensors,
        std::array<runtime::LatestSnapshot<OwnerActuation>,transport::kLeaves>& outputs,std::uint64_t start,std::vector<M4Event>& events,transport::Protection& override_signal,std::uint32_t first_epoch)
        :clock_(clock),gate_(gate),sensors_(sensors),outputs_(outputs),events_(events),override_(override_signal),released_epoch_(first_epoch),start_(start) {}
    void step();
    bool ok() const { return ok_; }
    int fault_code() const { return static_cast<int>(energy_.fault()); }
    std::vector<M4Trace> trace;
    const PhysicalFailure& failure() const {return failure_;}
    std::uint64_t last_success() const {return last_success_;}
private:
    std::array<std::uint64_t,4> component_success_{};
    PhysicalFailure failure_;std::uint64_t previous_call_=0,current_call_=0,last_success_=0;
    bool observe(bool ok,const char* model,const char* site,std::uint64_t input);
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
struct TransportTraceLog final : transport::TransportTrace {
    std::size_t owner{0};bool overflow{false};std::vector<transport::TransportTraceRow> rows;
    void record(transport::TransportTraceRow row) noexcept override {
        row.owner=owner;
        if(rows.size()<rows.capacity())rows.push_back(row);else overflow=true;
    }
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
    central::AsyncCoordinatorPort port{clock,gate,zones[0],zones[1],config.renewal}; central::VehicleCoordinator core{port,{true,config.renewal}};
    std::array<std::unique_ptr<zone::AsyncZoneOwner>,2> zone_owners;
    std::array<std::unique_ptr<ZoneSession>,2> zone_sessions;
    std::array<std::unique_ptr<AsyncLeafOwner>,transport::kLeaves> leaf_owners;
    CentralIngress ingress{port,clock,sensors[7]};
    session::SessionLinks session_links; BootPort boot{*this}; SessionCentralLoop startup{boot,session_links};
    std::array<std::unique_ptr<SessionOwnerLoop>,session::kRoleCount> sessions;
    std::array<std::vector<M4Event>,10> owner_events;
    transport::Protection monitor_override; std::atomic<std::uint32_t> running_epoch{0};
    PhysicalOwner physical{clock,gate,sensors,outputs,start,owner_events[8],monitor_override,config.first_epoch}; std::array<Audit,10> audit;
    std::array<TransportTraceLog,8> transport_logs;
    std::unique_ptr<M4ExecutionWatch> execution_watch;
    std::vector<std::unique_ptr<FaultEvidence>> filters;
    std::array<bool,10> paused{},overrun{},fault_seen{},selected_seen{},gate_seen{};
    bool restart_pending{false};
    std::array<std::array<std::uint64_t,6>,8> valid_observed{};
    session::State session_seen{session::State::Quiet}; bool armed_seen{false};
    M4Result result; std::vector<M4Trace> central_trace;
    std::uint64_t last_tick{0},last_root{0},last_vehicle{0},last_stop{0},next_management{0},vehicle_release{0},lifecycle_release{0}; std::uint32_t root_seq{0},vehicle_seq{0},stop_seq{0},active_epoch{0};
    bool began{false},rejoined{false},old_replayed{false};
    explicit Network(const M4Config& c);
    template<class T,std::size_t N> void bind(session::SessionMailbox<T,N>& mailbox,FaultPath path,std::size_t target) {
        auto filter=std::make_unique<FaultDelivery<T>>(clock,start,config.faults,path,static_cast<M4Owner>(target));
        mailbox.delivery(filter.get()); filters.push_back(std::move(filter));
    }
    void bind_filters();
    void configure_watch(std::uint64_t until);
    void poll_deadlines(std::size_t observer);
    void collect_filters();
    void replace_joined_links();
    void central_step();
    void step(std::size_t owner,std::uint64_t requested_wake=0);
    M4Result finish();
};
void execute_logical(Network& network);
void execute_native(Network& network);
} // namespace stratadrive::simulation::m4_detail
