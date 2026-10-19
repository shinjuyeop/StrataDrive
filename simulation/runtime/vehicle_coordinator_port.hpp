#pragma once

#include "vehicle_coordinator.hpp"
#include "normal_stop_control.hpp"
#include "front_startup_control.hpp"
#include "power_controller.hpp"

namespace stratadrive::simulation {
struct CoordinatorSilParticipants {
    vecu::SteeringActuator& steering; vecu::BrakeActuator& brake; vecu::DriveController& drive; vecu::PowerController& power;
    zone::CommandGateway& front; zone::CommandGateway& rear; zone::RearPowerGateway& rear_power;
    can::BmsReceiver& permission; zone::GatewayPort& clock;
};
// Same-host binding, no plant ownership or packet-created INIT. All actual
// CAN writes still go through the independent Zone gateways and Leaf receivers.
class VehicleCoordinatorPort final : public central::CoordinatorPort {
public:
    explicit VehicleCoordinatorPort(const CoordinatorSilParticipants& participants);
    std::uint64_t now_ns() noexcept override;
    bool session_ready(central::CoordinatorSession session) noexcept override;
    bool healthy(std::uint32_t epoch) noexcept override;
    bool authorize_lifecycle(const central::LifecycleRequest& root) noexcept override;
    bool authorize_vehicle(const central::VehicleRequest& root) noexcept override;
    bool arm(std::uint32_t epoch) noexcept override;
    bool deliver_power(const central::VehicleManagementOutput& output) noexcept override;
    std::optional<can::BmsCurrentSample> current_permission() noexcept override;
    bool deliver_commands(const central::AllocatedCommands& commands) noexcept override;
    bool select_stop(const central::NormalStopPlan& plan) noexcept override;
    bool protect() noexcept override;
private:
    bool epochs_match(std::uint32_t epoch) const;
    CoordinatorSilParticipants p_;
    FrontStartupControl front_;
    NormalStopControl stop_;
};
}  // namespace stratadrive::simulation
