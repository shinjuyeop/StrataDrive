#include "m4_owner_network.hpp"

namespace stratadrive::simulation {
M4Result run_m4_async(const M4Config& config) {
    if(config.duration_ns==0 || config.first_epoch==0 || (config.scenario==M4Scenario::Rejoin && config.rejoin_epoch<=config.first_epoch)) throw std::invalid_argument("M4 run configuration");
    for(const auto& f:config.faults) {
        validate_fault(f);
        if(f.target==M4Owner::Monitor && !config.execution_guards) throw std::invalid_argument("monitor injection requires execution guards");
    }
    if((!config.wall_time && (config.fifo || config.cpu_a>=0 || config.cpu_b>=0)) || config.cpu_a < -1 || config.cpu_b < -1) throw std::invalid_argument("native placement requires wall clock");
    if(config.startup_diagnostics_run && (config.wall_time || !config.speed_loop ||
       (config.scenario!=M4Scenario::Normal && config.scenario!=M4Scenario::Fault) || config.diagnostics_run || config.owner_diagnostics_run || config.native_diagnostics_run))
        throw std::invalid_argument("M9 startup diagnostics configuration");
    const bool native_loss=config.scenario==M4Scenario::BmsInputLoss || config.scenario==M4Scenario::PowerInputLoss;
    if(config.speed_loop && (config.wall_time || config.renewal!=central::CommandRenewal::Host10ms ||
       (config.scenario!=M4Scenario::Normal && config.scenario!=M4Scenario::FeedbackLoss && config.scenario!=M4Scenario::CommandLoss && config.scenario!=M4Scenario::SpeedInputLoss && config.scenario!=M4Scenario::Fault && !native_loss))) throw std::invalid_argument("M8 logical speed-loop configuration");
    if(config.owner_diagnostics_run && (config.wall_time || !config.speed_loop ||
       (config.scenario!=M4Scenario::Normal && config.scenario!=M4Scenario::Fault) ||
       (config.diagnostics_run && config.diagnostics_run!=config.owner_diagnostics_run))) throw std::invalid_argument("M9 local diagnostics configuration");
    if(config.native_diagnostics_run && (config.wall_time || !config.speed_loop ||
       (config.scenario!=M4Scenario::Normal && config.scenario!=M4Scenario::Fault && !native_loss) ||
       (config.diagnostics_run && config.diagnostics_run!=config.native_diagnostics_run) ||
       (config.owner_diagnostics_run && config.owner_diagnostics_run!=config.native_diagnostics_run))) throw std::invalid_argument("M9 native diagnostics configuration");
    if((config.diagnostics_run && config.wall_time) || (config.scenario==M4Scenario::SpeedInputLoss && (!config.speed_loop || !config.injection_ns || config.injection_ns>=config.duration_ns))) throw std::invalid_argument("M9 logical diagnostics configuration");
    if(config.diagnostics_run && config.scenario!=M4Scenario::Normal && config.scenario!=M4Scenario::NormalStop && config.scenario!=M4Scenario::SpeedInputLoss) throw std::invalid_argument("M9 diagnostic scenario scope");
    if((config.speed_input_restore_ns || config.speed_input_reinject_ns) &&
       (config.scenario!=M4Scenario::SpeedInputLoss || config.wall_time || !config.speed_input_restore_ns ||
        config.speed_input_restore_ns<=config.injection_ns || config.speed_input_restore_ns>=config.duration_ns ||
        (config.speed_input_reinject_ns && (config.speed_input_reinject_ns<=config.speed_input_restore_ns || config.speed_input_reinject_ns>=config.duration_ns)))) throw std::invalid_argument("M9 speed input windows");
    if((native_loss && (config.wall_time || !config.speed_loop || !config.faults.empty() || !config.injection_ns || config.injection_ns>=config.duration_ns ||
        (config.native_input_restore_ns && (config.native_input_restore_ns<=config.injection_ns || config.native_input_restore_ns>=config.duration_ns)) ||
        (config.recovery_ns && (!config.native_input_restore_ns || config.native_input_restore_ns>=config.recovery_ns)))) ||
       (!native_loss && config.native_input_restore_ns)) throw std::invalid_argument("M9 native input window");
    if(config.duration_ns>(config.speed_loop?95000000000ULL:10000000000ULL) || (config.scenario==M4Scenario::Fault && config.faults.empty()) ||
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
    case M4Scenario::SpeedInputLoss: return "speed-input-loss";
    case M4Scenario::BmsInputLoss: return "bms-input-loss"; case M4Scenario::PowerInputLoss: return "power-input-loss";
    }
    return "invalid";
}
} // namespace stratadrive::simulation
