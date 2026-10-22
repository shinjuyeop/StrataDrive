#include "m4_owner_network.hpp"
#include <chrono>
#include <new>

namespace stratadrive::simulation::m4_detail {
std::uint64_t cpu_now() { timespec t{}; if(clock_gettime(CLOCK_THREAD_CPUTIME_ID,&t)!=0) throw std::runtime_error("thread CPU clock"); return static_cast<std::uint64_t>(t.tv_sec)*1000000000+static_cast<std::uint64_t>(t.tv_nsec); }
std::uint64_t wall_now() { return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count()); }
bool PhysicalOwner::observe(bool ok,const char* model,const char* site,std::uint64_t input) {
    const unsigned component=model[0]=='e'?0:model[0]=='d'?1:model[0]=='s'?2:model[0]=='b'?3:4;
    if(!ok && !failure_.call_ns) {
        failure_={model,site,current_call_,previous_call_,last_success_,input,current_call_>=last_?current_call_-last_:0,released_epoch_,override_.pending(released_epoch_),{}};
        failure_.return_ns=clock_.now_ns();failure_.component_last_success_ns=component_success_[component];
        for(std::size_t i=0;i<outputs_.size();++i)if(auto out=outputs_[i].read())failure_.outputs[i]=*out;
        events_.push_back({current_call_,"physical-model-failure",8,released_epoch_,input,0,last_success_,fault_code()});
    }
    if(ok)component_success_[component]=clock_.now_ns();
    return ok;
}
void PhysicalOwner::step() {
        const auto released_at_start=gate_.epoch(); if(released_at_start>released_epoch_) released_epoch_=released_at_start;
        const bool force_at_start=override_.pending(released_epoch_);
        const auto now=clock_.now_ns();previous_call_=current_call_;current_call_=now;
        if(!begun_) {
            begun_=true; last_=now; motor_.begin(7,now);
            const bool initialized=vehicle_enabled_?coupled_.initialize({7,now,initial_soc_,25},0):energy_.initialize({7,now,initial_soc_,25},0);
            ok_=observe(angles_.begin(now),"steering","begin",now) && observe(pressure_.begin(now),"brake","begin",now) && observe(initialized,"energy","initialize",now); if(ok_)last_success_=now;return;
        }
        if(!ok_ || now<=last_) return;
        const battery::ModelIdentity id{7,sequence_++,last_};
        const double old_torque=motor_.actual_nm();
        const auto& p=electrical().power_state();
        const bool inverter=(p.contactors.positive && p.contactors.negative && p.bus_voltage_v>=300) || std::abs(old_torque)>1e-9;
        const EvPowerInputs inputs{battery::ModelMeasurement<double>{old_torque,id,last_},battery::ModelMeasurement<double>{vehicle_enabled_?coupled_.vehicle().wheel_speed_rad_s():0,id,last_},
            battery::ModelMeasurement<EvElectricalEnvironment>{{.25,inverter},id,last_}};
        if(vehicle_enabled_) {
            const VehicleActual a{{old_torque,id,last_},{pressure_.actual_pressure_pa(),id,last_},{angles_.actual_angle_rad(),id,last_}};
            ok_=observe(coupled_.step(last_,now,a,*inputs.electrical,coils_).fault==VehicleEvFault::None,"energy","vehicle-step",last_);
        } else ok_=observe(energy_.step({last_,now,inputs,coils_}).fault==EvPowerFault::None,"energy","step",last_);
        ok_=ok_ && observe(motor_.advance(now,false),"drive","advance",last_) && observe(angles_.advance(now),"steering","advance",last_) && observe(pressure_.advance(now),"brake","advance",last_);
        if(!ok_) return;
        OwnerSensors s; s.source_ns=now; s.angle=angles_.capture(); s.pressure=pressure_.capture(); s.torque=motor_.capture(now);
        s.power=electrical().power_observation(); s.battery=electrical().battery_observation();
        const auto& actual=electrical().power_state();
        s.drive.wheel_speed=battery::ModelMeasurement<double>{vehicle_enabled_?coupled_.vehicle().wheel_speed_rad_s():0,{7,sequence_,now},now};
        s.drive.hv=battery::ModelMeasurement<drive::HvFeedback>{{actual.bus_voltage_v,actual.contactors.positive && actual.contactors.negative && actual.bus_voltage_v>=300,false},
            {7,sequence_,now},last_};
        for(auto& channel:sensors_) channel.publish(s);
        // Apply new outputs only after advancing the previous interval. The
        // physical application time is distinct from original ECU/CAN source.
        for(std::size_t l=0;l<outputs_.size();++l) {
            const auto out=outputs_[l].read(); if(!out || out->source_ns>now || out->source_ns==applied_[l] || out->epoch>released_epoch_) continue;
            const bool stale=now-out->source_ns>30000000; applied_[l]=out->source_ns; applied_epoch_[l]=out->epoch;
            // An independently selected physical override has priority over a
            // still-live ECU's normal output in this same Epoch. Do not invoke
            // a nominal target/begin API on the model's latched protection.
            if(force_at_start && l<3) {
                if(l==0)ok_=ok_ && observe(angles_.hold(now),"steering","override-output",out->source_ns);
                if(l==1)ok_=ok_ && observe(pressure_.request_protection(1000000,now),"brake","override-output",out->source_ns);
                if(l==2)ok_=ok_ && observe(motor_.apply({drive::ActuationMode::Zero,0,std::nullopt,now}),"drive","override-output",out->source_ns);
                continue;
            }
            if(l==4 && out->epoch>power_driver_epoch_ && released_at_start==out->epoch) { watchdog_[4]=false; current_safe_since_=0; driver_shutdown_=false; power_driver_epoch_=0; }
            if(out->steering) ok_=ok_ && observe((stale || out->steering->mode==steering::ActuationMode::Hold?angles_.hold(now):angles_.set_target(out->steering->target_rad,now)),"steering","output",out->source_ns);
            if(out->brake) {
                // Trusted new application release clears only the modeled
                // actuator's protection-mode latch/pending demands. begin()
                // preserves pressure, model identity and sensor sequence.
                // A nominal Hold or CAN packet in the old Epoch cannot do so.
                if(out->epoch>brake_release_epoch_ && released_at_start==out->epoch) { ok_=ok_ && observe(pressure_.begin(now),"brake","release-begin",out->source_ns); brake_release_epoch_=out->epoch; }
                if(out->brake->mode!=brake::ActuationMode::Protect && brake_release_epoch_!=out->epoch) continue;
                if(stale || out->brake->mode==brake::ActuationMode::Protect) ok_=ok_ && observe(pressure_.request_protection(out->brake->target_pa,now),"brake","protect-output",out->source_ns);
                else if(out->brake->mode==brake::ActuationMode::Hold) ok_=ok_ && observe(pressure_.hold(now),"brake","hold-output",out->source_ns);
                else ok_=ok_ && observe(pressure_.set_target(out->brake->target_pa,now),"brake","target-output",out->source_ns);
            }
            if(out->drive) { auto application=*out->drive; application.issued_time_ns=now; if(stale) { application.mode=drive::ActuationMode::Zero; application.target_nm=0; } ok_=ok_ && observe(motor_.apply(application),"drive","output",out->source_ns); }
            if(out->coils) coils_=*out->coils;
        }
        // Independent application watchdog while a Leaf itself is stopped.
        if(applied_[0] && now-applied_[0]>30000000) ok_=ok_ && observe(angles_.hold(now),"steering","output-watchdog",applied_[0]);
        if(applied_[1] && now-applied_[1]>30000000) ok_=ok_ && observe(pressure_.request_protection(1000000,now),"brake","output-watchdog",applied_[1]);
        if(applied_[2] && now-applied_[2]>30000000) ok_=ok_ && observe(motor_.apply({drive::ActuationMode::Zero,0,std::nullopt,now}),"drive","driver-watchdog",applied_[2]);
        for(std::size_t l=0;l<5;++l) if(l!=3 && applied_[l] && now-applied_[l]>30000000 && !watchdog_[l]) {
            watchdog_[l]=true; if(l==4) power_driver_epoch_=applied_epoch_[l]; events_.push_back({now,"output-watchdog",8,applied_epoch_[l],applied_[l],applied_[l]+30000000,applied_[l],static_cast<int>(l+2)});
        }
        // A stopped Power ECU cannot run its controlled shutdown. The modeled
        // output driver interlock first forces torque zero, then releases coils
        // only after measured current/torque are safe; this is not an ECU ACK.
        if(watchdog_[4]) {
            ok_=ok_ && observe(motor_.apply({drive::ActuationMode::Zero,0,std::nullopt,now}),"drive","driver-watchdog",applied_[2]);
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
            ok_=ok_ && observe(angles_.hold(now),"steering","override",applied_[0]) && observe(pressure_.request_protection(1000000,now),"brake","override",applied_[1]) && observe(motor_.apply({drive::ActuationMode::Zero,0,std::nullopt,now}),"drive","override",applied_[2]);
            if(!override_.acknowledged(released_epoch_)) events_.push_back({now,"override-applied",8,released_epoch_,0,0,0,0});
            override_.selected.store(released_epoch_,std::memory_order_release);
        }
        last_=now;if(ok_)last_success_=now;
        if(now-last_trace_>=10000000) {
            last_trace_=now;
            trace.push_back({now-start_,now,0,false,false,false,0,0,0,angles_.actual_angle_rad(),pressure_.actual_pressure_pa(),motor_.actual_nm(),actual.bus_voltage_v,electrical().battery_state().soc});
            if(vehicle_enabled_) { if(energy_trace.size()==energy_trace.capacity()){ok_=observe(false,"energy","trace-capacity",now);return;} energy_trace.push_back({released_at_start,coupled_.ledger()});const auto& v=coupled_.vehicle().state();trace.back().speed_mps=v.speed_mps;trace.back().distance_m=v.distance_m;trace.back().x_m=v.x_m;trace.back().y_m=v.y_m;trace.back().yaw_rad=v.yaw_rad;trace.back().vehicle_balance_j=v.balance_error_j; }
            trace.back().run_gate=released_at_start!=0; trace.back().epoch=released_at_start;
            trace.back().energy_j=electrical().battery_state().energy_j;
            trace.back().model_epoch=actual.identity.epoch; trace.back().model_sequence=actual.identity.sequence;
            trace.back().contacts=static_cast<unsigned>(actual.contactors.positive)|(static_cast<unsigned>(actual.contactors.negative)<<1U)|(static_cast<unsigned>(actual.contactors.precharge)<<2U);
        }
    }
Network::Network(const M4Config& c):config(c),clock(c.wall_time),start(clock.now_ns()) {
        running_epoch.store(c.first_epoch);
        for(auto& log:owner_events) log.reserve(24000);
        // Finite harness storage is provisioned before any native start gate.
        // This removes known hot-path growth, not a claim about the old miss cause.
        for(std::size_t i=0;i<audit.size();++i) audit[i].durations.reserve(static_cast<std::size_t>(config.duration_ns/(i==9?2*kMs:i==8?kMs:kIoPoll))+32);
        physical.trace.reserve(static_cast<std::size_t>(config.duration_ns/(10*kMs))+32);
        central_trace.reserve(static_cast<std::size_t>(config.duration_ns/(10*kMs))+32);
        if(config.transport_trace) {
            for(std::size_t i=0;i<transport_logs.size();++i) {transport_logs[i].owner=i;transport_logs[i].rows.reserve(16384);}
            port.transport_trace(&transport_logs[7]);
        }
        bind_filters();
        std::array<transport::LeafLink*,transport::kLeaves> ptrs{}; for(std::size_t i=0;i<ptrs.size();++i) ptrs[i]=&leaves[i];
        for(std::size_t i=0;i<2;++i) {
            zone_owners[i]=std::make_unique<zone::AsyncZoneOwner>(i==0?zone::ZoneScope::Front:zone::ZoneScope::Rear,clock,gate,zones[i],ptrs);
            if(config.transport_trace)zone_owners[i]->transport_trace(&transport_logs[i]);
            zone_sessions[i]=std::make_unique<ZoneSession>(*zone_owners[i],clock,sensors[i]);
            sessions[i]=std::make_unique<SessionOwnerLoop>(static_cast<session::Role>(i),*zone_sessions[i],session_links[i]);
        }
        for(std::size_t i=0;i<transport::kLeaves;++i) {
            leaf_owners[i]=std::make_unique<AsyncLeafOwner>(static_cast<transport::Leaf>(i),clock,gate,leaves[i],sensors[i+2],outputs[i],bms_gate);
            leaf_owners[i]->execution_deadline(config.execution_guards);
            if(config.transport_trace)leaf_owners[i]->transport_trace(&transport_logs[i+2]);
            sessions[i+2]=std::make_unique<SessionOwnerLoop>(static_cast<session::Role>(i+2),*leaf_owners[i],session_links[i+2]);
        }
        sessions[7]=std::make_unique<SessionOwnerLoop>(session::Role::CentralIngress,ingress,session_links[7]);
    }
void Network::bind_filters() {
        if(config.scenario!=M4Scenario::Fault) return;
        for(std::size_t z=0;z<2;++z) {
            bind(zones[z].work,FaultPath::CentralToZone,z); bind(zones[z].results,FaultPath::ZoneToCentral,z); bind(zones[z].feedback,FaultPath::ZoneToCentral,z);
        }
        for(std::size_t l=0;l<5;++l) { bind(leaves[l].work,FaultPath::ZoneToLeaf,l+2); bind(leaves[l].reports,FaultPath::LeafToZone,l+2); }
        for(std::size_t i=0;i<8;++i) { bind(session_links[i].controls,FaultPath::SessionControl,i); bind(session_links[i].acks,FaultPath::SessionAck,i); }
    }
void Network::configure_watch(std::uint64_t until) {
        const auto enable=execution_watch?M4ReleaseGrid{start,2*kMs}.after(clock.now_ns()+100*kMs-1):start+100*kMs;
        if(execution_watch) { const auto rows=execution_watch->rows(); result.execution.insert(result.execution.end(),rows.begin(),rows.end()); }
        if(config.execution_guards) execution_watch=std::make_unique<M4ExecutionWatch>(enable,start+until);
    }
void Network::poll_deadlines(std::size_t observer) {
        if(!execution_watch) return;
        const auto now=clock.now_ns();
        for(const auto& fault:execution_watch->poll(observer,now)) if(fault) {
            const auto epoch=running_epoch.load(std::memory_order_acquire); gate.close(); monitor_override.request(epoch);
            for(auto& zone:zones) zone.protection.request(epoch);
            owner_events[observer].push_back({now,"deadline-detected",observer,epoch,fault->timing.deadline_ns-4000000,fault->timing.deadline_ns,fault->timing.deadline_ns,static_cast<int>(fault->target)});
        }
    }
void Network::collect_filters() {
        for(const auto& filter:filters) if(!filter->collect(result.events)) result.event_overflow=true;
        filters.clear();
    }
void Network::replace_joined_links() {
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
void Network::central_step() {
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
void Network::step(std::size_t owner,std::uint64_t requested_wake) {
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
        const auto job=execution_watch?(requested_wake?execution_watch->begin_requested(owner,now,!pause,requested_wake):execution_watch->begin(owner,now,!pause)):std::optional<std::size_t>{};
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
        audit[owner].record(wall_now()-body_start);
        if(execution_watch) execution_watch->finish(owner,job,clock.now_ns(),job?cpu_now()-cpu_start:0);
    }
std::uint64_t BootPort::now_ns() noexcept { return n_.clock.now_ns(); }
bool BootPort::quiesce_central() noexcept { n_.gate.close(); n_.core.request_protection(now_ns()); n_.port.protect(); return true; }
bool BootPort::commit_central(central::CoordinatorSession s) noexcept { return n_.core.start_session(s); }
void BootPort::protect_central() noexcept { n_.gate.close(); n_.core.request_protection(now_ns()); n_.port.protect(); }

} // namespace stratadrive::simulation::m4_detail
