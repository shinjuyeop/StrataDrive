#pragma once
#include "allocated_commands.hpp"
#include "power_commands.hpp"
#include "actuator_stop_lease.hpp"

namespace stratadrive::central {
struct NormalStopRequest { can::BmsParentContext identity; double curvature_inv_m{0}; };
enum class NormalStopState { NotInitialized, Waiting, Braking, HandoffPending, PowerDown, Complete, FailSafe };
struct NormalStopPlan {
    NormalStopState state;
    NormalStopRequest ancestor; // original stop authority; child generation cannot extend it
    LifecycleRequest lifecycle;
    std::optional<VehicleRequest> vehicle;
    ActuatorStopLease lease;
    bool handoff_required{false};
};
} // namespace stratadrive::central
