#include "native_diagnostic_routes.hpp"
#include "someip/owner_transport.hpp"
#include "native_execution_watch.hpp"
#include <fstream>
#include <iomanip>

namespace stratadrive::someip::test {
namespace {
namespace d=diagnostics;
namespace fs=std::filesystem;
std::uint64_t wall() {return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());}
constexpr std::uint64_t ms=1000000;
void require(bool yes,const char* why) {if(!yes)throw std::runtime_error(why);}
fs::path home(const fs::path& folder,Ecu ecu) {
    const auto* configured=std::getenv("STRATADRIVE_DIAGNOSTIC_STORE_ROOT");
    return (configured?fs::path(configured):folder/"native-diagnostics")/(ecu==Ecu::Central?"central":ecu==Ecu::Front?"front":"rear");
}
std::string source_name(unsigned i) {return "source-"+std::to_string(diagnostic_sources[i].producer);}
d::ControlContext manifest(unsigned producer) {return {diagnostic_run,producer,d::Domain::Monotonic,kDomain,1};}
void rows(const fs::path& path,const d::Ledger& ledger) {
    std::ofstream out(path);out<<"code,component,monitor,subject,condition,count,generation,cleared\n";
    for(const auto& r:ledger.records())out<<static_cast<unsigned>(r.key.code)<<','<<r.key.component<<','<<r.key.monitor<<','<<r.key.subject<<','<<static_cast<unsigned>(r.condition)<<','<<r.count<<','<<r.generation<<','<<r.cleared<<'\n';
}
}
NativeDiagnosticRoutes::Source::Source(const DiagnosticSource& s):queue(diagnostic_run,s.producer) {
    if(s.native)native=std::make_unique<d::NativeDiagnostics>(queue,manifest(s.producer),s.component);
    else owner=std::make_unique<d::OwnerDiagnostics>(queue,manifest(s.producer),s.component);
}
void NativeDiagnosticRoutes::bootstrap(const fs::path& folder) {
    for(const auto ecu:{Ecu::Central,Ecu::Front,Ecu::Rear})fs::create_directories(home(folder,ecu));
    d::FileJournal::initialize((home(folder,Ecu::Central)/"merged").string(),8000,{},3);
    for(unsigned z=0;z<2;++z) {
        d::FileJournal::initialize((home(folder,Ecu::Central)/("context-"+std::to_string(z))).string(),8101+z,{},3);
        d::FileJournal::initialize((home(folder,z?Ecu::Rear:Ecu::Front)/"context").string(),8101+z,{},3);
    }
    for(unsigned i=0;i<diagnostic_sources.size();++i) {
        d::FileJournal::initialize((home(folder,diagnostic_sources[i].ecu)/source_name(i)).string(),8200+i,{},3);
        d::FileJournal::initialize((home(folder,Ecu::Central)/source_name(i)).string(),8200+i,{},3);
    }
}
NativeDiagnosticRoutes::NativeDiagnosticRoutes(Ecu ecu,const fs::path& folder,const std::string& tag):ecu_(ecu),folder_(home(folder,ecu)),tag_(tag) {
    for(unsigned i=0;i<diagnostic_sources.size();++i)if(ecu==Ecu::Central || diagnostic_sources[i].ecu==ecu) {
        source_channels_[i]=std::make_unique<diagnostic::Channel>(ecu==Ecu::Central?diagnostic::Role::Replica:diagnostic::Role::Publisher,8200+i,3,source_services(i));
        if(ecu!=Ecu::Central)sources_[i]=std::make_unique<Source>(diagnostic_sources[i]);
    }
    for(unsigned z=0;z<2;++z)if(ecu==Ecu::Central || ecu==(z?Ecu::Rear:Ecu::Front))
        context_channels_[z]=std::make_unique<diagnostic::Channel>(ecu==Ecu::Central?diagnostic::Role::Publisher:diagnostic::Role::Replica,8101+z,3,context_services(z));
}
NativeDiagnosticRoutes::~NativeDiagnosticRoutes() {finish();}
void NativeDiagnosticRoutes::configure(const std::shared_ptr<vsomeip::application>& app) {
    for(auto& c:context_channels_)if(c)c->configure(app);
    for(auto& c:source_channels_)if(c)c->configure(app);
}
void NativeDiagnosticRoutes::registered() {
    for(auto& c:context_channels_)if(c)c->registered();
    for(auto& c:source_channels_)if(c)c->registered();
}
void NativeDiagnosticRoutes::start(Transport& net) {
    require(!worker_.joinable(),"diagnostic worker already started");
    net.start([this](const auto& app){configure(app);},[this]{registered();});finished_=false;
    try {worker_=std::thread([this]{work();finished_.store(true,std::memory_order_release);});}
    catch(...) {finished_=true;throw;}
}
bool NativeDiagnosticRoutes::finish() {producing_=false;if(worker_.joinable())worker_.join();return passed_;}
void NativeDiagnosticRoutes::bind(Source& s,std::uint32_t epoch,std::uint64_t enable,const remote::RunLeaseEvidence& evidence,std::uint64_t captured) {
    if(!epoch || !evidence.accepted || evidence.accepted->plan.epoch!=epoch || s.epoch==epoch)return;
    s.evidence.publish({evidence,captured});s.epoch=epoch;
    if(s.owner)s.owner->start_session(epoch,enable);else s.native->start_session(epoch,enable);
}
void NativeDiagnosticRoutes::original(Source& s,unsigned monitor,const std::optional<NativeObservation>& fault,std::optional<std::uint64_t> selected) {
    if(!fault)return;
    const unsigned slot=monitor==7?1:0;const auto& old=s.last_original[slot];
    if(old && old->fault.epoch==fault->epoch && old->fault.observed_ns==fault->observed_ns && old->selected==selected)return;
    Source::Original value{*fault,monitor,selected};s.original[slot].publish(value);s.last_original[slot]=value;
}
void NativeDiagnosticRoutes::central(const session::SessionCoordinator& boot,const central::VehicleCoordinator& core,std::uint64_t now) {
    startup_.attempt(boot.plan());startup_.observe(boot.fault_observation(),boot.success_observation(),boot.run_enabled(),boot.run_enabled(),now);
    if(boot.run_enabled() && central_epoch_!=boot.plan().epoch) {
        central_epoch_=boot.plan().epoch;central_.start_session(central_epoch_,boot.plan().enable_ns,false);
    }
    central_.observe(core,now);
}
void NativeDiagnosticRoutes::zone(unsigned z,const zone::AsyncZoneOwner& actor,bool gate,const remote::RunLeaseEvidence& evidence,std::uint64_t now) {
    auto& owner=*sources_[z];auto& native=*sources_[z+5];bind(owner,actor.epoch(),actor.enable_ns(),evidence,now);bind(native,actor.epoch(),actor.enable_ns(),evidence,now);
    if(!owner.epoch || owner.epoch!=actor.epoch())return;
    owner.owner->zone(actor.feedback_monitor(),gate && owner.admitted.load()==actor.epoch(),actor.protection_ack_ns(),now);
    const auto& g=actor.command_gateway();
    original(native,6,g.fault_observation(),actor.protection_ack_ns());
    native.native->observe(d::NativeMonitor::CommandGateway,g.fault_observation(),std::nullopt,g.success_observation(),!actor.faulted(),gate && native.admitted.load()==actor.epoch(),now);
    native.native->selection(d::NativeMonitor::CommandGateway,actor.protection_ack_ns(),true);
    if(const auto* p=actor.power_gateway()) {
        original(native,7,p->fault_observation(),actor.protection_ack_ns());
        native.native->observe(d::NativeMonitor::RearPowerGateway,p->fault_observation(),std::nullopt,p->success_observation(),!actor.faulted(),gate && native.admitted.load()==actor.epoch(),now);
        native.native->selection(d::NativeMonitor::RearPowerGateway,actor.protection_ack_ns(),true);
    }
}
void NativeDiagnosticRoutes::leaf(unsigned i,const simulation::AsyncLeafOwner& actor,bool gate,const remote::RunLeaseEvidence& evidence,std::uint64_t now) {
    const unsigned slot=i<3?i+2:i+4;auto& s=*sources_[slot];bind(s,actor.epoch(),actor.enable_ns(),evidence,now);
    if(!s.epoch || s.epoch!=actor.epoch())return;
    const bool normal=gate && s.admitted.load()==actor.epoch();
    if(s.owner)s.owner->leaf(actor.expiry_observation(),actor.command_success_observation(),!actor.faulted(),normal,actor.protection_selected_ns(),now);
    else if(i==3) {
        const auto& b=*actor.bms_controller();const auto& decision=b.decision();
        original(s,8,b.fault_observation()?b.fault_observation():b.propagation_observation(),actor.protection_selected_ns());
        s.native->observe(d::NativeMonitor::Bms,b.fault_observation(),b.propagation_observation(),b.success_observation(),decision.fault==vecu::BmsControlFault::None && decision.state==vecu::BmsControlState::Active && !decision.pending_trips && decision.recovery_ready,normal,now);
        s.native->selection(d::NativeMonitor::Bms,actor.protection_selected_ns(),false);
    } else {
        const auto& p=*actor.power_controller();original(s,9,p.fault_observation()?p.fault_observation():p.propagation_observation(),actor.protection_selected_ns());
        s.native->observe(d::NativeMonitor::Power,p.fault_observation(),p.propagation_observation(),p.success_observation(),p.output().fault==vecu::PowerControlFault::None && p.output().phase==vecu::PowerPhase::Ready,normal,now);
        s.native->selection(d::NativeMonitor::Power,actor.protection_selected_ns(),false);
    }
}
void NativeDiagnosticRoutes::work() {
    std::string error;std::uint64_t events=0,duplicates=0,acked=0,buffered=0,stale_acks=0;bool dropped_ack=false;unsigned restarts=0;
    try {
        simulation::NativeExecutionWatch::configure_thread(15,0);
        simulation::runtime_support::ThreadInfo actual;actual.capture();std::ofstream placement(folder_/(tag_+".writer.json"));actual.write_json(placement);
        std::ofstream log(folder_/(tag_+".delivery.csv"));log<<"wall_ns,action,stream,ordinal,producer,sequence,kind,epoch\n";
        std::ofstream credits(folder_/(tag_+".credits.csv"));credits<<"producer,epoch,requested_ns,prepare_deadline_ns,enable_ns,commit_deadline_ns,lease_sequence,source_ns,expiry_ns,captured_ns\n";
        std::ofstream originals(folder_/(tag_+".originals.csv"));originals<<"producer,monitor,epoch,enable_ns,detected_ns,reason,propagation,violation_ns,selected_ns,root_sequence,root_source,root_expiry\n";
        std::array<unsigned,9> credit_epoch{};std::array<std::array<std::optional<Source::Original>,2>,9> raw_seen{};
        const auto note=[&](const char* action,const d::wire::Data& data) {log<<wall()<<','<<action<<','<<data.stream<<','<<data.sequence<<','<<data.event.id.producer<<','<<data.event.id.sequence<<','<<static_cast<unsigned>(data.event.kind)<<','<<data.event.session.epoch<<'\n';};
        std::ofstream restart_log(folder_/(tag_+".restart.csv"));restart_log<<"phase,stream,ordinal,bytes\n";
        const auto* restart_env=std::getenv("STRATADRIVE_DIAGNOSTIC_RESTART");
        const std::string ecu_name=ecu_==Ecu::Central?"central":ecu_==Ecu::Front?"front":"rear";
        const bool requested=restart_env && (restart_env==ecu_name || std::string(restart_env)=="all");
        std::uint64_t finish_deadline=0;
        for(;;) {
            std::array<std::unique_ptr<d::FileJournal>,9> stores;
            std::array<std::unique_ptr<d::ContextualOutbox>,9> outboxes;
            std::array<std::unique_ptr<d::FileJournal>,2> contexts;
            std::array<std::unique_ptr<d::Outbox>,2> context_out;
            std::array<std::unique_ptr<d::Inbox>,2> context_in;
            std::unique_ptr<d::FileJournal> merged;std::unique_ptr<d::MergedCollector> collector;
            if(ecu_==Ecu::Central) {merged=std::make_unique<d::FileJournal>((folder_/"merged").string());}
            for(unsigned i=0;i<9;++i)if(source_channels_[i]) {
                stores[i]=std::make_unique<d::FileJournal>((folder_/source_name(i)).string());
                if(!merged)outboxes[i]=std::make_unique<d::ContextualOutbox>(*stores[i],manifest(diagnostic_sources[i].producer),7);
            }
            for(unsigned z=0;z<2;++z)if(context_channels_[z]) {
                contexts[z]=std::make_unique<d::FileJournal>((folder_/(merged?"context-"+std::to_string(z):"context")).string());
                if(merged)context_out[z]=std::make_unique<d::Outbox>(*contexts[z]);else context_in[z]=std::make_unique<d::Inbox>(*contexts[z]);
            }
            if(merged) {std::vector<d::FileJournal*> replicas;for(const auto& store:stores)replicas.push_back(store.get());collector=std::make_unique<d::MergedCollector>(*merged,replicas);}
            const auto checkpoint=[&](const char* phase) {
                for(unsigned i=0;i<9;++i)if(stores[i]) {
                    unsigned ordinal=0;for(const auto& entry:stores[i]->committed()) {
                        restart_log<<phase<<','<<8200+i<<','<<++ordinal<<',';
                        for(const auto byte:d::encode(entry))restart_log<<std::hex<<std::setw(2)<<std::setfill('0')<<static_cast<unsigned>(byte);
                        restart_log<<std::dec<<'\n';
                    }
                    if(outboxes[i])rows(folder_/(std::string("restart-")+phase+"-"+source_name(i)+"-records.csv"),outboxes[i]->ledger());
                }
                if(collector)rows(folder_/(std::string("restart-")+phase+"-records.csv"),collector->ledger());
                restart_log.flush();
            };
            if(restarts)checkpoint("after");
            bool restarting=false;
            const auto commit=[&](const d::Event& e) {const auto r=collector->record(e);require(r.durable,"merged diagnostic commit");++events;};
            std::optional<d::Event> global;
            for(const auto& context:contexts)if(context)for(const auto& entry:context->committed()) {
                const auto& e=std::get<d::Event>(entry);require(e.kind==d::Kind::Session,"retained native context event kind");global=e;
            }
            std::array<std::uint64_t,9> last_send{};std::array<std::uint64_t,2> context_send{};
            const auto* delay_env=std::getenv("STRATADRIVE_DIAGNOSTIC_CONTEXT_DELAY_MS");const auto delay=delay_env?std::stoull(delay_env)*ms:0;
            std::uint64_t context_due=0;
            const auto transmit=[&](auto& out,diagnostic::Channel& channel,std::uint64_t& last,bool eligible=true) {
                while(auto bytes=channel.pop()) {const auto r=out.acknowledge(*bytes);require(r==d::Result::Accepted || r==d::Result::Duplicate || (restarts && r==d::Result::NotReady),"diagnostic ACK binding");if(r==d::Result::NotReady)++stale_acks;if(r==d::Result::Accepted){++acked;last=0;}}
                if(eligible && channel.available() && (!last || wall()-last>=100*ms))if(auto bytes=out.next())if(channel.send(*bytes)) {last=wall();note("send",std::get<d::wire::Data>(d::wire::decode(*bytes)));}
            };
            while(!finish_deadline || wall()<finish_deadline) {
                if(!producing_ && !finish_deadline)finish_deadline=wall()+2000*ms;
                std::size_t consumed=0;bool complete=true;
                if(collector) {
                    for(auto* queue:{&startup_queue_,&central_queue_}) {
                        const auto h=queue->health();require(!h.dropped && !h.identity_error,"Central diagnostic queue loss");d::Event e;
                        for(unsigned i=0;i<8 && queue->pop(e);++i) {
                            ++consumed;commit(e);note("local-commit",{8000,merged->committed().size(),3,e});
                            if(e.kind==d::Kind::Session) {global=e;context_due=wall()+delay;for(auto& out:context_out)require(out->record(e).durable,"context source commit");}
                        }
                    }
                    for(unsigned i=0;i<9;++i)while(auto bytes=source_channels_[i]->pop()) {
                        ++consumed;const auto data=std::get<d::wire::Data>(d::wire::decode(*bytes));const auto r=collector->receive(*bytes);require(r.ack.has_value(),"native replica commit");
                        ++events;note(r.result==d::Result::Duplicate?"duplicate":"replica-commit",data);if(r.result==d::Result::Duplicate)++duplicates;
                        if(std::getenv("STRATADRIVE_DIAGNOSTIC_DROP_ACK") && !dropped_ack && data.event.kind==d::Kind::Fault) {dropped_ack=true;note("omit-ack",data);}
                        else if(!source_channels_[i]->send(*r.ack))note("ack-unavailable",data); // sender retains/retries durable prefix
                    }
                    for(unsigned z=0;z<2;++z) {transmit(*context_out[z],*context_channels_[z],context_send[z],global && wall()>=context_due);complete=complete && context_out[z]->healthy() && context_out[z]->acknowledged()==contexts[z]->committed().size();}
                    complete=complete && global.has_value();for(const auto& store:stores)complete=complete && !store->committed().empty();
                } else {
                    const unsigned z=ecu_==Ecu::Rear?1:0;
                    while(auto bytes=context_channels_[z]->pop()) {
                        ++consumed;const auto data=std::get<d::wire::Data>(d::wire::decode(*bytes));require(data.event.kind==d::Kind::Session,"native context event kind");
                        const auto r=context_in[z]->receive(*bytes);require(r.ack.has_value(),"native global context commit");
                        global=data.event;note("context-commit",data);if(!context_channels_[z]->send(*r.ack))note("context-ack-unavailable",data);
                    }
                    for(unsigned i=0;i<9;++i)if(outboxes[i]) {
                        auto& out=*outboxes[i];auto& source=*sources_[i];
                        if(global && source.admitted.load()!=global->session.epoch)if(const auto evidence=source.evidence.read()) {
                            const auto& lease=*evidence->credit.accepted;const auto& p=lease.plan;
                            if(credit_epoch[i]!=p.epoch) {credit_epoch[i]=p.epoch;credits<<diagnostic_sources[i].producer<<','<<p.epoch<<','<<p.requested_ns<<','<<p.prepare_deadline_ns<<','<<p.enable_ns<<','<<p.commit_deadline_ns<<','<<lease.sequence<<','<<lease.source_time_ns<<','<<lease.expires_at_ns<<','<<evidence->captured_ns<<'\n';}
                            if(restarts) {const auto restored=out.restore(evidence->credit);require(restored==d::Result::Accepted || restored==d::Result::Duplicate || restored==d::Result::NotReady,"retained source context admission");}
                            const auto r=out.context(*global,evidence->credit);require(r==d::Result::Accepted || r==d::Result::Duplicate || r==d::Result::NotReady,"native context admission");
                            if(r!=d::Result::NotReady)source.admitted=global->session.epoch;
                        }
                        for(unsigned j=0;j<2;++j)if(const auto original=source.original[j].read()) {
                            const auto& old=raw_seen[i][j];const auto& o=original->fault;
                            if(!old || old->fault.epoch!=o.epoch || old->fault.observed_ns!=o.observed_ns || old->selected!=original->selected) {
                                originals<<diagnostic_sources[i].producer<<','<<original->monitor<<','<<o.epoch<<','<<o.enable_ns<<','<<o.observed_ns<<','<<o.reason<<','<<o.propagation<<','<<o.violation_ns.value_or(0)<<','<<original->selected.value_or(0)<<','<<(o.root?o.root->sequence:0)<<','<<(o.root?o.root->source_ns:0)<<','<<(o.root?o.root->expiry_ns:0)<<'\n';raw_seen[i][j]=original;
                            }
                        }
                        consumed+=out.drain(source.queue,8);buffered=std::max<std::uint64_t>(buffered,out.pending());require(out.healthy(),"native source recording incomplete");
                        transmit(out,*source_channels_[i],last_send[i]);
                        complete=complete && source.admitted.load()!=0 && out.pending()==0 && out.acknowledged()==stores[i]->committed().size();
                    }
                }
                for(const auto& c:context_channels_)if(c)require(c->stats().dropped==0,"context SDK ingress loss");
                for(const auto& c:source_channels_)if(c)require(c->stats().dropped==0,"source SDK ingress loss");
                if(requested && !restarts) {
                    const bool fault=std::any_of(stores.begin(),stores.end(),[](const auto& store){return store && std::any_of(store->committed().begin(),store->committed().end(),[](const auto& entry){return std::get<d::Event>(entry).kind==d::Kind::Fault;});});
                    const bool pending=std::any_of(outboxes.begin(),outboxes.end(),[](const auto& out){return out && out->pending()!=0;});
                    if((fault || (requested && std::string(restart_env)=="all" && !producing_)) && !pending) {checkpoint("before");restarting=true;for(auto& source:sources_)if(source)source->admitted=0;break;}
                }
                if(finish_deadline && complete && !consumed) {passed_=true;break;}
                std::this_thread::sleep_for(std::chrono::milliseconds(1));
            }
            if(restarting) {++restarts;continue;}
            require(!requested || restarts==1,"requested diagnostic restart not reached");
            require(passed_,"native diagnostic drain timeout");
            if(collector) {require(collector->ledger().complete(),"merged diagnostic recording incomplete");rows(folder_/"records.csv",collector->ledger());}
            else for(unsigned i=0;i<9;++i)if(outboxes[i])rows(folder_/(source_name(i)+"-records.csv"),outboxes[i]->ledger());
            break;
        }
    } catch(const std::exception& e) {passed_=false;error=e.what();}
    std::ofstream channels(folder_/(tag_+".channels.csv"));channels<<"stream,received,rejected,sent,dropped,highwater\n";
    const auto stats=[&](unsigned stream,const diagnostic::Channel& c) {const auto s=c.stats();channels<<stream<<','<<s.received<<','<<s.rejected<<','<<s.send_returned<<','<<s.dropped<<','<<s.highwater<<'\n';};
    for(unsigned i=0;i<9;++i)if(source_channels_[i])stats(8200+i,*source_channels_[i]);
    for(unsigned z=0;z<2;++z)if(context_channels_[z])stats(8101+z,*context_channels_[z]);
    std::ofstream out(folder_/(tag_+".json"));out<<"{\"pass\":"<<(passed_?"true":"false")<<",\"events_seen\":"<<events<<",\"duplicates\":"<<duplicates<<",\"acks_accepted\":"<<acked<<",\"pending_highwater\":"<<buffered<<",\"ack_omitted\":"<<(dropped_ack?"true":"false")<<",\"stale_acks\":"<<stale_acks<<",\"restarts\":"<<restarts<<",\"writer_cpu\":15,\"error\":"<<std::quoted(error)<<"}\n";
}
} // namespace stratadrive::someip::test
