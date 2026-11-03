#pragma once
#include "diagnostics.hpp"
#include "speed_request.hpp"
#include "vehicle_coordinator.hpp"

namespace stratadrive::diagnostics {
// v1 numeric dictionary, not CAN IDs or producer identities.
enum class Component : std::uint32_t { Speed=1, Stop=2, Coordinator=3, Drive=4, Brake=5, Power=6, Front=7, Rear=8, Steering=9, Bms=10, DriveWheel=11 };
enum class Monitor : std::uint32_t { Speed=1, Stop=2, Coordinator=3 };
enum class Subject : std::uint32_t { Wheel=1, StopCycle=2, Handoff=3, Protection=4, Torque=5, Pressure=6, Power=7 };
struct ControlContext {
    std::uint64_t run,producer;
    Domain domain;
    std::uint64_t clock_instance,profile;
};
// Called by the single Central owner after its existing control/protection work.
// Reads immutable source snapshots; only publishes bounded queue copies. No
// file IO, allocation, actuator writes, invented clocks or implicit INIT/clear.
class ControlDiagnostics {
public:
    ControlDiagnostics(EventQueue&,ControlContext);
    bool start_session(std::uint32_t epoch,std::uint64_t enable_ns) noexcept;
    void observe(const central::SpeedRequest&,const central::VehicleCoordinator&,std::uint64_t observed_ns) noexcept;
    void observe(const central::SpeedRequest&,std::uint64_t observed_ns) noexcept;
    void observe(const central::NormalStop&,std::uint64_t observed_ns) noexcept;
    // Trusted original local-owner selection/ACK evidence, never a Central
    // poll timestamp. actor_roles uses existing 8-role session bit positions.
    void local_protection(Component actor,std::uint32_t actor_roles,std::uint32_t epoch,
                          std::uint64_t original_ns,bool acknowledgement) noexcept;
    void observe_response(const central::NormalDriveReadinessInputs&,std::uint64_t observed_ns) noexcept;
    bool healthy() const noexcept { return healthy_; }
private:
    Stamp stamp(std::uint64_t,bool trusted=true) const noexcept;
    Event base(std::uint64_t observed_ns) const noexcept;
    EventId publish(Event) noexcept;
    void speed(const central::SpeedRequest&,const std::optional<central::VehicleRequest>&,std::uint64_t) noexcept;
    void stop(const central::NormalStop&,std::uint64_t) noexcept;
    void coordinator(const central::VehicleCoordinator&,std::uint64_t) noexcept;
    void actuals(const central::NormalStopObservation&,const Event&,EventId,std::uint64_t) noexcept;
    EventQueue& queue_; const ControlContext context_;
    Session session_{}; std::uint64_t enable_{0},next_{1}; bool healthy_{true};
    bool speed_seen_{false},coordinator_seen_{false},response_seen_{false};
    std::array<bool,2> stop_seen_{},protection_seen_{}; std::array<bool,4> phase_seen_{};
    Event root_{};
};
} // namespace stratadrive::diagnostics
