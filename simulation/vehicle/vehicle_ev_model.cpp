#include "vehicle_ev_model.hpp"
#include <algorithm>
#include <cmath>
#include <utility>

namespace stratadrive::simulation {
VehicleEvModel::VehicleEvModel(SimpleVehicleConfig v,DriveEnergyConfig m,BatteryConfig b,PowerModelConfig c):
    vehicle_(v),electrical_(std::in_place,m,b,c) {}
bool VehicleEvModel::initialize(BatteryInitialization initial,double bus,power::ContactorPositions contacts,double speed) {
    if(vehicle_.state().identity.epoch)return false;
    auto v=vehicle_;auto e=*electrical_;
    if(!v.initialize(initial.epoch,initial.time_ns,speed) || !e.initialize(initial,bus,contacts))return false;
    vehicle_=std::move(v);electrical_.emplace(std::move(e));ledger_={};result_={VehicleEvFault::None};return true;
}
VehicleEvStep VehicleEvModel::step(std::uint64_t begin,std::uint64_t end,const VehicleActual& a,
        const ModelMeasurement<EvElectricalEnvironment>& environment,power::CoilCommand coils,
        const PowerFaultInjection& injection,const BatterySensorCapture& capture) {
    if(result_.fault!=VehicleEvFault::None)return result_;
    auto v=vehicle_;auto e=*electrical_;
    const auto previous_speed=v.wheel_speed_rad_s(),previous_work=v.state().motor_work_j;
    result_.vehicle=v.step(begin,end,a);
    if(result_.vehicle!=VehicleFault::None){result_.fault=VehicleEvFault::Vehicle;return result_;}
    // All actuals are acquired by this physical owner at interval begin; the
    // wheel sample is that same original acquisition, not an end-value rewrite.
    const EvPowerInputs in{a.torque,ModelMeasurement<double>{previous_speed,vehicle_.state().identity,begin},environment};
    const auto dep=std::min({a.torque.input_time_ns,a.pressure.input_time_ns,a.steering.input_time_ns,begin,environment.input_time_ns});
    const auto& id=e.diagnostic_state().identity;
    const IntegratedMotorWork work{{id.epoch,id.sequence+1,end},begin,end,dep,v.state().motor_work_j-previous_work};
    result_.electrical=e.step_integrated_motion({begin,end,in,coils},work,injection,capture);
    if(result_.electrical.fault!=EvPowerFault::None){result_.fault=VehicleEvFault::Electrical;return result_;}
    const auto& b=e.battery_state();const auto& ev=e.diagnostic_state();const auto& s=v.state();
    VehicleEnergyState l;
    l.begin_ns=begin;l.end_ns=end;l.input_ns=std::min({a.torque.input_time_ns,a.pressure.input_time_ns,a.steering.input_time_ns,environment.input_time_ns});
    l.model_epoch=id.epoch;l.sequence=ev.identity.sequence;l.torque_nm=a.torque.value;l.pressure_pa=a.pressure.value;l.wheel_speed_rad_s=previous_speed;
    l.kinetic_j=v.kinetic_j();
    l.motor_work_j=s.motor_work_j;l.friction_j=s.friction_work_j;l.road_j=s.road_work_j;
    l.electrical_mechanical_j=ev.mechanical_j;l.motor_loss_j=ev.motor_loss_j;l.battery_draw_j=b.initial_energy_j-b.energy_j;l.received_dc_j=b.received_dc_j;
    l.auxiliary_j=b.auxiliary_j;l.ohmic_j=b.ohmic_loss_j;l.capacitor_delta_j=ev.capacitor_j-ev.initial_capacitor_j;
    l.circuit_loss_j=ev.precharge_loss_j+ev.main_loss_j+ev.discharge_loss_j;l.soc=b.soc;l.vehicle_balance_j=s.balance_error_j;
    l.coupling_balance_j=ev.mechanical_j-s.motor_work_j;
    l.combined_balance_j=l.battery_draw_j-(l.capacitor_delta_j+(l.kinetic_j-v.initial_kinetic_j())+l.friction_j+l.road_j+l.motor_loss_j+l.auxiliary_j+l.ohmic_j+l.circuit_loss_j);
    if(!std::isfinite(l.combined_balance_j)||std::abs(l.combined_balance_j)>.001||std::abs(l.coupling_balance_j)>1e-6||std::abs(l.vehicle_balance_j)>1e-5){result_.fault=VehicleEvFault::Balance;return result_;}
    vehicle_=std::move(v);electrical_.emplace(std::move(e));ledger_=l;return result_;
}
}
