#pragma once

#include "local_safety.hpp"
#include "steering_actuator.hpp"
#include "brake_actuator.hpp"
#include "drive_controller.hpp"

namespace stratadrive::simulation {
// Explicit same-host SIL connection. No remote CAN protection protocol or plant
// writes: each Leaf selects its own existing Hold / Protect / Zero output.
class ZoneLeafProtection final : public zone::ProtectionPort {
public:
    ZoneLeafProtection(vecu::SteeringActuator& steering, vecu::BrakeActuator& brake) : steering_(&steering), brake_(&brake) {}
    explicit ZoneLeafProtection(vecu::DriveController& drive) : drive_(&drive) {}
    bool protect(zone::ZoneScope scope, zone::ProtectionCause cause, std::uint64_t now_ns) noexcept override;
private:
    vecu::SteeringActuator* steering_{nullptr};
    vecu::BrakeActuator* brake_{nullptr};
    vecu::DriveController* drive_{nullptr};
};
}  // namespace stratadrive::simulation
