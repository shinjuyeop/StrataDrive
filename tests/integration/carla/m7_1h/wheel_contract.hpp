#pragma once
#include "drive_value_codec.hpp"
#include <array>
#include <cmath>
#include <optional>

namespace stratadrive::m7_external {
enum class WheelValidity { Forward, Nonfinite, Range, SubResolutionNegative, ReverseOrMixed };
struct WheelAssessment {
    WheelValidity validity;
    std::optional<double> forward_rad_s;
};
// Wire resolution describes representation, not a calibrated noise tolerance.
// Never round/clamp a signed measurement into the native forward-only ODD.
inline WheelAssessment assess(const std::array<double,4>& omega) {
    for(double w:omega)if(!std::isfinite(w))return {WheelValidity::Nonfinite,{}};
    for(double w:omega)if(std::abs(w)>100)return {WheelValidity::Range,{}};
    if(omega[2]<0 || omega[3]<0) {
        const double half=can::kDriveWheelSpeedResolutionRadS/2;
        const bool zero_bin=std::abs(omega[2])<half && std::abs(omega[3])<half;
        return {zero_bin?WheelValidity::SubResolutionNegative:WheelValidity::ReverseOrMixed,{}};
    }
    return {WheelValidity::Forward,(omega[2]+omega[3])/2};
}
inline const char* reason(WheelValidity value) {
    switch(value) {
        case WheelValidity::Forward:return "forward";
        case WheelValidity::Nonfinite:return "wheel nonfinite";
        case WheelValidity::Range:return "wheel range";
        case WheelValidity::SubResolutionNegative:return "wheel sub-resolution negative; sign unresolved, no zero substitution";
        case WheelValidity::ReverseOrMixed:return "wheel reverse/mixed outside forward ODD";
    }
    return "wheel invalid";
}
} // namespace stratadrive::m7_external
