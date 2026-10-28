#include "functional_rig.hpp"
#include "m4_owner_network.hpp"
#include "run_lease_issuer.hpp"
#include "wheel_contract.hpp"
#include "wall_execution_watch.hpp"
#include <deque>

namespace stratadrive::m7_functional {
namespace {
using Role=session::Role;
constexpr remote::ClockAgreement agreement{domain,domain,0,0,true};
void require(bool value,const char* why) {if(!value)throw std::runtime_error(why);}
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
    CreditedActor(Role role,session::ParticipantPort& actor,transport::RunGate& gate)
        :actor_(actor),gate_(gate),participant_(role,*this) {}
    session::SessionParticipant participant_;
    remote::RunLeaseGate credit;
    void select_protection() {protect();}
    bool allowed() {return !protected_ && credit.allows(participant_,now_ns()) && gate_.allows(epoch_);}
    bool lease(const remote::RunLease& lease) {
        if(protected_ || !credit.receive(lease,domain,participant_,now_ns()))return false;
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
        if(!actor_.initialize(p) || !credit.bind(p,agreement,now_ns()))return false;
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
    std::uint32_t epoch_=0;bool released_=false,protected_=false;
};
}

struct FunctionalRig::Native final:session::CoordinatorPort {
    Scope scope;
    simulation::m4_detail::Clock clock{false};
    Time start,next_io,next_physical;
    std::array<transport::RunGate,8> gates;
    std::array<transport::ZoneLink,2> zones;
    std::array<transport::LeafLink,5> leaves;
    std::array<runtime::LatestSnapshot<simulation::OwnerSensors>,8> sensors;
    std::array<runtime::LatestSnapshot<simulation::OwnerSensors>,8> fixture_sensors;
    std::array<runtime::LatestSnapshot<simulation::OwnerActuation>,5> outputs;
    simulation::BmsGateChannel bms;
    central::AsyncCoordinatorPort port{clock,gates[7],zones[0],zones[1],central::CommandRenewal::Host10ms};
    central::VehicleCoordinator core{port,{true,central::CommandRenewal::Host10ms}};
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
    Time next_management=0,next_controller=0,last_lease=0;
    std::uint32_t lifecycle_seq=0,vehicle_seq=0;
    unsigned release_mask=0;std::size_t controller_releases=0;
    bool running=false,stop_credit=false,drop_actual=false;int omitted=-1;
    bool protection_requested=false;
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
    std::array<std::optional<session::Ack>,8> release_acks;

    Native(Scope s,Time initial,PlantMode mode,bool exporting):scope(s),start(initial),next_io(initial),next_physical(initial),export_actual(exporting) {
        clock.logical=initial;
        if(export_actual) {
            for(unsigned i=0;i<2;++i)zones[i].feedback.delivery(&feedback_capture[i]);
            for(unsigned i=0;i<5;++i)leaves[i].work.delivery(&command_capture[i]);
        }
        if(mode!=PlantMode::StationaryFixture)external=std::make_unique<m7_external::ActuatorElectrical>(initial,s.application,mode==PlantMode::ExternalSolverWork);
        else physical=std::make_unique<simulation::m4_detail::PhysicalOwner>(clock,gates[7],fixture_sensors,outputs,start,events,override_signal,s.application,false);
        std::array<transport::LeafLink*,5> ptr{};for(unsigned i=0;i<5;++i)ptr[i]=&leaves[i];
        for(unsigned i=0;i<2;++i) {
            zone[i]=std::make_unique<zone::AsyncZoneOwner>(i==0?zone::ZoneScope::Front:zone::ZoneScope::Rear,clock,gates[i],zones[i],ptr);
            zone_sessions[i]=std::make_unique<simulation::m4_detail::ZoneSession>(*zone[i],clock,sensors[i]);
            participants[i]=std::make_unique<CreditedActor>(static_cast<Role>(i),*zone_sessions[i],gates[i]);
        }
        for(unsigned i=0;i<5;++i) {
            leaf[i]=std::make_unique<simulation::AsyncLeafOwner>(static_cast<transport::Leaf>(i),clock,gates[i+2],leaves[i],sensors[i+2],outputs[i],bms);
            participants[i+2]=std::make_unique<CreditedActor>(static_cast<Role>(i+2),*leaf[i],gates[i+2]);
        }
        participants[7]=std::make_unique<CreditedActor>(Role::CentralIngress,ingress,gates[7]);
        if(!export_actual) {
            require(coordinator.begin(s.application,initial),"begin trusted fixture session");
            coordinator_started=true;
        }
    }
    Time now_ns() noexcept override {return clock.now_ns();}
    bool quiesce_central() noexcept override {gates[7].close();core.request_protection(now_ns());port.protect();return true;}
    bool commit_central(central::CoordinatorSession s) noexcept override {return core.start_session(s);}
    void protect_central() noexcept override {gates[7].close();core.request_protection(now_ns());port.protect();}
    bool send(const session::Control& c) noexcept override {
        const auto i=static_cast<unsigned>(c.role);
        if(i>=8 || controls[i].size()>=32)return false;
        controls[i].push_back(c);return true;
    }
    void ack(const std::optional<session::Ack>& a) {
        if(a){require(acks.size()<64,"ACK queue overflow");acks.push_back(*a);}
    }
    void cycle(Time now) {
        clock.logical=now;
        if(protection_requested && !protection_since) {
            require(running && core.decision().normal_armed,"protection requires established normal session");
            protection_since=now;
            protect_central();
            for(auto& p:participants)p->select_protection();
        }
        // M7 applied path only: delayed INIT puts 10ms leaf acquisitions near
        // the end of each CARLA frame. It changes phase, not any native rate,
        // original timestamp, parent expiry, or session deadline budget.
        if(!coordinator_started && now>=start+8*ms) {
            require(coordinator.begin(scope.application,now),"begin aligned native session");
            coordinator_started=true;
        }
        if(now==next_physical) {
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
                if(!external->step(now,input,out,gates[7].epoch(),override_signal.pending(scope.application)))
                    throw std::runtime_error(external->error());
                require(electrical_count<electrical_steps.size(),"M7 interval audit overflow");
                electrical_steps[electrical_count++]=external->audit();
                if(external->sensors())for(auto& channel:fixture_sensors)channel.publish(*external->sensors());
            }
            next_physical+=ms;
            if(watch)watch->finish(8,wall_job);
        }
        while(!pending_wheels.empty() && pending_wheels.front().source<=now) {
            wheel=pending_wheels.front();pending_wheels.pop_front();
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
                const auto c=controls[i].front();controls[i].pop_front();
                const auto m=wire({Role::CentralIngress,static_cast<Role>(i),domain,c});
                ack(participant.receive(std::get<session::Control>(m.payload),now));
            }
            if(i>=2 && i<=4)leaf[i-2]->drop_actual=drop_actual;
            ack(participant.poll(now));
            require(participant.fault()==session::ParticipantFault::None,"participant failure");
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
        require(coordinator.state()!=session::State::Failed,"coordinator failure");
        // Keep servicing original leaf/Zone/Central feedback after the terminal
        // safety selection. No root requests, normal credits or re-arm here.
        if(protection_since)return;
        if(!coordinator.run_enabled())return;
        if(!running){running=true;next_management=coordinator.plan().enable_ns+14*ms;next_controller=next_management;}
        if(!stop_credit && (!last_lease || now-last_lease>=10*ms)) {
            const auto lease=issuer.issue(now);require(bool(lease),"lease issuer");
            for(unsigned i=0;i<8;++i) {
                // The Central self-credit is local, not an invented v1 wire route.
                const auto delivered=i==7?*lease:std::get<remote::RunLease>(wire({Role::CentralIngress,static_cast<Role>(i),domain,*lease}).payload);
                require(participants[i]->lease(delivered),"credit rejected");
            }
            last_lease=now;
        }
        for(auto& p:participants)require(p->allowed(),"native credit/gate closed");
        if(now>=next_controller) {
            // Upstream Controller request remains 20ms. Existing Host10ms child
            // allocation/permission renewal is retained, not a new Controller rate.
            core.receive_lifecycle({{scope.application,lifecycle_seq++,now,now+60*ms},can::BmsPowerAction::Enable},now);
            if(core.decision().normal_armed) {
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
            next_controller+=20*ms;++controller_releases;
        }
        const bool due=now>=next_management;if(due)next_management+=10*ms;
        core.tick(port.feedback(),now,due);
        require(core.decision().fault==central::CoordinatorFault::None,"native control protection");
    }
    Report advance(Time observed) {
        require(observed>=clock.logical && observed-start<=10'000*ms,"finite logical horizon");
        electrical_count=0;
        // Jobs are scheduled on the existing 0.2ms ingress/1ms fixture grids.
        // No observation is used before its timestamp. The optional real wheel
        // feeds ECU sensors only; actuator/electrical models remain a fixture.
        while(next_io<=observed){cycle(next_io);next_io+=200000;}
        clock.logical=observed;
        Report r;r.now=observed;r.release_mask=release_mask;r.armed=core.decision().normal_armed;
        if(external && external->last_success()>start)r.electrical=external->audit();
        r.electrical_steps=electrical_steps;r.electrical_count=electrical_count;
        if(wheel)r.sensor_wheel=WheelAudit{wheel->source,(wheel->omega[2]+wheel->omega[3])/2};
        r.controller_releases=controller_releases;
        for(unsigned i=0;i<8;++i) {
            if(static_cast<int>(i)!=omitted)r.service_mask|=1U<<i;
            if(participants[i]->allowed())r.credit_mask|=1U<<i;
        }
        for(unsigned i=0;i<5;++i){r.commands[i]=leaf[i]->received_commands();r.leaf_body[i]=leaf[i]->last_body_ns();}
        if(const auto& lease=participants[7]->credit.accepted();lease){r.lease_source=lease->source_time_ns;r.lease_expiry=lease->expires_at_ns;}
        const auto feedback=port.feedback();
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
        if(r.armed)require(r.credit_mask==255 && r.actual_interval,"shadow Actual interval missing/stale");
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
            r.native_export=std::move(e);
        }
        return r;
    }
};

FunctionalRig::FunctionalRig(Scope scope,std::uint32_t actor,PlantMode mode,bool exporting):scope_(scope),clock_(scope),wheel_actor_(actor),plant_mode_(mode),export_actual_(exporting) {
    // Native PhysicalOwner's immutable fixture epoch is 7. Do not pretend a
    // packet can choose a new physical plant identity or an axle calibration.
    require(!actor || scope.plant==7,"wheel fixture plant binding");
    require(mode==PlantMode::StationaryFixture || actor!=0,"external plant requires wheel binding");
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
        const auto now=clock_.accept(o);
        require(bool(wheel)==bool(wheel_actor_),"missing/unbound wheel source");
        if(wheel) {
            require(wheel->actor==wheel_actor_ && wheel->frame==o.frame &&
                    wheel->frame<=UINT32_MAX && wheel->source==now,"wheel identity/time");
            const auto assessed=m7_external::assess(wheel->omega);
            require(bool(assessed.forward_rad_s),m7_external::reason(assessed.validity));
        }
        const bool initial=!native_;
        require(plant_mode_==PlantMode::ExternalSolverWork ? (initial?!work_:bool(work_)) : !work_,"missing/unexpected solver work");
        if(!native_)native_=std::make_unique<Native>(scope_,now,plant_mode_,export_actual_);
        native_->profile=profile_;
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
        if(native_ && plant_mode_==PlantMode::ExternalSolverWork)native_->external->abort_work_frame();
        clock_.fail();throw;
    }
}
void FunctionalRig::request_profile(std::vector<RequestPhase> phases) {
    require(!native_ && !phases.empty() && phases.size()<=32,"profile must be bounded and set before INIT");
    Time previous=0;
    for(const auto& p:phases) {
        require(p.end_ms>previous && p.end_ms<=10000 && std::isfinite(p.acceleration) &&
            p.acceleration>=-5 && p.acceleration<=2 && std::isfinite(p.curvature) &&
            std::abs(p.curvature)<=1 && std::isfinite(p.braking) && p.braking>=0 && p.braking<=1,"invalid request profile");
        previous=p.end_ms;
    }
    profile_=std::move(phases);
}
void FunctionalRig::omit_role(int role) {omitted_=role;}
void FunctionalRig::stop_credit(bool value) {stop_credit_=value;}
void FunctionalRig::drop_actual(bool value) {drop_actual_=value;}
void FunctionalRig::request_protection() {protect_=true;}
void FunctionalRig::execution_watch(WallExecutionWatch* watch) {watch_=watch;}
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
} // namespace stratadrive::m7_functional
