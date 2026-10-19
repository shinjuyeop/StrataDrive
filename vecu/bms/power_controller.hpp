#pragma once

#include "bms_receiver.hpp"
#include "power_sensor_snapshot.hpp"

namespace stratadrive::vecu {
// Host functional-SIL fixture defaults, not vehicle/OEM calibration.
struct PowerControllerConfig {
    can::BmsPhysicalRanges physical{{0, 1000}, {-3000, 3000}, {-50, 100}, 100000};
    double minimum_pack_v{300}, maximum_pack_v{450}, off_bus_max_v{30};
    double precharge_ratio{0.99}, ready_delta_v{5}, opening_current_max_a{5};
    std::uint64_t period_ns{10000000}, max_tick_gap_ns{30000000};
    std::uint64_t max_source_age_ns{50000000}, max_dependency_age_ns{70000000};
    std::uint64_t checks_dwell_ns{20000000}, ready_dwell_ns{20000000}, current_dwell_ns{20000000};
    std::uint64_t checks_timeout_ns{500000000}, contactor_timeout_ns{100000000};
    std::uint64_t precharge_timeout_ns{2000000000}, shutdown_current_timeout_ns{300000000}, discharge_timeout_ns{1000000000};
};
enum class PowerPhase {
    Inspect, Off, Checks, CloseNegative, Precharging, ClosePositive, OpenPrecharge, Ready,
    WaitCurrent, OpenContactors, Discharging
};
enum class PowerControlFault {
    None, StartupEnergized, InputsUnavailable, RequestLost, BmsInhibit, ConditionsUnsafe,
    ContactorResponse, PrechargeTimeout, BusNotReady, ShutdownCurrentBlocked, DischargeTimeout,
    ClockError, ControlDeadline, SequenceExhausted, ContinuityLost
};
struct PowerControlOutput {
    PowerPhase phase{PowerPhase::Inspect};
    PowerControlFault fault{PowerControlFault::None};
    std::optional<power::CoilCommand> coils; // no write until the actual state is known
    bool inhibit_drive{true}; // local request; Central separately owns the Drive permission
    bool shutdown_blocked{false};
};
// Power lifecycle runnable within the BMS leaf. No SIL plant includes or vehicle
// permission synthesis. Accepted requests use the existing receiver/trusted parent.
class PowerController {
public:
    explicit PowerController(PowerControllerConfig config);
    bool start_session(std::uint32_t application_epoch, std::uint32_t model_epoch, std::uint64_t enable_ns);
    can::BmsReceiveResult receive(const can::BmsFrame& frame, std::uint64_t now_ns, const can::BmsParentContext* parent);
    void mark_continuity_lost(std::uint64_t now_ns);
    bool request_local_protection(std::uint64_t now_ns); // latch; current/open/discharge sequence remains local
    std::optional<can::BmsMessage> tick(const std::optional<power::SensorSnapshot>& sensors,
        const std::optional<power::BmsSafetyGate>& bms, std::uint64_t now_ns);
    const PowerControlOutput& output() const { return output_; }
    std::uint32_t application_epoch() const { return epoch_; }
private:
    struct Dwell {
        std::optional<std::uint64_t> first, last;
        bool observe(bool condition, std::uint64_t source_ns, std::uint64_t duration_ns);
    };
    bool valid_sensor(const power::SensorSnapshot& s, std::uint64_t now_ns) const;
    bool bms_allows(const std::optional<power::BmsSafetyGate>& gate, std::uint64_t now_ns);
    void enter(PowerPhase phase, std::uint64_t now_ns);
    void fail(PowerControlFault fault);
    void shutdown(PowerControlFault fault, std::uint64_t now_ns, const power::SensorSnapshot* sensor);
    const PowerControllerConfig config_;
    can::BmsReceiver requests_;
    PowerControlOutput output_{};
    std::optional<power::SensorSnapshot> previous_;
    std::optional<power::BmsSafetyGate> previous_gate_;
    std::optional<can::BmsMessage> last_request_;
    Dwell dwell_{};
    std::uint32_t epoch_{0}, model_epoch_{0}, sequence_{0};
    std::uint64_t enable_ns_{0}, last_observed_ns_{0}, phase_since_ns_{0};
    std::optional<std::uint64_t> last_tick_ns_;
    bool stopped_{false}, qualified_{false};
};
}  // namespace stratadrive::vecu
