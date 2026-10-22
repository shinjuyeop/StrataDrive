#pragma once
#include "simple_vehicle.hpp"
#include "ev_power_model.hpp"

namespace stratadrive::simulation {
enum class VehicleEvFault { None, Uninitialized, Inputs, Vehicle, Electrical, Balance };
struct VehicleEvStep {
    VehicleEvFault fault{VehicleEvFault::Uninitialized};
    VehicleFault vehicle{VehicleFault::None};
    EvPowerStep electrical{EvPowerFault::None};
};
struct VehicleEnergyState {
    std::uint64_t begin_ns{0},end_ns{0},input_ns{0};
    std::uint32_t model_epoch{0},sequence{0};
    double torque_nm{0},pressure_pa{0},wheel_speed_rad_s{0};
    double kinetic_j{0},motor_work_j{0},friction_j{0},road_j{0};
    double electrical_mechanical_j{0},motor_loss_j{0},battery_draw_j{0},received_dc_j{0};
    double auxiliary_j{0},ohmic_j{0},capacitor_delta_j{0},circuit_loss_j{0},soc{0};
    double vehicle_balance_j{0},coupling_balance_j{0},combined_balance_j{0};
};
// One physical owner; candidate motion and electrical states commit together.
// Does not receive any ECU demand, permission, Epoch grant or synthetic sensor.
class VehicleEvModel {
public:
    VehicleEvModel(SimpleVehicleConfig vehicle,DriveEnergyConfig motor,BatteryConfig battery,PowerModelConfig circuit);
    bool initialize(BatteryInitialization initial,double bus_voltage,power::ContactorPositions contacts={},double speed_mps=0);
    VehicleEvStep step(std::uint64_t begin,std::uint64_t end,const VehicleActual& actual,
        const ModelMeasurement<EvElectricalEnvironment>& environment,power::CoilCommand coils,
        const PowerFaultInjection& injection={},const BatterySensorCapture& capture={});
    const SimpleVehicle& vehicle() const {return vehicle_;}
    const EvPowerModel& electrical() const {return *electrical_;}
    const VehicleEnergyState& ledger() const {return ledger_;}
    VehicleEvStep result() const {return result_;}
private:
    SimpleVehicle vehicle_;
    std::optional<EvPowerModel> electrical_;
    VehicleEnergyState ledger_{};
    VehicleEvStep result_{};
};
}
