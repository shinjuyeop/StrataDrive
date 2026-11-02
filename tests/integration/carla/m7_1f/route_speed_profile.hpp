#pragma once
#include <algorithm>
#include <cstdint>
#include <optional>

namespace stratadrive::m7_functional {
enum class RouteProfile { Curve30, Straight30, Combined, CombinedV2, Straight30Stop };
// Fixed scenario fixture, not a production Planner. Marker events latch once
// from the current validated rear-axle projection on the 20ms controller grid.
class RouteSpeedProfile {
public:
    explicit RouteSpeedProfile(RouteProfile profile):profile_(profile) {}
    double step(std::uint64_t elapsed_ns,double progress_m) {
        const double t=double(elapsed_ns)*1e-9;
        if(profile_==RouteProfile::Straight30Stop)return (30/3.6)*std::min(1.,t/20);
        if(!combined()) {
            if(t<20)return (30/3.6)*t/20;
            if(t<40)return 30/3.6;
            if(t<55)return (30/3.6)*(55-t)/15;
            return 0;
        }
        const bool v2=profile_==RouteProfile::CombinedV2;
        if(!slow_ && progress_m>=(v2?230:180))slow_=elapsed_ns;
        if(slow_ && !stop_ && progress_m>=(v2?380:330))stop_=elapsed_ns;
        if(stop_)return (20/3.6)*std::max(0.,1-double(elapsed_ns-*stop_)*1e-9/8);
        if(slow_)return (30/3.6)-(10/3.6)*std::min(1.,double(elapsed_ns-*slow_)*1e-9/6);
        return (30/3.6)*std::min(1.,t/(v2?20:10));
    }
    std::optional<std::uint64_t> slow_ns() const {return slow_;}
    std::optional<std::uint64_t> stop_ns() const {return stop_;}
    double requested_mps(double target) const {
        return combined()?(stop_?0.:slow_?20/3.6:30/3.6):target;
    }
    bool combined() const {return profile_==RouteProfile::Combined || profile_==RouteProfile::CombinedV2;}
private:
    RouteProfile profile_;
    std::optional<std::uint64_t> slow_,stop_;
};
} // namespace stratadrive::m7_functional
