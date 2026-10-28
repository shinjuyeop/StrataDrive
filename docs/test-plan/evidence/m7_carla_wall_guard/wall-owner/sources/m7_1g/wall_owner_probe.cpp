// Real CLOCK_MONOTONIC owner execution with an explicit stationary synthetic
// plant producer. Not a CARLA adapter, physical driving test or clock mapping.
#include "wall_rig.hpp"
#include "wall_mailbox.hpp"
#include "wall_execution_watch.hpp"
#include "owner_wire.hpp"
#include <atomic>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <thread>

using namespace stratadrive;
using namespace m7_functional;
namespace {
struct Row {
    Time now=0,source=0,energy=0,protection=0,brake_source=0,drive_source=0;
    std::size_t controller=0;
    unsigned service=0,credit=0,selected=0;
    double pressure=-1,torque=-1;
    bool armed=false,failed=false;
};
Row row(const WallReport& report) {
    const auto& r=report.native;
    Row x;x.now=r.now;x.source=r.sensor_wheel?r.sensor_wheel->source:0;
    x.energy=r.electrical?r.electrical->end:0;x.protection=report.protected_at;
    x.controller=r.controller_releases;x.service=r.service_mask;x.credit=r.credit_mask;
    x.armed=r.armed;x.failed=report.failed;
    if(r.native_export) {
        x.selected=r.native_export->protection_selected_mask;
        const auto& p=r.native_export->actual;
        if(p[1]) {
            const auto m=remote::decode_owner_message(p[1]->bytes.data(),p[1]->size);
            if(m)if(const auto* f=std::get_if<transport::Feedback>(&m->payload))if(const auto* b=std::get_if<can::BrakeFrame>(f)) {
                const auto sample=can::decode_brake_frame(*b);
                if(sample && sample->pressure_pa) {x.pressure=*sample->pressure_pa;x.brake_source=sample->source_time_ns;}
            }
        }
        if(p[2]) {
            const auto m=remote::decode_owner_message(p[2]->bytes.data(),p[2]->size);
            if(m)if(const auto* f=std::get_if<transport::Feedback>(&m->payload))if(const auto* d=std::get_if<can::DriveFrame>(f)) {
                const auto sample=can::decode_drive_frame(*d);
                if(sample && sample->torque_nm) {x.torque=*sample->torque_nm;x.drive_source=sample->source_time_ns;}
            }
        }
    }
    return x;
}
}
int main(int argc,char** argv) {
    try {
        if(argc!=3 || (std::string(argv[2])!="normal" && std::string(argv[2])!="gap" && std::string(argv[2])!="owner-stall"))
            throw std::runtime_error("usage: m7_wall_owner_probe output-prefix normal|gap|owner-stall");
        const std::string path=argv[1],mode=argv[2];
        WallMailbox<WallReceipt,8> inbox;
        std::atomic<bool> done{false};
        const auto initial=WallExecutionWatch::now()+100*ms;
        std::vector<Row> trace;trace.reserve(2000);
        std::vector<Time> deliveries;deliveries.reserve(160);
        simulation::runtime_support::ThreadInfo owner_info,io_info;
        std::string failure,exception;
        std::thread io([&] {
            try {
                io_info.capture();
                // Leave a complete owner window to drain the final receipt.
                for(unsigned i=1;i<=149;++i) {
                    if(mode=="gap" && i==111) {
                        // Deliberately block the IO owner, not the native owner.
                        simulation::runtime_support::sleep_until(initial+1500*ms);break;
                    }
                    const auto end=initial+i*10*ms;
                    simulation::runtime_support::sleep_until(end);
                    if(done.load(std::memory_order_acquire))break;
                    m7_external::SolverWork w;w.frame=100+i;w.begin=end-10*ms;w.end=end;
                    w.oldest=w.begin;w.dt=double(.01f*(1.f/320.f));
                    w.wheel={0,{7,99+i,w.begin},w.begin};
                    deliveries.push_back(WallExecutionWatch::now());
                    if(!inbox.push({{99,w.frame,end,{0,0,0,0}},w,wall_domain}))break;
                }
            } catch(...) {inbox.fail();}
        });
        try {
            WallRig rig({1,42,7},99,initial);owner_info.capture();
            WallExecutionWatch watch(initial+ms);rig.execution_watch(&watch);
            auto wake=initial+ms;
            while(wake<=initial+1500*ms) {
                simulation::runtime_support::sleep_until(wake);
                const auto now=WallExecutionWatch::now();
                if(mode=="owner-stall" && now>=initial+1100*ms && now<initial+1110*ms) {
                    simulation::runtime_support::sleep_until(initial+1110*ms);continue;
                }
                if(inbox.failed())rig.protect("receipt mailbox overflow/IO failure");
                const auto r=rig.service(now,inbox.pop());
                if(failure.empty() && r.failed)failure=r.reason;
                if(trace.size()==trace.capacity())throw std::runtime_error("trace capacity");
                trace.push_back(row(r));
                const auto finished=WallExecutionWatch::now();
                wake=initial+((finished-initial)/ms+1)*ms;
            }
            watch.write(path+"-wall.csv");
        } catch(const std::exception& e) {exception=e.what();}
        done.store(true,std::memory_order_release);io.join();
        std::ofstream out(path+".csv");out<<std::setprecision(17);
        out<<"now_ns,wheel_source_ns,energy_end_ns,protection_ns,brake_source_ns,drive_source_ns,controller_releases,service_mask,credit_mask,selected_mask,pressure_pa,torque_nm,armed,failed\n";
        for(const auto& x:trace)out<<x.now<<','<<x.source<<','<<x.energy<<','<<x.protection<<','<<x.brake_source<<','<<x.drive_source<<','
            <<x.controller<<','<<x.service<<','<<x.credit<<','<<x.selected<<','<<x.pressure<<','<<x.torque<<','<<x.armed<<','<<x.failed<<'\n';
        if(!out)throw std::runtime_error("trace write");
        std::ofstream meta(path+".json");meta<<"{\"scope\":\"wall owner with stationary synthetic work; NOT CARLA\",\"initial_ns\":"<<initial
            <<",\"mode\":\""<<mode<<"\",\"first_fault\":\""<<failure<<"\",\"exception\":\""<<exception
            <<"\",\"owner\":";owner_info.write_json(meta);meta<<",\"io\":";io_info.write_json(meta);
        meta<<",\"deliveries_ns\":[";for(std::size_t i=0;i<deliveries.size();++i){if(i)meta<<',';meta<<deliveries[i];}meta<<"]}\n";
        if(!meta)throw std::runtime_error("metadata write");
        return exception.empty()?0:1;
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}
