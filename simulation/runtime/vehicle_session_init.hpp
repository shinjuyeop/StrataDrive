#pragma once

#include "session_participant.hpp"
#include "vehicle_coordinator_port.hpp"
#include "rear_power_control.hpp"
#include "zone_feedback_monitor.hpp"
#include "bms_controller.hpp"

namespace stratadrive::simulation {
struct SessionResetEvidence {
    std::optional<battery::ModelMeasurement<double>> wheel_speed_rad_s;
    std::optional<drive::TorqueMeasurement> torque;
    std::optional<power::SensorSnapshot> power;
};
// Functional SIL reset preconditions, not production vehicle calibration.
// Each acquisition retains its own source/dependency time and model identity.
bool session_reset_safe(const SessionResetEvidence& evidence,std::uint32_t model_epoch,std::uint64_t now_ns);
class SessionRecoveryPort {
public:
    virtual ~SessionRecoveryPort() = default;
    virtual std::uint64_t now_ns() noexcept = 0;
    // Own-role normal ingress must be closed and queued old work flushed before
    // returning true. Never reset a fault/plant to manufacture safe evidence.
    virtual bool quiesce(session::Role role) noexcept = 0;
    virtual SessionResetEvidence evidence() noexcept = 0;
    virtual void protect(session::Role role) noexcept = 0;
    virtual void service(session::Role role) noexcept = 0;
};
struct SessionInitParticipants {
    CoordinatorSilParticipants actors;
    vecu::BmsController& bms;
    RearPowerControl& rear_control;
    zone::ZoneFeedbackMonitor& front_monitor; zone::ZoneFeedbackMonitor& rear_monitor;
    can::SteeringReceiver& steering_actual; can::BrakeReceiver& brake_actual; can::DriveReceiver& drive_actual;
    zone::ZoneStatusReceiver& front_status; zone::ZoneStatusReceiver& rear_status;
};
// Actual same-host initialization binding. Each invocation accesses only its
// role's mutable state. The existing synchronous normal CoordinatorSilParticipants
// must remain serialized; this adapter does not make normal control thread-safe.
class VehicleSessionInit final : public session::ParticipantPort {
public:
    VehicleSessionInit(session::Role role,std::uint32_t model_epoch,const SessionInitParticipants& participants,SessionRecoveryPort& port)
        :role_(role),model_epoch_(model_epoch),p_(participants),port_(port) {}
    std::uint64_t now_ns() noexcept override { return port_.now_ns(); }
    session::Preparation prepare(const session::Plan& plan) noexcept override;
    bool initialize(const session::Plan& plan) noexcept override;
    void protect() noexcept override { port_.protect(role_); }
    void service() noexcept override { port_.service(role_); }
private:
    session::Role role_; std::uint32_t model_epoch_;
    SessionInitParticipants p_; SessionRecoveryPort& port_;
};
}  // namespace stratadrive::simulation
