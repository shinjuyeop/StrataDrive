#pragma once

#include "actuator_session.hpp"
#include "actuator_stop_lease.hpp"

#include "brake_receiver.hpp"
#include "brake_actuation.hpp"
#include "brake_response_monitor.hpp"

#include <cstdint>
#include <optional>

namespace stratadrive::vecu {
struct BrakeActuatorConfig {
    double command_max_pa;
    double max_pressure_pa;
    double initial_pressure_pa; // fixture metadata; only the SIL plant applies it
    double rise_rate_pa_s;          // nominal 가압 속도, Pa/s
    double fall_rate_pa_s;          // nominal 감압 속도, Pa/s
    double fault_pressure_floor_pa; // fault 시 max(현재 압력, 이 값); 시험용 보호 설정
    std::uint64_t delay_ns;
    std::uint64_t period_ns{10000000};
    std::uint64_t max_tick_gap_ns{30000000};
    std::uint64_t max_source_age_ns{30000000};
    std::uint64_t timeout_ns{80000000};
    double healthy_min_rate_fraction{0.8}, healthy_max_rate_fraction{1.2}, response_tolerance_pa{25000};
    std::uint64_t response_confirmation_ns{60000000}, sensor_age_ns{20000000};
};
enum class BrakeFault { None, CommandUnavailable, ContinuityLost, ClockError, ControlDeadline,
    SensorUnavailable, SensorInvalid, ResponseError, PhysicalModelError, UpstreamProtection, StopLeaseExpired, NormalStopInvalid };

// ECU logic only: receiver, monitor, selected output and CAN publication.
// prepare/complete delimit one externally clocked job. Physics and acquisition
// run outside this object; use simulation's SIL runner for the legacy fixture.
class BrakeActuator {
public:
    explicit BrakeActuator(BrakeActuatorConfig config);
    bool start_session(ActuatorSession session, ActuatorCommandStartup startup = ActuatorCommandStartup::Immediate);
    bool can_arm_normal_commands(std::uint64_t now_ns);
    bool select_normal_stop(const ActuatorStopLease& lease, std::uint64_t now_ns);
    bool normal_stop_selected() const { return stop_.active(); }
    bool arm_normal_commands(std::uint64_t now_ns); // trusted local coordinator only
    std::uint32_t application_epoch() const { return epoch_; }
    can::BrakeReceiveResult receive(const can::BrakeFrame& frame, std::uint64_t now_ns);
    void mark_continuity_lost(std::uint64_t now_ns);
    void request_local_protection(std::uint64_t now_ns); // trusted local port, not a pressure command
    // prepare checks clock/period/communication before external actuation.
    // complete accepts a sensor snapshot for that same time, then selects the
    // next output. No physics, sensor generation or implicit 0 fallback here.
    bool prepare(std::uint64_t now_ns);
    std::optional<can::BrakeFrame> complete(const std::optional<brake::PressureMeasurement>& sensor, std::uint64_t now_ns);
    void mark_io_error(std::uint64_t now_ns);
    void mark_output_rejected(std::uint64_t now_ns);
    const brake::Actuation& output() const { return output_; }
    bool execution_gap() const { return execution_gap_; }
    const BrakeMonitorDecision& monitor_decision() const { return monitor_.decision(); }
    // Only a fresh valid acquisition can report whether the requested floor is
    // observed. A request or modeled truth does not establish physical success.
    std::optional<bool> protection_floor_observed() const { return floor_observed_; }
    BrakeFault fault() const { return fault_; }
    // Current command snapshot for ingress diagnostics; not actuator feedback.
    std::optional<can::BrakeMessage> current_sample(std::uint64_t now_ns);
    const can::BrakeReceiver& receiver() const { return receiver_; }
private:
    bool clock(std::uint64_t now_ns);
    void fail(BrakeFault fault, std::uint64_t now_ns);
    const BrakeActuatorConfig config_;
    can::BrakeReceiver receiver_;
    can::BrakeTxState tx_{can::BrakeFrameKind::Actual};
    BrakeResponseMonitor monitor_;
    std::optional<bool> floor_observed_;
    std::uint32_t epoch_{0}, sequence_{0};
    std::uint64_t last_tick_ns_{0}, last_observed_ns_{0};
    bool command_monitoring_{true};
    StopLeaseState stop_;
    bool sequence_exhausted_{false};
    brake::Actuation output_{};
    std::optional<std::uint64_t> prepared_ns_;
    bool execution_gap_{false};
    BrakeFault fault_{BrakeFault::None};
};
}  // namespace stratadrive::vecu
