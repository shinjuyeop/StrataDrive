#pragma once

#include "command_gateway.hpp"
#include "zone_leaf_protection.hpp"

namespace stratadrive::simulation {
struct FrontArmContext { std::uint32_t application_epoch; std::uint64_t now_ns; };
// Single-owner same-host coordinator binding. No CAN packet can invoke this.
// The caller still checks Central readiness/permission and owns INIT/recovery.
class FrontStartupControl final : public zone::ProtectionPort {
public:
    FrontStartupControl(vecu::SteeringActuator& steering, vecu::BrakeActuator& brake)
        : steering_(steering), brake_(brake), protection_(steering, brake) {}
    bool arm_commands(zone::CommandGateway& gateway, const FrontArmContext& context);
    bool protect(zone::ZoneScope scope, zone::ProtectionCause cause, std::uint64_t now_ns) noexcept override {
        return protection_.protect(scope, cause, now_ns);
    }
private:
    vecu::SteeringActuator& steering_;
    vecu::BrakeActuator& brake_;
    ZoneLeafProtection protection_;
};
}  // namespace stratadrive::simulation
