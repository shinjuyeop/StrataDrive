#include "demo_commands.hpp"
#include "m4_async_runtime.hpp"
#include "epoch_store.hpp"

#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>

namespace stratadrive::demo {
void demo_m4_async(const M4DemoOptions& options) {
    const auto& [clock,scenario,store,output]=options;
    simulation::M4Config config;
    if(clock!="logical" && clock!="wall") throw std::invalid_argument("M4 clock must be logical or wall");
    config.wall_time=clock=="wall"; bool found=false;
    for(const auto candidate:{simulation::M4Scenario::Normal,simulation::M4Scenario::NormalStop,simulation::M4Scenario::PartialFront,
        simulation::M4Scenario::FeedbackLoss,simulation::M4Scenario::CommandLoss,simulation::M4Scenario::PartialArm,
        simulation::M4Scenario::Rejoin,simulation::M4Scenario::OldEpoch}) {
        if(scenario==simulation::m4_scenario_name(candidate)) { config.scenario=candidate; found=true; }
    }
    if(!found) throw std::invalid_argument("unknown M4 scenario");
    const auto directory=std::filesystem::path(output);
    if(directory.empty() || std::filesystem::exists(directory)) throw std::invalid_argument("M4 output must be a new directory");
    // Durable grants are consumed before any owner thread/control cycle starts.
    // Missing/corrupt stores fail here; bootstrap is the separate epoch init command.
    const session::EpochStore issuer{store}; config.first_epoch=issuer.issue();
    if(config.scenario==simulation::M4Scenario::OldEpoch && config.first_epoch==1) config.first_epoch=issuer.issue();
    if(config.scenario==simulation::M4Scenario::Rejoin) { config.rejoin_epoch=issuer.issue(); config.duration_ns=4200000000; }
    if(config.scenario==simulation::M4Scenario::NormalStop) config.duration_ns=3000000000;
    std::filesystem::create_directories(directory);
    std::ofstream startup(directory/"startup.json");
    startup<<"{\"first_epoch\":"<<config.first_epoch<<",\"rejoin_epoch\":"<<(config.scenario==simulation::M4Scenario::Rejoin?config.rejoin_epoch:0)<<",\"model_epoch\":7}\n";
    startup.close();
    const auto result=simulation::run_m4_async(config); simulation::write_m4_result(config,result,output);
    if(!result.passed) throw std::runtime_error(result.reason);
    std::cout<<"M4_RESULT status=PASS clock="<<clock<<" scenario="<<scenario<<" epoch="<<config.first_epoch<<" output="<<output<<'\n';
}
}  // namespace stratadrive::demo
