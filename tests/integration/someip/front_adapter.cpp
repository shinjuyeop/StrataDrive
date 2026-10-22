// Opt-in Host adapter. Eight real participants; no pilot grants or synthetic feedback.
#include "adapter_transport.hpp"
#include "plant_io.hpp"
#include "energy_scenario.hpp"
#include "remote_leaf_endpoint.hpp"
#include "remote_zone_endpoint.hpp"
#include "run_lease_issuer.hpp"
#include "epoch_store.hpp"
#include "native_execution_watch.hpp"
#include <filesystem>
#include <iostream>
#include <map>
#include <set>

namespace fs=std::filesystem;
using namespace stratadrive;
using namespace stratadrive::someip;
namespace {
using Role=session::Role;
using Clock=simulation::m4_detail::Clock;
bool energy_enabled(){return std::getenv("STRATADRIVE_ENERGY_CYCLE")!=nullptr;}
bool no_charge(){const auto* p=std::getenv("STRATADRIVE_ENERGY_CYCLE");return p && std::string(p)=="no-charge";}
bool native_enabled(){return std::getenv("STRATADRIVE_NATIVE_WATCH")!=nullptr;}
bool three_enabled(){return std::getenv("STRATADRIVE_THREE_ECU")!=nullptr;}
unsigned fault_zone(){return std::getenv("STRATADRIVE_FAULT_REAR")?1:0;}
bool fifo_enabled(){return std::getenv("STRATADRIVE_NATIVE_FIFO")!=nullptr;}
std::uint64_t run_duration(){const auto* v=std::getenv("STRATADRIVE_NATIVE_DURATION_MS");return v?std::stoull(v)*kMs:9000*kMs;}
struct NativeIteration {
    simulation::NativeExecutionWatch* watch;std::optional<std::size_t> job;std::uint64_t cpu;
    NativeIteration(simulation::NativeExecutionWatch* w,std::uint64_t requested):watch(w),cpu(w?w->m4_cpu():0){if(w)job=w->begin(requested);}
    void finish(){if(watch){watch->finish(job,cpu);watch=nullptr;}}
    ~NativeIteration(){finish();}
};
constexpr remote::ClockAgreement agreement{kDomain,kDomain,0,0,true};
void mark(const fs::path& p){
    // Main owner only. Each diagnostic transition writes once, never each poll.
    static std::set<fs::path> written;
    if(written.insert(p).second)std::ofstream(p)<<now()<<'\n';
}
struct Trace final:transport::TransportTrace {
    std::ofstream out;std::vector<transport::TransportTraceRow> rows;bool overflow=false;
    explicit Trace(const fs::path& p):out(p){rows.reserve(energy_enabled()?196608:65536);}
    ~Trace(){out<<"event,ns,peer,epoch,token,sent,deadline,operation,decision,source,original_source,inner_deadline,payload_source\n";
        for(const auto& r:rows)out<<r.stage<<','<<r.time_ns<<','<<r.peer<<','<<r.epoch<<','<<r.token<<','<<r.sent_ns<<','<<r.deadline_ns<<','<<r.operation<<','<<r.outcome<<','<<r.result_source_ns<<','<<r.original_source_ns<<','<<r.inner_deadline_ns<<','<<r.payload_source_ns<<'\n';}
    void record(transport::TransportTraceRow r) noexcept override;
};
struct Owners final:session::CoordinatorPort {
    const Ecu ecu;const bool remote,three;const unsigned zi;const fs::path folder;const std::string tag;
    Clock clock{true};transport::RunGate gate;std::array<transport::RunGate,5> leaf_gates;
    std::array<transport::ZoneLink,2> zones;std::array<transport::LeafLink,5> leaves;
    std::array<runtime::LatestSnapshot<simulation::OwnerSensors>,8> sensors;
    std::array<runtime::LatestSnapshot<simulation::OwnerActuation>,5> outputs;
    simulation::BmsGateChannel bms;
    central::AsyncCoordinatorPort port{clock,gate,zones[0],zones[1],central::CommandRenewal::Host10ms};central::VehicleCoordinator core{port,{true,central::CommandRenewal::Host10ms}};
    std::array<std::unique_ptr<zone::AsyncZoneOwner>,2> zone;
    std::array<std::unique_ptr<simulation::m4_detail::ZoneSession>,2> zone_session;
    std::array<std::unique_ptr<simulation::AsyncLeafOwner>,5> leaf;
    simulation::m4_detail::CentralIngress ingress{port,clock,sensors[7]};
    session::SessionLinks links;
    std::array<std::unique_ptr<simulation::SessionOwnerLoop>,8> sessions;
    std::array<std::unique_ptr<simulation::RemoteLeafEndpoint>,5> remote_leaf;
    std::unique_ptr<simulation::RemoteZoneEndpoint> remote_zone;
    Transport& net;PlantIO io;
    session::SessionCoordinator coordinator{*this};central::RunLeaseIssuer issuer{coordinator};
    struct Event {std::uint64_t ns;const char* name;std::uint32_t epoch;unsigned role;std::uint64_t value,deadline;};
    std::vector<Event> event_rows;bool event_overflow=false;Trace trace;
    std::uint32_t epoch=0,root_seq=0,vehicle_seq=0;std::uint64_t released=0,next_management=0,last_credit=0,vehicle_release=0,lifecycle_slot=0;
    std::uint64_t armed_ns=0,protected_ns=0,selected_ns=0,last_lease_expiry=0,actual_count=0,result_count=0,accepted_results=0;
    std::uint64_t protection_token=0,release_acks=0;std::array<std::uint64_t,2> protection_sent{};bool stop_credit=false;
    std::map<std::uint64_t,transport::ZoneRequest> pending;
    std::optional<transport::ZoneRequest> last_request;
    std::map<std::pair<std::uint32_t,std::uint64_t>,std::uint64_t> diagnostic_pending;
    std::uint64_t diagnostic_sent=0,diagnostic_rejected=0,diagnostic_expired=0,diagnostic_late=0,pending_expired=0,state_violations=0,pre_init_rejected=0;
    std::uint64_t last_step=0,max_poll_gap=0;
    double max_validated_wheel_speed=0;std::uint64_t wheel_speed_samples=0,last_wheel_source=0;
    struct EnergyFeedback {std::uint64_t now,source;std::uint32_t epoch;double torque,speed,capability,charge;bool cap_present,charge_present;};
    std::vector<EnergyFeedback> energy_feedback;bool energy_feedback_overflow=false;const char* energy_phase=nullptr;
    int observed_regen=-1;
    bool freeze_normal=false;std::array<remote::ProtectionReceipt,2> receipt;
    bool stop_requested=false;std::uint32_t stop_seq=0;std::uint64_t stop_started=0,stop_complete=0,last_stop=0;
    std::atomic<std::uint64_t> monitor_delay{0};
    std::unique_ptr<simulation::NativeExecutionWatch> watch;
    void start_watch() {
        if(!native_enabled())return;
        const auto origin=now();
        watch=std::make_unique<simulation::NativeExecutionWatch>((folder/"sil-io"/(ecu==Ecu::Central?"watch-central.bin":ecu==Ecu::Front?"watch-front.bin":"watch-rear.bin")).string(),remote?zi:7,origin,run_duration()+(three?2500*kMs:0),fifo_enabled(),[this](std::uint32_t e){
            gate.close();for(auto& g:leaf_gates)g.close();for(auto& z:zones)z.protection.request(e);for(auto& l:leaves)l.protection.request(e);
        },[this]{if(const auto delay=monitor_delay.exchange(0))simulation::runtime_support::sleep_until(now()+delay);});
        simulation::NativeExecutionWatch::configure_thread(remote?(zi?7:2):1,fifo_enabled()?(remote?18:11):0);watch->owner_info.capture();
    }
    ~Owners(){
    if(!remote && energy_enabled()) {
        std::ofstream f(folder/(tag+".energy-feedback.csv"));f<<"ns,source_ns,epoch,torque_nm,wheel_speed_rad_s,capability_nm,charge_w,cap_present,charge_present\n";
        for(const auto& e:energy_feedback)f<<e.now<<','<<e.source<<','<<e.epoch<<','<<e.torque<<','<<e.speed<<','<<e.capability<<','<<e.charge<<','<<e.cap_present<<','<<e.charge_present<<'\n';
    }

        if(watch)watch->write((folder/(tag+".native")).string());
        std::ofstream events(folder/(tag+".events.csv"));events<<"ns,event,epoch,role,value,deadline\n";
        for(const auto& e:event_rows)events<<e.ns<<','<<e.name<<','<<e.epoch<<','<<e.role<<','<<e.value<<','<<e.deadline<<'\n';
    }
    explicit Owners(Ecu e,Transport& n,const fs::path& d,const std::string& label):ecu(e),remote(e!=Ecu::Central),three(three_enabled()),zi(e==Ecu::Rear?1:0),folder(d),tag(label),net(n),io((d/"sil-io"/"plant.bin").string()),trace(d/(tag+".transport.csv")) {
        event_rows.reserve(65536);if(energy_enabled() && !remote)energy_feedback.reserve(2000);
        std::array<transport::LeafLink*,5> ptr{};for(unsigned i=0;i<5;++i)ptr[i]=&leaves[i];
        if(remote || !three) {
            const unsigned z=remote?zi:1;
            zone[z]=std::make_unique<zone::AsyncZoneOwner>(z==0?zone::ZoneScope::Front:zone::ZoneScope::Rear,clock,gate,zones[z],ptr);
            zone[z]->transport_trace(&trace);
            zone_session[z]=std::make_unique<simulation::m4_detail::ZoneSession>(*zone[z],clock,sensors[z]);
            if(remote)remote_zone=std::make_unique<simulation::RemoteZoneEndpoint>(static_cast<Role>(zi),*zone_session[z],*zone[z],gate,zones[z],agreement);
            else sessions[1]=std::make_unique<simulation::SessionOwnerLoop>(Role::RearZone,*zone_session[1],links[1]);
            for(unsigned i=z==0?0:2;i<(z==0?2:5);++i) {
                leaf[i]=std::make_unique<simulation::AsyncLeafOwner>(static_cast<transport::Leaf>(i),clock,remote?leaf_gates[i]:gate,leaves[i],sensors[i+2],outputs[i],bms);
                leaf[i]->transport_trace(&trace);
                if(remote)remote_leaf[i]=std::make_unique<simulation::RemoteLeafEndpoint>(static_cast<Role>(i+2),*leaf[i],leaf_gates[i],leaves[i],agreement);
                else sessions[i+2]=std::make_unique<simulation::SessionOwnerLoop>(static_cast<Role>(i+2),*leaf[i],links[i+2]);
            }
        }
        if(!remote){sessions[7]=std::make_unique<simulation::SessionOwnerLoop>(Role::CentralIngress,ingress,links[7]);port.transport_trace(&trace);}
    }
    bool is_remote(Role role) const {return remote_role(role) || (three && owns_role(Ecu::Rear,role));}
    std::uint64_t command_count() const {std::uint64_t n=0;for(const auto& l:leaf)if(l)n+=l->received_commands();return n;}

    void event(const char* name,unsigned role,std::uint64_t value=0,std::uint64_t deadline=0){if(event_rows.size()<event_rows.capacity())event_rows.push_back({now(),name,epoch,role,value,deadline});else event_overflow=true;}
    std::uint64_t now_ns() noexcept override{return clock.now_ns();}
    bool quiesce_central() noexcept override {gate.close();core.request_protection(now());port.protect();return true;}
    bool commit_central(central::CoordinatorSession s) noexcept override{return core.start_session(s);}
    void protect_central() noexcept override{gate.close();core.request_protection(now());port.protect();}
    bool send(const session::Control& c) noexcept override {
        event("session-send",static_cast<unsigned>(c.role),static_cast<unsigned>(c.phase),c.plan.commit_deadline_ns);
        return is_remote(c.role)?net.send({Role::CentralIngress,c.role,kDomain,c}):links[static_cast<unsigned>(c.role)].controls.push(c);
    }
    std::uint32_t issue_epoch() {
        // Durable storage can block in fsync. No control authority exists yet;
        // finish it before enabling this generation's native execution guard.
        event("epoch-store-begin",7);
        const auto e=session::EpochStore((folder/"epochs").string()).issue();
        event("epoch-store-return",7,e);return e;
    }
    void begin(std::uint32_t e){epoch=e;event("host-renewal-period",7,central::allocation_period(central::CommandRenewal::Host10ms),central::permission_support(central::CommandRenewal::Host10ms));check(coordinator.begin(e,now()),"real session begin");event("epoch-issued",7,e);}
    void physical_io() {
        io.update([this](PlantState& s){
            for(auto& snapshot:sensors)snapshot.publish(s.sensors);
            for(unsigned i=0;i<5;++i)if(leaf[i])if(auto v=outputs[i].read())s.outputs[i]=*v;
            if(!remote && released)s.released_epoch=static_cast<std::uint32_t>(released);
        });
    }
    void emit(const std::optional<remote::OwnerMessage>& m){
        if(m && std::holds_alternative<session::Ack>(m->payload)){const auto& a=std::get<session::Ack>(m->payload);if(a.accepted && a.phase==session::Phase::Initialize) {
            net.initialized_epoch[static_cast<unsigned>(a.role)].store(a.plan.epoch);
            // A received INIT is only a request. Retire old diagnostic timestamps
            // after this actual Zone owner initialized successfully at enable time.
            if(remote && a.role==static_cast<Role>(zi)){event("initialized-diagnostic-reset",zi,protected_ns,selected_ns);protected_ns=selected_ns=0;}
        }event("local-ack-produced",static_cast<unsigned>(a.role),static_cast<unsigned>(a.phase),a.accepted);}
        if(m && !net.send(*m))fail("outbound-full");
    }
    void fail(const char* why) {
        if(!protected_ns){protected_ns=now();event(why,remote?zi:7);}
        if(remote){remote_zone->lost();for(auto& e:remote_leaf)if(e)e->continuity_lost();}
        else {protect_central();if(coordinator.state()!=session::State::Failed)coordinator.cancel(now());}
    }
    void ack(const session::Ack& a) {
        const auto result=coordinator.receive(a,now());
        event("session-ack",static_cast<unsigned>(a.role),static_cast<unsigned>(a.phase)*10+static_cast<unsigned>(result),a.plan.commit_deadline_ns);
        if(a.phase==session::Phase::Release && a.accepted && result==session::AckResult::Accepted)release_acks|=1ULL<<static_cast<unsigned>(a.role);
    }
    void receive(remote::OwnerMessage m) {
        if(remote) {
            if(const auto* c=std::get_if<session::Control>(&m.payload)) {
                event("control-received",static_cast<unsigned>(m.to),static_cast<unsigned>(c->phase),c->plan.epoch);
                if(c->phase==session::Phase::Initialize){epoch=c->plan.epoch;pre_init_rejected=net.rejected;event("pre-init-binding-rejections",0,pre_init_rejected);}
            }
            if(m.to==static_cast<Role>(zi)) {
                const auto commands=command_count();const auto old_gate=gate.epoch();
                const auto rejected=remote_zone->rejected;
                const auto response=remote_zone->receive(m);
                if(remote_zone->rejected>rejected && remote_zone->expired==0 &&
                   (commands!=command_count() || old_gate!=gate.epoch()))++state_violations;
                emit(response);
            }
            else emit(remote_leaf[static_cast<unsigned>(m.to)-2]->receive(m));
        } else if(auto* a=std::get_if<session::Ack>(&m.payload))ack(*a);
        else if(auto* r=std::get_if<transport::TxResult>(&m.payload)) {
            const auto key=std::make_pair(r->epoch,r->token);
            if(auto it=diagnostic_pending.find(key);it!=diagnostic_pending.end()) {
                check(!r->accepted,"diagnostic invalid command accepted");
                if(now()>=it->second){++diagnostic_late;++diagnostic_expired;}else ++diagnostic_rejected;
                diagnostic_pending.erase(it);event("diagnostic-result",0,r->token,r->source_ns);return;
            }
            // Late diagnostic replies remain negative evidence, never current control results.
            if(r->token>=1000000000ULL){check(!r->accepted,"late invalid accepted");++diagnostic_late;return;}
            ++result_count;if(r->accepted)++accepted_results;
            if(auto it=pending.find(r->token);it!=pending.end()) {
                event("result",0,r->token,it->second.deadline_ns);pending.erase(it);
            }
            if(!zones[static_cast<unsigned>(m.from)].results.push(*r))fail("result-overflow");
        } else if(auto* f=std::get_if<transport::Feedback>(&m.payload)) {
            if(energy_enabled())if(const auto* frame=std::get_if<can::DriveFrame>(f)) {
                const auto actual=can::decode_drive_frame(*frame);
                if(actual && actual->regen_capability)event("wire-capability",7,actual->regen_capability->source_time_ns,actual->regen_capability->input_time_ns);
            }
            ++actual_count;if(!zones[static_cast<unsigned>(m.from)].feedback.push(*f))fail("feedback-overflow");
        } else if(auto* a=std::get_if<remote::ProtectionAck>(&m.payload)) {
            const unsigned z=static_cast<unsigned>(m.from);
            if(z<2 && receipt[z].receive(m,now())) {
                zones[z].protection.selected.store(epoch);event("remote-protection-selected",z,a->selected_ns,a->request.deadline_ns);
            }
        }
    }
    void step(bool drop_commands=false,bool drop_results=false,bool drop_status=false,bool drop_lease=false) {
        const auto observed=now();if(last_step)max_poll_gap=std::max(max_poll_gap,observed-last_step);last_step=observed;
        physical_io();
        if(watch){watch->epoch(epoch);if(watch->faulted())fail("native-watch-protection");}
        if(net.overflow)fail("transport-overflow");
        if(remote) {
            // This priority path remains active even when normal receive consumption stops.
            emit(remote_zone->poll());for(auto& e:remote_leaf)if(e)emit(e->poll());
            if(zone[zi]->faulted() && !protected_ns){protected_ns=now();event("local-protection",zi,remote_zone->lease_fault(),remote_zone->last_lease_expiry);
                for(unsigned i=0;i<5;++i)if(leaf[i])event("leaf-first-fault",i+2,leaf[i]->fault_code());}
            if(zone[zi]->protected_selected() && !selected_ns){selected_ns=now();event("leaf-protection-selected",zi);}
            while(auto r=zones[zi].results.pop()) {
                event("result-produced",0,r->token,r->source_ns);
                if(!drop_results)emit(remote::OwnerMessage{static_cast<Role>(zi),Role::CentralIngress,kDomain,*r});
            }
            while(auto f=zones[zi].feedback.pop())if(!drop_status)emit(remote::OwnerMessage{static_cast<Role>(zi),Role::CentralIngress,kDomain,*f});
            return;
        }
        for(unsigned i=0;i<8;++i)if(sessions[i])sessions[i]->step();
        for(auto& l:links)while(auto a=l.acks.pop())ack(*a);
        coordinator.poll(now());
        if(coordinator.run_enabled()) {
            const auto t=now();const auto plan=coordinator.plan();
            if(!released){released=epoch;gate.release(epoch);next_management=plan.enable_ns+14*kMs;event("all-eight-released",7,release_acks);}
            if(!drop_lease && !stop_credit && gate.allows(epoch) && (!last_credit || t-last_credit>=10*kMs)) {
                if(auto lease=issuer.issue(t)) {for(unsigned i=0;i<7;++i)if(is_remote(static_cast<Role>(i)))emit(remote::OwnerMessage{Role::CentralIngress,static_cast<Role>(i),kDomain,*lease});last_credit=t;last_lease_expiry=lease->expires_at_ns;event("credit-issued",7,lease->sequence,lease->expires_at_ns);}
            }
            if(stop_requested && (!last_stop || t-last_stop>=20*kMs)) {
                const auto accepted=core.receive_stop({{epoch,stop_seq++,t,t+60*kMs},.02},now());
                check(accepted==central::CoordinatorReceive::Accepted,"normal stop request rejected");last_stop=t;
            }
            const bool due=t>=next_management;
            const auto slot=t>=plan.enable_ns+4*kMs?(t-plan.enable_ns-4*kMs)/(20*kMs)+1:0;
            if(!stop_requested && !freeze_normal && due && slot!=lifecycle_slot){lifecycle_slot=slot;core.receive_lifecycle({{epoch,root_seq++,t,t+60*kMs},can::BmsPowerAction::Enable},now());}
            if(!stop_requested && !freeze_normal && core.decision().normal_armed && t>=core.next_allocation_ns() && vehicle_release!=core.next_allocation_ns()) {
                vehicle_release=core.next_allocation_ns();
                auto demand=someip::test::EnergyDemand{"fixed",.2,false};
                if(energy_enabled() && armed_ns) {
                    demand=someip::test::energy_demand(t-armed_ns);
                    if(energy_phase!=demand.phase){energy_phase=demand.phase;event(demand.phase,7,t-armed_ns);}
                }
                core.receive_vehicle({epoch,vehicle_seq++,t,t+60*kMs,demand.acceleration,.02,0,demand.hold},now());
            }
            if(due)next_management=plan.enable_ns+4*kMs+((t-plan.enable_ns-4*kMs)/(10*kMs)+1)*(10*kMs);
            const auto feedback=port.feedback();
            if(feedback.rear.drive_actual && feedback.rear.drive_actual->wheel_speed) {
                const auto& wheel=*feedback.rear.drive_actual->wheel_speed;
                if(wheel.source_time_ns>last_wheel_source){last_wheel_source=wheel.source_time_ns;++wheel_speed_samples;max_validated_wheel_speed=std::max(max_validated_wheel_speed,wheel.value_rad_s);
                    if(energy_enabled()) {
                        const auto& d=*feedback.rear.drive_actual;const auto* limits=feedback.rear.power_limits?std::get_if<can::BmsPowerLimits>(&feedback.rear.power_limits->message.content):nullptr;
                        if(energy_feedback.size()<energy_feedback.capacity())energy_feedback.push_back({now(),wheel.source_time_ns,epoch,d.torque_nm.value_or(0),wheel.value_rad_s,d.regen_capability?d.regen_capability->torque_limit_nm:0,limits?limits->charge_power_w.value_or(0):0,d.regen_capability.has_value(),limits && limits->charge_power_w.has_value()});else energy_feedback_overflow=true;
                    }
                }
            }
            core.tick(feedback,now(),due);
            if(energy_enabled() && static_cast<int>(core.decision().allocation.regen)!=observed_regen) {
                observed_regen=static_cast<int>(core.decision().allocation.regen);
                const auto cap=feedback.rear.drive_actual?feedback.rear.drive_actual->regen_capability:std::nullopt;
                event("regen-admission",7,observed_regen,cap?std::min(cap->source_time_ns+30*kMs+1,cap->input_time_ns+70*kMs+1):0);
                if(cap)event("regen-capability-input",7,cap->source_time_ns,cap->input_time_ns);
            }
            if(stop_requested && !stop_complete && core.decision().stop.state==central::NormalStopState::Complete){stop_complete=now();event("normal-stop-complete",7);}

        }
        for(auto it=pending.begin();it!=pending.end();) {
            if(now()>=it->second.deadline_ns){event("pending-expired",0,it->first,it->second.deadline_ns);++pending_expired;it=pending.erase(it);}else ++it;
        }
        for(auto it=diagnostic_pending.begin();it!=diagnostic_pending.end();) {
            if(now()>=it->second){++diagnostic_expired;it=diagnostic_pending.erase(it);}else ++it;
        }
        if(core.decision().normal_armed && gate.allows(epoch) && !armed_ns){armed_ns=now();event("normal-armed",7);mark(folder/"armed");}
        if(core.decision().fault!=central::CoordinatorFault::None){event_first_fault();fail("central-protection");}
        if(coordinator.state()==session::State::Failed)gate.close();
        for(unsigned z=0;z<(three?2U:1U);++z) {
            while(auto r=zones[z].work.pop()) {
                if(z==fault_zone())last_request=*r;
                pending[r->token]=*r;event("command-enqueue",z,r->token,r->deadline_ns);
                if(!(drop_commands && z==fault_zone()))emit(remote::OwnerMessage{Role::CentralIngress,static_cast<Role>(z),kDomain,*r});
            }
            if(zones[z].protection.pending(epoch) && released && !protection_sent[z]) {
                protection_sent[z]=now();++protection_token;
                const remote::ProtectionRequest request{epoch,protection_token,protection_sent[z],protection_sent[z]+20*kMs};
                check(receipt[z].expect(request,static_cast<Role>(z),kDomain,now()),"protection receipt expectation");
                emit(remote::OwnerMessage{Role::CentralIngress,static_cast<Role>(z),kDomain,request});
                event("protection-request",z,protection_token,protection_sent[z]+20*kMs);
            }
        }
    }

    bool observed_normal_response() {
        const auto f=port.feedback();
        if(std::getenv("STRATADRIVE_SIMPLE_VEHICLE") && (!f.rear.drive_actual || !f.rear.drive_actual->wheel_speed || f.rear.drive_actual->wheel_speed->value_rad_s<.1))return false;
        return f.rear.drive_actual && f.rear.drive_actual->torque_nm && *f.rear.drive_actual->torque_nm>1 &&
            f.front.brake_actual && f.front.brake_actual->pressure_pa && *f.front.brake_actual->pressure_pa<1;
    }
    void diagnostic(transport::ZoneRequest r) {
        check(diagnostic_pending.size()<8,"diagnostic pending bound");
        diagnostic_pending[{r.epoch,r.token}]=now()+20*kMs;++diagnostic_sent;
        emit(remote::OwnerMessage{Role::CentralIngress,static_cast<Role>(fault_zone()),kDomain,r});
        event("diagnostic-send",0,r.token,r.deadline_ns);
    }
    void event_first_fault(){if(!protected_ns)event("central-fault",7,static_cast<unsigned>(core.decision().fault),static_cast<unsigned>(port.fault()));}
};
void Trace::record(transport::TransportTraceRow r) noexcept {
    if(rows.size()<rows.capacity())rows.push_back(r);else overflow=true;
}
int plant(const fs::path& folder) {
    Clock clock{true};transport::RunGate gate;transport::Protection override_signal;
    std::array<runtime::LatestSnapshot<simulation::OwnerSensors>,8> sensors;
    std::array<runtime::LatestSnapshot<simulation::OwnerActuation>,5> outputs;
    std::vector<simulation::M4Event> events;events.reserve(4000);const auto start=now();
    simulation::m4_detail::PhysicalOwner physical{clock,gate,sensors,outputs,start,events,override_signal,1,std::getenv("STRATADRIVE_SIMPLE_VEHICLE")!=nullptr,no_charge()?.96:.63};physical.trace.reserve(4000);
    PlantIO io((folder/"sil-io"/"plant.bin").string(),true);
    std::unique_ptr<simulation::NativeExecutionWatch> watch;
    std::vector<std::unique_ptr<simulation::NativeMonitorObserver>> observers;
    if(native_enabled()) {
        watch=std::make_unique<simulation::NativeExecutionWatch>((folder/"sil-io/watch-plant.bin").string(),8,start,18000*kMs,fifo_enabled(),[&](std::uint32_t e){override_signal.request(e);});watch->epoch(1);
        for(const auto* name:{"central","front","rear","plant"})if(three_enabled() || std::string(name)!="rear")observers.push_back(std::make_unique<simulation::NativeMonitorObserver>((folder/"sil-io"/(std::string("watch-")+name+".bin")).string()));
        simulation::NativeExecutionWatch::configure_thread(3,fifo_enabled()?19:0);watch->owner_info.capture();
    }
    mark(folder/"plant-ready");
    bool pass=true,delayed=false;std::string error;std::uint64_t previous=now(),maximum_gap=0,fault_time=0,requested=now(),injection=0;
    std::vector<std::array<std::uint64_t,3>> timing;timing.reserve(40000);
    try {while(!fs::exists(folder/"stop-plant") && now()-start<18'000*kMs) {
        if(watch)simulation::runtime_support::sleep_until(requested);
        NativeIteration iteration(watch.get(),requested);
        if(!delayed && fs::exists(folder/"inject-model-delay")){delayed=true;events.push_back({now(),"model-delay-injected",8,gate.epoch(),0,0,61000000,0});simulation::runtime_support::sleep_until(now()+61*kMs);}
        io.update([&](PlantState& state){
            for(unsigned i=0;i<5;++i)if(state.outputs[i].source_ns)outputs[i].publish(state.outputs[i]);
            if(state.released_epoch){gate.release(state.released_epoch);if(watch)watch->epoch(state.released_epoch);}
        });
        for(auto& observer:observers)if(const auto e=observer->poll(now()))override_signal.request(e);
        const auto before=now();maximum_gap=std::max(maximum_gap,before-previous);previous=before;
        physical.step();
        if(timing.size()<timing.capacity())timing.push_back({before,now(),physical.ok()?0ULL:1ULL});
        else {pass=false;fault_time=now();error="plant timing capacity";break;}
        if(!physical.ok()){pass=false;fault_time=now();break;}
        if(three_enabled() && !physical.trace.empty()) {
            const auto& sample=physical.trace.back();
            if(!injection && fs::exists(folder/"inject")){std::ifstream in(folder/"inject");in>>injection;}
            if(injection && sample.source_ns>=injection && std::abs(sample.torque_nm)<=1 && sample.pressure_pa>=100000)mark(folder/"physical-protected");
        }
        io.update([&](PlantState& state){if(auto sample=sensors[0].read())state.sensors=*sample;});
        iteration.finish();
        if(watch)requested=simulation::M4ReleaseGrid{start,500000}.after(now());
        else std::this_thread::sleep_for(std::chrono::microseconds(500));
    }}catch(const std::exception& e){pass=false;fault_time=now();error=e.what();}
    if(watch)watch->write((folder/"plant-1.native").string());
    std::ofstream log(folder/"physical.csv");log<<"ns,epoch,angle,pressure,torque,bus,model_epoch,model_sequence,speed_mps,distance_m,x_m,y_m,yaw_rad,vehicle_balance_j\n";
    for(const auto& r:physical.trace)log<<r.source_ns<<','<<r.epoch<<','<<r.angle_rad<<','<<r.pressure_pa<<','<<r.torque_nm<<','<<r.bus_v<<','<<r.model_epoch<<','<<r.model_sequence<<','<<r.speed_mps<<','<<r.distance_m<<','<<r.x_m<<','<<r.y_m<<','<<r.yaw_rad<<','<<r.vehicle_balance_j<<'\n';
    if(physical.vehicle()) {
        std::ofstream e(folder/"energy.csv");e<<std::setprecision(17)<<"begin_ns,end_ns,input_ns,epoch,model_epoch,sequence,torque_nm,pressure_pa,wheel_speed_rad_s,kinetic_j,motor_work_j,friction_j,road_j,electrical_mechanical_j,motor_loss_j,battery_draw_j,received_dc_j,auxiliary_j,ohmic_j,capacitor_delta_j,circuit_loss_j,soc,vehicle_balance_j,coupling_balance_j,combined_balance_j\n";
        for(const auto& row:physical.energy_trace){const auto& v=row.state;e<<v.begin_ns<<','<<v.end_ns<<','<<v.input_ns<<','<<row.epoch<<','<<v.model_epoch<<','<<v.sequence<<','<<v.torque_nm<<','<<v.pressure_pa<<','<<v.wheel_speed_rad_s<<','<<v.kinetic_j<<','<<v.motor_work_j<<','<<v.friction_j<<','<<v.road_j<<','<<v.electrical_mechanical_j<<','<<v.motor_loss_j<<','<<v.battery_draw_j<<','<<v.received_dc_j<<','<<v.auxiliary_j<<','<<v.ohmic_j<<','<<v.capacitor_delta_j<<','<<v.circuit_loss_j<<','<<v.soc<<','<<v.vehicle_balance_j<<','<<v.coupling_balance_j<<','<<v.combined_balance_j<<'\n';}
    }
    std::ofstream steps(folder/"plant-timing.csv");steps<<"before,after,failed\n";for(const auto& r:timing)steps<<r[0]<<','<<r[1]<<','<<r[2]<<'\n';
    std::ofstream ev(folder/"plant-events.csv");ev<<"ns,event,owner,epoch,source,deadline,reference,code\n";
    for(const auto& e:events)ev<<e.time_ns<<','<<e.kind<<','<<e.owner<<','<<e.epoch<<','<<e.source_ns<<','<<e.deadline_ns<<','<<e.reference_ns<<','<<e.code<<'\n';
    const auto& f=physical.failure();std::ofstream diag(folder/"plant-failure.json");
    diag<<"{\"model\":\""<<f.model<<"\",\"site\":\""<<f.site<<"\",\"call_ns\":"<<f.call_ns<<",\"return_ns\":"<<f.return_ns<<",\"component_last_success_ns\":"<<f.component_last_success_ns<<",\"previous_call_ns\":"<<f.previous_call_ns<<",\"last_success_ns\":"<<f.last_success_ns<<",\"input_ns\":"<<f.input_ns<<",\"dt_ns\":"<<f.dt_ns<<",\"epoch\":"<<f.epoch<<",\"protection\":"<<f.protection<<",\"io_attempts\":"<<io.attempts<<",\"io_busy\":"<<io.busy<<",\"io_errors\":"<<io.errors<<",\"io_errno\":"<<io.last_errno<<",\"io_error_ns\":"<<io.last_error_ns<<",\"io_first_busy_ns\":"<<io.first_busy_ns<<",\"io_last_busy_ns\":"<<io.last_busy_ns<<",\"outputs\":[";
    for(unsigned i=0;i<5;++i){if(i)diag<<',';const auto& o=f.outputs[i];diag<<"{\"source\":"<<o.source_ns<<",\"epoch\":"<<o.epoch<<",\"steering_mode\":"<<(o.steering?static_cast<int>(o.steering->mode):-1)<<",\"brake_mode\":"<<(o.brake?static_cast<int>(o.brake->mode):-1)<<",\"drive_mode\":"<<(o.drive?static_cast<int>(o.drive->mode):-1)<<'}';}diag<<"]}\n";
    std::ofstream(folder/"plant.json")<<"{\"pass\":"<<(pass?"true":"false")<<",\"samples\":"<<physical.trace.size()<<",\"max_step_gap_ns\":"<<maximum_gap<<",\"fault_time_ns\":"<<fault_time<<",\"energy_fault\":"<<physical.fault_code()<<",\"error\":\""<<error<<"\"}\n";return pass?0:1;
}
} // namespace
int main(int argc,char** argv) {
    if(argc<3)return 2;
    const std::string role=argv[1];const fs::path folder=argv[2];
    if(role=="bootstrap"){
        session::EpochStore::initialize((folder/"epochs").string());
        for(const auto* name:{"central","front","rear","plant"})if(three_enabled() || std::string(name)!="rear")simulation::NativeWatchChannel channel((folder/"sil-io"/(std::string("watch-")+name+".bin")).string(),true);
        return 0;
    }
    if(role=="plant"){try{return plant(folder);}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
    if(argc!=5)return 2;
    const Ecu ecu=role=="central"?Ecu::Central:role=="front"?Ecu::Front:Ecu::Rear;
    const bool remote=ecu!=Ecu::Central;const std::string test=argv[3],generation=argv[4],tag=role+"-"+generation;
    Transport net(ecu,three_enabled(),(folder/(tag+".sdk-api.csv")).string());
    std::unique_ptr<Owners> owners;
    bool pass=false;std::string error;std::uint64_t begin=now(),ready_ns=0,closing=0;
    try {
        net.start();mark(folder/(tag+".started"));
        owners=std::make_unique<Owners>(ecu,net,folder,tag);
        std::uint64_t probe_due=0;
        while(now()-begin<3000*kMs && net.ready!=net.ready_mask()) {
            owners->physical_io();if(now()>=probe_due){net.probe_peer();probe_due=now()+50*kMs;}
            std::this_thread::sleep_for(std::chrono::microseconds(200));
        }
        if(test=="ready-timeout" && !remote){check(net.ready!=net.ready_mask(),"unexpected ready");pass=true;}
        else {
            check(net.ready==net.ready_mask(),"bilateral readiness timeout");
            const auto issued_epoch=remote?0:owners->issue_epoch();
            ready_ns=now();owners->start_watch();mark(folder/(tag+".ready"));
            if(!remote && test=="invalid") {
                const auto t=now();auto p=remote::encode_owner_message({Role::CentralIngress,Role::FrontZone,kDomain,
                    session::Control{Role::FrontZone,session::Phase::Prepare,{999,t,t+2'000*kMs,0,0},t}});
                check(p.has_value(),"negative binding encode");
                net.inject_bad(0x21,1,1,*p);net.inject_bad(0x20,1,1,*p);net.inject_bad(0x40,0,1,*p);
                for(unsigned i=0;i<4;++i){remote::OwnerPacket b;b.size=4;std::copy(kProbe.begin(),kProbe.end(),b.bytes.begin());b.bytes[i]^=1;net.inject_bad(kReady,0,1,b);}
                remote::OwnerPacket b;b.size=3;std::copy(kProbe.begin(),kProbe.end(),b.bytes.begin());net.inject_bad(kReady,0,1,b);b.size=5;net.inject_bad(kReady,0,1,b);
                const auto count=net.probe_responses[0].load();net.probe_peer(true);const auto deadline=now()+1000*kMs;
                while(net.probe_responses[0]==count && now()<deadline)std::this_thread::sleep_for(std::chrono::microseconds(200));
                check(net.probe_responses[0]>count,"negative binding barrier");
            }
            if(!remote)owners->begin(issued_epoch);
            bool injected=false,rejoined=false,invalid_sent=false,rejoin_requested=false;
            std::uint64_t injected_ns=0,paused_until=0,full_sent=0;bool overflow_probe=false;
            std::optional<transport::ZoneRequest> prior_request;
            std::uint64_t requested_wake=owners->watch?owners->watch->next_wake(now()):now();bool native_injected=false;
            while(!fs::exists(folder/("stop-"+role)) && now()-ready_ns<(energy_enabled()?13000:9000)*kMs) {
                if(owners->watch)simulation::runtime_support::sleep_until(requested_wake);
                NativeIteration iteration(owners->watch.get(),requested_wake);
                const auto t=now();
                if(remote && owners->zi==fault_zone() && owners->watch && !native_injected && fs::exists(folder/"inject") && (test=="owner-pause" || test=="monitor-overrun")) {
                    native_injected=true;owners->event("native-injection",0,test=="owner-pause"?200*kMs:6*kMs);
                    if(test=="owner-pause")simulation::runtime_support::sleep_until(t+200*kMs);else owners->monitor_delay=6*kMs;
                }
                const bool fault_phase=fs::exists(folder/"inject");
                if(t>=probe_due){net.probe_peer();probe_due=t+50*kMs;}
                if(fault_phase && !injected){owners->event("injection",remote?0:7);injected=true;injected_ns=t;paused_until=(remote && test=="delay")?0:t+30*kMs;}
                if(remote && fault_phase && test=="delay" && !paused_until && net.queued(0)>0){paused_until=t+30*kMs;owners->event("consumer-paused",0,net.queued(0),paused_until);}
                const bool full=fault_phase && (test=="overflow" || test=="close-full");
                for(const unsigned lane:{1U,3U,0U,2U}) {
                    if(lane>=net.channels())continue;
                    if(remote && lane==0 && (full || (fault_phase && test=="delay" && (!paused_until || t<paused_until))))continue;
                    for(unsigned i=0;i<8;++i){auto m=net.pop(lane);if(!m)break;owners->receive(*m);}
                }
                if(remote && test=="delay" && owners->remote_zone->expired>0)mark(folder/"delay-drained");
                if(remote && full && net.queued(0)==8)mark(folder/"queue-full");
                owners->step(fault_phase && test=="command-loss",fault_phase && test=="result-loss",fault_phase && test=="status-loss",fault_phase && test=="lease-loss");
                if(!remote && full && owners->last_request && full_sent==0) {
                    owners->freeze_normal=true;
                    for(unsigned i=0;i<8;++i){auto r=*owners->last_request;r.epoch+=100;r.token=1000000000ULL+i;owners->diagnostic(r);}
                    full_sent=8;
                }
                if(!remote && test=="close-full" && fs::exists(folder/"queue-full") && !owners->protected_ns)owners->fail("full-queue-protection-request");
                if(!remote && test=="overflow" && full_sent==8 && fs::exists(folder/"queue-full") && !overflow_probe) {
                    // Test-only finite ninth arrival, not a larger normal pending window.
                    auto r=*owners->last_request;r.epoch+=100;r.token=1000000008ULL;
                    check(net.send({Role::CentralIngress,Role::FrontZone,kDomain,r}),"overflow test injection enqueue");
                    overflow_probe=true;owners->event("overflow-extra-send",0,r.token,r.deadline_ns);
                }
                if(!remote && test=="close-full" && full_sent==8 && owners->diagnostic_pending.empty() && now()-injected_ns<100*kMs) {
                    // Bounded uncooperative peer: one further window after the first is accounted.
                    for(unsigned i=0;i<8;++i){auto r=*owners->last_request;r.epoch+=100;r.token=1000000008ULL+i;owners->diagnostic(r);}
                    full_sent=16;
                }
                if(!remote && test=="invalid" && fault_phase && owners->last_request && !invalid_sent) {
                    auto r=*owners->last_request;owners->diagnostic(r);r.epoch+=100;owners->diagnostic(r);invalid_sent=true;
                }
                if(!remote && test=="restart-live" && fault_phase && !prior_request && owners->last_request) {
                    prior_request=owners->last_request;const auto p=remote::encode_owner_message({Role::CentralIngress,static_cast<Role>(fault_zone()),kDomain,*prior_request});
                    std::ofstream saved(folder/"previous-session.packet",std::ios::binary);saved.write(reinterpret_cast<const char*>(p->bytes.data()),p->size);
                }
                if(!remote && owners->protected_ns)mark(folder/"central-protected");
                if(!remote && injected && owners->diagnostic_pending.empty() && (test!="delay" || t>=paused_until))mark(folder/"diagnostics-settled");
                if(!remote && test=="restart-live" && fs::exists(folder/"rejoin-request") && !rejoined) {
                    if(!rejoin_requested){net.ready=0;net.probe_peer(true);rejoin_requested=true;}
                    else if(net.ready==net.ready_mask()) {
                        check(owners->protected_ns!=0 && !owners->gate.allows(owners->epoch),"rejoin before protection");
                        owners->event("ingress-transition-begin",7,owners->pending.size());
                        for(const auto& item:owners->pending)owners->event("retired-pending",7,item.first,item.second.deadline_ns);
                        net.begin_quiescent_transition();
                        iteration.finish();owners.reset(); // single owner stopped; all old mailbox users are gone
                        owners=std::make_unique<Owners>(Ecu::Central,net,folder,tag+"-rejoined");
                        const auto issued_epoch=owners->issue_epoch();
                        owners->start_watch();net.end_quiescent_transition();owners->event("ingress-transition-end",7,issued_epoch);owners->begin(issued_epoch);rejoined=true;
                    }
                }
                if(!remote && rejoined && owners->armed_ns && prior_request && !invalid_sent) {
                    owners->diagnostic(*prior_request);invalid_sent=true;mark(folder/"rejoined");
                }
                if(!remote && owners->port.completed_batches()>=10 && owners->pending.empty() && (!three_enabled() || owners->observed_normal_response()))mark(folder/"control-established");
                const bool healthy_case=test=="normal" || test=="late" || test=="invalid" || (test=="restart-live" && rejoined);
                if(!remote && healthy_case && owners->armed_ns && now()-owners->armed_ns>=500*kMs && (!owners->watch || now()-ready_ns>=run_duration()) && (!energy_enabled() || now()-owners->armed_ns>=5000*kMs) && owners->pending.empty()) {
                    check(owners->release_acks==255 && owners->port.completed_batches()>=10 && owners->accepted_results>=20 && owners->actual_count>=20,"normal real control coverage");
                    check(!owners->protected_ns && owners->core.decision().fault==central::CoordinatorFault::None,"normal control fault");
                    if(test=="invalid")check(invalid_sent && owners->diagnostic_rejected==2,"invalid replay evidence");
                    if(test=="restart-live")check(invalid_sent && owners->diagnostic_rejected==1,"prior session rejection missing");
                    if(!three_enabled()){pass=true;break;}
                    if(!owners->stop_requested){owners->stop_requested=true;owners->stop_started=now();owners->event("normal-stop-requested",7);}
                }
                if(!remote && three_enabled() && owners->stop_complete && owners->pending.empty()) {pass=true;break;}
                if(!remote && three_enabled() && owners->stop_started && now()-owners->stop_started>2500*kMs)throw std::runtime_error("normal stop completion missing");
                if(!remote && owners->protected_ns && healthy_case)throw std::runtime_error("normal owner selected protection");
                if(!remote && owners->coordinator.state()==session::State::Failed && !owners->armed_ns)throw std::runtime_error("session failed before arm");
                if(remote && owners->selected_ns)mark(folder/(role+"-protected"));
                if(!remote && test=="close-full" && injected && t-injected_ns>=250*kMs){pass=owners->protected_ns && owners->diagnostic_pending.empty();break;}
                iteration.finish();
                if(owners->watch)requested_wake=owners->watch->next_wake(now());
                else std::this_thread::sleep_for(std::chrono::microseconds(200));
            }
            if(remote)pass=fs::exists(folder/("stop-"+role));
            else if(test!="normal" && test!="late" && test!="invalid" && test!="restart-live")pass=owners->armed_ns && owners->protected_ns;

            check(pass,"completion condition absent");
        }
    } catch(const std::exception& e){error=e.what();}
    const auto pre_shutdown_protection=owners?owners->protected_ns:0;
    std::uint64_t unprocessed=0,pending_cancelled=0;
    if(owners){
        owners->fail("shutdown-protection");
        if(remote)while(auto m=net.pop(0)) {
            if(auto* r=std::get_if<transport::ZoneRequest>(&m->payload)) {
                ++unprocessed;owners->emit(remote::OwnerMessage{static_cast<Role>(owners->zi),Role::CentralIngress,kDomain,transport::TxResult{r->epoch,r->token,now(),transport::operation(r->work),false,0}});
                owners->event("shutdown-unprocessed-rejected",0,r->token,r->deadline_ns);
            }
        }
        const auto until=now()+20*kMs;
        auto cleanup_wake=owners->watch?owners->watch->next_wake(now()):now();
        do {
            if(owners->watch)simulation::runtime_support::sleep_until(cleanup_wake);
            NativeIteration iteration(owners->watch.get(),cleanup_wake);
            for(unsigned lane=0;lane<net.channels();++lane)for(unsigned i=0;i<8;++i){auto m=net.pop(lane);if(!m)break;owners->receive(*m);}
            owners->step();owners->physical_io();
            if(remote?owners->zone[owners->zi]->protected_selected():(owners->zones[0].protection.acknowledged(owners->epoch) && (!three_enabled() || owners->zones[1].protection.acknowledged(owners->epoch))))break;
            iteration.finish();
            if(owners->watch)cleanup_wake=owners->watch->next_wake(now());else std::this_thread::sleep_for(std::chrono::microseconds(200));
        }while(now()<until);
        for(const auto& item:owners->pending){++pending_cancelled;owners->event("cancelled-on-protection",0,item.first,item.second.deadline_ns);}
        owners->pending.clear();
        if(owners->trace.overflow || owners->event_overflow || owners->energy_feedback_overflow){pass=false;error="trace capacity exceeded";}
    }
    // Controller work has selected protection and finished cleanup. Artifact IO
    // and SDK teardown are outside the guarded owner lifetime.
    if(owners && owners->watch)owners->watch->stop();
    if(owners) {
        std::ofstream out(folder/(tag+".leaf-events.csv"));out<<"ns,event,owner,epoch,source,deadline,value,detail\n";
        for(const auto& leaf:owners->leaf)if(leaf)for(const auto& e:leaf->input_events())out<<e.time_ns<<','<<e.kind<<','<<e.owner<<','<<e.epoch<<','<<e.source_ns<<','<<e.deadline_ns<<','<<e.reference_ns<<','<<e.code<<'\n';
    }
    if(owners && owners->watch)owners->watch->write((folder/(tag+".native")).string());
    if(!remote && pass && test!="ready-timeout" && (test=="normal" || test=="late" || test=="invalid" || test=="restart-live")) {
        // Already protected/quiesced; retain the receive endpoint for the peer's
        // final evidence. This handshake never extends a live command deadline.
        mark(folder/(tag+".quiesced"));const auto cleanup_deadline=now()+1000*kMs;
        while(!fs::exists(folder/"stop-central") && now()<cleanup_deadline) {
            for(unsigned lane=0;lane<net.channels();++lane)for(unsigned i=0;i<8;++i){auto m=net.pop(lane);if(!m)break;owners->receive(*m);}
            owners->step();std::this_thread::sleep_for(std::chrono::microseconds(200));
        }
        if(!fs::exists(folder/"stop-central")){pass=false;error="peer shutdown handshake timeout";}
    }
    closing=now();net.stop();
    std::ofstream summary(folder/(tag+".json"));
    summary<<"{\"pass\":"<<(pass?"true":"false")<<",\"orderly_stop\":true,\"stop_begin\":"<<closing<<",\"stop_return\":"<<net.stop_return_ns<<",\"join_return\":"<<net.join_return_ns
        <<",\"pending_cancelled\":"<<pending_cancelled<<",\"pending_expired\":"<<(owners?owners->pending_expired:0)<<",\"pre_shutdown_protection\":"<<pre_shutdown_protection<<",\"unprocessed_rejected\":"<<unprocessed<<",\"diagnostic_sent\":"<<(owners?owners->diagnostic_sent:0)<<",\"diagnostic_rejected\":"<<(owners?owners->diagnostic_rejected:0)<<",\"diagnostic_expired\":"<<(owners?owners->diagnostic_expired:0)<<",\"diagnostic_late\":"<<(owners?owners->diagnostic_late:0)<<",\"state_violations\":"<<(owners?owners->state_violations:0)<<",\"pre_init_rejected\":"<<(owners?owners->pre_init_rejected:0)<<",\"epoch\":"<<(owners?owners->epoch:0)<<",\"release_ack_mask\":"<<(owners?owners->release_acks:0)<<",\"armed_ns\":"<<(owners?owners->armed_ns:0)
        <<",\"protected_ns\":"<<(owners?owners->protected_ns:0)<<",\"selected_ns\":"<<(owners?owners->selected_ns:0)<<",\"last_lease_expiry\":"<<(owners?(remote?owners->remote_zone->last_lease_expiry:owners->last_lease_expiry):0)
        <<",\"batches\":"<<(owners?owners->port.completed_batches():0)<<",\"actual_count\":"<<(owners?owners->actual_count:0)<<",\"result_count\":"<<(owners?owners->result_count:0)
        <<",\"steering_applied\":"<<(owners && ecu==Ecu::Front?owners->leaf[0]->received_commands():0)<<",\"brake_applied\":"<<(owners && ecu==Ecu::Front?owners->leaf[1]->received_commands():0)
        <<",\"drive_applied\":"<<(owners && ecu==Ecu::Rear?owners->leaf[2]->received_commands():0)
        <<",\"max_validated_wheel_speed\":"<<(owners?owners->max_validated_wheel_speed:0)<<",\"wheel_speed_samples\":"<<(owners?owners->wheel_speed_samples:0)
        <<",\"normal_stop_started\":"<<(owners?owners->stop_started:0)<<",\"normal_stop_complete\":"<<(owners?owners->stop_complete:0)
        <<",\"expired_rejected\":"<<(owners && remote?owners->remote_zone->expired:0)<<",\"rx_highwater\":"<<std::max(net.highwater[0].load(),net.highwater[2].load())<<",\"authority_highwater\":"<<std::max(net.highwater[1].load(),net.highwater[3].load())<<",\"max_owner_poll_gap_ns\":"<<(owners?owners->max_poll_gap:0)<<",\"stale_authority_rejected\":"<<net.stale_authority_rejected<<",\"binding_rejected\":"<<net.rejected<<",\"send_returned\":"<<net.send_returned
        <<",\"authority_rejected\":"<<net.rx_rejected[1]<<",\"transition_discarded\":["<<net.transition_discarded[0]<<','<<net.transition_discarded[1]<<','<<net.transition_discarded[2]<<','<<net.transition_discarded[3]<<']'<<",\"rx_rejected\":"<<net.rx_rejected[0]<<",\"rx_overflow_ns\":"<<net.rx_overflow_ns<<",\"rx_overflow_token\":"<<net.rx_overflow_token<<",\"fifo_preserved\":"<<(net.fifo_preserved?"true":"false")<<",\"overflow_drained\":"<<net.drained_count<<",\"io_attempts\":"<<(owners?owners->io.attempts:0)<<",\"io_busy\":"<<(owners?owners->io.busy:0)<<",\"io_errors\":"<<(owners?owners->io.errors:0)<<",\"overflow\":"<<(net.overflow?"true":"false")<<",\"error\":\""<<error<<"\"}\n";
    return pass?0:1;
}
