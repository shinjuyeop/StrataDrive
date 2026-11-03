#include "m4_owner_network.hpp"

namespace stratadrive::simulation::m4_detail {
namespace {
double target(std::uint64_t ns) {
    const double t=static_cast<double>(ns)*1e-9;
    if(t<20) return (30/3.6)*t/20;
    if(t<35) return 30/3.6;
    if(t<43) return 30/3.6-(10/3.6)*(t-35)/8;
    if(t<58) return 20/3.6;
    if(t<72) return (20/3.6)*(72-t)/14;
    return 0;
}
}
void Network::speed_step(std::uint64_t now) {
    if(!result.speed_origin_ns) result.speed_origin_ns=now;
    const auto elapsed=now-result.speed_origin_ns;
    const auto in=port.feedback();
    const auto permission=port.current_permission();
    const auto* grant=permission?std::get_if<can::BmsDriveGrant>(&permission->message.content):nullptr;
    const bool permitted=permission && permission->message.epoch==active_epoch && grant &&
        grant->permission==can::BmsDrivePermission::AllowNormal && now<grant->expires_at_ns &&
        gate.allows(active_epoch) && core.decision().management.normal_allowed &&
        core.decision().fault==central::CoordinatorFault::None;
    const bool input_loss=config.scenario==M4Scenario::SpeedInputLoss && now-start>=config.injection_ns;
    const auto request=speed_control.step(now,target(elapsed),input_loss?std::nullopt:in.rear.drive_actual,permitted);
    next_speed_ns=now+central::SpeedPI::kPeriodNs;
    result.speed_fault=static_cast<int>(speed_control.fault());
    if(!request) { core.request_protection(now); return; }
    const auto received=core.receive_vehicle(*request,now);
    if(received!=central::CoordinatorReceive::Accepted) { core.request_protection(now); return; }
    last_vehicle=now;
    const auto& state=speed_control.state();
    result.speed_trace.push_back({now,elapsed,request->source_time_ns,request->expires_at_ns,
        request->epoch,request->sequence,target(elapsed),state.sample->speed_mps,
        request->acceleration_mps2,state.integral});
}
} // namespace stratadrive::simulation::m4_detail
