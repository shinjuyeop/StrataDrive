#pragma once

#include <cstdint>
#include <optional>

namespace stratadrive {
// Trusted terminal handoff; remote owner-wire v1 preserves this identity.
// Never reconstruct it from normal CAN or refresh its source/expiry at a hop.
struct ActuatorStopLease {
    std::uint32_t epoch, sequence;
    std::uint64_t source_time_ns, expires_at_ns;
};
// One speed wire step, existing torque release tolerance and allocation hold
// pressure. Distinct from the allocator's 0.5 rad/s hold-entry threshold.
inline constexpr double kStopSpeedRadS = 0.01, kStopTorqueNm = 0.1, kStopPressurePa = 100000;
inline bool same_stop_lease(const ActuatorStopLease& a, const ActuatorStopLease& b) {
    return a.epoch==b.epoch && a.sequence==b.sequence && a.source_time_ns==b.source_time_ns && a.expires_at_ns==b.expires_at_ns;
}
class StopLeaseState {
public:
    bool active() const { return lease_.has_value(); }
    bool live(std::uint64_t now) const {
        return lease_ && now>=lease_->source_time_ns && now<lease_->expires_at_ns && now-lease_->source_time_ns<=50000000;
    }
    bool accept(const ActuatorStopLease& lease, std::uint32_t epoch, std::uint64_t now) {
        if(epoch==0 || lease.epoch!=epoch || lease.source_time_ns<enable_ns_ || lease.source_time_ns>now || now-lease.source_time_ns>50000000 ||
            lease.expires_at_ns<=now || lease.expires_at_ns<=lease.source_time_ns || lease.expires_at_ns-lease.source_time_ns>80000000 ||
            (lease_ && !live(now))) return false;
        if(lease_) {
            if(lease.sequence==lease_->sequence) return same_stop_lease(lease,*lease_);
            if(lease.sequence<lease_->sequence || lease.sequence-lease_->sequence>10 || lease.source_time_ns<=lease_->source_time_ns) return false;
        }
        lease_=lease; return true;
    }
    void reset(std::uint64_t enable_ns = 0) { lease_.reset(); enable_ns_=enable_ns; }
private:
    std::uint64_t enable_ns_{0};
    std::optional<ActuatorStopLease> lease_;
};
} // namespace stratadrive
