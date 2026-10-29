#pragma once
#include <cmath>
namespace stratadrive { namespace m7_native {
// A completed protected interval must precede an IDENTICAL protected hold.
// No velocity threshold, sleep forcing, wheel correction or effort rewriting.
inline bool held_protection(bool previous_protection,bool protection,
    const double* previous_steer,const double* steer,
    const double* previous_drive,const double* drive,
    const double* previous_brake,const double* brake) {
    if(!previous_protection || !protection)return false;
    for(unsigned i=0;i<4;++i) {
        if(!std::isfinite(steer[i]) || !std::isfinite(brake[i]) ||
           steer[i]!=previous_steer[i] || drive[i]!=0 || previous_drive[i]!=0 ||
           brake[i]<=0 || brake[i]!=previous_brake[i])return false;
    }
    return true;
}
}}
