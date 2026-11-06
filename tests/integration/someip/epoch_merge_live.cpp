#include "someip/diagnostic_channel.hpp"
#include "diagnostics_delivery.hpp"
#include "m4_async_runtime.hpp"
#include <algorithm>
#include <array>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <thread>

namespace {
using namespace stratadrive;
namespace d=diagnostics;namespace sdk=someip::diagnostic;namespace fs=std::filesystem;
constexpr std::uint64_t run=7101,ms=1000000;
constexpr std::array<std::uint64_t,3> producers{7,30,31};
std::uint64_t wall(){return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());}
void require(bool yes,const char* reason){if(!yes)throw std::runtime_error(reason);}
void mark(const fs::path& path,std::uint64_t value=0){std::ofstream(path)<<value<<'\n';}
void records(const fs::path& path,const d::Ledger& ledger) {
    std::ofstream out(path);out<<"code,component,monitor,subject,count,condition,generation,cleared\n";
    for(const auto& r:ledger.records())out<<static_cast<unsigned>(r.key.code)<<','<<r.key.component<<','<<r.key.monitor<<','<<r.key.subject<<','<<r.count<<','<<static_cast<unsigned>(r.condition)<<','<<r.generation<<','<<r.cleared<<'\n';
}
void physical(const fs::path& path,const simulation::M4Result& result) {
    std::ofstream out(path);out<<"source_ns,epoch,model_epoch,model_sequence,speed_mps,distance_m,energy_j,balance_j,torque_nm,pressure_pa,gate\n"<<std::setprecision(17);
    for(const auto& r:result.trace)out<<r.source_ns<<','<<r.epoch<<','<<r.model_epoch<<','<<r.model_sequence<<','<<r.speed_mps<<','<<r.distance_m<<','<<r.energy_j<<','<<r.vehicle_balance_j<<','<<r.torque_nm<<','<<r.pressure_pa<<','<<r.run_gate<<'\n';
}
// Frozen original native-owner output, then independent non-RT SDK delivery.
// This cohort is not a wall-time control or live 3-process ECU timing claim.
void bootstrap(const fs::path& folder) {
    simulation::M4Config c;c.speed_loop=true;c.renewal=central::CommandRenewal::Host10ms;c.native_diagnostics_run=run;
    c.scenario=simulation::M4Scenario::Fault;c.faults={simulation::parse_m4_fault("owner:pause:central:10000:200:0")};
    c.duration_ns=24000*ms;c.recovery_ns=20000*ms;c.replace_links=true;
    const auto result=simulation::run_m4_async(c);require(result.passed && result.diagnostics_complete,"native fixture verdict");
    simulation::write_m4_result(c,result,(folder/"logical").string());physical(folder/"physical.csv",result);
    c.native_diagnostics_run=0;const auto baseline=simulation::run_m4_async(c);require(baseline.passed,"baseline verdict");physical(folder/"baseline-physical.csv",baseline);
    std::ofstream original(folder/"original-events.hex");
    for(const auto& event:result.diagnostic_events){for(auto byte:d::encode(event))original<<std::hex<<std::setw(2)<<std::setfill('0')<<static_cast<unsigned>(byte);original<<'\n';}
    fs::create_directory(folder/"source-store");fs::create_directory(folder/"replica-store");
    d::EpochRecorder::initialize((folder/"replica-store"/"merged").string(),7900,{{128,32,32,8},4,16});
    for(unsigned i=0;i<producers.size();++i) {
        const auto name=std::to_string(i);const auto id=7200+i;
        d::EpochRecorder::initialize((folder/"source-store"/name).string(),id,{{64,16,16,8},1,16});
        d::EpochRecorder::initialize((folder/"replica-store"/name).string(),id,{{64,16,16,8},2,16});
        d::EpochRecorder source((folder/"source-store"/name).string());
        for(unsigned epoch=1;epoch<=2;++epoch) {
            const auto context=std::find_if(result.diagnostic_events.begin(),result.diagnostic_events.end(),[&](const auto& e){return e.kind==d::Kind::Session && e.session.epoch==epoch;});
            require(context!=result.diagnostic_events.end(),"missing original global Session");require(source.record(*context).durable,"context source commit");
            for(const auto& e:result.diagnostic_events)if(e.id.producer==producers[i] && e.session.epoch==epoch && e.kind!=d::Kind::Session)
                require(source.record(e).durable,"native source commit");
        }
        records(folder/("source-"+name+"-records.csv"),source.ledger());
        if(i==1)require(source.watermark()>2 && std::get<d::Event>(source.committed(2)).session.epoch==1,"no original late tail");
    }
}
struct Network {
    std::shared_ptr<vsomeip::application> app;std::array<std::unique_ptr<sdk::Channel>,3> lanes;std::thread dispatch;
    explicit Network(bool publisher) {
        app=vsomeip::runtime::get()->create_application(publisher?"diag-source":"diag-replica");require(app && app->init(),"SDK init");
        for(unsigned i=0;i<lanes.size();++i) {
            lanes[i]=std::make_unique<sdk::Channel>(publisher?sdk::Role::Publisher:sdk::Role::Replica,7200+i,4,
                sdk::Services{static_cast<std::uint16_t>(0x5d10+2*i),static_cast<std::uint16_t>(0x5d11+2*i)});lanes[i]->configure(app);
        }
        app->register_state_handler([this](auto state){if(state==vsomeip::state_type_e::ST_REGISTERED)for(auto& lane:lanes)lane->registered();});
        dispatch=std::thread([this]{app->start();});
    }
    ~Network(){if(dispatch.joinable()){app->clear_all_handler();app->stop();dispatch.join();}}
    void stats(const fs::path& path) {
        std::ofstream out(path);out<<"stream,received,rejected,sent,dropped,highwater\n";
        for(unsigned i=0;i<lanes.size();++i){const auto s=lanes[i]->stats();out<<7200+i<<','<<s.received<<','<<s.rejected<<','<<s.send_returned<<','<<s.dropped<<','<<s.highwater<<'\n';require(!s.dropped && !s.rejected,"SDK ingress error");}
    }
};
void publisher(const fs::path& folder) {
    std::array<std::unique_ptr<d::EpochRecorder>,3> stores;std::array<std::unique_ptr<d::Outbox>,3> out;
    for(unsigned i=0;i<stores.size();++i){stores[i]=std::make_unique<d::EpochRecorder>((folder/"source-store"/std::to_string(i)).string());out[i]=std::make_unique<d::Outbox>(*stores[i]);}
    Network net(true);std::ofstream log(folder/"publisher.csv");log<<"wall_ns,stream,ordinal,action,result\n";
    std::array<std::uint64_t,3> last{},retry_ms{100,100,100};const auto deadline=wall()+45*1000*ms;bool finished=false;
    while(wall()<deadline) {
        finished=true;
        for(unsigned i=0;i<out.size();++i) {
            while(const auto bytes=net.lanes[i]->pop()) {
                const auto ack=std::get<d::wire::Ack>(d::wire::decode(*bytes));const auto result=out[i]->acknowledge(*bytes);
                require(result==d::Result::Accepted || result==d::Result::Duplicate,"source ACK");
                log<<wall()<<','<<ack.stream<<','<<ack.sequence<<",ack,"<<static_cast<unsigned>(result)<<'\n';
                if(result==d::Result::Accepted){last[i]=0;retry_ms[i]=100;}
            }
            finished=finished && out[i]->healthy() && out[i]->acknowledged()==stores[i]->watermark();
            if(last[i] && wall()-last[i]<retry_ms[i]*ms)continue;
            if(const auto bytes=out[i]->next()) {
                const auto packet=std::get<d::wire::Data>(d::wire::decode(*bytes));
                if(i==1 && packet.sequence>1 && !fs::exists(folder/"release-delay"))continue;
                if(net.lanes[i]->send(*bytes)) {
                    // SD availability does not prove that TCP has reconnected.
                    // Back off unacknowledged diagnostic retries so the SDK
                    // cannot accumulate a 100ms burst during replacement.
                    if(last[i])retry_ms[i]=std::min<std::uint64_t>(1000,retry_ms[i]*2);
                    last[i]=wall();log<<last[i]<<','<<packet.stream<<','<<packet.sequence<<",send,0\n";
                }
            }
        }
        if(finished)break;
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    require(finished,"merge source delivery timeout");net.stats(folder/"publisher-sdk.csv");
    std::ofstream receipts(folder/"receipts.csv");receipts<<"stream,committed,acknowledged\n";
    for(unsigned i=0;i<out.size();++i)receipts<<7200+i<<','<<stores[i]->watermark()<<','<<out[i]->acknowledged()<<'\n';
    receipts.close();mark(folder/"publisher-done");
}
void replica(const fs::path& folder,unsigned generation) {
    std::array<std::unique_ptr<d::EpochRecorder>,3> stores;std::vector<d::EpochRecorder*> members;
    for(unsigned i=0;i<stores.size();++i){stores[i]=std::make_unique<d::EpochRecorder>((folder/"replica-store"/std::to_string(i)).string());members.push_back(stores[i].get());}
    d::EpochRecorder merged((folder/"replica-store"/"merged").string());d::EpochMergedCollector collector(merged,members);
    Network net(false);std::ofstream log(folder/("replica-"+std::to_string(generation)+".csv"));
    log<<"wall_ns,stream,ordinal,epoch,result,ack_sent,merged_epoch,merged_entries\n";
    if(generation==2){require(merged.ledger().session().epoch==1,"restart skipped delayed old tail");mark(folder/"release-delay");}
    const auto deadline=wall()+50*1000*ms;bool frozen=false;
    while(wall()<deadline && !fs::exists(folder/"finish")) {
        for(auto& lane:net.lanes)while(!frozen) {
            const auto bytes=lane->pop();if(!bytes)break;
            const auto packet=std::get<d::wire::Data>(d::wire::decode(*bytes));const auto receipt=collector.receive(*bytes);
            require(collector.healthy() && (receipt.ack || receipt.result==d::Result::NotReady),"merged receive");
            const bool sent=receipt.ack && lane->send(*receipt.ack);
            log<<wall()<<','<<packet.stream<<','<<packet.sequence<<','<<packet.event.session.epoch<<','<<static_cast<unsigned>(receipt.result)<<','<<sent<<','<<merged.ledger().session().epoch<<','<<merged.watermark()<<'\n';log.flush();
            // Freeze all writer IO before the runner kills this process. This
            // specific case targets a DURABLE waiting prefix, not an unfinished
            // journal transaction (which must remain incomplete on restart).
            if(generation==1 && !receipt.ack && packet.event.session.epoch==2 && merged.ledger().session().epoch==1) {
                frozen=true;mark(folder/"restart-needed",packet.stream);
            }
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    require(fs::exists(folder/"finish") && collector.healthy() && merged.ledger().session().epoch==2,"collector incomplete");
    records(folder/"merged-records.csv",collector.ledger());net.stats(folder/("replica-"+std::to_string(generation)+"-sdk.csv"));mark(folder/"replica-done",merged.watermark());
}
}
int main(int argc,char** argv) {
    try {
        require(argc==5 && std::string(argv[3])=="epoch-merge-restart","role folder epoch-merge-restart generation");
        const std::string role=argv[1];const fs::path folder=argv[2];
        if(role=="bootstrap")bootstrap(folder);else if(role=="publisher")publisher(folder);else {require(role=="replica","role");replica(folder,static_cast<unsigned>(std::stoul(argv[4])));}
        return 0;
    }catch(const std::exception& e){std::cerr<<"epoch merge pilot: "<<e.what()<<'\n';return 1;}
}
