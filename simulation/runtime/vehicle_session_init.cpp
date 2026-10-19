#include "vehicle_session_init.hpp"

#include <cmath>

namespace stratadrive::simulation {
namespace {
constexpr std::uint64_t kEvidenceAgeNs=20000000ULL;
bool fresh(std::uint64_t source,std::uint64_t input,std::uint64_t now) {
    return input<=source && source<=now && now-input<=kEvidenceAgeNs;
}
}
bool session_reset_safe(const SessionResetEvidence& e,std::uint32_t model_epoch,std::uint64_t now) {
    if(model_epoch==0 || !e.wheel_speed_rad_s || !e.torque || !e.power) return false;
    const auto& speed=*e.wheel_speed_rad_s; const auto& torque=*e.torque; const auto& power=*e.power;
    if(speed.identity.epoch!=model_epoch || torque.model_epoch!=model_epoch || power.identity.epoch!=model_epoch ||
        !fresh(speed.identity.source_time_ns,speed.input_time_ns,now) || !fresh(torque.source_time_ns,torque.source_time_ns,now) ||
        !fresh(power.identity.source_time_ns,power.input_time_ns,now)) return false;
    return std::isfinite(speed.value) && speed.value>=0 && speed.value<=.01 &&
        std::isfinite(torque.torque_nm) && std::abs(torque.torque_nm)<=.1 && power.bus_voltage_v &&
        std::isfinite(*power.bus_voltage_v) && *power.bus_voltage_v>=0 && *power.bus_voltage_v<=30 && power.contactors &&
        !power.contactors->positive && !power.contactors->negative && !power.contactors->precharge;
}
session::Preparation VehicleSessionInit::prepare(const session::Plan&) noexcept {
    if(!port_.quiesce(role_)) return session::Preparation::Rejected;
    return session_reset_safe(port_.evidence(),model_epoch_,now_ns())?session::Preparation::Ready:session::Preparation::Pending;
}
bool VehicleSessionInit::initialize(const session::Plan& plan) noexcept {
    // Prepared evidence is not a capability: read the current independent
    // sensors again at the actual enable boundary, without changing timestamps.
    if(!session_reset_safe(port_.evidence(),model_epoch_,now_ns())) return false;
    const ActuatorSession mapping{plan.epoch,model_epoch_,plan.enable_ns};
    switch(role_) {
    case session::Role::FrontZone:
        return p_.actors.front.start_session(plan.epoch,plan.enable_ns) && p_.front_monitor.start_session(plan.epoch,plan.enable_ns);
    case session::Role::RearZone:
        return p_.actors.rear.start_session(plan.epoch,plan.enable_ns) && p_.actors.rear_power.start_session(plan.epoch,plan.enable_ns) &&
            p_.rear_control.start_session(plan.epoch) && p_.rear_monitor.start_session(plan.epoch,plan.enable_ns);
    case session::Role::Steering: return p_.actors.steering.start_session(mapping,ActuatorCommandStartup::NonDriving);
    case session::Role::Brake: return p_.actors.brake.start_session(mapping,ActuatorCommandStartup::NonDriving);
    case session::Role::Drive: return p_.actors.drive.start_session(mapping,vecu::DriveCommandStartup::NonDriving);
    case session::Role::Bms: return p_.bms.start_session(plan.epoch,model_epoch_,plan.enable_ns);
    case session::Role::Power: return p_.actors.power.start_session(plan.epoch,model_epoch_,plan.enable_ns);
    case session::Role::CentralIngress:
        return p_.actors.permission.start_session(plan.epoch,plan.enable_ns) && p_.steering_actual.start_session(plan.epoch,plan.enable_ns) &&
            p_.brake_actual.start_session(plan.epoch,plan.enable_ns) && p_.drive_actual.start_session(plan.epoch,plan.enable_ns) &&
            p_.front_status.start_session(plan.epoch,plan.enable_ns) && p_.rear_status.start_session(plan.epoch,plan.enable_ns);
    case session::Role::Count: return false;
    }
    return false;
}
}  // namespace stratadrive::simulation
