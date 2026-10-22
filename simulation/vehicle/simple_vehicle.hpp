#pragma once
#include "battery_sensor_snapshot.hpp"
#include <optional>

namespace stratadrive::simulation {
// Flat-road, forward-only SIL calibration, not an identified production vehicle.
struct SimpleVehicleConfig {
    double mass_kg{1000}, wheel_radius_m{.3}, wheelbase_m{2.7};
    double friction_nm_per_pa{.001}, rolling_n{100}, drag_n_per_mps2{.4};
    double max_torque_nm{300}, max_pressure_pa{1500000}, max_steering_rad{.3};
    std::uint64_t max_step_ns{20000000}, max_age_ns{30000000}, max_skew_ns{10000000};
};
struct VehicleActual {
    // Values acquired at/before interval begin, ZOH. Never a command/permission.
    battery::ModelMeasurement<double> torque, pressure, steering;
};
struct VehicleState {
    battery::ModelIdentity identity{};
    double speed_mps{0}, x_m{0}, y_m{0}, yaw_rad{0}, distance_m{0};
    double motor_work_j{0}, friction_work_j{0}, road_work_j{0}, balance_error_j{0};
};
enum class VehicleFault { None, Uninitialized, Timing, Identity, Timestamp, Stale, Skew, Value, Numerical };
class SimpleVehicle {
public:
    explicit SimpleVehicle(SimpleVehicleConfig config = {});
    // Scenario initialization only. A live physical model cannot be reset by ECU INIT.
    bool initialize(std::uint32_t model_epoch, std::uint64_t now_ns, double speed_mps=0);
    VehicleFault step(std::uint64_t begin, std::uint64_t end, const VehicleActual& actual);
    const VehicleState& state() const { return state_; }
    double wheel_speed_rad_s() const { return state_.speed_mps/config_.wheel_radius_m; }
private:
    SimpleVehicleConfig config_;
    VehicleState state_{};
    std::optional<VehicleActual> previous_;
    double initial_kinetic_j_{0};
};
}
