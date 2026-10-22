#include "simple_vehicle.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace stratadrive::simulation {
SimpleVehicle::SimpleVehicle(SimpleVehicleConfig c):config_(c) {
    for(double x:{c.mass_kg,c.wheel_radius_m,c.wheelbase_m,c.friction_nm_per_pa,c.max_torque_nm,c.max_pressure_pa,c.max_steering_rad})
        if(!std::isfinite(x)||x<=0)throw std::invalid_argument("vehicle positive calibration");
    if(!std::isfinite(c.rolling_n)||c.rolling_n<0||!std::isfinite(c.drag_n_per_mps2)||c.drag_n_per_mps2<0||c.max_steering_rad>=1.5707963267948966||!c.max_step_ns||!c.max_age_ns)
        throw std::invalid_argument("vehicle road/time calibration");
}
bool SimpleVehicle::initialize(std::uint32_t epoch,std::uint64_t now,double speed) {
    if(state_.identity.epoch||!epoch||!std::isfinite(speed)||speed<0)return false;
    state_.identity={epoch,0,now};state_.speed_mps=speed;initial_kinetic_j_=.5*config_.mass_kg*speed*speed;
    if(!std::isfinite(initial_kinetic_j_)){state_={};return false;}return true;
}
VehicleFault SimpleVehicle::step(std::uint64_t begin,std::uint64_t end,const VehicleActual& a) {
    if(!state_.identity.epoch)return VehicleFault::Uninitialized;
    if(begin!=state_.identity.source_time_ns||end<=begin||end-begin>config_.max_step_ns)return VehicleFault::Timing;
    const battery::ModelMeasurement<double>* samples[]{&a.torque,&a.pressure,&a.steering};
    const battery::ModelMeasurement<double>* old[]{previous_?&previous_->torque:nullptr,previous_?&previous_->pressure:nullptr,previous_?&previous_->steering:nullptr};
    std::uint64_t oldest=end,newest=0;
    for(unsigned i=0;i<3;++i){
        const auto& s=*samples[i];const auto& id=s.identity;
        if(id.epoch!=state_.identity.epoch)return VehicleFault::Identity;
        if(id.source_time_ns>begin||s.input_time_ns>id.source_time_ns)return VehicleFault::Timestamp;
        if(end-s.input_time_ns>config_.max_age_ns)return VehicleFault::Stale;
        if(!std::isfinite(s.value))return VehicleFault::Value;
        if(old[i]){
            const auto& p=*old[i];
            if(id.sequence<p.identity.sequence||id.source_time_ns<p.identity.source_time_ns||s.input_time_ns<p.input_time_ns)return VehicleFault::Identity;
            if(id.sequence==p.identity.sequence && (id.source_time_ns!=p.identity.source_time_ns||s.input_time_ns!=p.input_time_ns||s.value!=p.value))return VehicleFault::Identity;
            if(id.sequence>p.identity.sequence && id.source_time_ns<=p.identity.source_time_ns)return VehicleFault::Identity;
        }
        oldest=std::min(oldest,s.input_time_ns);newest=std::max(newest,id.source_time_ns);
    }
    if(newest-oldest>config_.max_skew_ns)return VehicleFault::Skew;
    if(std::abs(a.torque.value)>config_.max_torque_nm||a.pressure.value<0||a.pressure.value>config_.max_pressure_pa||std::abs(a.steering.value)>config_.max_steering_rad)return VehicleFault::Value;
    if(state_.identity.sequence==std::numeric_limits<std::uint32_t>::max())return VehicleFault::Identity;
    const double dt=static_cast<double>(end-begin)*1e-9,v=state_.speed_mps;
    const double traction=a.torque.value/config_.wheel_radius_m,brake=a.pressure.value*config_.friction_nm_per_pa/config_.wheel_radius_m;
    const double road=config_.rolling_n+config_.drag_n_per_mps2*v*v;
    const double acceleration=(traction-brake-road)/config_.mass_kg;
    // Constant beginning-of-step force; solve the stop crossing, never reverse.
    const double moving=acceleration<0?std::min(dt,v/-acceleration):dt;
    const double next_v=std::max(0.,v+acceleration*moving);
    const double distance=(v+next_v)*.5*moving,curvature=std::tan(a.steering.value)/config_.wheelbase_m;
    auto n=state_;const double turn=curvature*distance;
    // Exact circular arc for ZOH steering, stable straight-line limit.
    const double half=turn*.5,sinc=std::abs(half)<1e-8?1.-half*half/6.:std::sin(half)/half;
    n.x_m+=distance*sinc*std::cos(n.yaw_rad+half);n.y_m+=distance*sinc*std::sin(n.yaw_rad+half);
    n.yaw_rad=std::remainder(n.yaw_rad+turn,2*3.14159265358979323846);n.distance_m+=distance;n.speed_mps=next_v;
    n.motor_work_j+=traction*distance;n.friction_work_j+=brake*distance;n.road_work_j+=road*distance;
    n.balance_error_j=.5*config_.mass_kg*next_v*next_v-initial_kinetic_j_-n.motor_work_j+n.friction_work_j+n.road_work_j;
    for(double x:{n.speed_mps,n.x_m,n.y_m,n.yaw_rad,n.distance_m,n.motor_work_j,n.friction_work_j,n.road_work_j,n.balance_error_j})if(!std::isfinite(x))return VehicleFault::Numerical;
    n.identity={state_.identity.epoch,state_.identity.sequence+1,end};state_=n;previous_=a;return VehicleFault::None;
}
}
