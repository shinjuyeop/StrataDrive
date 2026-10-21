// Opt-in two-node component fixture. No global SessionCoordinator / RunLease.
#include <vsomeip/vsomeip.hpp>
#include "owner_wire.hpp"
#include "run_lease_gate.hpp"
#include "front_startup_control.hpp"
#include "allocation_fixture.hpp"
#include <array>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <deque>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <mutex>
#include <thread>

namespace fs = std::filesystem;
using namespace stratadrive;
using namespace std::chrono_literals;
namespace {
constexpr vsomeip::service_t service=0x5344;
constexpr vsomeip::instance_t instance=1;
constexpr vsomeip::method_t ready_method=0x10,work_method=0x20,status_method=0x30;
constexpr std::uint64_t domain=0x53444d4f4e4fULL,ms=1000000;
std::uint64_t now() { return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
void require(bool value,const char* why) { if(!value) throw std::runtime_error(why); }
void mark(const fs::path& path) { std::ofstream(path)<<now()<<'\n'; }
template<class F> bool wait(F f,std::chrono::milliseconds budget) {
    const auto end=std::chrono::steady_clock::now()+budget;
    while(!f()) { if(std::chrono::steady_clock::now()>=end) return false; std::this_thread::sleep_for(1ms); }
    return true;
}
remote::OwnerPacket encode(const remote::OwnerPayload& payload,bool front=false) {
    auto p=remote::encode_owner_message({front?session::Role::FrontZone:session::Role::CentralIngress,
        front?session::Role::CentralIngress:session::Role::FrontZone,domain,payload});
    require(p.has_value(),"owner encode failed"); return *p;
}
bool route(const remote::OwnerMessage& m,bool front) {
    return m.clock_domain==domain && m.from==(front?session::Role::FrontZone:session::Role::CentralIngress) &&
        m.to==(front?session::Role::CentralIngress:session::Role::FrontZone);
}
struct Item { std::shared_ptr<vsomeip::message> request; remote::OwnerPacket packet; };
class Node {
public:
    explicit Node(bool server):app(vsomeip::runtime::get()->create_application(server?"front":"central")),server_(server) {}
    std::shared_ptr<vsomeip::application> app;
    std::mutex mutex;
    std::deque<Item> inbox;
    std::atomic<bool> available{false},overflow{false};
    std::atomic<unsigned> received{0},highwater{0};
    void start() {
        require(app->init(),"vsomeip init failed");
        app->register_state_handler([this](vsomeip::state_type_e s) {
            if(s==vsomeip::state_type_e::ST_REGISTERED) {
                if(server_) app->offer_service(service,instance,1,0);
                else app->request_service(service,instance,1,0);
            }
        });
        if(!server_) app->register_availability_handler(service,instance,[this](auto,auto,bool yes){available=yes;},1,0);
        app->register_message_handler(service,instance,vsomeip::ANY_METHOD,[this](const auto& message) {
            if(server_ && message->get_method()==ready_method) {
                const auto payload=message->get_payload();
                if(payload->get_length()==4 && payload->get_data()[0]==0x53 && payload->get_data()[3]==1) reply(message,nullptr,true);
                return;
            }
            Item item{message,{}};
            const auto p=message->get_payload();
            if(p->get_length()<=item.packet.bytes.size()) {
                item.packet.size=p->get_length();
                std::copy_n(p->get_data(),item.packet.size,item.packet.bytes.begin());
            }
            std::lock_guard<std::mutex> lock(mutex);
            ++received;
            if(inbox.size()==transport::kBudget) {
                overflow=true;
                // No owner object is touched on the SDK dispatcher thread.
                if(server_) reply(message,nullptr);
                return;
            }
            inbox.push_back(std::move(item));
            highwater=std::max(highwater.load(),static_cast<unsigned>(inbox.size()));
        });
        thread_=std::thread([this]{app->start();});
    }
    std::optional<Item> pop() {
        std::lock_guard<std::mutex> lock(mutex);
        if(inbox.empty()) return {};
        auto v=std::move(inbox.front()); inbox.pop_front(); return v;
    }
    void send(vsomeip::method_t method,const remote::OwnerPacket* packet=nullptr) {
        auto message=vsomeip::runtime::get()->create_request(true);
        message->set_service(service); message->set_instance(instance); message->set_method(method); message->set_interface_version(1);
        auto p=vsomeip::runtime::get()->create_payload();
        const std::array<std::uint8_t,4> hello{0x53,0x44,0,1};
        if(packet) p->set_data(packet->bytes.data(),packet->size); else p->set_data(hello.data(),hello.size());
        message->set_payload(p); app->send(message);
    }
    void reply(const std::shared_ptr<vsomeip::message>& request,const remote::OwnerPacket* packet,bool ready=false) {
        auto message=vsomeip::runtime::get()->create_response(request);
        auto p=vsomeip::runtime::get()->create_payload();
        const std::array<std::uint8_t,4> hello{0x53,0x44,0,1};
        if(packet) p->set_data(packet->bytes.data(),packet->size); else if(ready) p->set_data(hello.data(),hello.size());
        message->set_payload(p); app->send(message);
    }
    std::optional<Item> response() {
        std::optional<Item> v;
        wait([&]{v=pop();return v.has_value();},1000ms); return v;
    }
    void stop() {
        if(!thread_.joinable()) return;
        if(server_) app->stop_offer_service(service,instance,1,0); else app->release_service(service,instance);
        app->clear_all_handler(); app->stop(); thread_.join();
    }
    ~Node() { stop(); }
private:
    bool server_;
    std::thread thread_;
};

// Same component fixture as CommandGateway/FrontStartup unit tests. The launcher
// supplies a local grant; no received SOME/IP packet can INIT, Release or arm it.
class Front final:public zone::GatewayPort {
public:
    vecu::SteeringActuator steering{{-.5,.5,-.3,.3,0,1,50*ms}};
    vecu::BrakeActuator brake{{2000000,1500000,0,5000000,10000000,1000000,50*ms}};
    simulation::FrontStartupControl local{steering,brake};
    zone::CommandGateway gateway{zone::ZoneScope::Front,*this};
    std::optional<remote::OwnerPacket> status;
    unsigned frames=0,accepted=0,rejected=0,protection_calls=0;
    std::uint64_t token=0,next_tick=0,write_deadline=0;
    std::uint32_t epoch,sequence=0;
    bool armed=false;
    explicit Front(std::uint32_t e):epoch(e) {
        const auto t=now();
        require(steering.start_session({e,7,t},ActuatorCommandStartup::NonDriving),"steering INIT");
        require(brake.start_session({e,7,t},ActuatorCommandStartup::NonDriving),"brake INIT");
        require(gateway.start_session(e,t),"gateway INIT");
    }
    std::uint64_t now_ns() noexcept override { return now(); }
    bool protect(zone::ZoneScope s,zone::ProtectionCause c,std::uint64_t t) noexcept override {
        ++protection_calls; return local.protect(s,c,t);
    }
    bool send(const zone::CommandFrame& f,const central::CommandContext& ctx) noexcept override {
        const auto t=now(); if(t>=std::min(ctx.expires_at_ns,write_deadline)) return false;
        bool ok=false;
        if(const auto* s=std::get_if<can::SteeringFrame>(&f)) ok=steering.receive(*s,t).decision==can::ActuatorReceiveDecision::Accepted;
        if(const auto* b=std::get_if<can::BrakeFrame>(&f)) ok=brake.receive(*b,t).decision==can::ActuatorReceiveDecision::Accepted;
        if(ok) ++frames;
        return ok;
    }
    void tick() {
        if(now()<next_tick) return;
        gateway.poll();
        const auto t=now(); next_tick=t+10*ms;
        if(steering.prepare(t)) {
            auto f=steering.complete(steering::AngleMeasurement{7,sequence,t,0},t);
            if(f) status=encode(transport::Feedback{*f},true);
        }
        if(brake.prepare(t)) brake.complete(brake::PressureMeasurement{7,sequence,t,0},t);
        ++sequence;
        if(!armed && status) {
            require(local.arm_commands(gateway,{epoch,now()}),"local component fixture grant");
            armed=true;
        }
    }
    remote::OwnerPacket handle(const transport::ZoneRequest& r) {
        bool ok=false; unsigned sent=0; const auto t=now();
        write_deadline=transport::delivery_deadline(r.sent_ns,r.deadline_ns);
        const remote::ClockAgreement clock{domain,domain,0,0,true};
        if(r.epoch==epoch && r.token>token) {
            if(!remote::source_and_expiry_current(r.sent_ns,transport::delivery_deadline(r.sent_ns,r.deadline_ns),t,20*ms,clock)) {
                gateway.request_protection();
            } else {
                token=r.token;
                if(const auto* parent=std::get_if<central::VehicleRequest>(&r.work)) {
                    const auto result=gateway.authorize_request(*parent);
                    ok=result==zone::AdmissionResult::Accepted || result==zone::AdmissionResult::Unchanged;
                } else if(const auto* commands=std::get_if<central::ScopedCommands>(&r.work)) {
                    if(gateway.enqueue(*commands)==zone::AdmissionResult::Accepted) {
                        const auto result=gateway.dispatch(); sent=result.frames_enqueued; ok=sent==2 && !result.partial_front;
                    }
                }
            }
        }
        if(ok) ++accepted; else ++rejected;
        return encode(transport::TxResult{r.epoch,r.token,now(),transport::operation(r.work),ok,sent},true);
    }
};

central::AllocatedCommands commands(std::uint32_t epoch,std::uint32_t sequence,std::uint64_t t) {
    central::AllocatedCommands c;
    c.parent={epoch,sequence,t,t+60*ms,0,0,0,false};
    c.oldest_input_time_ns=t; c.expires_at_ns=t+30*ms;
    const can::ActuatorMetadata m{sequence,epoch,t,sequence,can::ActuatorLocalState::Normal,can::ActuatorOrigin::NormalPath};
    static_cast<can::ActuatorMetadata&>(c.brake)=m; static_cast<can::ActuatorMetadata&>(c.drive)=m;
    c.steering.sequence=sequence; c.steering.epoch=epoch; c.steering.source_time_ns=t; c.steering.causal_sequence=sequence;
    c.steering.local_state=m.local_state; c.steering.origin=m.origin;
    c.steering.angle_rad=0; c.brake.pressure_pa=0; c.drive.torque_nm=0; return c;
}
struct Client {
    Node& node; unsigned applied=0,rejected=0,statuses=0;
    std::uint32_t expected_epoch;
    std::ofstream trace;
    explicit Client(Node& n,const fs::path& folder,std::uint32_t epoch):node(n),expected_epoch(epoch),trace(folder/("transactions-"+std::to_string(epoch)+".csv")) {
        trace<<"epoch,token,operation,sent,deadline,received,result_source,accepted,frames\n";
    }
    void transact(const transport::ZoneRequest& request,bool expected,const remote::OwnerPacket* override_packet=nullptr,bool malformed=false) {
        const auto packet=encode(request); node.send(work_method,override_packet?override_packet:&packet);
        const auto response=node.response(); require(response.has_value(),"missing processing result");
        require(response->request->get_method()==work_method,"wrong result method");
        const auto t=now(); const auto m=remote::decode_owner_message(response->packet.bytes.data(),response->packet.size);
        if(malformed) {require(!m,"malformed packet accepted");++rejected;return;}
        require(m && route(*m,true),"result CRC/route/clock");
        const auto* result=std::get_if<transport::TxResult>(&m->payload);
        require(result && result->epoch==request.epoch && result->token==request.token && result->operation==transport::operation(request.work),"result correlation");
        trace<<request.epoch<<','<<request.token<<','<<static_cast<int>(result->operation)<<','<<request.sent_ns<<','<<request.deadline_ns<<','<<t<<','<<result->source_ns<<','<<result->accepted<<','<<result->frames<<'\n';
        require(result->accepted==expected,"unexpected processing verdict");
        if(expected) {
            require(t<transport::delivery_deadline(request.sent_ns,request.deadline_ns) && result->source_ns>=request.sent_ns && result->source_ns<=t,"late normal result");
            if(result->operation==transport::Operation::Commands) {require(result->frames==2,"CAN pair not processed");++applied;}
        } else ++rejected;
    }
    void status() {
        node.send(status_method); const auto response=node.response(); require(response.has_value(),"missing status");
        require(response->request->get_method()==status_method,"wrong status method");
        auto m=remote::decode_owner_message(response->packet.bytes.data(),response->packet.size);
        require(m && route(*m,true),"status CRC/route/clock");
        auto* feedback=std::get_if<transport::Feedback>(&m->payload); require(feedback,"not canonical feedback");
        auto* frame=std::get_if<can::SteeringFrame>(feedback); require(frame,"not actual CAN feedback");
        auto decoded=can::decode_steering_frame(*frame);
        require(decoded && decoded->epoch==expected_epoch && decoded->kind==can::SteeringFrameKind::Actual && now()-decoded->source_time_ns<20*ms,"stale/invalid Actual");
        ++statuses;
    }
};

transport::ZoneRequest normal_cycles(Client& client,std::uint32_t epoch,std::uint64_t& token) {
    const auto begin=now();central::ControlAllocation allocator;
    require(allocator.start_session(epoch,begin),"allocator local INIT");
    auto next=now();transport::ZoneRequest last{};
    for(unsigned cycle=0;cycle<8;++cycle) {
        std::this_thread::sleep_until(std::chrono::steady_clock::time_point(std::chrono::nanoseconds(next)));
        const auto t=now();next=t+20*ms;
        const auto root=commands(epoch,cycle,t).parent;
        require(allocator.receive_request(root,t)==central::AllocationReceiveDecision::Accepted,"allocator request rejected");
        const auto output=allocator.tick(allocation_fixture(epoch,cycle,begin,t),t);
        require(output.has_value(),"allocator refused fixture inputs");const auto& c=*output;
        last={epoch,token++,c.parent.source_time_ns,c.parent.source_time_ns+20*ms,c.parent};client.transact(last,true);
        last={epoch,token++,c.parent.source_time_ns,c.parent.source_time_ns+20*ms,central::front_commands(c)};client.transact(last,true);client.status();
    }
    return last;
}
} // namespace

int main(int argc,char** argv) {
    if(argc!=5) return 2;
    const bool server=std::string(argv[1])=="front";
    const fs::path folder=argv[2]; const std::string test=argv[3]; const auto epoch=static_cast<std::uint32_t>(std::stoul(argv[4]));
    const auto prefix=folder/(std::string(argv[1])+"-"+std::to_string(epoch));
    Node node(server); bool pass=false,stopped=false; unsigned applied=0,rejected=0,statuses=0,frames=0,protection=0,fault_protection=0;
    unsigned busy_sent=0,busy_rejected=0,busy_expired=0,busy_peak=0;
    std::string error;
    try {
        node.start(); mark(prefix.string()+".started");
        if(server) {
            std::unique_ptr<Front> front; std::uint64_t hold_until=0;
            const auto end=now()+10'000*ms;
            while(!fs::exists(folder/("stop-"+std::to_string(epoch)))) {
                require(now()<end,"Front supervisor stop missing");
                if(!front && fs::exists(folder/("grant-"+std::to_string(epoch)))) {
                    front=std::make_unique<Front>(epoch);
                }
                if(front) {
                    front->tick();
                    if(front->armed && !fs::exists(prefix.string()+".fixture")) mark(prefix.string()+".fixture");
                    if(node.overflow) front->gateway.request_protection();
                    if((test=="delay" || test=="overflow") && hold_until==0 && node.received>0) hold_until=now()+(test=="delay"?30:120)*ms;
                }
                if(front && (!hold_until || now()>=hold_until)) for(unsigned i=0;i<8;++i) {
                    const auto item=node.pop(); if(!item) break;
                    if(item->request->get_method()==status_method) {node.reply(item->request,front->status?&*front->status:nullptr);continue;}
                    auto m=remote::decode_owner_message(item->packet.bytes.data(),item->packet.size);
                    if(!m || !route(*m,false) || !std::holds_alternative<transport::ZoneRequest>(m->payload)) {++front->rejected;node.reply(item->request,nullptr);continue;}
                    auto result=front->handle(std::get<transport::ZoneRequest>(m->payload)); node.reply(item->request,&result);
                }
                std::this_thread::sleep_for(1ms);
            }
            if(front) {
                frames=front->frames; rejected=front->rejected; applied=front->accepted;
                // Orderly stop always selects local protection before SDK teardown.
                fault_protection=front->protection_calls;
                front->gateway.request_protection(); protection=front->protection_calls;
                require(front->gateway.poll().safety.handoff_accepted,"local protection not selected");
            }
            pass=true;
        } else {
            const bool found=wait([&]{return node.available.load();},3000ms);
            if(test=="ready-timeout") {require(!found,"unexpected peer in timeout case");pass=true;}
            else {
                require(found,"service discovery timeout"); node.send(ready_method); auto hello=node.response();
                require(hello && hello->packet.size==4 && hello->packet.bytes[0]==0x53 && hello->packet.bytes[3]==1,"bidirectional readiness failed");
                mark(prefix.string()+".ready");
                require(wait([&]{return fs::exists(folder/("front-"+std::to_string(epoch)+".fixture"));},3000ms),"local fixture grant missing");
                Client client(node,folder,epoch); std::uint64_t token=1; transport::ZoneRequest last{};
                if(test=="delay") {
                    auto c=commands(epoch,0,now()); last={epoch,token++,c.parent.source_time_ns,c.parent.source_time_ns+20*ms,c.parent};
                    client.transact(last,false);
                } else if(test=="overflow") {
                    for(unsigned i=0;i<9;++i) {auto c=commands(epoch,i,now()); auto p=encode(transport::ZoneRequest{epoch,token++,c.parent.source_time_ns,c.parent.source_time_ns+20*ms,c.parent});node.send(work_method,&p);}
                    for(unsigned i=0;i<9;++i) {
                        auto r=node.response();require(r.has_value(),"overflow response missing");auto m=remote::decode_owner_message(r->packet.bytes.data(),r->packet.size);
                        if(m) {auto* result=std::get_if<transport::TxResult>(&m->payload);require(result && !result->accepted,"overflow accepted command");}
                        ++client.rejected;
                    }
                } else {
                    if(test=="restart" && epoch==43) {
                        remote::OwnerPacket old_packet;
                        std::ifstream old_file(folder/"epoch42.packet",std::ios::binary);
                        old_file.read(reinterpret_cast<char*>(old_packet.bytes.data()),old_packet.bytes.size());old_packet.size=old_file.gcount();
                        const auto old=remote::decode_owner_message(old_packet.bytes.data(),old_packet.size);
                        require(old && std::holds_alternative<transport::ZoneRequest>(old->payload),"preserved prior-session bytes missing");
                        client.transact(std::get<transport::ZoneRequest>(old->payload),false,&old_packet);
                    }
                    last=normal_cycles(client,epoch,token);
                    if((test=="restart" || test=="restart-live") && epoch==42) {
                        const auto p=encode(last);std::ofstream saved(folder/"epoch42.packet",std::ios::binary);
                        saved.write(reinterpret_cast<const char*>(p.bytes.data()),p.size);
                    }
                    if(test=="restart-live") {
                        mark(folder/"restart-request");
                        require(wait([&]{return !node.available.load();},3000ms),"live peer disappearance not observed");
                        mark(folder/"central-observed-down");
                        require(wait([&]{return fs::exists(folder/"rejoin-43") && node.available.load();},3000ms),"new peer/local rejoin grant missing");
                        node.send(ready_method);const auto ready=node.response();
                        require(ready && ready->packet.size==4 && ready->packet.bytes[0]==0x53 && ready->packet.bytes[3]==1,"new peer bidirectional readiness");
                        mark(folder/"central-43.ready");
                        require(wait([&]{return fs::exists(folder/"front-43.fixture");},3000ms),"new local fixture grant missing");
                        Client rejoined(node,folder,43);
                        // Same immutable old packet, same surviving SDK application.
                        rejoined.transact(last,false);
                        std::uint64_t new_token=1;normal_cycles(rejoined,43,new_token);
                        client.applied+=rejoined.applied;client.rejected+=rejoined.rejected;client.statuses+=rejoined.statuses;
                        mark(folder/"live-rejoined");
                    }
                    if(test=="invalid") {
                        client.transact(last,false); // identical bytes, duplicate token
                        auto c=commands(epoch-1,10,now());auto old=transport::ZoneRequest{epoch-1,token++,c.parent.source_time_ns,c.parent.source_time_ns+20*ms,c.parent};client.transact(old,false);
                        auto bad=encode(last); bad.bytes[bad.size-1]^=1;client.transact(last,false,&bad,true);
                        auto wrong=remote::encode_owner_message({session::Role::RearZone,session::Role::FrontZone,domain,last});client.transact(last,false,&*wrong,true);
                        wrong=remote::encode_owner_message({session::Role::CentralIngress,session::Role::FrontZone,domain+1,last});client.transact(last,false,&*wrong,true);
                        c=commands(epoch,11,now()-30*ms);last={epoch,token++,c.parent.source_time_ns,c.parent.source_time_ns+20*ms,c.parent};client.transact(last,false);
                    }
                    if(test=="close-busy") {
                        // An uncooperative peer is still bounded: at most eight
                        // outstanding requests. A lost result closes this lane;
                        // continuing blind sends after disconnect hid send loss.
                        std::deque<std::uint64_t> pending;
                        bool failed=false;
                        const auto until=now()+250*ms;
                        while(now()<until) {
                            if(const auto reply=node.pop()) {
                                const auto m=remote::decode_owner_message(reply->packet.bytes.data(),reply->packet.size);
                                require(m && route(*m,true),"busy response CRC/route/clock");
                                const auto* r=std::get_if<transport::TxResult>(&m->payload);
                                require(r && r->epoch==last.epoch && r->token==last.token && r->operation==transport::operation(last.work) && !r->accepted,"busy duplicate not rejected");
                                require(!pending.empty(),"unexpected busy result");pending.pop_front();++busy_rejected;
                                if(busy_rejected==1) mark(folder/"busy");
                            }
                            while(!pending.empty() && now()-pending.front()>=20*ms) {
                                pending.pop_front();++busy_expired;failed=true;
                            }
                            if(!failed && pending.size()<transport::kBudget) {
                                auto p=encode(last);node.send(work_method,&p);pending.push_back(now());++busy_sent;
                                busy_peak=std::max(busy_peak,static_cast<unsigned>(pending.size()));
                            }
                            std::this_thread::sleep_for(1ms);
                        }
                        require(pending.empty() && busy_sent==busy_rejected+busy_expired,"busy request bookkeeping");
                    }
                }
                applied=client.applied;rejected=client.rejected;statuses=client.statuses;pass=true;
            }
        }
    } catch(const std::exception& e) {error=e.what();}
    const auto closing=now();mark(prefix.string()+".closing");node.stop();stopped=true;
    const auto stop_ns=now()-closing;
    std::ofstream summary(prefix.string()+".json");
    summary<<"{\"pass\":"<<(pass?"true":"false")<<",\"orderly_stop\":"<<(stopped?"true":"false")
      <<",\"stop_ns\":"<<stop_ns<<",\"applied\":"<<applied<<",\"rejected\":"<<rejected<<",\"statuses\":"<<statuses
      <<",\"frames\":"<<frames<<",\"protection_calls\":"<<protection<<",\"fault_protection_calls\":"<<fault_protection<<",\"overflow\":"<<(node.overflow?"true":"false")
      <<",\"busy_sent\":"<<busy_sent<<",\"busy_rejected\":"<<busy_rejected<<",\"busy_expired\":"<<busy_expired<<",\"busy_peak\":"<<busy_peak
      <<",\"highwater\":"<<node.highwater<<",\"control_gate_open\":false,\"error\":\""<<error<<"\"}\n";
    return pass?0:1;
}
