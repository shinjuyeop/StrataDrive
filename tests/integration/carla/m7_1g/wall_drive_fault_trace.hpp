#pragma once
#include "wall_rig.hpp"
#include <iomanip>
#include <ostream>
namespace stratadrive::m7_functional {
inline void write_drive_fault(std::ostream& out,const std::optional<vecu::DriveFaultObservation>& fault) {
    if(!fault) {out<<"null\n";return;}
    const auto& r=*fault;
    out<<std::setprecision(17)<<"{\"fault\":"<<static_cast<unsigned>(r.fault)
       <<",\"epoch\":"<<r.epoch<<",\"model_epoch\":"<<r.model_epoch<<",\"observed_ns\":"<<r.observed_ns
       <<",\"local_age_ns\":"<<r.local_age_ns<<",\"hv_dependency_age_ns\":"<<r.hv_dependency_age_ns
       <<",\"local_skew_ns\":"<<r.local_skew_ns<<",\"held_speed\":";
    const auto stamp=[&](const auto& sample) {
        out<<"{\"epoch\":"<<sample.identity.epoch<<",\"sequence\":"<<sample.identity.sequence
           <<",\"source_ns\":"<<sample.identity.source_time_ns<<",\"dependency_ns\":"<<sample.input_time_ns;
    };
    if(r.held.wheel_speed) {stamp(*r.held.wheel_speed);out<<",\"rad_s\":"<<r.held.wheel_speed->value<<'}';}
    else out<<"null";
    out<<",\"held_hv\":";
    if(r.held.hv) {
        stamp(*r.held.hv);const auto& v=r.held.hv->value;
        out<<",\"voltage_v\":"<<v.bus_voltage_v<<",\"inverter_ready\":"<<(v.inverter_ready?"true":"false")
           <<",\"local_fault\":"<<(v.local_fault?"true":"false")<<'}';
    } else out<<"null";
    out<<"}\n";
}
}
