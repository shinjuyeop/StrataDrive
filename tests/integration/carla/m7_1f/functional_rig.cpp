#include "functional_rig.hpp"
#include "m4_owner_network.hpp"
#include "run_lease_issuer.hpp"
#include "wheel_contract.hpp"
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
    std::array<m7_external::ElectricalAudit,11> electrical_steps{};
    unsigned electrical_count=0;
    Time next_management=0,next_controller=0,last_lease=0;
    std::uint32_t lifecycle_seq=0,vehicle_seq=0;
    unsigned release_mask=0;std::size_t controller_releases=0;
    bool running=false,stop_credit=false,drop_actual=false;int omitted=-1;
    bool wheel_mode=false;
    std::optional<WheelSample> wheel;
    std::deque<WheelSample> pending_wheels;

    Native(Scope s,Time initial,PlantMode mode):scope(s),start(initial),next_io(initial),next_physical(initial) {
        clock.logical=initial;
        if(mode==PlantMode::ExternalWheelZoh)external=std::make_unique<m7_external::ActuatorElectrical>(initial,s.application);
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
        require(coordinator.begin(s.application,initial),"begin trusted fixture session");
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
        if(now==next_physical) {
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
            auto& participant=participants[i]->participant_;
            while(!controls[i].empty()) {
                const auto c=controls[i].front();controls[i].pop_front();
                const auto m=wire({Role::CentralIngress,static_cast<Role>(i),domain,c});
                ack(participant.receive(std::get<session::Control>(m.payload),now));
            }
            if(i>=2 && i<=4)leaf[i-2]->drop_actual=drop_actual;
            ack(participant.poll(now));
            require(participant.fault()==session::ParticipantFault::None,"participant failure");
        }
        while(!acks.empty()) {
            const auto a=acks.front();acks.pop_front();
            const auto m=wire({a.role,Role::CentralIngress,domain,a});
            const auto result=coordinator.receive(std::get<session::Ack>(m.payload),now);
            if(result==session::AckResult::Accepted && a.accepted && a.phase==session::Phase::Release)
                release_mask|=1U<<static_cast<unsigned>(a.role);
        }
        coordinator.poll(now);
        require(coordinator.state()!=session::State::Failed,"coordinator failure");
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
            if(core.decision().normal_armed)
                core.receive_vehicle({scope.application,vehicle_seq++,now,now+60*ms,.2,.02,0,false},now);
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
        return r;
    }
};

FunctionalRig::FunctionalRig(Scope scope,std::uint32_t actor,PlantMode mode):scope_(scope),clock_(scope),wheel_actor_(actor),plant_mode_(mode) {
    // Native PhysicalOwner's immutable fixture epoch is 7. Do not pretend a
    // packet can choose a new physical plant identity or an axle calibration.
    require(!actor || scope.plant==7,"wheel fixture plant binding");
    require(mode!=PlantMode::ExternalWheelZoh || actor!=0,"external plant requires wheel binding");
}
FunctionalRig::~FunctionalRig()=default;
Report FunctionalRig::observe(const Observation& o) {
    return observe_impl(o,std::nullopt);
}
Report FunctionalRig::observe(const Observation& o,const WheelSample& wheel) {
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
        if(!native_)native_=std::make_unique<Native>(scope_,now,plant_mode_);
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
        auto r=native_->advance(now);
        for(unsigned i=0;i<8;++i)if(r.service_mask&(1U<<i))clock_.serviced(i);
        r.next_frame=clock_.permit_non_driving_tick();return r;
    } catch(...) {clock_.fail();throw;}
}
void FunctionalRig::omit_role(int role) {omitted_=role;}
void FunctionalRig::stop_credit(bool value) {stop_credit_=value;}
void FunctionalRig::drop_actual(bool value) {drop_actual_=value;}
} // namespace stratadrive::m7_functional
