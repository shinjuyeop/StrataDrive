#include "vehicle_coordinator_port.hpp"

namespace stratadrive::simulation {
VehicleCoordinatorPort::VehicleCoordinatorPort(const CoordinatorSilParticipants& p):p_(p),front_(p.steering,p.brake),
    stop_(NormalStopLeafParticipants{p.steering,p.brake,p.drive,p.front,p.rear,p.rear_power}) {}
std::uint64_t VehicleCoordinatorPort::now_ns() noexcept { return p_.clock.now_ns(); }
bool VehicleCoordinatorPort::epochs_match(std::uint32_t epoch) const {
    return epoch!=0 && p_.front.scope()==zone::ZoneScope::Front && p_.rear.scope()==zone::ZoneScope::Rear &&
        p_.front.application_epoch()==epoch && p_.rear.application_epoch()==epoch && p_.rear_power.application_epoch()==epoch &&
        p_.steering.application_epoch()==epoch && p_.brake.application_epoch()==epoch && p_.drive.application_epoch()==epoch &&
        p_.power.application_epoch()==epoch && p_.permission.application_epoch()==epoch;
}
bool VehicleCoordinatorPort::healthy(std::uint32_t epoch) noexcept {
    const auto front=p_.front.poll(), rear=p_.rear.poll(); const auto power=p_.rear_power.poll();
    return epochs_match(epoch) && front.safety.cause==zone::ProtectionCause::None && rear.safety.cause==zone::ProtectionCause::None &&
        power.safety.cause==zone::ProtectionCause::None && p_.steering.fault()==vecu::SteeringFault::None &&
        p_.brake.fault()==vecu::BrakeFault::None && p_.drive.decision().fault==vecu::DriveGateFault::None &&
        p_.power.output().fault==vecu::PowerControlFault::None;
}
bool VehicleCoordinatorPort::session_ready(central::CoordinatorSession session) noexcept {
    if(!healthy(session.epoch) || now_ns()<session.enable_ns) return false;
    return p_.front.poll().admission.state==zone::AdmissionState::Idle && p_.rear.poll().admission.state==zone::AdmissionState::Idle &&
        !p_.rear_power.poll().normal_armed && !p_.front.normal_stop_selected() && !p_.rear.normal_stop_selected() && !p_.rear_power.normal_stop_selected();
}
bool VehicleCoordinatorPort::authorize_lifecycle(const central::LifecycleRequest& root) noexcept {
    return p_.rear_power.authorize_request(root)==zone::RearPowerResult::Accepted;
}
bool VehicleCoordinatorPort::authorize_vehicle(const central::VehicleRequest& root) noexcept {
    const auto allowed=[](zone::AdmissionResult result) { return result==zone::AdmissionResult::Accepted || result==zone::AdmissionResult::Unchanged; };
    return allowed(p_.front.authorize_request(root)) && allowed(p_.rear.authorize_request(root));
}
bool VehicleCoordinatorPort::arm(std::uint32_t epoch) noexcept {
    if(!epochs_match(epoch)) return false;
    return front_.arm_commands(p_.front,{epoch,now_ns()}) && p_.rear_power.arm_normal_commands();
}
bool VehicleCoordinatorPort::deliver_power(const central::VehicleManagementOutput& output) noexcept {
    if(p_.rear_power.enqueue_power(output.power_request)!=zone::RearPowerResult::Accepted ||
        p_.rear_power.enqueue_permission(output.drive_permission)!=zone::RearPowerResult::Accepted) return false;
    return p_.rear_power.dispatch()==3U && p_.rear_power.poll().safety.cause==zone::ProtectionCause::None;
}
std::optional<can::BmsCurrentSample> VehicleCoordinatorPort::current_permission() noexcept { return p_.permission.current_sample(now_ns()); }
bool VehicleCoordinatorPort::deliver_commands(const central::AllocatedCommands& commands) noexcept {
    // Independent writes are not atomic. A failure is returned immediately;
    // the owner selects both protections and never retries a normal packet.
    if(p_.front.enqueue(central::front_commands(commands))!=zone::AdmissionResult::Accepted ||
        p_.rear.enqueue(central::rear_commands(commands))!=zone::AdmissionResult::Accepted) return false;
    const auto front=p_.front.dispatch();
    if(front.frames_enqueued!=2U || front.partial_front) return false;
    return p_.rear.dispatch().frames_enqueued==1U;
}
bool VehicleCoordinatorPort::select_stop(const central::NormalStopPlan& plan) noexcept { return stop_.select(plan,now_ns()); }
bool VehicleCoordinatorPort::protect() noexcept {
    stop_.protect(now_ns());
    return p_.front.poll().safety.handoff_accepted && p_.rear.poll().safety.handoff_accepted && p_.rear_power.poll().safety.handoff_accepted;
}
}  // namespace stratadrive::simulation
