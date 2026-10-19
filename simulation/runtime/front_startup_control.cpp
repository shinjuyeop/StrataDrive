#include "front_startup_control.hpp"

#include <algorithm>

namespace stratadrive::simulation {
bool FrontStartupControl::arm_commands(zone::CommandGateway& gateway, const FrontArmContext& context) {
    const auto epoch = context.application_epoch;
    const auto now = context.now_ns;
    if (epoch == 0 || gateway.scope() != zone::ZoneScope::Front || gateway.application_epoch() != epoch ||
        steering_.application_epoch() != epoch || brake_.application_epoch() != epoch) return false;
    const bool steering_ready = steering_.can_arm_normal_commands(now);
    const bool brake_ready = brake_.can_arm_normal_commands(now);
    // poll/arm may already call the protection port at a later clock reading.
    // Never follow that handoff with a Leaf callback carrying the older context time.
    const auto state = gateway.poll();
    const auto protect_front = [&] {
        protect(zone::ZoneScope::Front, zone::ProtectionCause::CoordinatorRequest, std::max(now, gateway.observed_time_ns()));
        gateway.request_protection();
    };
    if (state.safety.cause != zone::ProtectionCause::None || steering_.fault() != vecu::SteeringFault::None ||
        brake_.fault() != vecu::BrakeFault::None) {
        protect_front();
        return false;
    }
    if (state.admission.state != zone::AdmissionState::Idle || !steering_ready || !brake_ready) return false;
    if (!gateway.arm() || !steering_.arm_normal_commands(now) || !brake_.arm_normal_commands(now)) {
        // Preflight cannot make three independent transitions atomic. Never leave
        // a partially armed Front normal path running if any commit fails.
        protect_front();
        return false;
    }
    return true;
}
}  // namespace stratadrive::simulation
