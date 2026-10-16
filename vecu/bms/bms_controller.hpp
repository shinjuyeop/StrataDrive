#pragma once

#include "battery_sensor_snapshot.hpp"
#include "bms_frame_codec.hpp"
#include "power_sensor_snapshot.hpp"

namespace stratadrive::vecu {
// The ramp is zero at `zero`, one at `full`, clamped outside those points.
// Descending ramps (e.g. charge SOC) use zero > full.
struct BmsRamp { double zero{0}, full{0}; };
struct BmsTemperatureWindow { double cold_stop{0}, cold_full{0}, hot_full{0}, hot_stop{0}; };
// Separate trip/release thresholds provide recovery hysteresis.
struct BmsProtectionBand { double trip_low{0}, release_low{0}, release_high{0}, trip_high{0}; };
struct BmsControllerConfig {
    double charge_current_a{0}, discharge_current_a{0}; // nonnegative magnitudes
    double max_charge_power_w{0}, max_discharge_power_w{0};
    BmsRamp charge_soc, discharge_soc, charge_cell_v, discharge_cell_v;
    BmsTemperatureWindow charge_temperature, discharge_temperature;
    BmsProtectionBand cell_v, pack_v, temperature_c, current_a;
    std::uint32_t series_cells{0};
    double pack_extrema_tolerance_v{0}; // extrema bounds only, not a cell-sum diagnostic
    std::uint64_t period_ns{20000000}, max_tick_gap_ns{40000000};
    std::uint64_t max_source_age_ns{50000000}, max_dependency_age_ns{70000000};
    std::uint64_t max_sensor_skew_ns{20000000};
    std::uint64_t trip_dwell_ns{40000000}, release_dwell_ns{100000000};
};
enum class BmsControlState { NotInitialized, InitialChecks, Active, Latched };
enum class BmsControlFault { None, InputsInvalid, Protection, ClockError, ControlDeadline, SequenceExhausted };
enum class BmsInputIssue { None, Unavailable, Identity, Timestamp, Stale, Skew, Value };
enum BmsTrip : std::uint16_t {
    CellUnderVoltage = 1U << 0U, CellOverVoltage = 1U << 1U,
    PackUnderVoltage = 1U << 2U, PackOverVoltage = 1U << 3U,
    UnderTemperature = 1U << 4U, OverTemperature = 1U << 5U,
    ChargeOverCurrent = 1U << 6U, DischargeOverCurrent = 1U << 7U
};
struct BmsControlDecision {
    BmsControlState state{BmsControlState::NotInitialized};
    BmsControlFault fault{BmsControlFault::None};
    BmsInputIssue input_issue{BmsInputIssue::Unavailable};
    can::BmsPowerLimits limits{};
    std::optional<double> charge_current_a, discharge_current_a;
    std::uint16_t pending_trips{0}, latched_trips{0};
    bool recovery_ready{false}; // informational; NEVER clears a latch
    bool inhibit_requested{true}; // request for the future power/Drive gate, not contactor feedback
};

// Single-owner, externally clocked BMS limit/protection runnable. It consumes
// only the local sensor port: no physical truth, energy integration or HV state.
// PowerLimits is the sole published message; PowerStatus/permission are separate.
class BmsController {
public:
    explicit BmsController(BmsControllerConfig config);
    // Trusted local startup mapping: new application epoch, continuing physical
    // model epoch. This does not reset BatteryModel or change battery energy.
    // Every startup/recovery must pass release-band checks and fresh-data dwell.
    bool start_session(std::uint32_t application_epoch, std::uint32_t model_epoch, std::uint64_t enable_ns);
    // No output on early/repeated calls, clock rollback or sequence exhaustion.
    // Caller applies the existing per-stream P05 encoder to each returned sample.
    std::optional<can::BmsMessage> tick(const battery::SensorSnapshot& inputs, std::uint64_t now_ns);
    const BmsControlDecision& decision() const { return decision_; }
    const std::optional<power::BmsSafetyGate>& power_gate() const { return power_gate_; }
private:
    struct Dwell {
        enum class Kind { Trip, Release };
        std::optional<std::uint64_t> first, last;
        bool observe(bool condition, std::uint64_t source_ns, const BmsControllerConfig& config, Kind kind = Kind::Trip);
    };
    BmsInputIssue validate(const battery::SensorSnapshot& inputs, std::uint64_t now_ns) const;
    void evaluate(const battery::SensorSnapshot& inputs);
    void latch(BmsControlFault fault);
    const BmsControllerConfig config_;
    BmsControlDecision decision_{};
    std::optional<battery::SensorSnapshot> previous_;
    std::array<Dwell, 8> trip_dwell_{};
    Dwell release_dwell_{};
    std::uint32_t application_epoch_{0}, model_epoch_{0}, sequence_{0};
    std::uint64_t enable_ns_{0}, last_observed_ns_{0};
    std::optional<std::uint64_t> last_tick_ns_;
    bool stopped_{false};
    std::optional<power::BmsSafetyGate> power_gate_;
};
}  // namespace stratadrive::vecu
