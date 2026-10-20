#include "m4_owner_network.hpp"

namespace stratadrive::simulation {
M4Result run_m4_async(const M4Config& config) {
    if(config.duration_ns==0 || config.first_epoch==0 || (config.scenario==M4Scenario::Rejoin && config.rejoin_epoch<=config.first_epoch)) throw std::invalid_argument("M4 run configuration");
    for(const auto& f:config.faults) {
        validate_fault(f);
        if(f.target==M4Owner::Monitor && !config.execution_guards) throw std::invalid_argument("monitor injection requires execution guards");
    }
    if((!config.wall_time && (config.fifo || config.cpu_a>=0 || config.cpu_b>=0)) || config.cpu_a < -1 || config.cpu_b < -1) throw std::invalid_argument("native placement requires wall clock");
    if(config.duration_ns>10000000000ULL || (config.scenario==M4Scenario::Fault && config.faults.empty()) ||
       (config.recovery_ns && (config.rejoin_epoch<=config.first_epoch || config.recovery_ns>=config.duration_ns))) throw std::invalid_argument("M4 fault/recovery configuration");
    auto network=std::make_unique<m4_detail::Network>(config);
    if(config.wall_time) m4_detail::execute_native(*network); else m4_detail::execute_logical(*network);
    return network->finish();
}
const char* m4_scenario_name(M4Scenario s) {
    switch(s) {
    case M4Scenario::Normal: return "normal"; case M4Scenario::NormalStop: return "normal-stop";
    case M4Scenario::PartialFront: return "partial-front"; case M4Scenario::FeedbackLoss: return "feedback-loss";
    case M4Scenario::CommandLoss: return "command-loss"; case M4Scenario::PartialArm: return "partial-arm";
    case M4Scenario::Rejoin: return "rejoin"; case M4Scenario::OldEpoch: return "old-epoch"; case M4Scenario::Fault: return "fault";
    }
    return "invalid";
}
} // namespace stratadrive::simulation
