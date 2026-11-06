#pragma once

#include "speed_pi.hpp"

namespace stratadrive::central {
enum class ForceProfile { Snapshot30ms, ReceiverPowerLimits };
// Trusted upstream estimate, not measured actuator output or permission.
// Positive road load opposes forward travel; negative load includes downhill
// gravity. Bounds must include grade, drag/rolling load and estimator error.
struct AvailableForce {
    std::uint32_t epoch{0};
    std::uint64_t sequence{0}, source_ns{0}, expires_ns{0};
    double propulsion_n{0}, braking_n{0}, road_load_min_n{0}, road_load_max_n{0};
    ForceProfile profile{ForceProfile::Snapshot30ms};
};
struct ReferenceConfig {
    double mass_kg{1000}, capacity_fraction{0.9};
    double max_acceleration_mps2{2}, max_deceleration_mps2{5};
    double max_tracking_lead_mps{0.5};
};
enum class ReferenceFault { None, Session, Clock, Input, Capacity, Tracking };
struct FeasibleReference {
    double target_mps{0}, acceleration_mps2{0};
    double minimum_acceleration_mps2{0}, maximum_acceleration_mps2{0};
    std::uint64_t oldest_source_ns{0}, expires_ns{0};
    bool limited{false};
};
// Fixed 20ms, single-owner governor before SpeedRequest. No IO/authority.
// A fault latches until a newer session, just like the downstream controller.
class AvailableForceReference {
public:
    explicit AvailableForceReference(ReferenceConfig config = {});
    bool start_session(std::uint32_t epoch, std::uint64_t enable_ns) noexcept;
    std::optional<FeasibleReference> step(std::uint64_t now_ns, double desired_mps,
        const SpeedSample&, const AvailableForce&) noexcept;
    ReferenceFault fault() const noexcept { return fault_; }
private:
    ReferenceConfig config_;
    std::uint32_t epoch_{0};
    std::uint64_t enable_ns_{0};
    std::optional<std::uint64_t> last_ns_;
    std::optional<double> target_;
    std::optional<AvailableForce> force_;
    std::optional<SpeedSample> speed_;
    ReferenceFault fault_{ReferenceFault::None};
};
} // namespace stratadrive::central
