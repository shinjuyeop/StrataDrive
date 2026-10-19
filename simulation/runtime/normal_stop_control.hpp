#pragma once

#include "normal_stop.hpp"
#include "control_allocation.hpp"
#include "command_gateway.hpp"
#include "rear_power_gateway.hpp"
#include "steering_actuator.hpp"
#include "brake_actuator.hpp"
#include "drive_controller.hpp"

namespace stratadrive::simulation {
struct NormalStopParticipants {
    vecu::SteeringActuator& steering; vecu::BrakeActuator& brake; vecu::DriveController& drive;
    zone::CommandGateway& front; zone::CommandGateway& rear; zone::RearPowerGateway& power;
    central::ControlAllocation& allocation;
};
struct NormalStopLeafParticipants {
    vecu::SteeringActuator& steering; vecu::BrakeActuator& brake; vecu::DriveController& drive;
    zone::CommandGateway& front; zone::CommandGateway& rear; zone::RearPowerGateway& power;
};
// Trusted same-host single owner. Output-selection ACK, not physical completion.
class NormalStopControl {
public:
    explicit NormalStopControl(const NormalStopParticipants& p):p_{p.steering,p.brake,p.drive,p.front,p.rear,p.power},allocation_(&p.allocation) {}
    // The owning Central coordinator quiesces its private allocator itself.
    explicit NormalStopControl(const NormalStopLeafParticipants& p):p_(p) {}
    bool select(const central::NormalStopPlan& plan,std::uint64_t now_ns);
    void protect(std::uint64_t now_ns);
private:
    std::uint64_t observed(std::uint64_t now_ns) const;
    NormalStopLeafParticipants p_;
    central::ControlAllocation* allocation_{nullptr};
};
} // namespace stratadrive::simulation
