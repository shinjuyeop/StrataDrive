#pragma once
#include "async_leaf_owner.hpp"
#include "brake_pressure_response.hpp"
#include "drive_sil_plant.hpp"
#include "ev_power_model.hpp"
#include "steering_response.hpp"
#include "solver_work.hpp"
#include <memory>
#include <string>

namespace stratadrive::m7_external {
using Time=std::uint64_t;
using Wheel=battery::ModelMeasurement<double>;
struct ElectricalAudit {
    Time begin=0,end=0,wheel_source=0,wheel_oldest=0;
    double wheel_rad_s=0,torque_nm=0,mechanical_j=0,total_mechanical_j=0,soc=0,balance_j=0;
    double motor_loss_j=0,auxiliary_j=0,ohmic_j=0,capacitor_delta_j=0,circuit_loss_j=0,chemical_j=0;
};
// Separate M7 test owner: actuator response + circuit/battery, NO motion model.
// Values reuse the named M6 functional fixture, not CARLA/OEM calibration.
// Legacy mode uses beginning-speed ZOH prediction. Opt-in solver mode consumes
// complete observed receipts, using the same single EvPowerModel and no ZOH.
class ActuatorElectrical {
public:
    ActuatorElectrical(Time start,std::uint32_t first_application,bool solver_work=false);
    ~ActuatorElectrical();
    ActuatorElectrical(const ActuatorElectrical&)=delete;
    ActuatorElectrical& operator=(const ActuatorElectrical&)=delete;
    // wheel must be an acquisition at/before the interval BEGIN. End samples
    // cannot retrospectively drive the EV step. Faults latch; no partial commit.
    bool step(Time now,const std::optional<Wheel>& wheel,
              const std::array<std::optional<simulation::OwnerActuation>,5>& outputs,
              std::uint32_t released_application,bool protect=false);
    const std::optional<simulation::OwnerSensors>& sensors() const {return sensors_;}
    const ElectricalAudit& audit() const {return audit_;}
    bool ok() const {return error_.empty();}
    const std::string& error() const {return error_;}
    Time last_success() const;
    bool begin_work_frame(const SolverWork& work);
    bool finish_work_frame(Time end);
    void commit_work_frame();
    void abort_work_frame();
    double settled_work() const;
    Time electrical_time() const;
private:
    struct State;
    bool fail(const char* reason);
    bool settle(State& candidate,Time end);
    void capture_electrical(State& candidate,simulation::OwnerSensors& measured);
    std::unique_ptr<State> state_;
    std::unique_ptr<State> checkpoint_;
    std::optional<simulation::OwnerSensors> sensors_;
    ElectricalAudit audit_{};
    ElectricalAudit checkpoint_audit_{};
    std::string error_;
};
} // namespace stratadrive::m7_external
