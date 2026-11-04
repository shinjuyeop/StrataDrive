#include "fixture_placement.hpp"
#include "native_continuity_service.hpp"
#include "native_diagnostic_routes.hpp"
#include "native_execution_watch.hpp"
#include "someip/owner_transport.hpp"
#include <algorithm>
#include <fstream>
#include <iomanip>
#include <poll.h>
#include <sstream>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <unistd.h>

namespace stratadrive::someip::test {
namespace {
namespace d=diagnostics;namespace fs=std::filesystem;
std::uint64_t wall(){return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());}
void require(bool good,const char* reason){if(!good)throw std::runtime_error(reason);}
std::string hex(const std::vector<std::uint8_t>& b){std::ostringstream s;for(auto v:b)s<<std::hex<<std::setw(2)<<std::setfill('0')<<static_cast<unsigned>(v);return s.str();}
struct Descriptor {int fd{-1};~Descriptor(){if(fd>=0)close(fd);}};
struct FrozenRow {std::uint64_t ns,epoch,stream,producer,committed,acknowledged,pending,dropped,first_lost,identity_error;};
std::vector<FrozenRow> report(const fs::path& path){
    std::ifstream input(path);std::string line;require(static_cast<bool>(std::getline(input,line)),"freeze report missing");
    require(line=="ns,epoch,stream,producer,committed,acknowledged,pending,dropped,first_lost,identity_error","freeze report schema");
    std::vector<FrozenRow> result;
    while(std::getline(input,line)){std::replace(line.begin(),line.end(),',',' ');std::istringstream row(line);FrozenRow value{};
        require(static_cast<bool>(row>>value.ns>>value.epoch>>value.stream>>value.producer>>value.committed>>value.acknowledged>>value.pending>>value.dropped>>value.first_lost>>value.identity_error),"freeze report row");
        row>>std::ws;require(row.eof(),"freeze report trailing data");result.push_back(value);require(result.size()<=9,"freeze report bound");}
    return result;
}
class Capture final:public d::ContinuityCapture {
public:
    runtime::LatestSnapshot<d::ServiceEvidence>& latest;std::ofstream samples;
    d::Event global{};std::vector<d::StreamState> states;std::vector<std::unique_ptr<d::FileJournal>> owned;
    bool held{false};std::uint64_t after{0};
    Capture(runtime::LatestSnapshot<d::ServiceEvidence>& input,const fs::path& folder):latest(input),samples(folder/"service-samples.csv"){
        samples<<"now,owner_capture,enable,wheel,drive,brake,wheel_rad_s,torque_nm,pressure_pa,valid,inhibited\n";samples<<std::setprecision(17);
    }
    struct Cut final:d::FrozenContinuity {
        Capture& c;explicit Cut(Capture& owner):c(owner){c.held=true;}~Cut() override{c.held=false;}
        const d::Event& global() const noexcept override{return c.global;}
        const std::vector<d::StreamState>& streams() const noexcept override{return c.states;}
        d::ServiceEvidence sample() override {
            auto input=c.latest.read();require(input.has_value(),"current owner Actual missing");auto evidence=*input;
            // Independent current service clock: a stalled owner snapshot cannot
            // keep old Actuals fresh by retaining its earlier polling time.
            const auto captured=evidence.now.ns;evidence.now.ns=wall();
            if(evidence.wheel.ns<c.after || evidence.drive.ns<c.after || evidence.brake.ns<c.after)evidence.current_streams_valid=false;
            c.samples<<evidence.now.ns<<','<<captured<<','<<evidence.enable.ns<<','<<evidence.wheel.ns<<','<<evidence.drive.ns<<','<<evidence.brake.ns<<','<<evidence.wheel_rad_s<<','<<evidence.torque_nm<<','<<evidence.pressure_pa<<','<<evidence.current_streams_valid<<','<<evidence.normal_dispatch_inhibited<<'\n';c.samples.flush();
            require(c.samples.good(),"service sample evidence write");return evidence;
        }
    };
    std::unique_ptr<d::FrozenContinuity> acquire() override {if(held)return {};return std::make_unique<Cut>(*this);}
};
}
NativeContinuityService::NativeContinuityService(const fs::path& folder):folder_(folder){}
NativeContinuityService::~NativeContinuityService(){stop_=true;if(worker_.joinable())worker_.join();}
void NativeContinuityService::start(){require(!worker_.joinable(),"service already started");worker_=std::thread([this]{work();done_.store(true,std::memory_order_release);});}
void NativeContinuityService::work(){
    std::string error;std::uint64_t base=0;std::string socket_path;
    try {
        simulation::NativeExecutionWatch::configure_thread(stratadrive::someip::test::auxiliary_io_cpu(),0);simulation::runtime_support::ThreadInfo placement;placement.capture();std::ofstream where(folder_/"service-writer.json");placement.write_json(where);
        const auto* configured=std::getenv("STRATADRIVE_DIAGNOSTIC_STORE_ROOT");require(configured,"service storage provision missing");const fs::path storage(configured);const auto central=storage/"central";
        Capture capture(current_,folder_);std::vector<d::StreamBinding> bindings;
        const auto contexts=report(central/"central-2.freeze.csv");require(contexts.size()==2,"collector freeze coverage");
        for(unsigned z=0;z<2;++z){require(contexts[z].epoch==3 && contexts[z].stream==8101+z && contexts[z].committed==3 && contexts[z].acknowledged==3,"collector context ACK cut");capture.after=std::max(capture.after,contexts[z].ns);}
        std::vector<FrozenRow> rows;
        for(const auto* role:{"front","rear"}){auto r=report(storage/role/(std::string(role)+"-1.freeze.csv"));rows.insert(rows.end(),r.begin(),r.end());}
        require(rows.size()==9,"whole native source freeze coverage");
        for(unsigned i=0;i<9;++i){const auto& source=diagnostic_sources[i];const auto found=std::find_if(rows.begin(),rows.end(),[&](const FrozenRow& r){return r.stream==8200+i && r.producer==source.producer;});
            require(found!=rows.end() && found->epoch==3 && !found->pending && !found->dropped && !found->first_lost && !found->identity_error,"source freeze/queue health");
            require(found->ns && found->ns<=wall(),"original freeze report clock");capture.after=std::max(capture.after,found->ns);
            const auto role=source.ecu==Ecu::Front?"front":"rear";const auto name="source-"+std::to_string(source.producer);
            auto original=std::make_unique<d::FileJournal>((storage/role/name).string());auto replica=std::make_unique<d::FileJournal>((central/(name+"-2")).string());
            require(found->committed==original->committed().size(),"actual frozen source watermark");
            capture.states.push_back({original.get(),replica.get(),found->acknowledged,found->pending,{found->dropped,found->first_lost,found->identity_error!=0}});
            capture.owned.push_back(std::move(original));capture.owned.push_back(std::move(replica));bindings.push_back({8200+i,source.producer});
        }
        d::FileJournal merged((central/"merged-2").string()),local((central/"service-case").string());d::Recorder writer(local);
        require(local.committed().empty(),"fresh separate service journal required");
        for(const auto& entry:merged.committed()){const auto& event=std::get<d::Event>(entry);require(writer.record(event).durable,"frozen merged original import");if(event.kind==d::Kind::Session)capture.global=event;}
        base=local.committed().size();require(capture.global.session.epoch==3,"fresh actual service epoch");
        d::ServicePermit permit;permit.actor={diagnostic_run,64,d::Domain::Monotonic,kDomain,1};permit.session=capture.global.session;permit.incident={diagnostic_run,(1ULL<<32)|8,1};
        const auto* pid=std::getenv("STRATADRIVE_SERVICE_PID");const auto* uid=std::getenv("STRATADRIVE_SERVICE_UID");const auto* token=std::getenv("STRATADRIVE_SERVICE_CAPABILITY");require(pid && uid && token,"service principal provision missing");
        permit.pid=std::stoi(pid);permit.uid=static_cast<std::uint32_t>(std::stoul(uid));const std::string capability(token);require(capability.size()==32,"service capability length");
        for(unsigned i=0;i<16;++i){const auto byte=capability.substr(2*i,2);require(byte.find_first_not_of("0123456789abcdef")==std::string::npos,"service capability encoding");permit.capability[i]=static_cast<std::uint8_t>(std::stoul(byte,nullptr,16));}
        d::ContinuityService service(writer,bindings,permit,capture);
        const auto* incident=writer.ledger().find({d::Code::RecordingGap,static_cast<unsigned>(d::Component::Coordinator),10,8});require(incident,"continuity record missing");
        Descriptor listener{socket(AF_UNIX,SOCK_SEQPACKET|SOCK_CLOEXEC|SOCK_NONBLOCK,0)};sockaddr_un address{};address.sun_family=AF_UNIX;const auto path=(storage/"service.sock").string();require(path.size()<sizeof(address.sun_path),"service socket path bound");std::copy(path.begin(),path.end(),address.sun_path);
        require(listener.fd>=0 && !bind(listener.fd,reinterpret_cast<sockaddr*>(&address),sizeof(address)),"private service bind");socket_path=path;
        require(!chmod(path.c_str(),0600) && !listen(listener.fd,4),"private service listener");
        const auto fresh_deadline=wall()+200000000ULL;bool fresh=false;
        while(!stop_ && wall()<fresh_deadline){if(const auto value=current_.read()){auto e=*value;e.now.ns=wall();fresh=d::stationary_evidence(e) && e.wheel.ns>=capture.after && e.drive.ns>=capture.after && e.brake.ns>=capture.after;if(fresh)break;}std::this_thread::sleep_for(std::chrono::milliseconds(1));}
        require(fresh,"physical Actual after whole frozen cut missing");
        {std::ofstream ready(folder_/"service-ready.tmp");ready<<"{\"socket\":"<<std::quoted(path)<<",\"revision\":"<<incident->revision<<",\"epoch\":3,\"base\":"<<base<<",\"pid\":"<<getpid()<<",\"authorized_pid\":"<<permit.pid<<",\"uid\":"<<permit.uid<<"}\n";ready.flush();require(ready.good(),"service ready metadata");}
        fs::rename(folder_/"service-ready.tmp",folder_/"service-ready.json");
        std::ofstream requests(folder_/"service-requests.csv");requests<<"ns,peer_pid,peer_uid,request,response\n";
        const auto deadline=wall()+2000000000ULL;unsigned count=0;
        while(!stop_ && wall()<deadline && count<16){pollfd poller{listener.fd,POLLIN,0};const auto ready=poll(&poller,1,1);require(ready>=0,"service accept poll");if(!ready)continue;
            Descriptor peer{accept4(listener.fd,nullptr,nullptr,SOCK_CLOEXEC|SOCK_NONBLOCK)};if(peer.fd<0)continue;pollfd packet{peer.fd,POLLIN,0};require(poll(&packet,1,100)>0,"bounded service request readiness");
            std::vector<std::uint8_t> bytes(77);const auto n=recv(peer.fd,bytes.data(),bytes.size(),MSG_PEEK|MSG_TRUNC|MSG_DONTWAIT);require(n>=0 && n<=77,"service request audit bound");bytes.resize(static_cast<std::size_t>(n));
            ucred principal{};socklen_t length=sizeof(principal);require(!getsockopt(peer.fd,SOL_SOCKET,SO_PEERCRED,&principal,&length),"kernel peer audit");const auto reply=service.serve(peer.fd);++count;
            requests<<wall()<<','<<principal.pid<<','<<principal.uid<<','<<hex(bytes)<<','<<hex(d::encode_service_reply(reply))<<'\n';requests.flush();require(requests.good(),"service request evidence write");
            if(reply.status==d::ServiceStatus::Accepted && reply.stage==4){passed_=true;break;}
        }
        require(passed_,"service review/clear completion missing");require(local.committed().size()==base+4,"service exactly four durable transactions");
        const auto* final=writer.ledger().find({d::Code::RecordingGap,static_cast<unsigned>(d::Component::Coordinator),10,8});require(final && final->cleared && final->count==1,"service explicit continuity tombstone");
        std::ofstream result(folder_/"service-records.csv");result<<"code,component,monitor,subject,condition,count,generation,cleared\n";for(const auto& r:writer.ledger().records())result<<static_cast<unsigned>(r.key.code)<<','<<r.key.component<<','<<r.key.monitor<<','<<r.key.subject<<','<<static_cast<unsigned>(r.condition)<<','<<r.count<<','<<r.generation<<','<<r.cleared<<'\n';
    }catch(const std::exception& e){passed_=false;error=e.what();}
    if(!socket_path.empty())unlink(socket_path.c_str());
    std::ofstream result(folder_/"service-result.json");result<<"{\"pass\":"<<(passed_?"true":"false")<<",\"base\":"<<base<<",\"error\":"<<std::quoted(error)<<"}\n";
}
} // namespace stratadrive::someip::test
