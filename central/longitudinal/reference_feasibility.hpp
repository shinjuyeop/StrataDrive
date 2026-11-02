#pragma once
#include <cmath>
#include <initializer_list>
namespace stratadrive::central {
// Necessary inertial-capacity condition only. Road load, grade and dynamic BMS
// derating can still make a nominally accepted reference untrackable.
inline bool inertial_ramp_feasible(double from,double to,double seconds,double mass,
                                   double radius,double propulsion_nm,double braking_nm) noexcept {
    for(double x:{from,to,seconds,mass,radius,propulsion_nm,braking_nm})if(!std::isfinite(x))return false;
    if(from<0 || to<0 || from>40/3.6 || to>40/3.6 || seconds<=0 || mass<=0 || radius<=0 ||
       propulsion_nm<0 || braking_nm<0)return false;
    const double torque=mass*radius*((to-from)/seconds);
    return std::isfinite(torque) && torque<=propulsion_nm && -torque<=braking_nm;
}
} // namespace stratadrive::central
