#include "vehicle_session_init.hpp"

namespace stratadrive::simulation {
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
