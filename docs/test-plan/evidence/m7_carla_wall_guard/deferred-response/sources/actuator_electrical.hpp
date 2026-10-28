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
enum class PlantExecution { Zoh, CoupledObservedWork, DeferredObservedWork };
// Separate M7 test owner: actuator response + circuit/battery, NO motion model.
// Values reuse the named M6 functional fixture, not CARLA/OEM calibration.
// Legacy mode uses beginning-speed ZOH prediction. Both observed-work modes
// use one EvPowerModel and no ZOH. Deferred mode has separate response/energy
// cursors and historical coils; all public operations still have ONE mutation
// owner. An IO thread must hand off receipts, never mutate this model directly.
class ActuatorElectrical {
public:
    ActuatorElectrical(Time start,std::uint32_t first_application,bool solver_work=false);
    ActuatorElectrical(Time start,std::uint32_t first_application,PlantExecution execution);
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
    bool ok() const {return error_.empty() && electrical_error_.empty();}
    const std::string& error() const {return error_.empty()?electrical_error_:error_;}
    Time last_success() const;
    bool begin_work_frame(const SolverWork& work);
    bool finish_work_frame(Time end);
    void commit_work_frame();
    void abort_work_frame();
    double settled_work() const;
    Time electrical_time() const;
    // Single owner, separate progress: response needs no solver receipt. The
    // caller supplies one declared clock domain; this is NOT a wall/sim mapping.
    // Cached electrical/wheel measurements retain their original timestamps.
    bool advance_actuators(Time now,const std::optional<Wheel>& wheel,
        const std::array<std::optional<simulation::OwnerActuation>,5>& outputs,
        std::uint32_t released_application,bool protect=false);
    // Atomic electrical-only commit using historical applied coils. Never rolls
    // back response state. Bad/replayed/missing-history work latches an energy
    // fault; subsequent actuator steps continue terminal protection, no rearm.
    bool settle_observed_frame(const SolverWork& work);
    bool actuators_ok() const {return error_.empty();}
    bool electrical_ok() const {return error_.empty() && electrical_error_.empty();}
    std::size_t pending_intervals() const {return history_count_;}
    power::CoilCommand applied_coils() const;
private:
    struct State;
    bool fail(const char* reason);
    bool settle(State& candidate,Time end,const power::CoilCommand& coils);
    bool advance_response(State& candidate,Time now,const std::optional<Wheel>& wheel,
        const std::array<std::optional<simulation::OwnerActuation>,5>& outputs,
        std::uint32_t released,bool protect,simulation::OwnerSensors& measured);
    bool fail_electrical(const char* reason);
    void capture_electrical(State& candidate,simulation::OwnerSensors& measured);
    std::unique_ptr<State> state_;
    std::unique_ptr<State> checkpoint_;
    std::optional<simulation::OwnerSensors> sensors_;
    ElectricalAudit audit_{};
    ElectricalAudit checkpoint_audit_{};
    std::string error_;
    std::string electrical_error_;
    bool deferred_=false,protection_latched_=false;
    std::optional<Wheel> last_wheel_;
    struct CoilInterval {Time begin=0,end=0;power::CoilCommand coils{};};
    // Bounded applied-output history, not a freshness allowance. Overflow
    // invalidates further electrical settlement; protective response continues.
    std::array<CoilInterval,128> history_{};
    std::size_t history_head_=0,history_count_=0;
};
} // namespace stratadrive::m7_external
