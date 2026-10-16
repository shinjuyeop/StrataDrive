#pragma once

#include "battery_model.hpp"

namespace stratadrive::simulation {
struct DriveEnergyConfig {
    // Load-proportional conversion terms, not total efficiencies including copper/idle.
    double motoring_efficiency{0.92}, generating_efficiency{0.85};
    double copper_loss_w_per_nm2{0.01}, inverter_idle_w{50};
    double maximum_abs_torque_nm{300}, maximum_speed_rad_s{100};
    std::uint64_t max_step_ns{20000000}, max_input_age_ns{30000000}, max_source_skew_ns{10000000};
};
struct MotorPower { double mechanical_w, loss_w, dc_w; };
std::optional<MotorPower> calculate_motor_power(const DriveEnergyConfig& config, double torque_nm, double speed_rad_s);
struct DriveEnergyInputs {
    // Physical acquisitions at/before begin, held over the entire interval (ZOH).
    // No demand, permission or capability is an electrical-energy input.
    std::optional<ModelMeasurement<double>> actual_torque_nm, wheel_speed_rad_s, auxiliary_w;
};
struct DriveEnergyInterval {
    std::uint64_t begin_ns, end_ns;
    DriveEnergyInputs inputs;
};
enum class DriveEnergyFault {
    None, NotInitialized, Timing, Clock, Unavailable, Identity, Timestamp, Stale, Skew, Value,
    Battery, Numerical
};
struct DriveEnergyStep {
    DriveEnergyFault fault;
    BatteryFault battery_fault{BatteryFault::None};
    double boundary_excess_j{0};
};
struct DriveEnergyState {
    ModelIdentity identity{};
    double mechanical_w{0}, motor_loss_w{0}, traction_dc_w{0};
    double mechanical_j{0}, motor_loss_j{0}, balance_error_j{0};
};

// Energized, ideal DC path only: no contactor/RC-link energy, vehicle inertia or
// friction brake. BatteryModel alone owns chemical energy, SOC and battery heat.
// The caller supplies actual forward wheel speed from a plant or explicit fixture.
class DriveEnergyModel {
public:
    DriveEnergyModel(DriveEnergyConfig drive, BatteryConfig battery);
    bool initialize(BatteryInitialization initial); // scenario reset only; never ECU restart
    DriveEnergyStep step(const DriveEnergyInterval& interval, const BatterySensorCapture& capture = {});
    const BatteryObservation& observation() const { return observation_; }
    const BatteryState& battery_state() const { return battery_.diagnostic_state(); }
    const DriveEnergyState& diagnostic_state() const { return state_; }
    DriveEnergyFault fault() const { return result_.fault; }
private:
    struct Sum {
        double value{0}, correction{0};
        void add(double increment);
    };
    DriveEnergyStep fail(DriveEnergyFault fault);
    const DriveEnergyConfig config_;
    const double balance_tolerance_j_;
    BatteryModel battery_;
    BatteryObservation observation_{};
    DriveEnergyState state_{};
    std::optional<DriveEnergyInputs> previous_;
    Sum mechanical_{}, losses_{};
    std::uint64_t initialization_ns_{0}, last_observed_ns_{0};
    DriveEnergyStep result_{DriveEnergyFault::NotInitialized};
};
}  // namespace stratadrive::simulation
