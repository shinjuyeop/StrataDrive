#include "available_force_reference.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace stratadrive::central {
namespace {
bool same(const AvailableForce& a,const AvailableForce& b) noexcept {
    return a.epoch==b.epoch && a.sequence==b.sequence && a.source_ns==b.source_ns && a.expires_ns==b.expires_ns &&
        a.propulsion_n==b.propulsion_n && a.braking_n==b.braking_n &&
        a.road_load_min_n==b.road_load_min_n && a.road_load_max_n==b.road_load_max_n;
}
}
AvailableForceReference::AvailableForceReference(ReferenceConfig c):config_(c) {
    for(double x:{c.mass_kg,c.capacity_fraction,c.max_acceleration_mps2,c.max_deceleration_mps2,c.max_tracking_lead_mps})
        if(!std::isfinite(x) || x<=0) throw std::invalid_argument("reference configuration");
    if(c.capacity_fraction>1 || c.max_acceleration_mps2>SpeedPI::kHighMps2 ||
       c.max_deceleration_mps2>-SpeedPI::kLowMps2) throw std::invalid_argument("reference controller envelope");
}
bool AvailableForceReference::start_session(std::uint32_t epoch,std::uint64_t enable) noexcept {
    if(epoch<=epoch_ || enable<enable_ns_ || (last_ns_ && enable<*last_ns_)) return false;
    epoch_=epoch;enable_ns_=enable;last_ns_.reset();target_.reset();force_.reset();speed_.reset();fault_=ReferenceFault::None;
    return true;
}
std::optional<FeasibleReference> AvailableForceReference::step(std::uint64_t now,double desired,
    const SpeedSample& speed,const AvailableForce& force) noexcept {
    const auto fail=[&](ReferenceFault f)->std::optional<FeasibleReference>{fault_=f;return std::nullopt;};
    if(fault_!=ReferenceFault::None) return std::nullopt;
    if(!epoch_ || now<enable_ns_ || speed.epoch!=epoch_ || force.epoch!=epoch_) return fail(ReferenceFault::Session);
    if(last_ns_ && (now<=*last_ns_ || now-*last_ns_!=SpeedPI::kPeriodNs)) return fail(ReferenceFault::Clock);
    for(double x:{desired,speed.speed_mps,force.propulsion_n,force.braking_n,force.road_load_min_n,force.road_load_max_n})
        if(!std::isfinite(x)) return fail(ReferenceFault::Input);
    if(desired<0 || desired>SpeedPI::kMaxTargetMps || speed.speed_mps<0 || speed.speed_mps>SpeedPI::kMaxTargetMps ||
       force.propulsion_n<0 || force.braking_n<0 || force.road_load_min_n>force.road_load_max_n ||
       speed.source_ns<enable_ns_ || speed.source_ns>now || now-speed.source_ns>30000000 ||
       force.source_ns<enable_ns_ || force.source_ns>now || now-force.source_ns>30000000 || force.expires_ns<=now ||
       force.expires_ns-force.source_ns>30000001 ||
       (speed_ && (speed.sequence<=speed_->sequence || speed.source_ns<=speed_->source_ns)) ||
       (force_ && (force.sequence<force_->sequence || force.source_ns<force_->source_ns ||
           (force.sequence==force_->sequence && !same(force,*force_)) ||
           (force.sequence>force_->sequence && force.source_ns<=force_->source_ns)))) return fail(ReferenceFault::Input);
    // Intersection of feasible accelerations for EVERY load inside the bounds.
    const double lower=std::max(-config_.max_deceleration_mps2,
        (-force.braking_n*config_.capacity_fraction-force.road_load_min_n)/config_.mass_kg);
    const double upper=std::min(config_.max_acceleration_mps2,
        (force.propulsion_n*config_.capacity_fraction-force.road_load_max_n)/config_.mass_kg);
    if(!std::isfinite(lower) || !std::isfinite(upper) || lower>0 || upper<0 || lower>upper)
        return fail(ReferenceFault::Capacity); // Even steady speed cannot be guaranteed.
    const double previous=target_.value_or(speed.speed_mps);
    constexpr double dt=static_cast<double>(SpeedPI::kPeriodNs)/1e9;
    const double requested=(desired-previous)/dt;
    double acceleration=std::clamp(requested,lower,upper);
    const double reachable_low=std::max({0.0,previous+lower*dt,speed.speed_mps-config_.max_tracking_lead_mps});
    const double reachable_high=std::min({SpeedPI::kMaxTargetMps,previous+upper*dt,speed.speed_mps+config_.max_tracking_lead_mps});
    if(reachable_low>reachable_high) return fail(ReferenceFault::Tracking);
    const double unbounded=previous+acceleration*dt;
    const double target=std::clamp(unbounded,reachable_low,reachable_high);
    if(target!=unbounded)acceleration=(target-previous)/dt;
    if(speed.source_ns>std::numeric_limits<std::uint64_t>::max()-30000001) return fail(ReferenceFault::Input);
    FeasibleReference result{target,acceleration,lower,upper,std::min(speed.source_ns,force.source_ns),
        std::min(speed.source_ns+30000001,force.expires_ns),acceleration!=requested};
    last_ns_=now;target_=target;speed_=speed;force_=force;
    return result;
}
} // namespace stratadrive::central
