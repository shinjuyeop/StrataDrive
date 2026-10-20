#include "demo_commands.hpp"
#include "m4_async_runtime.hpp"
#include "epoch_store.hpp"

#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <charconv>

namespace stratadrive::demo {
void demo_m4_async(const M4DemoOptions& options) {
    const auto& clock=options.clock; const auto& scenario=options.scenario; const auto& store=options.store; const auto& output=options.output;
    simulation::M4Config config;
    if(clock!="logical" && clock!="wall") throw std::invalid_argument("M4 clock must be logical or wall");
    config.wall_time=clock=="wall"; bool found=false;
    for(const auto candidate:{simulation::M4Scenario::Normal,simulation::M4Scenario::NormalStop,simulation::M4Scenario::PartialFront,
        simulation::M4Scenario::FeedbackLoss,simulation::M4Scenario::CommandLoss,simulation::M4Scenario::PartialArm,
        simulation::M4Scenario::Rejoin,simulation::M4Scenario::OldEpoch,simulation::M4Scenario::Fault}) {
        if(scenario==simulation::m4_scenario_name(candidate)) { config.scenario=candidate; found=true; }
    }
    if(!found) throw std::invalid_argument("unknown M4 scenario");
    const auto milliseconds=[](const std::string& value) {
        std::uint64_t number=0; const auto parsed=std::from_chars(value.data(),value.data()+value.size(),number);
        if(parsed.ec!=std::errc{} || parsed.ptr!=value.data()+value.size() || number>10000) throw std::invalid_argument("M4 time must be 0..10000 integer ms");
        return number*1000000;
    };
    for(const auto& argument:options.extra) {
        if(argument.rfind("fault=",0)==0) config.faults.push_back(simulation::parse_m4_fault(argument.substr(6)));
        else if(argument.rfind("duration-ms=",0)==0) config.duration_ns=milliseconds(argument.substr(12));
        else if(argument.rfind("recover-ms=",0)==0) config.recovery_ns=milliseconds(argument.substr(11));
        else if(argument=="replace-links") config.replace_links=true;
        else if(argument=="guards") config.execution_guards=true;
        else if(argument=="fifo") config.fifo=true;
        else if(argument.rfind("cpus=",0)==0) {
            const auto value=argument.substr(5); const auto comma=value.find(',');
            if(comma==std::string::npos) throw std::invalid_argument("cpus requires A,B");
            config.cpu_a=static_cast<int>(milliseconds(value.substr(0,comma))/1000000);
            config.cpu_b=static_cast<int>(milliseconds(value.substr(comma+1))/1000000);
        }
        else throw std::invalid_argument("unknown M4 option: "+argument);
    }
    if(config.scenario==simulation::M4Scenario::Fault && config.faults.empty()) throw std::invalid_argument("fault scenario requires fault= recipe");
    if(config.replace_links && !config.recovery_ns) throw std::invalid_argument("replace-links requires recover-ms");
    const auto directory=std::filesystem::path(output);
    if(directory.empty() || std::filesystem::exists(directory)) throw std::invalid_argument("M4 output must be a new directory");
    // Durable grants are consumed before any owner thread/control cycle starts.
    // Missing/corrupt stores fail here; bootstrap is the separate epoch init command.
    const session::EpochStore issuer{store}; config.first_epoch=issuer.issue();
    if(config.scenario==simulation::M4Scenario::OldEpoch && config.first_epoch==1) config.first_epoch=issuer.issue();
    if(config.scenario==simulation::M4Scenario::Rejoin || config.recovery_ns) {
        config.rejoin_epoch=issuer.issue(); if(config.scenario==simulation::M4Scenario::Rejoin) config.duration_ns=4200000000;
    }
    if(config.scenario==simulation::M4Scenario::NormalStop) config.duration_ns=3000000000;
    std::filesystem::create_directories(directory);
    std::ofstream startup(directory/"startup.json");
    startup<<"{\"first_epoch\":"<<config.first_epoch<<",\"rejoin_epoch\":"<<(config.scenario==simulation::M4Scenario::Rejoin || config.recovery_ns?config.rejoin_epoch:0)<<",\"model_epoch\":7}\n";
    startup.close();
    const auto result=simulation::run_m4_async(config); simulation::write_m4_result(config,result,output);
    if(!result.passed) throw std::runtime_error(result.reason);
    std::cout<<"M4_RESULT status=PASS clock="<<clock<<" scenario="<<scenario<<" epoch="<<config.first_epoch<<" output="<<output<<'\n';
}
}  // namespace stratadrive::demo
