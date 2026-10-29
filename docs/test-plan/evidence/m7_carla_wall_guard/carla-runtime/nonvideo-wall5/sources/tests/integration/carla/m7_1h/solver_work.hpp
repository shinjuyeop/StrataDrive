#pragma once
#include "battery_model.hpp"
#include <array>
#include <cmath>
#include <cstdint>

namespace stratadrive::m7_external {
// Already observed solver work, NOT a new wheel acquisition. The adapter binds
// it to one original receipt; native admission supplies the applied Actual.
struct SolverWork {
    std::uint64_t frame=0,begin=0,end=0,oldest=0;
    double torque=0,dt=0;
    bool sleeping=false;
    battery::ModelMeasurement<double> wheel{}; // original interval-begin wheel
    std::array<double,320> rear_mean{};
    bool valid(std::uint64_t interval=10000000) const {
        if((interval!=10000000 && interval!=5000000) || !frame || frame>UINT32_MAX || !begin || end<=begin || end-begin<interval-999 || end-begin>interval+999 ||
           !oldest || oldest>begin || end-oldest>30000000 || !std::isfinite(torque) || torque < -200 || torque>300 ||
           dt!=double((interval==5000000?.005f:.01f)*(1.f/320.f)) || wheel.identity.epoch!=7 ||
           wheel.identity.source_time_ns!=begin || wheel.input_time_ns!=begin ||
           !std::isfinite(wheel.value) || wheel.value<0 || wheel.value>100 || (sleeping && torque!=0))return false;
        for(double omega:rear_mean)if(!std::isfinite(omega) ||
            (torque!=0 && (omega<0 || omega>100)) || (sleeping && omega!=0))return false;
        return true;
    }
    double work(std::uint64_t from,std::uint64_t to) const {
        // Conservative projection of the existing discrete work measure onto
        // native model boundaries. No wheel sample or solver dt is replaced.
        // Fractional subdivision assigns each solver bin its original energy;
        // the complete frame sum equals sum(torque*omega*raw solver dt).
        const double duration=double(end-begin),a=double(from-begin),b=double(to-begin);
        double result=0;
        for(unsigned k=0;k<320;++k) {
            const double lo=duration*double(k)/320,hi=duration*double(k+1)/320;
            const double overlap=std::fmax(0.,std::fmin(b,hi)-std::fmax(a,lo));
            result+=torque*rear_mean[k]*dt*(overlap/(hi-lo));
        }
        return result;
    }
};
}
