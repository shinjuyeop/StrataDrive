#pragma once

#include "brake_receiver.hpp"
#include "brake_pressure_response.hpp"
#include "brake_response_monitor.hpp"

#include <cstdint>
#include <optional>

namespace stratadrive::vecu {
struct BrakeActuatorConfig {
    double command_max_pa;
    double max_pressure_pa;
    double initial_pressure_pa;
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
    SensorUnavailable, SensorInvalid, ResponseError, PhysicalModelError };

// Single-owner functional SIL composition, not an OS task/production SWC.
// Plant, acquisition and local monitoring are separate. The monitor sees only
// issued targets and typed sensors, never physical truth or injection flags.
class BrakeActuator {
public:
    explicit BrakeActuator(BrakeActuatorConfig config);
    bool start_session(std::uint32_t epoch, std::uint64_t enable_ns);
    can::BrakeReceiveResult receive(const can::BrakeFrame& frame, std::uint64_t now_ns);
    void mark_continuity_lost(std::uint64_t now_ns);
    // At most one publication per period. A missed control deadline holds the
    // pressure rather than catching up physics. No output with an untrusted clock.
    // Injection covers the elapsed physical interval; sensor action/override
    // applies to the end acquisition. These are explicit SIL fixture inputs.
    std::optional<can::BrakeFrame> tick(std::uint64_t now_ns,
        const simulation::BrakePressureResponseInjection& injection = {},
        simulation::BrakeSensorAction sensor_action = simulation::BrakeSensorAction::Acquire,
        std::optional<double> sensed_pressure_override = std::nullopt);
    double actual_pressure_pa() const { return response_.actual_pressure_pa(); } // diagnostics only
    const BrakeMonitorDecision& monitor_decision() const { return monitor_.decision(); }
    // Only a fresh valid acquisition can report whether the requested floor is
    // observed. A request or modeled truth does not establish physical success.
    std::optional<bool> protection_floor_observed() const { return floor_observed_; }
    BrakeFault fault() const { return fault_; }
    // Current command snapshot for ingress diagnostics; not actuator feedback.
    std::optional<can::BrakeMessage> current_sample(std::uint64_t now_ns) {
        return fault_ == BrakeFault::None ? receiver_.current_sample(now_ns) : std::nullopt;
    }
    const can::BrakeReceiver& receiver() const { return receiver_; }
private:
    void fail(BrakeFault fault, std::uint64_t now_ns);
    const BrakeActuatorConfig config_;
    can::BrakeReceiver receiver_;
    can::BrakeTxState tx_{can::BrakeFrameKind::Actual};
    simulation::BrakePressureResponse response_;
    BrakeResponseMonitor monitor_;
    std::optional<bool> floor_observed_;
    std::uint32_t epoch_{0}, sequence_{0};
    std::uint64_t last_tick_ns_{0};
    bool sequence_exhausted_{false};
    BrakeFault fault_{BrakeFault::None};
};
}  // namespace stratadrive::vecu
