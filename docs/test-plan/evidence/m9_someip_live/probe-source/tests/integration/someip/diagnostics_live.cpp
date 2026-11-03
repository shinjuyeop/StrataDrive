#include "someip/diagnostic_transport.hpp"
#include "diagnostics_delivery.hpp"
#include "m4_owner_network.hpp"
#include <atomic>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>

namespace {
using namespace stratadrive;
namespace diag=diagnostics;
namespace sdk=someip::diagnostic;
namespace fs=std::filesystem;
constexpr std::uint64_t run=7001,ms=1000000;
std::uint64_t wall() {return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count());}
void require(bool ok,const char* why) {if(!ok)throw std::runtime_error(why);}
void mark(const fs::path& p,std::uint64_t value=0) {std::ofstream(p)<<value<<'\n';}
void records(const fs::path& p,const diag::Ledger& ledger) {
    std::ofstream out(p);out<<"code,component,monitor,subject,condition,count,generation,cleared\n";
    for(const auto& r:ledger.records())out<<static_cast<unsigned>(r.key.code)<<','<<r.key.component<<','<<r.key.monitor<<','<<r.key.subject<<','<<static_cast<unsigned>(r.condition)<<','<<r.count<<','<<r.generation<<','<<r.cleared<<'\n';
}
void stats(const fs::path& p,const sdk::Transport::Stats& s) {
    std::ofstream(p)<<"{\"received\":"<<s.received<<",\"rejected\":"<<s.rejected<<",\"send_returned\":"<<s.send_returned<<",\"dropped\":"<<s.dropped<<",\"highwater\":"<<s.highwater<<"}\n";
}
void physical(const fs::path& p,const simulation::M4Result& r) {
    std::ofstream out(p);out<<"source_ns,epoch,model_epoch,model_sequence,speed_mps,distance_m,energy_j,balance_j,bus_v,contacts,torque_nm,pressure_pa,gate\n"<<std::setprecision(17);
    for(const auto& t:r.trace)out<<t.source_ns<<','<<t.epoch<<','<<t.model_epoch<<','<<t.model_sequence<<','<<t.speed_mps<<','<<t.distance_m<<','<<t.energy_j<<','<<t.vehicle_balance_j<<','<<t.bus_v<<','<<t.contacts<<','<<t.torque_nm<<','<<t.pressure_pa<<','<<t.run_gate<<'\n';
}
void publisher(const fs::path& folder,const std::string& scenario) {
    sdk::Transport net(sdk::Role::Publisher,run,3,"diag-source");net.start();
    const auto ready_deadline=wall()+10*1000*ms;while(!net.available() && wall()<ready_deadline)std::this_thread::sleep_for(std::chrono::milliseconds(1));
    require(net.available(),"replica availability timeout");
    simulation::M4Config c;c.speed_loop=true;c.renewal=central::CommandRenewal::Host10ms;c.diagnostics_run=run;
    c.scenario=scenario=="normal"?simulation::M4Scenario::Normal:simulation::M4Scenario::SpeedInputLoss;c.duration_ns=scenario=="normal"?92000*ms:13000*ms;
    simulation::m4_detail::Network owner(c);std::atomic<bool> producing{true},cancel{false};std::exception_ptr failure;
    unsigned commits=0,overlap=0;std::uint64_t acked=0;bool fault_overlap=false;
    std::thread writer([&] {
        try {
            diag::FileJournal journal((folder/"source-store").string());diag::Outbox out(journal);
            std::ofstream log(folder/"publisher.csv");log<<"wall_ns,action,ordinal,event_sequence,kind,producer_running,result\n";
            const auto deadline=wall()+45*1000*ms;std::uint64_t last_send=0;
            while(!cancel && wall()<deadline) {
                const bool finished=!producing.load(std::memory_order_acquire);
                diag::Event event;unsigned consumed=0;
                while(consumed<8 && owner.diagnostic_queue->pop(event)) {
                    ++consumed;
                    const auto receipt=out.record(event);require(receipt.durable,"source commit failed");++commits;
                    const bool live=producing.load(std::memory_order_acquire);if(live)++overlap;if(live && event.kind==diag::Kind::Fault)fault_overlap=true;
                    log<<wall()<<",commit,"<<receipt.watermark<<','<<event.id.sequence<<','<<static_cast<unsigned>(event.kind)<<','<<live<<','<<static_cast<unsigned>(receipt.result)<<'\n';
                }
                const auto health=owner.diagnostic_queue->health();require(!health.dropped && !health.identity_error,"live source queue loss");
                while(auto bytes=net.pop()) {
                    const auto a=std::get<diag::wire::Ack>(diag::wire::decode(*bytes));const auto result=out.acknowledge(*bytes);
                    require(result==diag::Result::Accepted || result==diag::Result::Duplicate,"invalid SDK ACK");
                    log<<wall()<<",ack,"<<a.sequence<<",0,0,"<<producing.load()<<','<<static_cast<unsigned>(result)<<'\n';last_send=0;
                }
                if(finished && consumed<8 && out.acknowledged()==journal.committed().size() && commits)break;
                if(net.available() && (!last_send || wall()-last_send>=100*ms))if(auto bytes=out.next())if(net.send(*bytes)) {
                    const auto d=std::get<diag::wire::Data>(diag::wire::decode(*bytes));last_send=wall();
                    log<<last_send<<",send-return,"<<d.sequence<<','<<d.event.id.sequence<<','<<static_cast<unsigned>(d.event.kind)<<','<<producing.load()<<",0\n";
                }
                std::this_thread::sleep_for(std::chrono::milliseconds(1));
            }
            require(!cancel && out.healthy() && out.acknowledged()==journal.committed().size(),"diagnostic delivery incomplete");acked=out.acknowledged();records(folder/"source-records.csv",out.ledger());
        } catch(...) {failure=std::current_exception();cancel=true;}
    });
    try {
        for(std::uint64_t t=0;t<=c.duration_ns;t+=simulation::m4_detail::kIoPoll) {
            if(cancel)throw std::runtime_error("writer aborted");
            owner.clock.logical=simulation::m4_detail::kLogicalStart+t;
            if(t%ms==0)owner.step(8);
            for(std::size_t role=0;role<8;++role)owner.step(role);
            if(t%ms==0)std::this_thread::sleep_for(std::chrono::microseconds(20));
        }
    } catch(...) {cancel=true;producing=false;writer.join();if(failure)std::rethrow_exception(failure);throw;}
    producing.store(false,std::memory_order_release);writer.join();if(failure)std::rethrow_exception(failure);
    auto result=owner.finish();require(result.passed && result.diagnostics_complete,"live logical owner verdict");
    {
        diag::FileJournal journal((folder/"source-store").string());for(const auto& e:journal.committed())result.diagnostic_events.push_back(std::get<diag::Event>(e));
    }
    require(result.diagnostic_events.size()==commits && overlap>0 && (scenario=="normal" || fault_overlap),"not a live owner source");
    auto baseline_config=c;baseline_config.diagnostics_run=0;const auto baseline=simulation::run_m4_async(baseline_config);require(baseline.passed,"baseline verdict");
    require(result.trace.size()==baseline.trace.size(),"physical denominator");
    for(std::size_t i=0;i<result.trace.size();++i) {
        const auto& a=result.trace[i];const auto& b=baseline.trace[i];
        require(a.epoch==b.epoch && a.run_gate==b.run_gate && a.model_epoch==b.model_epoch && a.model_sequence==b.model_sequence && a.contacts==b.contacts &&
                a.speed_mps==b.speed_mps && a.distance_m==b.distance_m && a.energy_j==b.energy_j && a.soc==b.soc && a.bus_v==b.bus_v &&
                a.torque_nm==b.torque_nm && a.pressure_pa==b.pressure_pa && a.vehicle_balance_j==b.vehicle_balance_j,"diagnostics changed physics");
    }
    physical(folder/"physical.csv",result);physical(folder/"baseline-physical.csv",baseline);simulation::write_m4_result(c,result,(folder/"logical").string());
    net.stop();stats(folder/"publisher-sdk.json",net.stats());require(!net.stats().dropped,"SDK ingress overflow");
    std::ofstream(folder/"publisher.json")<<"{\"pass\":true,\"events\":"<<commits<<",\"acknowledged\":"<<acked<<",\"live_commits\":"<<overlap<<",\"live_fault\":"<<fault_overlap<<",\"physical_samples\":"<<result.trace.size()<<",\"controls\":"<<result.speed_trace.size()<<",\"on_off_identical\":true}\n";
    mark(folder/"publisher-done",acked);
}
void replica(const fs::path& folder,const std::string& scenario,unsigned generation) {
    sdk::Transport net(sdk::Role::Replica,run,3,"diag-replica");net.start();diag::FileJournal journal((folder/"replica-store").string());diag::Inbox in(journal);
    std::ofstream log(folder/("replica-"+std::to_string(generation)+".csv"));log<<"wall_ns,ordinal,result,watermark,ack_sent,condition,count,generation,cleared\n";
    bool held=false,dropped=false;const auto deadline=wall()+50*1000*ms;
    while(wall()<deadline && !fs::exists(folder/"finish")) {
        while(auto bytes=net.pop()) {
            const auto d=std::get<diag::wire::Data>(diag::wire::decode(*bytes));const auto r=in.receive(*bytes);require(r.ack.has_value(),"replica rejected bound source");
            const bool fault=d.event.kind==diag::Kind::Fault;
            if(generation==1 && fault && scenario=="restart")held=true;
            const bool omit=held || (scenario=="drop-ack" && fault && !dropped);if(omit)dropped=true;
            const bool sent=!omit && net.send(*r.ack);
            log<<wall()<<','<<d.sequence<<','<<static_cast<unsigned>(r.result)<<','<<r.watermark<<','<<sent<<',';
            if(in.ledger().records().empty())log<<"-1,0,0,0\n";
            else {const auto& record=in.ledger().records()[0];log<<static_cast<unsigned>(record.condition)<<','<<record.count<<','<<record.generation<<','<<record.cleared<<'\n';}
            log.flush();if(held)mark(folder/"restart-needed",r.watermark);
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    require(fs::exists(folder/"finish") && in.healthy(),"replica did not finish");net.stop();records(folder/"replica-records.csv",in.ledger());stats(folder/("replica-"+std::to_string(generation)+"-sdk.json"),net.stats());
    require(!net.stats().dropped,"replica ingress overflow");mark(folder/"replica-done",journal.committed().size());
}
}
int main(int argc,char** argv) {
    try {
        require(argc==5,"role folder scenario generation");const fs::path folder=argv[2];const std::string scenario=argv[3];
        require(scenario=="normal" || scenario=="loss" || scenario=="drop-ack" || scenario=="restart","diagnostic scenario");
        if(std::string(argv[1])=="bootstrap") {diag::FileJournal::initialize((folder/"source-store").string(),run,{},3);diag::FileJournal::initialize((folder/"replica-store").string(),run,{},3);return 0;}
        if(std::string(argv[1])=="publisher")publisher(folder,scenario);else {require(std::string(argv[1])=="replica","role");replica(folder,scenario,static_cast<unsigned>(std::stoul(argv[4])));}
        return 0;
    } catch(const std::exception& e) {std::cerr<<"diagnostic pilot: "<<e.what()<<'\n';return 1;}
}
