#include "functional_rig.hpp"
#include "reference_feasibility.hpp"
#include "wall_rig.hpp"
#include "m4_owner_network.hpp"
#include "run_lease_issuer.hpp"
#include "wheel_contract.hpp"
#include "wall_execution_watch.hpp"
#include "native_diagnostics.hpp"
#include "owner_diagnostics.hpp"
#include "diagnostic_response.hpp"
#include <deque>
#include <functional>

namespace stratadrive::m7_functional {
namespace {
using Role=session::Role;
central::AllocationConfig allocation(bool speed) {
    central::AllocationConfig c;
    if(speed) {c.mass_kg=1696;c.wheel_radius_m=.355;c.wheelbase_m=2.860470886230469;}
    return c;
}
central::NormalStopConfig stop_configuration(RouteProfile profile) {
    central::NormalStopConfig c;
    if(profile==RouteProfile::Straight30Stop)c.braking_timeout_ns=10000000000ULL;
    return c;
}
double speed_target(Time elapsed) {
    const double t=static_cast<double>(elapsed)*1e-9;
    if(t<10)return (10/3.6)*t/10;
    if(t<20)return 10/3.6;
    if(t<30)return (10/3.6)*(30-t)/10;
    return 0;
}
void require(bool value,const char* why) {if(!value)throw std::runtime_error(why);}
template<class T> class OmitDelivery final:public session::MailboxDelivery<T> {
public:
    const Time& trigger;const DiagnosticFault& fault;std::uint64_t count=0;
    OmitDelivery(const Time& t,const DiagnosticFault& f):trigger(t),fault(f) {}
    session::Delivery send(const T& value) noexcept override {
        bool drop=false;
        if constexpr(std::is_same_v<T,transport::ZoneRequest>)drop=fault==DiagnosticFault::FrontCommandLoss;
        else drop=fault==DiagnosticFault::StopAckLoss && value.operation==transport::Operation::Stop;
        if(trigger && drop){++count;return {true,0};}return {};
    }
    bool blocked() noexcept override {return false;}
    std::uint64_t now_ns() const noexcept override {return 0;}
    void delivered(const T&) noexcept override {}
    void overflow(const T&) noexcept override {}
};
remote::OwnerMessage wire(const remote::OwnerMessage& message) {
    const auto packet=remote::encode_owner_message(message);require(bool(packet),"encode");
    const auto decoded=remote::decode_owner_message(packet->bytes.data(),packet->size);
    require(bool(decoded),"decode");
    const auto again=remote::encode_owner_message(*decoded);
    require(again && again->size==packet->size && again->bytes==packet->bytes,"wire changed original fields");
    return *decoded;
}
// A trusted local adapter binds the original native RunLeaseGate during INIT.
// Each participant has its own gate; a single local Release cannot open it.
class CreditedActor final:private session::ParticipantPort {
    session::ParticipantPort& actor_;transport::RunGate& gate_;
public:
    CreditedActor(Role role,session::ParticipantPort& actor,transport::RunGate& gate,Time clock_domain)
        :actor_(actor),gate_(gate),participant_(role,*this),domain_(clock_domain) {}
    session::SessionParticipant participant_;
    remote::RunLeaseGate credit;
    void select_protection() {protect();}
    bool allowed() {return !protected_ && credit.allows(participant_,now_ns()) && gate_.allows(epoch_);}
    bool lease(const remote::RunLease& lease) {
        if(protected_ || !credit.receive(lease,domain_,participant_,now_ns()))return false;
        if(!released_){gate_.release(epoch_);released_=true;}
        return allowed();
    }
private:
    Time now_ns() noexcept override {return actor_.now_ns();}
    session::Preparation prepare(const session::Plan& p) noexcept override {
        gate_.close();return actor_.prepare(p);
    }
    bool initialize(const session::Plan& p) noexcept override {
        gate_.close();
        if(!actor_.initialize(p) || !credit.bind(p,{domain_,domain_,0,0,true},now_ns()))return false;
        epoch_=p.epoch;protected_=false;released_=false;return true;
    }
    void protect() noexcept override {
        protected_=true;gate_.close();credit.protect(epoch_);actor_.protect();
    }
    void service() noexcept override {
        if(epoch_) {
            const bool valid=credit.allows(participant_,now_ns());
            if(credit.fault()!=remote::RunLeaseFault::None || (released_ && (!valid || !gate_.allows(epoch_))))protect();
        }
        actor_.service();
    }
    Time domain_;
    std::uint32_t epoch_=0;bool released_=false,protected_=false;
};
}

struct FunctionalRig::Native final:session::CoordinatorPort {
    Scope scope;
    const Time domain;
    const bool wall_mode;
    const Time horizon_ms;
    simulation::m4_detail::Clock clock{false};
    Time start,next_io,next_physical;
    Time reinit_after=0;
    std::array<transport::RunGate,8> gates;
    std::array<transport::ZoneLink,2> zones;
    std::array<transport::LeafLink,5> leaves;
    std::array<runtime::LatestSnapshot<simulation::OwnerSensors>,8> sensors;
    std::array<runtime::LatestSnapshot<simulation::OwnerSensors>,8> fixture_sensors;
    std::array<runtime::LatestSnapshot<simulation::OwnerActuation>,5> outputs;
    simulation::BmsGateChannel bms;
    central::AsyncCoordinatorPort port{clock,gates[7],zones[0],zones[1],central::CommandRenewal::Host10ms};
    const central::NormalStopConfig stop_settings;
    central::VehicleCoordinator core;
    central::SpeedRequest speed_request;
    std::unique_ptr<central::AvailableForceEstimator> force_estimator;
    std::unique_ptr<central::SupervisedSpeedRequest> supervised_speed;
    std::optional<central::AvailableForce> available_force;
    bool omit_force=false;
    const bool antiwindup;
    bool saturation_used=false,braking_saturation_used=false;
    std::optional<central::PropulsionSelection> speed_selection;
    const bool speed_enabled;
    Time speed_origin=0;
    RouteSpeedProfile route_speed;
    std::optional<SpeedControlAudit> speed_audit;
    std::unique_ptr<central::PurePursuit> pursuit;
    std::deque<central::RoutePose> pending_poses;
    std::optional<central::RoutePose> pose;
    std::optional<central::PursuitOutput> lateral_audit;
    std::array<std::unique_ptr<zone::AsyncZoneOwner>,2> zone;
    std::array<std::unique_ptr<simulation::m4_detail::ZoneSession>,2> zone_sessions;
    std::array<std::unique_ptr<simulation::AsyncLeafOwner>,5> leaf;
    simulation::m4_detail::CentralIngress ingress{port,clock,sensors[7]};
    std::array<std::unique_ptr<CreditedActor>,8> participants;
    std::array<std::deque<session::Control>,8> controls;
    std::deque<session::Ack> acks;
    session::SessionCoordinator coordinator{*this};central::RunLeaseIssuer issuer{coordinator};
    std::vector<simulation::M4Event> events;transport::Protection override_signal;
    // simple_vehicle=false: no vehicle motion integration. Wheel=0 is explicitly
    // the stationary native fixture, never attributed to CARLA measurement.
    std::unique_ptr<simulation::m4_detail::PhysicalOwner> physical;
    std::unique_ptr<m7_external::ActuatorElectrical> external;
    std::deque<WheelSample> wheel_history;
    std::array<m7_external::ElectricalAudit,12> electrical_steps{};
    unsigned electrical_count=0;
    Time next_management=0,next_controller=0,last_lease=0,controller_phase=14*ms;
    std::uint32_t lifecycle_seq=0,vehicle_seq=0;
    unsigned release_mask=0;std::size_t controller_releases=0;
    bool running=false,stop_credit=false,drop_actual=false;int omitted=-1;
    SpeedTerminal terminal_mode=SpeedTerminal::None;
    Time trigger_ns=0,detection_ns=0,handoff_ns=0;std::uint32_t stop_seq=0;
    DiagnosticFault diagnostic_fault=DiagnosticFault::Disabled;
    OmitDelivery<transport::ZoneRequest> command_omission{trigger_ns,diagnostic_fault};
    OmitDelivery<transport::TxResult> ack_omission{trigger_ns,diagnostic_fault};
    std::unique_ptr<diagnostics::EventQueue> startup_events,control_events;
    std::unique_ptr<diagnostics::StartupDiagnostics> startup_diagnostics;
    std::unique_ptr<diagnostics::ControlDiagnostics> control_diagnostics;
    std::array<std::unique_ptr<diagnostics::EventQueue>,5> command_events;
    std::array<std::unique_ptr<diagnostics::NativeDiagnostics>,2> gateway_diagnostics;
    std::array<std::unique_ptr<diagnostics::OwnerDiagnostics>,3> leaf_diagnostics;
    DiagnosticResponse command_response;
    bool diagnostic_session=false;std::array<bool,7> diagnostic_selected{};
    bool protection_requested=false,terminal_response=false;
    Time protection_since=0;
    bool wheel_mode=false;
    std::vector<RequestPhase> profile;
    std::optional<WheelSample> wheel;
    std::deque<WheelSample> pending_wheels;
    bool export_actual=false;
    bool coordinator_started=false;
    WallExecutionWatch* watch=nullptr;
    std::array<DeliveredCapture<transport::Feedback>,2> feedback_capture;
    std::array<DeliveredCapture<transport::LeafRequest>,5> command_capture;
    std::array<DeliveredCapture<transport::LeafReport>,5> result_capture;
    std::array<std::optional<session::Ack>,8> release_acks;

    Native(Scope s,Time initial,PlantMode mode,bool exporting,bool wall=false,Time model_initial=0,Time horizon=10000,Time model_step=10000000,Time hv_dependency_ns=30000000,bool speed=false,const std::vector<central::RoutePoint>& route={},RouteProfile route_profile=RouteProfile::Curve30,bool external_aw=false,std::optional<central::RoadLoadBounds> load=std::nullopt):scope(s),domain(wall?wall_domain:m7_functional::domain),wall_mode(wall),horizon_ms(horizon),start(initial),next_io(initial),next_physical(initial),stop_settings(stop_configuration(route_profile)),core(port,{true,central::CommandRenewal::Host10ms},allocation(speed),stop_settings),speed_request(.355,external_aw),antiwindup(external_aw || bool(load)),speed_enabled(speed),route_speed(route_profile),export_actual(exporting) {
        if(!route.empty())pursuit=std::make_unique<central::PurePursuit>(route,2.860470886230469);
        clock.logical=initial;
        if(load) {
            require(speed && !wall,"supervised speed requires simulation speed profile");
            const auto config=allocation(true);
            force_estimator=std::make_unique<central::AvailableForceEstimator>(config,*load);
            central::ReferenceConfig reference;reference.mass_kg=config.mass_kg;
            supervised_speed=std::make_unique<central::SupervisedSpeedRequest>(reference,config.wheel_radius_m);
        }
        if(export_actual) {
            for(unsigned i=0;i<2;++i)zones[i].feedback.delivery(&feedback_capture[i]);
            for(unsigned i=0;i<5;++i) {leaves[i].work.delivery(&command_capture[i]);leaves[i].reports.delivery(&result_capture[i]);}
        }
        if(wall)external=std::make_unique<m7_external::ActuatorElectrical>(initial,s.application,model_initial?m7_external::PlantExecution::CarlaObservedWork:m7_external::PlantExecution::DeferredObservedWork,model_initial,model_step);
        else if(mode!=PlantMode::StationaryFixture)external=std::make_unique<m7_external::ActuatorElectrical>(initial,s.application,mode==PlantMode::ExternalSolverWork);
        else physical=std::make_unique<simulation::m4_detail::PhysicalOwner>(clock,gates[7],fixture_sensors,outputs,start,events,override_signal,s.application,false);
        std::array<transport::LeafLink*,5> ptr{};for(unsigned i=0;i<5;++i)ptr[i]=&leaves[i];
        for(unsigned i=0;i<2;++i) {
            zone[i]=std::make_unique<zone::AsyncZoneOwner>(i==0?zone::ZoneScope::Front:zone::ZoneScope::Rear,clock,gates[i],zones[i],ptr);
            zone_sessions[i]=std::make_unique<simulation::m4_detail::ZoneSession>(*zone[i],clock,sensors[i]);
            participants[i]=std::make_unique<CreditedActor>(static_cast<Role>(i),*zone_sessions[i],gates[i],domain);
        }
        for(unsigned i=0;i<5;++i) {
            simulation::LeafOwnerConfig config;
            if(speed_enabled || (wall && horizon_ms>30000)) config.input_event_capacity=static_cast<std::size_t>(horizon_ms)+12000;
            if(i==2 && model_initial) {
                config.drive_sensor_ingress=simulation::DriveSensorIngress::BeforeIo;
                config.hv_dependency_age_ns=hv_dependency_ns;
            }
            leaf[i]=std::make_unique<simulation::AsyncLeafOwner>(static_cast<transport::Leaf>(i),clock,gates[i+2],leaves[i],sensors[i+2],outputs[i],bms,config);
            participants[i+2]=std::make_unique<CreditedActor>(static_cast<Role>(i+2),*leaf[i],gates[i+2],domain);
        }
        participants[7]=std::make_unique<CreditedActor>(Role::CentralIngress,ingress,gates[7],domain);
        if(!export_actual) {
            require(coordinator.begin(s.application,initial),"begin trusted fixture session");
            coordinator_started=true;
        }
    }
    Time now_ns() noexcept override {return clock.now_ns();}
    bool quiesce_central() noexcept override {gates[7].close();core.request_protection(now_ns());port.protect();return true;}
    bool commit_central(central::CoordinatorSession s) noexcept override {return core.start_session(s) && (!speed_enabled || (supervised_speed?supervised_speed->start_session(s.epoch,domain,s.enable_ns):speed_request.start_session(s.epoch,s.enable_ns))) && (!pursuit || pursuit->start_session(s.epoch,s.enable_ns));}
    void protect_central() noexcept override {gates[7].close();core.request_protection(now_ns());port.protect();}
    bool send(const session::Control& c) noexcept override {
        const auto i=static_cast<unsigned>(c.role);
        if(i>=8 || controls[i].size()>=32)return false;
        controls[i].push_back(c);return true;
    }
    void ack(const std::optional<session::Ack>& a) {
        if(a){require(acks.size()<64,"ACK queue overflow");acks.push_back(*a);}
    }
    void enable_diagnostics(DiagnosticFault fault) {
        diagnostic_fault=fault;
        startup_events=std::make_unique<diagnostics::EventQueue>(scope.run,7);
        control_events=std::make_unique<diagnostics::EventQueue>(scope.run,8);
        const diagnostics::ControlContext context{scope.run,7,diagnostics::Domain::Simulation,domain,1};
        startup_diagnostics=std::make_unique<diagnostics::StartupDiagnostics>(*startup_events,context,diagnostics::Component::Coordinator,8,true);
        auto control_context=context;control_context.producer=8;
        control_diagnostics=std::make_unique<diagnostics::ControlDiagnostics>(*control_events,control_context);
        const std::array<diagnostics::Component,5> actors{diagnostics::Component::Front,diagnostics::Component::Rear,
            diagnostics::Component::Steering,diagnostics::Component::Brake,diagnostics::Component::Drive};
        for(unsigned i=0;i<5;++i) {
            auto c=context;c.producer=i<2?30+i:20+i;
            command_events[i]=std::make_unique<diagnostics::EventQueue>(scope.run,c.producer);
            if(i<2)gateway_diagnostics[i]=std::make_unique<diagnostics::NativeDiagnostics>(*command_events[i],c,actors[i]);
            else leaf_diagnostics[i-2]=std::make_unique<diagnostics::OwnerDiagnostics>(*command_events[i],c,actors[i]);
        }
        zones[0].work.delivery(&command_omission);zones[0].results.delivery(&ack_omission);
    }
    void sample_diagnostics(Time now) {
        if(!control_diagnostics || (reinit_after && !coordinator_started))return;
        startup_diagnostics->attempt(coordinator.plan());
        startup_diagnostics->observe(coordinator.fault_observation(),coordinator.success_observation(),coordinator.run_enabled(),coordinator.run_enabled(),now);
        if(!diagnostic_session && coordinator.run_enabled()) {
            const auto enable=coordinator.plan().enable_ns;
            diagnostic_session=control_diagnostics->start_session(scope.application,enable,false);
            for(auto& d:gateway_diagnostics)require(d->start_session(scope.application,enable),"gateway diagnostic session");
            for(auto& d:leaf_diagnostics)require(d->start_session(scope.application,enable),"leaf diagnostic session");
        }
        if(!diagnostic_session)return;
        for(unsigned i=0;i<2;++i) {
            const auto& g=zone[i]->command_gateway();auto& d=*gateway_diagnostics[i];
            d.observe(diagnostics::NativeMonitor::CommandGateway,g.fault_observation(),std::nullopt,g.success_observation(),
                !zone[i]->faulted(),gates[i].allows(scope.application),now);
            d.selection(diagnostics::NativeMonitor::CommandGateway,zone[i]->protection_ack_ns(),true);
        }
        for(unsigned i=0;i<3;++i)leaf_diagnostics[i]->leaf(leaf[i]->expiry_observation(),leaf[i]->command_success_observation(),
            !leaf[i]->faulted(),gates[i+2].allows(scope.application),leaf[i]->protection_selected_ns(),now);
        if(supervised_speed)control_diagnostics->observe(*supervised_speed,core,now);
        else control_diagnostics->observe(speed_request,core,now);
        const auto feedback=port.feedback();control_diagnostics->observe_response(feedback,now);
        if(supervised_speed)control_diagnostics->observe_speed_recovery(*supervised_speed,core,feedback,now);
        for(unsigned i=0;i<7;++i) {
            const auto selected=i<2?zone[i]->protection_ack_ns():leaf[i-2]->protection_selected_ns();
            if(selected && !diagnostic_selected[i]) {
                const std::array<diagnostics::Component,7> actors{diagnostics::Component::Front,diagnostics::Component::Rear,diagnostics::Component::Steering,diagnostics::Component::Brake,diagnostics::Component::Drive,diagnostics::Component::Bms,diagnostics::Component::Power};
                control_diagnostics->local_protection(actors[i],1U<<i,scope.application,*selected,i<2);diagnostic_selected[i]=true;
            }
        }
    }
    void select_diagnostic_protection(Time now) {
        if(protection_since)return;
        detection_ns=now;protection_since=now;protect_central();for(auto& p:participants)p->select_protection();
    }
    void cycle(Time now,const std::function<void()>& completed_work={}) {
        clock.logical=now;
        struct DiagnosticSample {Native& owner;Time now;~DiagnosticSample(){owner.sample_diagnostics(now);}} diagnostic_sample{*this,now};
        // Fixed SIL injection: 100ms after original handoff ACK, before HV-off.
        if(terminal_mode==SpeedTerminal::StopProtection && handoff_ns && !protection_since && now>=handoff_ns+100*ms) {
            detection_ns=now;protection_since=now;protect_central();
            for(auto& p:participants)p->select_protection();
        }
        if(protection_requested && !protection_since && !wall_mode) {
            require(running && core.decision().normal_armed,"protection requires established normal session");
            protection_since=now;
            protect_central();
            for(auto& p:participants)p->select_protection();
        }
        // M7 applied path only: delayed INIT puts 10ms leaf acquisitions near
        // the end of each CARLA frame. It changes phase, not any native rate,
        // original timestamp, parent expiry, or session deadline budget.
        // A wall INIT must not straddle the first receipt's source boundary.
        // After one completed work receipt, choose a phase at least one original
        // 2ms opportunity after its acquisition. This is phase, not extra age.
        const bool init_ready=wall_mode?
            (wheel && external->electrical_acquisition()>=wheel->source && now>=wheel->source && now-wheel->source>=2*ms):
            now>=(reinit_after?reinit_after:start+8*ms);
        if(!coordinator_started && !protection_since && init_ready) {
            if(reinit_after)coordinator.cancel(now);
            require(coordinator.begin(scope.application,now),"begin aligned native session");
            coordinator_started=true;
        }
        if(wall_mode || terminal_response || now==next_physical) {
            const auto wall_job=watch && (physical || now>start)?watch->begin(8):std::nullopt;
            if(physical){physical->step();require(physical->ok(),"fixture physical failure");}
            else if(now>start) {
                std::optional<m7_external::Wheel> input;
                // Beginning-speed ZOH: select from original acquisition history,
                // not the latest end-of-interval sensor or a fabricated zero.
                const auto begin=external->last_success();
                for(const auto& w:wheel_history)if(w.source<=begin)
                    input=m7_external::Wheel{*m7_external::assess(w.omega).forward_rad_s,
                        {7,static_cast<std::uint32_t>(w.frame),w.source},w.source};
                std::array<std::optional<simulation::OwnerActuation>,5> out{};
                for(unsigned i=0;i<5;++i)out[i]=outputs[i].read();
                if(terminal_response || wall_mode) {
                    // Integrator substeps are NOT owner execution opportunities.
                    // Only this complete invocation is measured by wall watch.
                    while(external->last_success()<now) {
                        const auto end=std::min(now,external->last_success()+ms);
                        if(!external->advance_actuators(end,input,out,wall_mode?gates[7].epoch():0,terminal_response || protection_since!=0))throw std::runtime_error(external->error());
                    }
                } else {
                    if(!external->step(now,input,out,gates[7].epoch(),override_signal.pending(scope.application)))
                        throw std::runtime_error(external->error());
                    require(electrical_count<electrical_steps.size(),"M7 interval audit overflow");
                    electrical_steps[electrical_count++]=external->audit();
                }
                if(external->sensors())for(auto& channel:fixture_sensors)channel.publish(*external->sensors());
            }
            // Commit completed work after response history covers NOW, before
            // ECU service, inside the physical owner's measured invocation.
            if(completed_work)completed_work();
            next_physical+=ms;
            if(watch)watch->finish(8,wall_job);
        }
        // A request observed at this invocation cannot affect integration of
        // the already elapsed interval. Select it at NOW, before owner service.
        if(wall_mode && protection_requested)select_wall_protection(now,"wall protection request");
        while(!pending_wheels.empty() && pending_wheels.front().source<=now) {
            wheel=pending_wheels.front();pending_wheels.pop_front();
        }
        while(!pending_poses.empty() && pending_poses.front().source_ns<=now) {
            pose=pending_poses.front();pending_poses.pop_front();
        }
        // One publisher of each actor channel. Pending observations cannot feed
        // earlier subjobs; a held sample keeps its original source AND oldest.
        for(unsigned i=0;i<8;++i)if(auto s=fixture_sensors[i].read()) {
            if(wheel_mode) {
                s->drive.wheel_speed.reset();
                if(wheel)s->drive.wheel_speed=battery::ModelMeasurement<double>{
                    (wheel->omega[2]+wheel->omega[3])/2,
                    {7,static_cast<std::uint32_t>(wheel->frame),wheel->source},wheel->source};
            }
            sensors[i].publish(*s);
        }
        for(unsigned i=0;i<8;++i)if(static_cast<int>(i)!=omitted) {
            const auto wall_job=watch?watch->begin(i):std::nullopt;
            auto& participant=participants[i]->participant_;
            while(!controls[i].empty()) {
                const auto c=controls[i].front();
                if(wall_mode && c.phase==session::Phase::Initialize &&
                   now<c.plan.commit_deadline_ns && now-c.source_ns<=session::kMessageAgeNs) {
                    const auto sample=sensors[i].read();
                    // Receipt latency can leave the previous EV dependency just
                    // past the ORIGINAL 20ms reset-evidence limit at enable.
                    // Keep servicing Prepared; deliver the ORIGINAL INIT only
                    // when safe evidence exists inside its unchanged window.
                    // Never retry a rejected INIT or alter enable/source/ACK.
                    if(now<c.plan.enable_ns || !sample ||
                       !simulation::session_reset_safe(simulation::reset_evidence(*sample),7,now))break;
                }
                controls[i].pop_front();
                const auto m=wire({Role::CentralIngress,static_cast<Role>(i),domain,c});
                ack(participant.receive(std::get<session::Control>(m.payload),now));
            }
            if(i>=2 && i<=4)leaf[i-2]->drop_actual=drop_actual;
            ack(participant.poll(now));
            if(wall_mode && participant.fault()!=session::ParticipantFault::None)select_wall_protection(now,"participant failure");
            else require(participant.fault()==session::ParticipantFault::None,"participant failure");
            if(watch)watch->finish(i,wall_job);
        }
        while(!acks.empty()) {
            const auto a=acks.front();acks.pop_front();
            const auto m=wire({a.role,Role::CentralIngress,domain,a});
            const auto result=coordinator.receive(std::get<session::Ack>(m.payload),now);
            if(result==session::AckResult::Accepted && a.accepted && a.phase==session::Phase::Release) {
                release_mask|=1U<<static_cast<unsigned>(a.role);
                release_acks[static_cast<unsigned>(a.role)]=a;
            }
        }
        coordinator.poll(now);
        if(wall_mode && coordinator.state()==session::State::Failed)select_wall_protection(now,"coordinator failure");
        else require(coordinator.state()!=session::State::Failed,"coordinator failure");
        // Keep servicing original leaf/Zone/Central feedback after the terminal
        // safety selection. No root requests, normal credits or re-arm here.
        if(protection_since || (reinit_after && !coordinator_started))return;
        if(!coordinator.run_enabled())return;
        if(!running){running=true;next_management=coordinator.plan().enable_ns+controller_phase;next_controller=next_management;}
        if(!stop_credit && (!last_lease || now-last_lease>=10*ms)) {
            const auto lease=issuer.issue(now);require(bool(lease),"lease issuer");
            for(unsigned i=0;i<8;++i) {
                // The Central self-credit is local, not an invented v1 wire route.
                const auto delivered=i==7?*lease:std::get<remote::RunLease>(wire({Role::CentralIngress,static_cast<Role>(i),domain,*lease}).payload);
                if(wall_mode && !participants[i]->lease(delivered))select_wall_protection(now,"credit rejected");
                else if(!wall_mode)require(participants[i]->lease(delivered),"credit rejected");
            }
            last_lease=now;
        }
        for(auto& p:participants) {
            if(wall_mode && !p->allowed())select_wall_protection(now,"native credit/gate closed");
            else if(!wall_mode && diagnostic_session && trigger_ns && !p->allowed())select_diagnostic_protection(now);
            else if(!wall_mode)require(p->allowed(),"native credit/gate closed");
        }
        if(protection_since)return;
        const bool controller_due=now>=next_controller;
        if(controller_due && speed_origin && now-speed_origin>=(terminal_mode==SpeedTerminal::NormalStop30?35000:15000)*ms && terminal_mode!=SpeedTerminal::None) {
            if(!trigger_ns){trigger_ns=now;if(diagnostic_fault==DiagnosticFault::FrontLinkFailure)zones[0].work.close();}
            if((terminal_mode==SpeedTerminal::NormalStop || terminal_mode==SpeedTerminal::StopProtection || terminal_mode==SpeedTerminal::NormalStop30) && diagnostic_fault!=DiagnosticFault::SpeedInputLoss && diagnostic_fault!=DiagnosticFault::FrontCommandLoss && diagnostic_fault!=DiagnosticFault::FrontLinkFailure)
                require(core.receive_stop({{scope.application,stop_seq++,now,now+60*ms},0},now)==central::CoordinatorReceive::Accepted,"normal stop request rejected");
        }
        if(controller_due && !core.decision().stopping) {
            // Upstream Controller request remains 20ms. Existing Host10ms child
            // allocation/permission renewal is retained, not a new Controller rate.
            core.receive_lifecycle({{scope.application,lifecycle_seq++,now,now+60*ms},can::BmsPowerAction::Enable},now);
            if(core.decision().normal_armed && !speed_enabled) {
                RequestPhase request{10000,.2,.02,0,false};
                if(!profile.empty()) {
                    const auto it=std::find_if(profile.begin(),profile.end(),[&](const RequestPhase& phase) {
                        return now-start<phase.end_ms*ms;
                    });
                    require(it!=profile.end(),"request profile exhausted");request=*it;
                }
                core.receive_vehicle({scope.application,vehicle_seq++,now,now+60*ms,
                    request.acceleration,request.curvature,request.braking,request.hold},now);
            }
        }
        if(controller_due) {next_controller=wall_mode?next_controller+((now-next_controller)/(20*ms)+1)*(20*ms):next_controller+20*ms;++controller_releases;}
        if(speed_enabled && core.decision().normal_armed && controller_due && (!trigger_ns || terminal_mode==SpeedTerminal::SpeedInputLoss || diagnostic_fault==DiagnosticFault::SpeedInputLoss || diagnostic_fault==DiagnosticFault::FrontCommandLoss)) {
                if(!speed_origin)speed_origin=now;
                const auto feedback=port.feedback();
                const auto permission=port.current_permission();
                const auto* grant=permission?std::get_if<can::BmsDriveGrant>(&permission->message.content):nullptr;
                const bool allowed=core.decision().management.normal_allowed && grant &&
                    permission->message.epoch==scope.application &&
                    grant->permission==can::BmsDrivePermission::AllowNormal && now<grant->expires_at_ns;
                if(pursuit) {
                    if(!pose) {protect_central();require(false,"missing route pose");}
                    require(allowed && feedback.rear.drive_actual && feedback.rear.drive_actual->wheel_speed,"route speed input missing");
                    lateral_audit=pursuit->step(now,*pose,feedback.rear.drive_actual->wheel_speed->value_rad_s*.355);
                    if(!lateral_audit) {protect_central();require(false,"route control rejected");}
                }
                const auto target=pursuit?route_speed.step(now-speed_origin,lateral_audit->progress_m):speed_target(now-speed_origin);
                speed_selection=antiwindup && speed_audit?core.decision().allocation.propulsion_selection:std::nullopt;
                saturation_used=antiwindup && (!speed_audit || (speed_selection && speed_selection->limited));
                braking_saturation_used=antiwindup && (!speed_audit || (speed_selection && speed_selection->braking_limited));
                const bool omit_speed=trigger_ns && (terminal_mode==SpeedTerminal::SpeedInputLoss || diagnostic_fault==DiagnosticFault::SpeedInputLoss);
                std::optional<central::DerivedVehicleRequest> derived;
                if(supervised_speed) {
                    available_force=omit_force?std::nullopt:force_estimator->estimate(feedback,now);
                    // The classical route computation is performed on this release.
                    // Its live pose dependency is attached below without refreshing it.
                    const central::ClassicalSpeedProposal fallback{scope.application,domain,now,now+30*ms+1,target,true};
                    derived=supervised_speed->step(now,std::nullopt,fallback,
                        omit_speed?std::nullopt:feedback.rear.drive_actual,available_force,allowed,speed_selection);
                    if(!derived) {select_diagnostic_protection(now);return;}
                } else derived=speed_request.step_derived(now,target,omit_speed?std::nullopt:feedback.rear.drive_actual,allowed,speed_selection);
                if(!derived && (terminal_mode==SpeedTerminal::SpeedInputLoss || diagnostic_fault==DiagnosticFault::SpeedInputLoss) && trigger_ns) {
                    detection_ns=now;protection_since=now;protect_central();for(auto& p:participants)p->select_protection();return;
                }
                if(derived && pursuit) {
                    derived->request.curvature_inv_m=lateral_audit->curvature_inv_m;
                    derived->input.source_time_ns=std::min(derived->input.source_time_ns,pose->source_ns);
                    derived->input.expires_at_ns=std::min(derived->input.expires_at_ns,pose->source_ns+60*ms+1);
                    derived->request.expires_at_ns=std::min(derived->request.expires_at_ns,derived->input.expires_at_ns);
                }
                const auto* request=derived?&derived->request:nullptr;
                if(!request) {protect_central();throw std::runtime_error("speed request rejected");}
                require(core.receive_vehicle(*request,now,derived->input)==central::CoordinatorReceive::Accepted,"speed request admission");
                const auto& state=supervised_speed?supervised_speed->controller().state():speed_request.state();
                speed_audit=SpeedControlAudit{now,speed_origin,state.sample->source_ns,request->expires_at_ns,derived->input.expires_at_ns,request->sequence,
                    supervised_speed?supervised_speed->reference()->target_mps:target,state.sample->speed_mps,request->acceleration_mps2,state.integral};

        }
        const bool due=now>=next_management;
        if(due)next_management=wall_mode?next_management+((now-next_management)/(10*ms)+1)*(10*ms):next_management+10*ms;
        core.tick(port.feedback(),now,due);
        if((terminal_mode==SpeedTerminal::StopProtection || terminal_mode==SpeedTerminal::NormalStop30) && !handoff_ns && core.decision().stop.state==central::NormalStopState::PowerDown)handoff_ns=now;
        if(wall_mode && core.decision().fault!=central::CoordinatorFault::None)select_wall_protection(now,"native control protection");
        else if(diagnostic_session && trigger_ns && core.decision().fault!=central::CoordinatorFault::None)select_diagnostic_protection(now);
        else require(core.decision().fault==central::CoordinatorFault::None,"native control protection");
    }
    std::string wall_failure;
    void select_wall_protection(Time now,const char* reason) {
        if(!wall_mode || protection_since)return;
        wall_failure=reason;protection_since=now;
        for(unsigned i=0;i<5;++i)if(leaf[i]->faulted())
            wall_failure+=" leaf="+std::to_string(i)+" code="+std::to_string(leaf[i]->fault_code());
        for(unsigned i=0;i<8;++i)if(participants[i]->participant_.fault()!=session::ParticipantFault::None)
            wall_failure+=" participant="+std::to_string(i)+" code="+std::to_string(static_cast<unsigned>(participants[i]->participant_.fault()));
        protect_central();for(auto& p:participants)p->select_protection();
    }
    Report advance(Time observed) {
        require(observed>=clock.logical && observed-start<=horizon_ms*ms,"finite logical horizon");
        electrical_count=0;
        // Jobs are scheduled on the existing 0.2ms ingress/1ms fixture grids.
        // No observation is used before its timestamp. The optional real wheel
        // feeds ECU sensors only; actuator/electrical models remain a fixture.
        while(next_io<=observed){cycle(next_io);next_io+=200000;}
        clock.logical=observed;
        return report(observed);
    }
    Report report(Time observed) {
        Report r;r.terminal_mode=terminal_mode;r.trigger_ns=trigger_ns;r.detection_ns=detection_ns;r.handoff_ns=handoff_ns;r.stop_configuration=stop_settings;
        r.diagnostic_fault=diagnostic_fault;r.fault_omissions=command_omission.count+ack_omission.count+(diagnostic_fault==DiagnosticFault::FrontLinkFailure && trigger_ns?1:0);
        if(control_diagnostics) {
            require(control_diagnostics->healthy() && startup_diagnostics->healthy(),"diagnostic capture incomplete");
            std::vector<diagnostics::Event> batch;diagnostics::Event event;
            for(auto* queue:{startup_events.get(),control_events.get()})while(queue->pop(event))batch.push_back(event);
            for(unsigned i=0;i<5;++i) {
                require(i<2?gateway_diagnostics[i]->healthy():leaf_diagnostics[i-2]->healthy(),"command diagnostic capture incomplete");
                while(command_events[i]->pop(event)) {command_response.root(event);batch.push_back(event);}
            }
            command_response.observe(port.feedback(),observed,[&](const auto& e){batch.push_back(e);});
            if(!batch.empty())r.diagnostic_events=std::make_shared<const std::vector<diagnostics::Event>>(std::move(batch));
        }
        if(supervised_speed)r.supervised_speed=SupervisedSpeedAudit{supervised_speed->decision(),available_force,
            supervised_speed->reference(),supervised_speed->fault_observation()};
        r.speed_fault=static_cast<int>(supervised_speed?supervised_speed->controller().fault():speed_request.fault());r.stop_state=core.decision().stop.state;r.stop_fault=static_cast<int>(core.decision().stop.fault);r.power_off=core.decision().management.power_off_confirmed;
        r.propulsion_antiwindup=antiwindup;r.saturation_used=saturation_used;r.braking_saturation_used=braking_saturation_used;r.speed_selection=speed_selection;
        r.allocation_selection=core.decision().allocation.propulsion_selection;
        r.speed_control=speed_audit;r.lateral_control=lateral_audit;r.now=observed;r.release_mask=release_mask;r.armed=core.decision().normal_armed;
        if(pursuit && speed_audit)r.route_reference=RouteReferenceAudit{
            route_speed.requested_mps(speed_audit->target_mps),
            route_speed.slow_ns(),route_speed.stop_ns()};
        if(external && external->last_success()>start)r.electrical=external->audit();
        if(external) {r.coils=external->applied_coils();r.coil_source=external->applied_coil_source();r.electrical_acquired=external->electrical_acquisition();}
        if(external && external->sensors() && external->sensors()->drive.hv) {
            const auto& hv=*external->sensors()->drive.hv;
            r.hv_source=hv.identity.source_time_ns;r.hv_dependency=hv.input_time_ns;
        }
        r.electrical_steps=electrical_steps;r.electrical_count=electrical_count;
        if(wheel)r.sensor_wheel=WheelAudit{wheel->source,(wheel->omega[2]+wheel->omega[3])/2};
        r.controller_releases=controller_releases;
        for(unsigned i=0;i<8;++i) {
            if(static_cast<int>(i)!=omitted)r.service_mask|=1U<<i;
            if(participants[i]->allowed())r.credit_mask|=1U<<i;
        }
        for(unsigned i=0;i<5;++i) {r.commands[i]=leaf[i]->received_commands();r.leaf_body[i]=leaf[i]->last_body_ns();}
        if(const auto& lease=participants[7]->credit.accepted();lease){r.lease_source=lease->source_time_ns;r.lease_expiry=lease->expires_at_ns;}
        const auto feedback=port.feedback();
        if(terminal_mode!=SpeedTerminal::None && feedback.rear.power_status) {
            const auto& m=feedback.rear.power_status->message;
            const auto f=feedback_capture[1].find([&](const transport::Feedback& v) {
                const auto* raw=std::get_if<can::BmsFrame>(&v);const auto x=raw?can::decode_bms_frame(*raw):std::nullopt;
                return x && x->kind==m.kind && x->epoch==m.epoch && x->sequence==m.sequence && x->source_time_ns==m.source_time_ns;
            });
            if(f)r.power_status=remote::encode_owner_message({Role::RearZone,Role::CentralIngress,domain,*f});
        }
        if(feedback.rear.drive_actual) {
            const auto& drive=*feedback.rear.drive_actual;
            if(drive.wheel_speed)r.returned_wheel=WheelAudit{drive.wheel_speed->source_time_ns,drive.wheel_speed->value_rad_s};
            r.returned_torque=drive.torque_nm;
            if(drive.regen_capability)r.regen_oldest=drive.regen_capability->input_time_ns;
        }
        if(feedback.front.steering_actual && feedback.front.brake_actual && feedback.rear.drive_actual) {
            r.actual_sources={feedback.front.steering_actual->source_time_ns,feedback.front.brake_actual->source_time_ns,feedback.rear.drive_actual->source_time_ns};
            r.actual_interval=true;
            for(const auto source:r.actual_sources)
                r.actual_interval=r.actual_interval && source<=observed && observed+tick_ns-source<=30*ms;
            const auto bounds=std::minmax_element(r.actual_sources.begin(),r.actual_sources.end());
            r.actual_interval=r.actual_interval && *bounds.second-*bounds.first<=10*ms;
        }
        if(r.armed && !wall_mode)require(r.credit_mask==255 && r.actual_interval,"shadow Actual interval missing/stale");
        if(export_actual) {
            NativeExport e;e.observed=observed;e.enable=feedback.session_enable_ns;e.normal=r.armed;
            e.protection_since=protection_since;
            if(protection_since) {
                for(unsigned i=0;i<2;++i)if(zones[i].protection.acknowledged(scope.application))e.protection_selected_mask|=1U<<i;
                for(unsigned i=0;i<5;++i)if(leaves[i].protection.acknowledged(scope.application))e.protection_selected_mask|=1U<<(i+2);
                if(core.decision().fault!=central::CoordinatorFault::None && !gates[7].allows(scope.application))e.protection_selected_mask|=128;
            }
            for(unsigned i=0;i<8;++i)if(release_acks[i])
                e.release[i]=remote::encode_owner_message({static_cast<Role>(i),Role::CentralIngress,domain,*release_acks[i]});
            for(unsigned i=0;i<7;++i)if(participants[i]->credit.accepted())
                e.credit[i]=remote::encode_owner_message({Role::CentralIngress,static_cast<Role>(i),domain,*participants[i]->credit.accepted()});
            const auto capture=[&](unsigned i,const auto& message) {
                if(!message)return;
                const unsigned z=i<2?0:1;
                const auto raw=feedback_capture[z].find([&](const transport::Feedback& f) {
                    const auto meta=std::visit([](const auto& frame)->std::optional<can::ActuatorMetadata> {
                        using F=std::decay_t<decltype(frame)>;
                        if constexpr(std::is_same_v<F,can::SteeringFrame>) {auto v=can::decode_steering_frame(frame);if(v)return can::ActuatorMetadata{v->sequence,v->epoch,v->source_time_ns,v->causal_sequence,v->local_state,v->origin};}
                        if constexpr(std::is_same_v<F,can::BrakeFrame>) {auto v=can::decode_brake_frame(frame);if(v)return can::ActuatorMetadata{v->sequence,v->epoch,v->source_time_ns,v->causal_sequence,v->local_state,v->origin};}
                        if constexpr(std::is_same_v<F,can::DriveFrame>) {auto v=can::decode_drive_frame(frame);if(v)return can::ActuatorMetadata{v->sequence,v->epoch,v->source_time_ns,v->causal_sequence,v->local_state,v->origin};}
                        return {};
                    },f);
                    return f.index()==i && meta && meta->epoch==message->epoch && meta->sequence==message->sequence && meta->source_time_ns==message->source_time_ns;
                });
                if(raw)e.actual[i]=remote::encode_owner_message({static_cast<Role>(z),Role::CentralIngress,domain,*raw});
                const auto command=command_capture[i].find([&](const transport::LeafRequest& q) {
                    if(!q.command || q.operation!=transport::LeafOperation::Frame)return false;
                    const auto seq=std::visit([](const auto& f)->std::optional<std::uint32_t> {
                        using F=std::decay_t<decltype(f)>;
                        if constexpr(std::is_same_v<F,can::SteeringFrame>) {auto v=can::decode_steering_frame(f);if(v)return v->sequence;}
                        if constexpr(std::is_same_v<F,can::BrakeFrame>) {auto v=can::decode_brake_frame(f);if(v)return v->sequence;}
                        if constexpr(std::is_same_v<F,can::DriveFrame>) {auto v=can::decode_drive_frame(f);if(v)return v->sequence;}
                        return {};
                    },q.frame);
                    return q.epoch==message->epoch && seq && *seq==message->causal_sequence;
                });
                if(command)e.commands[i]=remote::encode_owner_message({static_cast<Role>(z),static_cast<Role>(i+2),domain,*command});
                if((message->local_state!=can::ActuatorLocalState::Normal && message->local_state!=can::ActuatorLocalState::Degraded) || message->origin!=can::ActuatorOrigin::NormalPath)e.normal=false;
            };
            capture(0,feedback.front.steering_actual);capture(1,feedback.front.brake_actual);capture(2,feedback.rear.drive_actual);
            if((terminal_mode==SpeedTerminal::NormalStop || terminal_mode==SpeedTerminal::StopProtection || terminal_mode==SpeedTerminal::NormalStop30) && core.decision().stop.state>=central::NormalStopState::HandoffPending) {
                for(unsigned i=0;i<3;++i) {
                    const auto q=command_capture[i].find([](const transport::LeafRequest& q){return q.operation==transport::LeafOperation::Stop;});
                    if(!q)continue;
                    const auto a=result_capture[i].find([&](const transport::LeafReport& v){const auto* a=std::get_if<transport::LeafResult>(&v);return a && a->epoch==q->epoch && a->token==q->token && a->operation==q->operation && a->accepted;});
                    if(!a)continue;
                    e.stop_requests[i]=remote::encode_owner_message({i<2?Role::FrontZone:Role::RearZone,static_cast<Role>(i+2),domain,*q});
                    e.stop_results[i]=remote::encode_owner_message({static_cast<Role>(i+2),i<2?Role::FrontZone:Role::RearZone,domain,*a});
                }
            }
            const auto permission=port.current_permission();
            if(permission) {
                const auto q=command_capture[2].find([&](const transport::LeafRequest& q) {
                    const auto* f=std::get_if<can::BmsFrame>(&q.frame);const auto m=f?can::decode_bms_frame(*f):std::nullopt;
                    return m && m->kind==can::BmsFrameKind::DrivePermission && m->epoch==permission->message.epoch && m->sequence==permission->message.sequence && m->source_time_ns==permission->message.source_time_ns;
                });
                if(q)e.permission=remote::encode_owner_message({Role::RearZone,Role::Drive,domain,*q});
            }
            for(unsigned i=0;i<3;++i)e.normal=e.normal && bool(e.actual[i]) && bool(e.commands[i]);
            e.normal=e.normal && bool(e.permission);
            // Previous-epoch caches cannot authorize the new bootstrap. The
            // original queues/owners still perform real PREPARE/INIT/Release.
            if(reinit_after && !running){e=NativeExport{};e.observed=observed;}
            r.native_export=std::move(e);
        }
        return r;
    }
};

FunctionalRig::FunctionalRig(Scope scope,std::uint32_t actor,PlantMode mode,bool exporting,Time horizon):scope_(scope),clock_(scope),wheel_actor_(actor),plant_mode_(mode),export_actual_(exporting),horizon_ms_(horizon) {
    // Native PhysicalOwner's immutable fixture epoch is 7. Do not pretend a
    // packet can choose a new physical plant identity or an axle calibration.
    require(!actor || scope.plant==7,"wheel fixture plant binding");
    require(mode==PlantMode::StationaryFixture || actor!=0,"external plant requires wheel binding");
    require(horizon>=10000 && (horizon<=60000 || horizon==80000) &&
            (horizon==10000 || (mode==PlantMode::ExternalSolverWork && exporting)),"bounded simulation-only horizon");
}
FunctionalRig::~FunctionalRig()=default;
Report FunctionalRig::observe(const Observation& o) {
    return observe_impl(o,std::nullopt);
}
Report FunctionalRig::observe(const Observation& o,const WheelSample& wheel) {
    return observe_impl(o,wheel);
}
Report FunctionalRig::observe(const Observation& o,const WheelSample& wheel,const m7_external::SolverWork& work) {
    require(!work_,"duplicate pending work");work_=work;
    return observe_impl(o,wheel);
}
Report FunctionalRig::observe_impl(const Observation& o,const std::optional<WheelSample>& wheel) {
    try {
        require(horizon_ms_!=80000 || (!route_.empty() && (route_profile_==RouteProfile::Combined || route_profile_==RouteProfile::CombinedV2)),"extended route scope");
        const auto now=clock_.accept(o);
        require(bool(pose_)==!route_.empty(),"missing/unexpected route pose");
        if(pose_)require(pose_->sequence==o.frame && pose_->source_ns==now,"route pose identity/time");
        require(bool(wheel)==bool(wheel_actor_),"missing/unbound wheel source");
        if(wheel) {
            require(wheel->actor==wheel_actor_ && wheel->frame==o.frame &&
                    wheel->frame<=UINT32_MAX && wheel->source==now,"wheel identity/time");
            const auto assessed=m7_external::assess(wheel->omega);
            require(bool(assessed.forward_rad_s),m7_external::reason(assessed.validity));
        }
        const bool initial=!native_;
        require(plant_mode_==PlantMode::ExternalSolverWork ? (initial?!work_:bool(work_)) : !work_,"missing/unexpected solver work");
        if(!native_){native_=std::make_unique<Native>(scope_,now,plant_mode_,export_actual_,false,0,horizon_ms_,10000000,30000000,speed_profile_,route_,route_profile_,antiwindup_,road_load_);
            if(diagnostic_fault_!=DiagnosticFault::Disabled || road_load_)
                native_->enable_diagnostics(diagnostic_fault_==DiagnosticFault::Disabled?DiagnosticFault::None:diagnostic_fault_);
        }
        native_->terminal_mode=terminal_mode_;native_->omit_force=omit_force_;
        if(pose_) {
            require(native_->pending_poses.size()<2,"pose pending overflow");
            native_->pending_poses.push_back(*pose_);pose_.reset();
        }
        native_->profile=profile_;
        native_->controller_phase=controller_phase_;
        native_->watch=watch_;
        if(work_) {
            require(work_->frame==o.frame && work_->end==now && native_->external->begin_work_frame(*work_),"solver work admission");
        }
        native_->wheel_mode=wheel_actor_!=0;
        if(wheel) {
            // An original floating timestamp may precede the next native job
            // by a few ns. Keep that sample until its first eligible job; never
            // overwrite it with the following frame or shift its source time.
            require(native_->pending_wheels.size()<2,"wheel pending overflow");
            native_->pending_wheels.push_back(*wheel);
            native_->wheel_history.push_back(*wheel);
            // At most current + four original acquisitions; the oldest retained
            // sample predates the next pending 1ms step even at fractional phases.
            if(native_->wheel_history.size()>5)native_->wheel_history.pop_front();
        }
        native_->omitted=omitted_;native_->stop_credit=stop_credit_;native_->drop_actual=drop_actual_;
        native_->protection_requested=protect_;
        auto r=native_->advance(now);
        if(work_) {
            require(native_->external->finish_work_frame(now),native_->external->error().c_str());
            const auto& audit=native_->external->audit();
            if(audit.end>audit.begin) {
                require(r.electrical_count<r.electrical_steps.size(),"solver tail audit overflow");
                r.electrical_steps[r.electrical_count++]=audit;
            }
            r.electrical=audit;
            if(native_->external->sensors())for(auto& channel:native_->fixture_sensors)channel.publish(*native_->external->sensors());
            work_.reset();
        }
        for(unsigned i=0;i<8;++i)if(r.service_mask&(1U<<i))clock_.serviced(i);
        r.next_frame=clock_.permit_non_driving_tick();
        if(plant_mode_==PlantMode::ExternalSolverWork)native_->external->commit_work_frame();
        return r;
    } catch(...) {
        if(native_ && !terminal_wall_ && plant_mode_==PlantMode::ExternalSolverWork)native_->external->abort_work_frame();
        clock_.fail();throw;
    }
}
void FunctionalRig::request_profile(std::vector<RequestPhase> phases) {
    require(!native_ && !speed_profile_ && !phases.empty() && phases.size()<=32,"profile must be bounded and set before INIT");
    Time previous=0;
    for(const auto& p:phases) {
        require(p.end_ms>previous && p.end_ms<=horizon_ms_ && std::isfinite(p.acceleration) &&
            p.acceleration>=-5 && p.acceleration<=2 && std::isfinite(p.curvature) &&
            std::abs(p.curvature)<=1 && std::isfinite(p.braking) && p.braking>=0 && p.braking<=1,"invalid request profile");
        previous=p.end_ms;
    }
    profile_=std::move(phases);
}
void FunctionalRig::speed_profile(SpeedTerminal terminal) {
    require(terminal==SpeedTerminal::None || terminal==SpeedTerminal::NormalStop || terminal==SpeedTerminal::SpeedInputLoss || terminal==SpeedTerminal::StopProtection,"unknown terminal profile");
    require(!native_ && profile_.empty() && !speed_profile_ && export_actual_ &&
        plant_mode_==PlantMode::ExternalSolverWork && horizon_ms_==60000,"speed profile requires solver simulation scope");
    speed_profile_=true;terminal_mode_=terminal;
}
void FunctionalRig::supervise_speed(central::RoadLoadBounds bounds) {
    require(!native_ && !road_load_ && !watch_,"supervision must be selected once before INIT");
    const central::AvailableForceEstimator checked(allocation(true),bounds);
    road_load_=bounds;
}
void FunctionalRig::omit_force_input(bool value) {
    require(bool(road_load_),"force omission requires supervised path");omit_force_=value;
}
void FunctionalRig::reinitialize(std::uint32_t application) {
    require(owner_==std::this_thread::get_id() && native_ && !clock_.failed() && !work_ && !terminal_wall_ &&
        !watch_ && road_load_ && route_.empty() && application>scope_.application &&
        native_->protection_since && native_->external && native_->external->ok(),"reinit protected simulation barrier");
    auto& n=*native_;const auto now=clock_.now();
    require(n.external->electrical_time()==now,"reinit fully settled energy barrier");
    for(unsigned i=0;i<8;++i){const auto sample=n.sensors[i].read();
        require(!n.gates[i].allows(scope_.application) && sample &&
            simulation::session_reset_safe(simulation::reset_evidence(*sample),7,now),"reinit stationary HV-off physical evidence");
    }
    require(n.wheel && now>=n.wheel->source && now-n.wheel->source<=30*ms &&
        std::all_of(n.wheel->omega.begin(),n.wheel->omega.end(),[](double v){return std::abs(v)<=.01;}),"reinit stationary original wheel");
    clock_.application(application);scope_.application=application;n.scope=scope_;
    n.reinit_after=now+8*ms;n.coordinator_started=false;n.running=false;
    n.protection_since=0;n.protection_requested=false;protect_=false;
    n.release_mask=0;n.release_acks={};n.last_lease=0;
    n.diagnostic_session=false;n.diagnostic_selected={};
    n.speed_origin=0;n.speed_audit.reset();n.available_force.reset();n.speed_selection.reset();
    n.lifecycle_seq=0;n.vehicle_seq=0;n.stop_seq=0;n.trigger_ns=0;n.detection_ns=0;n.handoff_ns=0;
    n.terminal_mode=terminal_mode_=SpeedTerminal::None;omit_force_=false;n.omit_force=false;
}
void FunctionalRig::controller_phase(Time delay) {
    require(!native_ && delay<=20*ms && delay%200000==0,"controller phase must be set before INIT on existing ingress grid");
    controller_phase_=delay;
}
void FunctionalRig::route_profile(std::vector<central::RoutePoint> points,RouteProfile profile,bool antiwindup) {
    require(profile==RouteProfile::Curve30 || profile==RouteProfile::Straight30 || profile==RouteProfile::Combined || profile==RouteProfile::CombinedV2 || profile==RouteProfile::Straight30Stop,"unknown route profile");
    require(profile!=RouteProfile::Straight30Stop || !antiwindup,"stop30 uses frozen v1 PI");
    central::PurePursuit checked(points,2.860470886230469);
    if(antiwindup) {
        const auto c=allocation(true);
        require(central::inertial_ramp_feasible(0,30/3.6,profile==RouteProfile::Combined?10:20,
            c.mass_kg,c.wheel_radius_m,c.max_propulsion_nm,c.max_service_braking_nm),"infeasible startup reference");
        const bool combined=profile==RouteProfile::Combined || profile==RouteProfile::CombinedV2;
        require(central::inertial_ramp_feasible(30/3.6,combined?20/3.6:0,combined?6:15,
            c.mass_kg,c.wheel_radius_m,c.max_propulsion_nm,c.max_service_braking_nm),"infeasible braking reference");
        if(combined)require(central::inertial_ramp_feasible(20/3.6,0,8,c.mass_kg,c.wheel_radius_m,c.max_propulsion_nm,c.max_service_braking_nm),"infeasible stop reference");
    }
    require(!native_ && profile_.empty() && !speed_profile_ && export_actual_ &&
        plant_mode_==PlantMode::ExternalSolverWork && horizon_ms_==((profile==RouteProfile::Combined || profile==RouteProfile::CombinedV2)?80000U:60000U),"route profile scope");
    speed_profile_=true;route_profile_=profile;route_=std::move(points);antiwindup_=antiwindup;
    if(profile==RouteProfile::Straight30Stop)terminal_mode_=SpeedTerminal::NormalStop30;
}
void FunctionalRig::pose(central::RoutePose sample,std::uint32_t actor) {
    require(!route_.empty() && !pose_ && actor==wheel_actor_ && sample.epoch==scope_.application,"route pose binding");
    pose_=sample;
}
void FunctionalRig::omit_role(int role) {omitted_=role;}
void FunctionalRig::stop_credit(bool value) {stop_credit_=value;}
void FunctionalRig::drop_actual(bool value) {drop_actual_=value;}
void FunctionalRig::diagnostic_profile(DiagnosticFault fault) {
    require(!native_ && !watch_ && fault>=DiagnosticFault::None && fault<=DiagnosticFault::FrontLinkFailure && route_profile_==RouteProfile::Straight30Stop && !route_.empty(),"diagnostic profile requires frozen STOP30 before INIT");
    diagnostic_fault_=fault;
}
void FunctionalRig::request_protection() {protect_=true;}
void FunctionalRig::execution_watch(WallExecutionWatch* watch) {watch_=watch;}
void FunctionalRig::begin_terminal_response(Time wall) {
    require(owner_==std::this_thread::get_id(),"terminal mutation owner");
    require(!terminal_wall_ && wall && native_ && !work_ &&
        plant_mode_==PlantMode::ExternalSolverWork && native_->external &&
        native_->running && native_->core.decision().normal_armed,
        "terminal response requires settled normal solver barrier");
    require(native_->external->electrical_time()==native_->clock.logical &&
        native_->external->begin_terminal_response(),"terminal model handoff");
    terminal_wall_=last_terminal_wall_=wall;terminal_local_=native_->clock.logical;
    native_->terminal_response=true;
    // Select at the handoff anchor, before any elapsed response integration.
    // A later service must not feed its newly issued outputs to earlier substeps.
    native_->protection_since=terminal_local_;
    native_->protect_central();
    for(auto& p:native_->participants)p->select_protection();
    native_->watch=watch_;
    clock_.fail(); // Irreversible: never map this local branch back into CARLA.
}
Report FunctionalRig::service_terminal_response(Time wall) {
    require(owner_==std::this_thread::get_id(),"terminal mutation owner");
    require(terminal_wall_ && wall>last_terminal_wall_ && wall-terminal_wall_<=1000*ms &&
        terminal_local_<=UINT64_MAX-(wall-terminal_wall_),"terminal monotonic interval/horizon");
    const auto local=terminal_local_+(wall-terminal_wall_);
    // No catch-up ECU polls. Original timer owners see the actual elapsed time
    // once; missed wall opportunities stay missing in the original monitor.
    native_->electrical_count=0;
    native_->cycle(local);
    last_terminal_wall_=wall;
    auto report=native_->report(local);
    report.next_frame=0;
    require(!report.armed && !report.credit_mask,"terminal authority reopened");
    return report;
}
BarrierStop FunctionalRig::stop_at_barrier() {
    require(bool(native_),"wall stop requires a completed barrier");
    auto& n=*native_;
    n.protect_central();
    for(auto& p:n.participants)p->select_protection();
    BarrierStop result{n.clock.logical,0,0,n.core.decision().normal_armed};
    // Local readback, NOT a fabricated remote ProtectionAck. No service/replay
    // is needed to observe that the original Zone selected its leaf protection.
    for(unsigned i=0;i<2;++i)if(n.zone[i]->protected_selected())result.selected_mask|=1U<<i;
    for(unsigned i=0;i<5;++i)if(n.leaves[i].protection.acknowledged(scope_.application))result.selected_mask|=1U<<(i+2);
    if(n.core.decision().fault!=central::CoordinatorFault::None && !n.gates[7].allows(scope_.application))result.selected_mask|=128;
    for(unsigned i=0;i<8;++i)if(n.participants[i]->allowed())result.credit_mask|=1U<<i;
    clock_.fail(); // A fresh snapshot cannot heal this terminal wall stop.
    return result;
}

WallRig::WallRig(Scope scope,std::uint32_t actor,Time initial,Time model_initial,Time model_step,Time hv_dependency_ns,unsigned endurance_seconds)
    :scope_(scope),actor_(actor),model_initial_(model_initial),model_step_(model_step),
     horizon_ms_(endurance_seconds?(Time(endurance_seconds)+5)*1000:(model_initial?30000:10000)),initial_(initial) {
    require(scope.run && scope.application && scope.plant==7 && actor && initial,"wall INIT scope");
    require(model_step==10000000 || (model_initial && model_step==5000000),"wall model step profile");
    require(hv_dependency_ns==30000000 || (model_initial && model_step==5000000 && hv_dependency_ns==50000000),"wall HV dependency profile");
    require(!endurance_seconds || ((endurance_seconds==30 || endurance_seconds==300) && model_initial &&
        model_step==5000000 && hv_dependency_ns==30000000),"bounded endurance wall profile");
    native_=std::make_unique<FunctionalRig::Native>(scope,initial,PlantMode::ExternalSolverWork,true,true,model_initial,
        endurance_seconds?horizon_ms_:10000,model_step,hv_dependency_ns);
    native_->wheel_mode=true;
}
WallRig::~WallRig()=default;
std::array<simulation::LeafStartupObservation,5> WallRig::startup_observations() const {
    require(owner_==std::this_thread::get_id(),"wall startup observation owner");
    std::array<simulation::LeafStartupObservation,5> result{};
    for(unsigned i=0;i<5;++i)result[i]=native_->leaf[i]->startup_observation();
    return result;
}
void WallRig::request_profile(std::vector<RequestPhase> profile) {
    require(owner_==std::this_thread::get_id() && !last_,"wall profile before service");
    FunctionalRig validator(scope_,actor_,PlantMode::ExternalSolverWork,true);
    validator.request_profile(profile);
    if(model_initial_)profile.back().end_ms=horizon_ms_;
    native_->profile=std::move(profile);
}
void WallRig::execution_watch(WallExecutionWatch* watch) {
    require(owner_==std::this_thread::get_id() && !last_,"wall watch before service");
    native_->watch=watch;
}
void WallRig::protect(const char* reason) {
    require(owner_==std::this_thread::get_id(),"wall mutation owner");
    if(failure_.empty())failure_=reason;
    native_->protection_requested=true;
}
WallReport WallRig::service(Time now,const std::optional<WallReceipt>& receipt) {
    require(owner_==std::this_thread::get_id(),"wall mutation owner");
    require(now>=initial_ && (!last_ || now>last_) && now-initial_<=horizon_ms_*ms,"wall monotonic horizon");
    auto& n=*native_;
    bool valid_receipt=false;
    if(receipt) {
        const auto& w=receipt->wheel;
        const auto& work=receipt->work;
        // Validate before insertion. Original wall acquisition and observed work
        // must agree; no arrival-time rewrite, implicit offset or frame skipping.
        if(receipt->clock!=wall_domain || w.actor!=actor_ || w.frame>UINT32_MAX || !w.frame || w.source>now || w.source<initial_ ||
           (last_frame_ && (w.frame!=last_frame_+1 || w.source<=last_source_)) ||
           !m7_external::assess(w.omega).forward_rad_s ||
           work.frame!=w.frame || !work.valid(model_step_) || bool(receipt->carla)!=bool(model_initial_) ||
           (receipt->carla ? (receipt->carla->acquired_begin!=w.source || receipt->carla->acquired_end>now ||
                             receipt->carla->work.frame!=work.frame) : work.end!=w.source)) {
            protect("wall receipt identity/clock/value");
        } else {
            n.wheel=w;n.wheel_history.push_back(w);
            if(n.wheel_history.size()>5)n.wheel_history.pop_front();
            last_frame_=w.frame;last_source_=w.source;
            valid_receipt=true;
        }
    }
    if(n.watch && n.watch->faulted())protect("wall execution deadline");
    n.electrical_count=0;
    // One actual service invocation. Substeps below integrate held model output;
    // they do not call the ECU owners and are not counted as execution slots.
    n.cycle(now,[&] {
        // A normal-authority fault does not erase already executed physics.
        if(valid_receipt) {
            if(!(receipt->carla?n.external->settle_carla_frame(*receipt->carla):n.external->settle_observed_frame(receipt->work)))protect(n.external->error().c_str());
            if(n.external->sensors())for(auto& s:n.fixture_sensors)s.publish(*n.external->sensors());
        }
    });
    if(!n.external->electrical_ok())protect(n.external->error().c_str());
    if(horizon_ms_>30000)for(const auto& leaf:n.leaf)
        if(leaf->input_event_capacity_exhausted())protect("bounded endurance leaf diagnostic capacity");
    if(!failure_.empty())n.select_wall_protection(now,failure_.c_str());
    if(failure_.empty() && !n.wall_failure.empty())failure_=n.wall_failure;
    last_=now;
    auto report=n.report(now);report.next_frame=0;
    return {std::move(report),initial_,n.protection_since,!failure_.empty(),failure_};
}
} // namespace stratadrive::m7_functional
