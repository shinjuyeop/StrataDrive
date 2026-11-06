#include "native_diagnostic_routes.hpp"
#include "epoch_local_spool.hpp"
#include "fixture_placement.hpp"
#include "native_execution_watch.hpp"
#include <algorithm>
#include <fstream>
#include <iomanip>

namespace stratadrive::someip::test {
namespace {
namespace d=diagnostics;namespace fs=std::filesystem;
constexpr std::uint64_t ms=1000000;
std::uint64_t wall(){return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());}
void require(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
std::string name(unsigned i){return "source-"+std::to_string(diagnostic_sources[i].producer);}
d::ControlContext manifest(std::uint64_t producer){return {diagnostic_run,producer,d::Domain::Monotonic,kDomain,1};}
void rows(const fs::path& path,const d::Ledger& ledger) {
    std::ofstream out(path);out<<"code,component,monitor,subject,condition,count,generation,cleared\n";
    for(const auto& r:ledger.records())out<<static_cast<unsigned>(r.key.code)<<','<<r.key.component<<','<<r.key.monitor<<','<<r.key.subject<<','<<static_cast<unsigned>(r.condition)<<','<<r.count<<','<<r.generation<<','<<r.cleared<<'\n';
}
}
void NativeDiagnosticRoutes::work_epochs() {
    bool started=false,omitted_ack=false;std::string error;std::uint64_t events=0,duplicates=0,acked=0,buffered=0,stale=0;
    int writer_cpu=-1;
    try {
        writer_cpu=auxiliary_io_cpu();simulation::NativeExecutionWatch::configure_thread(writer_cpu,0);
        simulation::runtime_support::ThreadInfo actual;actual.capture();std::ofstream placement(folder_/(tag_+".writer.json"));actual.write_json(placement);placement.flush();
        std::ofstream log(folder_/(tag_+".delivery.csv"));log<<"wall_ns,action,stream,ordinal,producer,sequence,kind,epoch\n";
        std::ofstream credits(folder_/(tag_+".credits.csv"));credits<<"producer,epoch,requested_ns,prepare_deadline_ns,enable_ns,commit_deadline_ns,lease_sequence,source_ns,expiry_ns,captured_ns\n";
        std::ofstream originals(folder_/(tag_+".originals.csv"));originals<<"producer,monitor,epoch,enable_ns,detected_ns,reason,propagation,violation_ns,selected_ns,root_sequence,root_source,root_expiry\n";
        std::ofstream releases(folder_/(tag_+".release.csv"));releases<<"epoch,role,ns\n";ReleaseAcks written_acks;
        std::ofstream cuts(folder_/(tag_+".cuts.csv"));cuts<<"retired_epoch,observed_ns\n";std::uint32_t last_cut=0;
        const auto note=[&](const char* action,const d::wire::Data& data){log<<wall()<<','<<action<<','<<data.stream<<','<<data.sequence<<','<<data.event.id.producer<<','<<data.event.id.sequence<<','<<static_cast<unsigned>(data.event.kind)<<','<<data.event.session.epoch<<'\n';};
        std::array<std::unique_ptr<d::EpochRecorder>,9> stores;
        std::array<std::unique_ptr<d::ContextualOutbox>,9> outboxes;
        std::array<std::unique_ptr<d::EpochRecorder>,2> contexts;
        std::array<std::unique_ptr<d::Outbox>,2> context_out;
        std::array<std::unique_ptr<d::Inbox>,2> context_in;
        std::unique_ptr<d::EpochRecorder> merged,local,local_replica;
        std::unique_ptr<d::EpochLocalSpool> spool;std::unique_ptr<d::EpochMergedCollector> collector;
        const bool central=ecu_==Ecu::Central;
        const auto target=std::getenv("STRATADRIVE_FAULT_REAR")?Ecu::Rear:Ecu::Front;
        const bool replacement=std::getenv("STRATADRIVE_DIAGNOSTIC_PROCESS_RESTART");
        std::vector<d::EpochRecorder*> members;
        for(unsigned i=0;i<9;++i)if(source_channels_[i]) {
            stores[i]=std::make_unique<d::EpochRecorder>((folder_/name(i)).string());
            if(central)members.push_back(stores[i].get());
            else {
                const auto logical=diagnostic_sources[i].producer;
                std::vector<d::EpochProducer> lineage{{logical,1}};
                if(replacement && diagnostic_sources[i].ecu==target)lineage.push_back({(1ULL<<32)|logical,2});
                outboxes[i]=std::make_unique<d::ContextualOutbox>(*stores[i],manifest(sources_[i]->producer),std::vector<d::CentralIssuer>{{7,1}},std::move(lineage));
                require(outboxes[i]->healthy(),"epoch source incomplete; original family retained");
            }
        }
        for(unsigned z=0;z<2;++z)if(context_channels_[z]) {
            contexts[z]=std::make_unique<d::EpochRecorder>((folder_/(central?"context-"+std::to_string(z):"context")).string());
            if(central)context_out[z]=std::make_unique<d::Outbox>(*contexts[z]);else context_in[z]=std::make_unique<d::Inbox>(*contexts[z]);
            require(contexts[z]->ledger().complete(),"epoch context incomplete");
        }
        if(central) {
            merged=std::make_unique<d::EpochRecorder>((folder_/"merged").string());
            local=std::make_unique<d::EpochRecorder>((folder_/"central-source").string());
            local_replica=std::make_unique<d::EpochRecorder>((folder_/"central-replica").string());
            spool=std::make_unique<d::EpochLocalSpool>(*local,7,8);members.push_back(local_replica.get());
            collector=std::make_unique<d::EpochMergedCollector>(*merged,members);
        }
        startup_ready_.set_value();started=true;
        std::optional<d::Event> global;
        for(const auto& context:contexts)if(context)for(std::uint64_t ordinal=1;ordinal<=context->watermark();++ordinal) {
            const auto e=std::get<d::Event>(context->committed(ordinal));require(e.kind==d::Kind::Session,"context family contains non-Session");
            if(!global || e.session.epoch>global->session.epoch)global=e;
        }
        struct Retry {std::uint64_t last{0},delay{100};};
        std::array<Retry,9> retry{};std::array<Retry,2> context_retry{};
        std::array<std::uint32_t,9> credit_epoch{};std::array<std::array<std::optional<Source::Original>,2>,9> seen{};
        const auto transmit=[&](auto& out,diagnostic::Channel& channel,Retry& state) {
            while(auto bytes=channel.pop()) {
                const auto r=out.acknowledge(*bytes);
                require(r==d::Result::Accepted || r==d::Result::Duplicate || (generation_>1 && r==d::Result::NotReady),"epoch ACK binding");
                if(r==d::Result::Accepted){++acked;state={};}else if(r==d::Result::NotReady)++stale;
            }
            if((!state.last || wall()-state.last>=state.delay*ms) && channel.available())if(auto bytes=out.next())if(channel.send(*bytes)) {
                if(state.last)state.delay=std::min<std::uint64_t>(1000,state.delay*2);
                state.last=wall();note("send",std::get<d::wire::Data>(d::wire::decode(*bytes)));
            }
        };
        std::uint64_t context_cursor=0,deadline=0;bool prefix_marked=false;
        while(!deadline || wall()<deadline) {
            if(!producing_ && !deadline)deadline=wall()+2000*ms;
            std::size_t consumed=0;bool complete=true;
            if(central) {
                const auto cut=retired_central_.load(std::memory_order_acquire);
                if(cut!=last_cut){cuts<<cut<<','<<wall()<<'\n';cuts.flush();last_cut=cut;}
                consumed+=spool->drain(*startup_queue_,*central_queue_,cut);require(spool->healthy(),"Central epoch spool incomplete");
                buffered=std::max<std::uint64_t>(buffered,spool->pending());
                // Distribute genuine context independently of the merged ACK.
                while(context_cursor<local->watermark()) {
                    const auto e=std::get<d::Event>(local->committed(++context_cursor));note("local-spool",{8300,context_cursor,4,e});
                    if(e.kind==d::Kind::Session) {global=e;for(auto& out:context_out)require(out->record(e).durable,"context source commit");}
                }
                if(const auto snapshot=accepted_acks_.read()) {
                    if(written_acks.epoch!=snapshot->epoch)written_acks={snapshot->epoch,{}};
                    for(unsigned role=0;role<8;++role)if(snapshot->times[role] && !written_acks.times[role]){releases<<snapshot->epoch<<','<<role<<','<<snapshot->times[role]<<'\n';written_acks.times[role]=snapshot->times[role];}
                    releases.flush();
                }
                if(const auto bytes=spool->delivery().next()) {
                    const auto r=collector->receive(*bytes);require(r.ack || r.result==d::Result::NotReady,"local epoch merge");
                    if(r.ack){require(spool->delivery().acknowledge(*r.ack)==d::Result::Accepted,"local merge ACK");++acked;}
                }
                for(unsigned i=0;i<9;++i)while(const auto bytes=source_channels_[i]->pop()) {
                    ++consumed;const auto data=std::get<d::wire::Data>(d::wire::decode(*bytes));const auto r=collector->receive(*bytes);
                    require(r.ack || r.result==d::Result::NotReady,"epoch replica merge");
                    note(r.ack?(r.result==d::Result::Duplicate?"duplicate":"replica-commit"):"await-epoch",data);
                    if(!r.ack)continue;
                    ++events;if(r.result==d::Result::Duplicate)++duplicates;
                    if(std::getenv("STRATADRIVE_DIAGNOSTIC_DROP_ACK") && !omitted_ack && data.event.kind==d::Kind::Fault){omitted_ack=true;note("omit-ack",data);}
                    else if(!source_channels_[i]->send(*r.ack))note("ack-unavailable",data);
                }
                require(collector->healthy(),"epoch merged recording incomplete");
                for(unsigned z=0;z<2;++z){transmit(*context_out[z],*context_channels_[z],context_retry[z]);complete=complete && context_out[z]->acknowledged()==contexts[z]->watermark();}
                complete=complete && spool->pending()==0 && spool->delivery().acknowledged()==local->watermark();
                for(const auto& store:stores)complete=complete && store->watermark()!=0;
            } else {
                const unsigned z=ecu_==Ecu::Rear?1:0;
                while(auto bytes=context_channels_[z]->pop()) {
                    ++consumed;const auto data=std::get<d::wire::Data>(d::wire::decode(*bytes));const auto r=context_in[z]->receive(*bytes);
                    require(r.ack.has_value(),"epoch global context commit");
                    if(!global || data.event.session.epoch>global->session.epoch)global=data.event;
                    note("context-commit",data);if(!context_channels_[z]->send(*r.ack))note("context-ack-unavailable",data);
                }
                for(unsigned i=0;i<9;++i)if(outboxes[i]) {
                    auto& out=*outboxes[i];auto& source=*sources_[i];
                    // Acquire the endpoint owner's newer lease BEFORE draining:
                    // it closes the old publisher prefix. Global context alone
                    // does not establish that local owner handoff.
                    const auto evidence=source.evidence.read();
                    consumed+=out.drain(source.queue);buffered=std::max<std::uint64_t>(buffered,out.pending());
                    if(global && source.admitted.load()!=global->session.epoch && evidence) {
                        const auto& lease=*evidence->credit.accepted;const auto& p=lease.plan;
                        if(credit_epoch[i]!=p.epoch){credit_epoch[i]=p.epoch;credits<<source.producer<<','<<p.epoch<<','<<p.requested_ns<<','<<p.prepare_deadline_ns<<','<<p.enable_ns<<','<<p.commit_deadline_ns<<','<<lease.sequence<<','<<lease.source_time_ns<<','<<lease.expires_at_ns<<','<<evidence->captured_ns<<'\n';credits.flush();}
                        const auto r=out.context(*global,evidence->credit);require(r==d::Result::Accepted || r==d::Result::Duplicate || r==d::Result::NotReady,"epoch local context admission");
                        if(r!=d::Result::NotReady)source.admitted=global->session.epoch;
                    }
                    for(unsigned j=0;j<2;++j)if(const auto original=source.original[j].read()) {
                        const auto& old=seen[i][j];const auto& o=original->fault;
                        if(!old || old->fault.epoch!=o.epoch || old->fault.observed_ns!=o.observed_ns || old->selected!=original->selected) {
                            originals<<source.producer<<','<<original->monitor<<','<<o.epoch<<','<<o.enable_ns<<','<<o.observed_ns<<','<<o.reason<<','<<o.propagation<<','<<o.violation_ns.value_or(0)<<','<<original->selected.value_or(0)<<','<<(o.root?o.root->sequence:0)<<','<<(o.root?o.root->source_ns:0)<<','<<(o.root?o.root->expiry_ns:0)<<'\n';originals.flush();seen[i][j]=original;
                        }
                    }
                    require(out.healthy(),"epoch source recording incomplete");transmit(out,*source_channels_[i],retry[i]);
                    complete=complete && source.admitted.load()!=0 && out.pending()==0 && out.acknowledged()==stores[i]->watermark();
                }
            }
            for(const auto& channel:source_channels_)if(channel)require(!channel->stats().dropped && !channel->stats().rejected,"epoch source SDK ingress loss");
            for(const auto& channel:context_channels_)if(channel)require(!channel->stats().dropped && !channel->stats().rejected,"epoch context SDK ingress loss");
            complete=complete && global.has_value();
            if(complete && !consumed && !prefix_marked){std::ofstream(folder_/(tag_+".prefix-ready"))<<global->session.epoch;prefix_marked=true;}
            if(deadline && complete && !consumed){passed_=true;break;}
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
        require(passed_,"epoch diagnostic drain timeout");
        std::ofstream receipts(folder_/(tag_+".receipts.csv"));receipts<<"stream,entries,acknowledged,segments\n";
        if(central) {
            receipts<<8300<<','<<local->watermark()<<','<<spool->delivery().acknowledged()<<','<<local->segment()<<'\n';
            for(unsigned z=0;z<2;++z)receipts<<8101+z<<','<<contexts[z]->watermark()<<','<<context_out[z]->acknowledged()<<','<<contexts[z]->segment()<<'\n';
        } else for(unsigned i=0;i<9;++i)if(outboxes[i])receipts<<8200+i<<','<<stores[i]->watermark()<<','<<outboxes[i]->acknowledged()<<','<<stores[i]->segment()<<'\n';
        if(central)rows(folder_/"records.csv",collector->ledger());
        else for(unsigned i=0;i<9;++i)if(outboxes[i])rows(folder_/(name(i)+"-records.csv"),outboxes[i]->ledger());
    }catch(const std::exception& e){error=e.what();passed_=false;if(!started){startup_ready_.set_exception(std::current_exception());started=true;}}
    std::ofstream channels(folder_/(tag_+".channels.csv"));channels<<"stream,received,rejected,sent,dropped,highwater\n";
    const auto stats=[&](unsigned stream,const diagnostic::Channel& channel){const auto s=channel.stats();channels<<stream<<','<<s.received<<','<<s.rejected<<','<<s.send_returned<<','<<s.dropped<<','<<s.highwater<<'\n';};
    for(unsigned i=0;i<9;++i)if(source_channels_[i])stats(8200+i,*source_channels_[i]);
    for(unsigned z=0;z<2;++z)if(context_channels_[z])stats(8101+z,*context_channels_[z]);
    std::ofstream(folder_/(tag_+".json"))<<"{\"pass\":"<<(passed_?"true":"false")<<",\"epochs\":true,\"events_seen\":"<<events<<",\"duplicates\":"<<duplicates<<",\"acks_accepted\":"<<acked<<",\"pending_highwater\":"<<buffered<<",\"ack_omitted\":"<<(omitted_ack?"true":"false")<<",\"stale_acks\":"<<stale<<",\"restarts\":0,\"producer_generation\":"<<generation_<<",\"previous_unclean\":"<<(lifecycle_ && lifecycle_->previous_unclean()?"true":"false")<<",\"writer_cpu\":"<<writer_cpu<<",\"error\":"<<std::quoted(error)<<"}\n";
}
} // namespace stratadrive::someip::test
