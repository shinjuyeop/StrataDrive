#pragma once
#include "wall_rig.hpp"
#include <ostream>
namespace stratadrive::m7_functional {
inline void write_startup_observations(std::ostream& out,const std::array<simulation::LeafStartupObservation,5>& rows) {
    out<<'[';
    for(std::size_t i=0;i<rows.size();++i) {
        if(i)out<<',';
        const auto& r=rows[i];
        out<<"{\"leaf\":"<<i<<",\"epoch\":"<<r.epoch<<",\"enable_ns\":"<<r.enable_ns<<",\"initialized_ns\":"<<r.initialized_ns
           <<",\"first_due_ns\":"<<r.first_due_ns<<",\"first_wait_ns\":"<<r.first_wait_ns<<",\"last_wait_ns\":"<<r.last_wait_ns
           <<",\"wait_calls\":"<<r.wait_calls<<",\"first_wait_mask\":"<<r.first_wait_mask<<",\"first_body_ns\":"<<r.first_body_ns
           <<",\"first_due_source_ns\":"<<r.first_due_source_ns<<",\"first_due_power_dependency_ns\":"<<r.first_due_power_dependency_ns
           <<",\"first_due_battery_dependency_ns\":"<<r.first_due_battery_dependency_ns<<",\"first_body_source_ns\":"<<r.first_body_source_ns
           <<",\"first_body_power_dependency_ns\":"<<r.first_body_power_dependency_ns<<",\"first_body_battery_dependency_ns\":"<<r.first_body_battery_dependency_ns
           <<",\"first_body_fault\":"<<r.first_body_fault<<'}';
    }
    out<<"]\n";
}
}
