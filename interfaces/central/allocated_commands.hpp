#pragma once

#include "steering_frame_codec.hpp"
#include "brake_frame_codec.hpp"
#include "drive_frame_codec.hpp"

#include <variant>
#include <optional>

namespace stratadrive::central {
// Historical successful Central allocation, not actuator Actual or permission.
// Used only for directional anti-windup on the next control release. The
// historical type/positive flag names are retained; neither grants authority.
struct PropulsionSelection {
    std::uint32_t epoch, request_sequence;
    std::uint64_t selection_ns;
    double requested_acceleration_mps2, requested_propulsion_nm, selected_propulsion_nm;
    bool limited;
    double requested_braking_nm{0}, selected_braking_nm{0};
    bool braking_limited{false};
};
// Shared in-process contracts. These are not DDS IDL or a CAN wire extension.
// Target speed remains upstream; allocation consumes its bounded acceleration.
struct VehicleRequest {
    std::uint32_t epoch{0}, sequence{0};
    std::uint64_t source_time_ns{0}, expires_at_ns{0};
    double acceleration_mps2{0}, curvature_inv_m{0}, braking_demand{0};
    bool standstill_hold{false}; // explicit request, not inferred from zero acceleration
};
// Trusted in-process provenance of a computed request. It is carried to remote
// owners by CommandContext.oldest_input_time_ns / expires_at_ns, not a new wire
// field. Request generation never refreshes this original acquisition.
struct PowerInputDependency {
    std::uint64_t source_time_ns{0}, expires_at_ns{0};
};
struct VehicleInputDependency {
    std::uint64_t source_time_ns{0}, expires_at_ns{0};
    // Optional original BMS physical dependency: separate from the unchanged
    // 30ms speed/route acquisition gate; BMS already has a 70ms input contract.
    std::optional<PowerInputDependency> power{};
};
struct DerivedVehicleRequest {
    VehicleRequest request;
    VehicleInputDependency input;
};
inline bool same_vehicle_request(const VehicleRequest& a, const VehicleRequest& b) {
    return a.epoch == b.epoch && a.sequence == b.sequence && a.source_time_ns == b.source_time_ns &&
        a.expires_at_ns == b.expires_at_ns && a.acceleration_mps2 == b.acceleration_mps2 &&
        a.curvature_inv_m == b.curvature_inv_m && a.braking_demand == b.braking_demand && a.standstill_hold == b.standstill_hold;
}
struct CommandContext {
    // Mandatory sideband: legacy 32-byte actuator CAN does not encode it.
    VehicleRequest parent; // vehicle root, distinct from lifecycle permission root
    std::uint64_t oldest_input_time_ns{0}, expires_at_ns{0};
};
struct AllocatedCommands : CommandContext {
    can::SteeringMessage steering;
    can::BrakeMessage brake;
    can::DriveMessage drive;
};
struct FrontCommands : CommandContext {
    can::SteeringMessage steering;
    can::BrakeMessage brake; // atomic pair from one allocation
};
struct RearCommands : CommandContext {
    can::DriveMessage drive;
};
using ScopedCommands = std::variant<FrontCommands, RearCommands>;
inline FrontCommands front_commands(const AllocatedCommands& commands) {
    return {static_cast<const CommandContext&>(commands), commands.steering, commands.brake};
}
inline RearCommands rear_commands(const AllocatedCommands& commands) {
    return {static_cast<const CommandContext&>(commands), commands.drive};
}
}  // namespace stratadrive::central
