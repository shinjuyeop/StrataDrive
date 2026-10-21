// Opt-in Host adapter. Eight real participants; no pilot grants or synthetic feedback.
#include "adapter_transport.hpp"
#include "plant_io.hpp"
#include "remote_leaf_endpoint.hpp"
#include "run_lease_issuer.hpp"
#include "epoch_store.hpp"
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
constexpr remote::ClockAgreement agreement{kDomain,kDomain,0,0,true};
void mark(const fs::path& p){
    // Main owner only. Each diagnostic transition writes once, never each poll.
    static std::set<fs::path> written;
    if(written.insert(p).second)std::ofstream(p)<<now()<<'\n';
}
struct Trace final:transport::TransportTrace {
    std::ofstream out;std::vector<transport::TransportTraceRow> rows;bool overflow=false;
    explicit Trace(const fs::path& p):out(p){rows.reserve(65536);}
    ~Trace(){out<<"event,ns,peer,epoch,token,sent,deadline,operation,decision,source,original_source,inner_deadline,payload_source\n";
        for(const auto& r:rows)out<<r.stage<<','<<r.time_ns<<','<<r.peer<<','<<r.epoch<<','<<r.token<<','<<r.sent_ns<<','<<r.deadline_ns<<','<<r.operation<<','<<r.outcome<<','<<r.result_source_ns<<','<<r.original_source_ns<<','<<r.inner_deadline_ns<<','<<r.payload_source_ns<<'\n';}
    void record(transport::TransportTraceRow r) noexcept override;
};
class FrontEndpoint final:private session::ParticipantPort {
    simulation::m4_detail::ZoneSession& actor_;zone::AsyncZoneOwner& zone_;
    transport::RunGate& gate_; transport::ZoneLink& link_;
    session::SessionParticipant participant_{Role::FrontZone,*this};remote::RunLeaseGate credit_;
    std::uint32_t epoch_=0;std::uint64_t last_token_=0;
    std::array<std::optional<remote::ProtectionAck>,8> protection_{};
    std::uint64_t now_ns() noexcept override{return actor_.now_ns();}
    session::Preparation prepare(const session::Plan& p) noexcept override {gate_.close();return actor_.prepare(p);}
    bool initialize(const session::Plan& p) noexcept override {
        gate_.close();if(!actor_.initialize(p) || !credit_.bind(p,agreement,now_ns()))return false;
        epoch_=p.epoch;last_token_=0;protection_={};return true;
    }
    void protect() noexcept override{gate_.close();credit_.protect(epoch_);actor_.protect();}
    bool allowed(){return credit_.allows(participant_,now_ns()) && !zone_.faulted() && !link_.failed();}
    void service() noexcept override {
        if(allowed())gate_.release(epoch_);else {gate_.close();if(credit_.fault()!=remote::RunLeaseFault::None)protect();}
        actor_.service();
    }
public:
    std::uint64_t rejected=0,expired=0,last_lease_expiry=0;
    FrontEndpoint(simulation::m4_detail::ZoneSession& a,zone::AsyncZoneOwner& z,transport::RunGate& g,transport::ZoneLink& l):actor_(a),zone_(z),gate_(g),link_(l){}
    remote::OwnerMessage reply(remote::OwnerPayload p){return {Role::FrontZone,Role::CentralIngress,kDomain,std::move(p)};}
    std::optional<remote::OwnerMessage> receive(const remote::OwnerMessage& m) {
        const auto t=now_ns();
        if(const auto* c=std::get_if<session::Control>(&m.payload)) {if(auto a=participant_.receive(*c,t))return reply(*a);}
        else if(const auto* l=std::get_if<remote::RunLease>(&m.payload)) {
            if(credit_.receive(*l,m.clock_domain,participant_,t))last_lease_expiry=l->expires_at_ns;
            service();
        } else if(const auto* r=std::get_if<transport::ZoneRequest>(&m.payload)) {
            // Old Epoch and duplicates cannot poll or mutate live-session state.
            const bool identity=r->epoch==epoch_ && r->token>last_token_;
            const bool timely=r->sent_ns<=t && t<r->deadline_ns && r->deadline_ns-r->sent_ns<=transport::kResultBudgetNs;
            if(!identity || !timely || !allowed()) {
                ++rejected;if(identity && !timely){++expired;protect();}
                return reply(transport::TxResult{r->epoch,r->token,t,transport::operation(r->work),false,0});
            }
            last_token_=r->token;
            if(!link_.work.push(*r)){participant_.continuity_lost(t);++rejected;}
        } else if(const auto* p=std::get_if<remote::ProtectionRequest>(&m.payload)) {
            if(p->epoch!=epoch_ || !p->token || p->source_time_ns>t || t>=p->deadline_ns || p->deadline_ns-p->source_time_ns>20*kMs)return {};
            for(const auto& a:protection_)if(a && a->request.token==p->token) {
                if(a->request.source_time_ns==p->source_time_ns && a->request.deadline_ns==p->deadline_ns)return reply(*a);
                return {};
            }
            protect(); // ACK only after the actual Leaf selection, in poll().
            for(auto& a:protection_)if(!a){a=remote::ProtectionAck{*p,0,false};break;}
        }
        return {};
    }
    std::optional<remote::OwnerMessage> poll() {
        if(auto a=participant_.poll(now_ns()))return reply(*a);
        for(auto& a:protection_)if(a && !a->selected && zone_.protected_selected() && now_ns()<a->request.deadline_ns) {
            a->selected=true;a->selected_ns=now_ns();return reply(*a);
        }
        return {};
    }
    void lost(){participant_.continuity_lost(now_ns());}
    unsigned lease_fault() const{return static_cast<unsigned>(credit_.fault());}
};
struct Owners final:session::CoordinatorPort {
    const bool front;const fs::path folder;const std::string tag;
    Clock clock{true};transport::RunGate gate;std::array<transport::RunGate,2> leaf_gates;
    std::array<transport::ZoneLink,2> zones;std::array<transport::LeafLink,5> leaves;
    std::array<runtime::LatestSnapshot<simulation::OwnerSensors>,8> sensors;
    std::array<runtime::LatestSnapshot<simulation::OwnerActuation>,5> outputs;
    simulation::BmsGateChannel bms;
    central::AsyncCoordinatorPort port{clock,gate,zones[0],zones[1]};central::VehicleCoordinator core{port,{true}};
    std::array<std::unique_ptr<zone::AsyncZoneOwner>,2> zone;
    std::array<std::unique_ptr<simulation::m4_detail::ZoneSession>,2> zone_session;
    std::array<std::unique_ptr<simulation::AsyncLeafOwner>,5> leaf;
    simulation::m4_detail::CentralIngress ingress{port,clock,sensors[7]};
    session::SessionLinks links;
    std::array<std::unique_ptr<simulation::SessionOwnerLoop>,8> sessions;
    std::array<std::unique_ptr<simulation::RemoteLeafEndpoint>,2> remote_leaf;
    std::unique_ptr<FrontEndpoint> remote_zone;
    Transport& net;PlantIO io;
    session::SessionCoordinator coordinator{*this};central::RunLeaseIssuer issuer{coordinator};
    std::ofstream events;Trace trace;
    std::uint32_t epoch=0,root_seq=0,vehicle_seq=0;std::uint64_t released=0,next_management=0,last_credit=0,vehicle_release=0,lifecycle_slot=0;
    std::uint64_t armed_ns=0,protected_ns=0,selected_ns=0,last_lease_expiry=0,actual_count=0,result_count=0,accepted_results=0;
    std::uint64_t protection_token=0,protection_sent=0,release_acks=0;bool stop_credit=false;
    std::map<std::uint64_t,transport::ZoneRequest> pending;
    std::optional<transport::ZoneRequest> last_request;
    std::map<std::pair<std::uint32_t,std::uint64_t>,std::uint64_t> diagnostic_pending;
    std::uint64_t diagnostic_sent=0,diagnostic_rejected=0,diagnostic_expired=0,diagnostic_late=0,pending_expired=0,state_violations=0,pre_init_rejected=0;
    std::uint64_t last_step=0,max_poll_gap=0;
    bool freeze_normal=false;remote::ProtectionReceipt receipt;
    explicit Owners(bool f,Transport& n,const fs::path& d,const std::string& label):front(f),folder(d),tag(label),net(n),io((d/"sil-io"/"plant.bin").string()),events(d/(tag+".events.csv")),trace(d/(tag+".transport.csv")) {
        events<<"ns,event,epoch,role,value,deadline\n";
        std::array<transport::LeafLink*,5> ptr{};for(unsigned i=0;i<5;++i)ptr[i]=&leaves[i];
        const unsigned z=front?0:1;
        zone[z]=std::make_unique<zone::AsyncZoneOwner>(front?zone::ZoneScope::Front:zone::ZoneScope::Rear,clock,gate,zones[z],ptr);
        zone[z]->transport_trace(&trace);
        zone_session[z]=std::make_unique<simulation::m4_detail::ZoneSession>(*zone[z],clock,sensors[z]);
        if(front)remote_zone=std::make_unique<FrontEndpoint>(*zone_session[0],*zone[0],gate,zones[0]);
        else sessions[1]=std::make_unique<simulation::SessionOwnerLoop>(Role::RearZone,*zone_session[1],links[1]);
        for(unsigned i=front?0:2;i<(front?2:5);++i) {
            leaf[i]=std::make_unique<simulation::AsyncLeafOwner>(static_cast<transport::Leaf>(i),clock,front?leaf_gates[i]:gate,leaves[i],sensors[i+2],outputs[i],bms);
            leaf[i]->transport_trace(&trace);
            if(front)remote_leaf[i]=std::make_unique<simulation::RemoteLeafEndpoint>(static_cast<Role>(i+2),*leaf[i],leaf_gates[i],leaves[i],agreement);
            else sessions[i+2]=std::make_unique<simulation::SessionOwnerLoop>(static_cast<Role>(i+2),*leaf[i],links[i+2]);
        }
        if(!front){sessions[7]=std::make_unique<simulation::SessionOwnerLoop>(Role::CentralIngress,ingress,links[7]);port.transport_trace(&trace);}
    }
    void event(const char* name,unsigned role,std::uint64_t value=0,std::uint64_t deadline=0){events<<now()<<','<<name<<','<<epoch<<','<<role<<','<<value<<','<<deadline<<'\n';}
    std::uint64_t now_ns() noexcept override{return clock.now_ns();}
    bool quiesce_central() noexcept override {gate.close();core.request_protection(now());port.protect();return true;}
    bool commit_central(central::CoordinatorSession s) noexcept override{return core.start_session(s);}
    void protect_central() noexcept override{gate.close();core.request_protection(now());port.protect();}
    bool send(const session::Control& c) noexcept override {
        event("session-send",static_cast<unsigned>(c.role),static_cast<unsigned>(c.phase),c.plan.commit_deadline_ns);
        return remote_role(c.role)?net.send({Role::CentralIngress,c.role,kDomain,c}):links[static_cast<unsigned>(c.role)].controls.push(c);
    }
    void begin(std::uint32_t e){epoch=e;check(coordinator.begin(e,now()),"real session begin");event("epoch-issued",7,e);}
    void physical_io() {
        io.update([this](PlantState& s){
            for(auto& snapshot:sensors)snapshot.publish(s.sensors);
            for(unsigned i=front?0:2;i<(front?2:5);++i)if(auto v=outputs[i].read())s.outputs[i]=*v;
            if(!front && released)s.released_epoch=static_cast<std::uint32_t>(released);
        });
    }
    void emit(const std::optional<remote::OwnerMessage>& m){
        if(m && std::holds_alternative<session::Ack>(m->payload)){const auto& a=std::get<session::Ack>(m->payload);if(a.accepted && a.phase==session::Phase::Initialize)net.initialized_epoch[static_cast<unsigned>(a.role)].store(a.plan.epoch);event("local-ack-produced",static_cast<unsigned>(a.role),static_cast<unsigned>(a.phase),a.accepted);events.flush();}
        if(m && !net.send(*m))fail("outbound-full");
    }
    void fail(const char* why) {
        if(!protected_ns){protected_ns=now();event(why,front?0:7);}
        if(front){remote_zone->lost();for(auto& e:remote_leaf)e->continuity_lost();}
        else {protect_central();if(coordinator.state()!=session::State::Failed)coordinator.cancel(now());}
    }
    void ack(const session::Ack& a) {
        const auto result=coordinator.receive(a,now());
        event("session-ack",static_cast<unsigned>(a.role),static_cast<unsigned>(a.phase)*10+static_cast<unsigned>(result),a.plan.commit_deadline_ns);
        if(a.phase==session::Phase::Release && a.accepted && result==session::AckResult::Accepted)release_acks|=1ULL<<static_cast<unsigned>(a.role);
    }
    void receive(remote::OwnerMessage m) {
        if(front) {
            if(const auto* c=std::get_if<session::Control>(&m.payload)) {
                event("control-received",static_cast<unsigned>(m.to),static_cast<unsigned>(c->phase),c->plan.epoch);events.flush();
                if(c->phase==session::Phase::Initialize){epoch=c->plan.epoch;pre_init_rejected=net.rejected;event("pre-init-binding-rejections",0,pre_init_rejected);}
            }
            if(m.to==Role::FrontZone) {
                const auto commands=leaf[0]->received_commands()+leaf[1]->received_commands();const auto old_gate=gate.epoch();
                const auto rejected=remote_zone->rejected;
                const auto response=remote_zone->receive(m);
                if(remote_zone->rejected>rejected && remote_zone->expired==0 &&
                   (commands!=leaf[0]->received_commands()+leaf[1]->received_commands() || old_gate!=gate.epoch()))++state_violations;
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
            if(!zones[0].results.push(*r))fail("result-overflow");
        } else if(auto* f=std::get_if<transport::Feedback>(&m.payload)) {
            ++actual_count;if(!zones[0].feedback.push(*f))fail("feedback-overflow");
        } else if(auto* a=std::get_if<remote::ProtectionAck>(&m.payload)) {
            if(receipt.receive(m,now())) {
                zones[0].protection.selected.store(epoch);event("remote-protection-selected",0,a->selected_ns,a->request.deadline_ns);
            }
        }
    }
    void step(bool drop_commands=false,bool drop_results=false,bool drop_status=false,bool drop_lease=false) {
        const auto observed=now();if(last_step)max_poll_gap=std::max(max_poll_gap,observed-last_step);last_step=observed;
        physical_io();
        if(net.overflow)fail("transport-overflow");
        if(front) {
            // This priority path remains active even when normal receive consumption stops.
            emit(remote_zone->poll());for(auto& e:remote_leaf)emit(e->poll());
            if(zone[0]->faulted() && !protected_ns){protected_ns=now();event("local-protection",0,remote_zone->lease_fault(),remote_zone->last_lease_expiry);}
            if(zone[0]->protected_selected() && !selected_ns){selected_ns=now();event("leaf-protection-selected",0);}
            while(auto r=zones[0].results.pop()) {
                event("result-produced",0,r->token,r->source_ns);
                if(!drop_results)emit(remote::OwnerMessage{Role::FrontZone,Role::CentralIngress,kDomain,*r});
            }
            while(auto f=zones[0].feedback.pop())if(!drop_status)emit(remote::OwnerMessage{Role::FrontZone,Role::CentralIngress,kDomain,*f});
            return;
        }
        for(unsigned i=0;i<8;++i)if(sessions[i])sessions[i]->step();
        for(auto& l:links)while(auto a=l.acks.pop())ack(*a);
        coordinator.poll(now());
        if(coordinator.run_enabled() && !freeze_normal) {
            const auto t=now();const auto plan=coordinator.plan();
            if(!released){released=epoch;gate.release(epoch);next_management=plan.enable_ns+14*kMs;event("all-eight-released",7,release_acks);}
            if(!drop_lease && !stop_credit && gate.allows(epoch) && (!last_credit || t-last_credit>=10*kMs)) {
                if(auto lease=issuer.issue(t)) {for(const auto r:{Role::FrontZone,Role::Steering,Role::Brake})emit(remote::OwnerMessage{Role::CentralIngress,r,kDomain,*lease});last_credit=t;last_lease_expiry=lease->expires_at_ns;event("credit-issued",7,lease->sequence,lease->expires_at_ns);}
            }
            const bool due=t>=next_management;
            const auto slot=t>=plan.enable_ns+4*kMs?(t-plan.enable_ns-4*kMs)/(20*kMs)+1:0;
            if(due && slot!=lifecycle_slot){lifecycle_slot=slot;core.receive_lifecycle({{epoch,root_seq++,t,t+60*kMs},can::BmsPowerAction::Enable},now());}
            if(core.decision().normal_armed && t>=core.next_allocation_ns() && vehicle_release!=core.next_allocation_ns()) {
                vehicle_release=core.next_allocation_ns();core.receive_vehicle({epoch,vehicle_seq++,t,t+60*kMs,.2,.02,0,false},now());
            }
            if(due)next_management=plan.enable_ns+4*kMs+((t-plan.enable_ns-4*kMs)/(10*kMs)+1)*(10*kMs);
            const auto feedback=port.feedback();core.tick(feedback,now(),due);
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
        while(auto r=zones[0].work.pop()) {
            last_request=*r;pending[r->token]=*r;event("command-enqueue",0,r->token,r->deadline_ns);
            if(!drop_commands)emit(remote::OwnerMessage{Role::CentralIngress,Role::FrontZone,kDomain,*r});
        }
        if(zones[0].protection.pending(epoch) && released && !protection_sent) {
            protection_sent=now();++protection_token;
            const remote::ProtectionRequest request{epoch,protection_token,protection_sent,protection_sent+20*kMs};
            check(receipt.expect(request,Role::FrontZone,kDomain,now()),"protection receipt expectation");
            emit(remote::OwnerMessage{Role::CentralIngress,Role::FrontZone,kDomain,request});
            event("protection-request",0,protection_token,protection_sent+20*kMs);
        }
    }
    void diagnostic(transport::ZoneRequest r) {
        check(diagnostic_pending.size()<8,"diagnostic pending bound");
        diagnostic_pending[{r.epoch,r.token}]=now()+20*kMs;++diagnostic_sent;
        emit(remote::OwnerMessage{Role::CentralIngress,Role::FrontZone,kDomain,r});
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
    std::vector<simulation::M4Event> events;const auto start=now();
    simulation::m4_detail::PhysicalOwner physical{clock,gate,sensors,outputs,start,events,override_signal,1};
    PlantIO io((folder/"sil-io"/"plant.bin").string(),true);mark(folder/"plant-ready");
    bool pass=true;std::uint64_t previous=now(),maximum_gap=0,fault_time=0;
    std::vector<std::array<std::uint64_t,3>> timing;timing.reserve(40000);
    while(!fs::exists(folder/"stop-plant") && now()-start<18'000*kMs) {
        io.update([&](PlantState& state){
            for(unsigned i=0;i<5;++i)if(state.outputs[i].source_ns)outputs[i].publish(state.outputs[i]);
            if(state.released_epoch)gate.release(state.released_epoch);
        });
        const auto before=now();maximum_gap=std::max(maximum_gap,before-previous);previous=before;
        physical.step();
        if(timing.size()<timing.capacity())timing.push_back({before,now(),physical.ok()?0ULL:1ULL});
        else {pass=false;fault_time=now();break;}
        if(!physical.ok()){pass=false;fault_time=now();break;}
        io.update([&](PlantState& state){if(auto s=sensors[0].read())state.sensors=*s;});
        std::this_thread::sleep_for(std::chrono::microseconds(500));
    }
    std::ofstream log(folder/"physical.csv");log<<"ns,epoch,angle,pressure,torque,bus,model_epoch,model_sequence\n";
    for(const auto& r:physical.trace)log<<r.source_ns<<','<<r.epoch<<','<<r.angle_rad<<','<<r.pressure_pa<<','<<r.torque_nm<<','<<r.bus_v<<','<<r.model_epoch<<','<<r.model_sequence<<'\n';
    std::ofstream steps(folder/"plant-timing.csv");steps<<"before,after,failed\n";for(const auto& r:timing)steps<<r[0]<<','<<r[1]<<','<<r[2]<<'\n';
    std::ofstream(folder/"plant.json")<<"{\"pass\":"<<(pass?"true":"false")<<",\"samples\":"<<physical.trace.size()<<",\"max_step_gap_ns\":"<<maximum_gap<<",\"fault_time_ns\":"<<fault_time<<",\"energy_fault\":"<<physical.fault_code()<<"}\n";return pass?0:1;
}
} // namespace
int main(int argc,char** argv) {
    if(argc<3)return 2;
    const std::string role=argv[1];const fs::path folder=argv[2];
    if(role=="bootstrap"){session::EpochStore::initialize((folder/"epochs").string());return 0;}
    if(role=="plant"){try{return plant(folder);}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
    if(argc!=5)return 2;
    const bool front=role=="front";const std::string test=argv[3],generation=argv[4],tag=role+"-"+generation;
    Transport net(front,(folder/(tag+".sdk-api.csv")).string());
    std::unique_ptr<Owners> owners;
    bool pass=false;std::string error;std::uint64_t begin=now(),ready_ns=0,closing=0;
    try {
        net.start();mark(folder/(tag+".started"));
        owners=std::make_unique<Owners>(front,net,folder,tag);
        std::uint64_t probe_due=0;
        while(now()-begin<3000*kMs && net.ready!=3) {
            owners->physical_io();if(now()>=probe_due){net.probe_peer();probe_due=now()+50*kMs;}
            std::this_thread::sleep_for(std::chrono::microseconds(200));
        }
        if(test=="ready-timeout" && !front){check(net.ready!=3,"unexpected ready");pass=true;}
        else {
            check(net.ready==3,"bilateral readiness timeout");ready_ns=now();mark(folder/(tag+".ready"));
            if(!front && test=="invalid") {
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
            if(!front)owners->begin(session::EpochStore((folder/"epochs").string()).issue());
            bool injected=false,rejoined=false,invalid_sent=false,rejoin_requested=false;
            std::uint64_t injected_ns=0,paused_until=0,full_sent=0;
            std::optional<transport::ZoneRequest> prior_request;
            while(!fs::exists(folder/("stop-"+role)) && now()-ready_ns<9000*kMs) {
                const auto t=now();
                const bool fault_phase=fs::exists(folder/"inject");
                if(t>=probe_due){net.probe_peer();probe_due=t+50*kMs;}
                if(fault_phase && !injected){owners->event("injection",front?0:7);injected=true;injected_ns=t;paused_until=(front && test=="delay")?0:t+30*kMs;}
                if(front && fault_phase && test=="delay" && !paused_until && net.queued(0)>0){paused_until=t+30*kMs;owners->event("consumer-paused",0,net.queued(0),paused_until);}
                const bool full=fault_phase && (test=="overflow" || test=="close-full");
                for(const unsigned lane:{1U,0U}) {
                    if(front && lane==0 && (full || (fault_phase && test=="delay" && (!paused_until || t<paused_until))))continue;
                    for(unsigned i=0;i<8;++i){auto m=net.pop(lane);if(!m)break;owners->receive(*m);}
                }
                if(front && test=="delay" && owners->remote_zone->expired>0)mark(folder/"delay-drained");
                if(front && full && net.queued(0)==8)mark(folder/"queue-full");
                owners->step(fault_phase && test=="command-loss",fault_phase && test=="result-loss",fault_phase && test=="status-loss",fault_phase && test=="lease-loss");
                if(!front && full && owners->last_request && full_sent==0) {
                    owners->freeze_normal=true;
                    for(unsigned i=0;i<8;++i){auto r=*owners->last_request;r.epoch+=100;r.token=1000000000ULL+i;owners->diagnostic(r);}
                    full_sent=8;
                }
                if(!front && full && fs::exists(folder/"queue-full") && !owners->protected_ns)owners->fail("full-queue-protection-request");
                if(!front && test=="close-full" && full_sent==8 && owners->diagnostic_pending.empty() && now()-injected_ns<100*kMs) {
                    // Bounded uncooperative peer: one further window after the first is accounted.
                    for(unsigned i=0;i<8;++i){auto r=*owners->last_request;r.epoch+=100;r.token=1000000008ULL+i;owners->diagnostic(r);}
                    full_sent=16;
                }
                if(!front && test=="invalid" && fault_phase && owners->last_request && !invalid_sent) {
                    auto r=*owners->last_request;owners->diagnostic(r);r.epoch+=100;owners->diagnostic(r);invalid_sent=true;
                }
                if(!front && test=="restart-live" && fault_phase && !prior_request && owners->last_request) {
                    prior_request=owners->last_request;const auto p=remote::encode_owner_message({Role::CentralIngress,Role::FrontZone,kDomain,*prior_request});
                    std::ofstream saved(folder/"previous-session.packet",std::ios::binary);saved.write(reinterpret_cast<const char*>(p->bytes.data()),p->size);
                }
                if(!front && owners->protected_ns)mark(folder/"central-protected");
                if(!front && injected && owners->diagnostic_pending.empty() && (test!="delay" || t>=paused_until))mark(folder/"diagnostics-settled");
                if(!front && test=="restart-live" && fs::exists(folder/"rejoin-request") && !rejoined) {
                    if(!rejoin_requested){net.ready=0;net.probe_peer(true);rejoin_requested=true;}
                    else if(net.ready==3) {
                        check(owners->protected_ns!=0,"rejoin before protection");
                        owners.reset(); // single owner stopped; all old mailbox users are gone
                        owners=std::make_unique<Owners>(false,net,folder,tag+"-rejoined");
                        owners->begin(session::EpochStore((folder/"epochs").string()).issue());rejoined=true;
                    }
                }
                if(!front && rejoined && owners->armed_ns && prior_request && !invalid_sent) {
                    owners->diagnostic(*prior_request);invalid_sent=true;mark(folder/"rejoined");
                }
                if(!front && owners->port.completed_batches()>=10 && owners->pending.empty())mark(folder/"control-established");
                const bool healthy_case=test=="normal" || test=="late" || test=="invalid" || (test=="restart-live" && rejoined);
                if(!front && healthy_case && owners->armed_ns && now()-owners->armed_ns>=500*kMs && owners->pending.empty()) {
                    check(owners->release_acks==255 && owners->port.completed_batches()>=10 && owners->accepted_results>=20 && owners->actual_count>=20,"normal real control coverage");
                    check(!owners->protected_ns && owners->core.decision().fault==central::CoordinatorFault::None,"normal control fault");
                    if(test=="invalid")check(invalid_sent && owners->diagnostic_rejected==2,"invalid replay evidence");
                    if(test=="restart-live")check(invalid_sent && owners->diagnostic_rejected==1,"prior session rejection missing");
                    pass=true;break;
                }
                if(!front && owners->protected_ns && healthy_case)throw std::runtime_error("normal owner selected protection");
                if(!front && owners->coordinator.state()==session::State::Failed && !owners->armed_ns)throw std::runtime_error("session failed before arm");
                if(front && owners->selected_ns)mark(folder/"front-protected");
                if(!front && test=="close-full" && injected && t-injected_ns>=250*kMs){pass=owners->protected_ns && owners->diagnostic_pending.empty();break;}
                std::this_thread::sleep_for(std::chrono::microseconds(200));
            }
            if(front)pass=fs::exists(folder/"stop-front");
            else if(test!="normal" && test!="late" && test!="invalid" && test!="restart-live")pass=owners->armed_ns && owners->protected_ns;

            check(pass,"completion condition absent");
        }
    } catch(const std::exception& e){error=e.what();}
    const auto pre_shutdown_protection=owners?owners->protected_ns:0;
    std::uint64_t unprocessed=0,pending_cancelled=0;
    if(owners){
        owners->fail("shutdown-protection");
        if(front)while(auto m=net.pop(0)) {
            if(auto* r=std::get_if<transport::ZoneRequest>(&m->payload)) {
                ++unprocessed;owners->emit(remote::OwnerMessage{Role::FrontZone,Role::CentralIngress,kDomain,transport::TxResult{r->epoch,r->token,now(),transport::operation(r->work),false,0}});
                owners->event("shutdown-unprocessed-rejected",0,r->token,r->deadline_ns);
            }
        }
        const auto until=now()+20*kMs;
        do {
            for(unsigned lane=0;lane<2;++lane)for(unsigned i=0;i<8;++i){auto m=net.pop(lane);if(!m)break;owners->receive(*m);}
            owners->step();owners->physical_io();
            if(front?owners->zone[0]->protected_selected():owners->zones[0].protection.acknowledged(owners->epoch))break;
            std::this_thread::sleep_for(std::chrono::microseconds(200));
        }while(now()<until);
        for(const auto& item:owners->pending){++pending_cancelled;owners->event("cancelled-on-protection",0,item.first,item.second.deadline_ns);}
        owners->pending.clear();
        if(owners->trace.overflow){pass=false;error="trace capacity exceeded";}
    }
    if(owners) {
        std::ofstream out(folder/(tag+".leaf-events.csv"));out<<"ns,event,owner,epoch,source,deadline,value,detail\n";
        for(const auto& leaf:owners->leaf)if(leaf)for(const auto& e:leaf->input_events())out<<e.time_ns<<','<<e.kind<<','<<e.owner<<','<<e.epoch<<','<<e.source_ns<<','<<e.deadline_ns<<','<<e.reference_ns<<','<<e.code<<'\n';
    }
    closing=now();net.stop();
    std::ofstream summary(folder/(tag+".json"));
    summary<<"{\"pass\":"<<(pass?"true":"false")<<",\"orderly_stop\":true,\"stop_begin\":"<<closing<<",\"stop_return\":"<<net.stop_return_ns<<",\"join_return\":"<<net.join_return_ns
        <<",\"pending_cancelled\":"<<pending_cancelled<<",\"pending_expired\":"<<(owners?owners->pending_expired:0)<<",\"pre_shutdown_protection\":"<<pre_shutdown_protection<<",\"unprocessed_rejected\":"<<unprocessed<<",\"diagnostic_sent\":"<<(owners?owners->diagnostic_sent:0)<<",\"diagnostic_rejected\":"<<(owners?owners->diagnostic_rejected:0)<<",\"diagnostic_expired\":"<<(owners?owners->diagnostic_expired:0)<<",\"diagnostic_late\":"<<(owners?owners->diagnostic_late:0)<<",\"state_violations\":"<<(owners?owners->state_violations:0)<<",\"pre_init_rejected\":"<<(owners?owners->pre_init_rejected:0)<<",\"epoch\":"<<(owners?owners->epoch:0)<<",\"release_ack_mask\":"<<(owners?owners->release_acks:0)<<",\"armed_ns\":"<<(owners?owners->armed_ns:0)
        <<",\"protected_ns\":"<<(owners?owners->protected_ns:0)<<",\"selected_ns\":"<<(owners?owners->selected_ns:0)<<",\"last_lease_expiry\":"<<(owners?(front?owners->remote_zone->last_lease_expiry:owners->last_lease_expiry):0)
        <<",\"batches\":"<<(owners?owners->port.completed_batches():0)<<",\"actual_count\":"<<(owners?owners->actual_count:0)<<",\"result_count\":"<<(owners?owners->result_count:0)
        <<",\"steering_applied\":"<<(owners && front?owners->leaf[0]->received_commands():0)<<",\"brake_applied\":"<<(owners && front?owners->leaf[1]->received_commands():0)
        <<",\"expired_rejected\":"<<(owners && front?owners->remote_zone->expired:0)<<",\"rx_highwater\":"<<net.highwater[0]<<",\"authority_highwater\":"<<net.highwater[1]<<",\"max_owner_poll_gap_ns\":"<<(owners?owners->max_poll_gap:0)<<",\"stale_authority_rejected\":"<<net.stale_authority_rejected<<",\"binding_rejected\":"<<net.rejected<<",\"send_returned\":"<<net.send_returned
        <<",\"overflow\":"<<(net.overflow?"true":"false")<<",\"error\":\""<<error<<"\"}\n";
    return pass?0:1;
}
