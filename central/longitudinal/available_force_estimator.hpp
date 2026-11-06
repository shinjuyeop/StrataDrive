#pragma once
#include "available_force_reference.hpp"
#include "control_allocation.hpp"

namespace stratadrive::central {
// Fixed, reviewed operating-envelope calibration, NOT a live grade estimate.
// Must bound grade/rolling/aero load over the entire selected SIL scenario.
struct RoadLoadBounds { double minimum_n{0}, maximum_n{0}; };
class AvailableForceEstimator {
public:
    AvailableForceEstimator(AllocationConfig,RoadLoadBounds);
    // Current receiver snapshots only. Friction-only braking reserve avoids
    // assuming optional regeneration survives to the next allocation release.
    // No permission or command is issued. Every physical timestamp is retained.
    std::optional<AvailableForce> estimate(const NormalDriveReadinessInputs&,
        std::uint64_t now_ns) const noexcept;
private:
    AllocationConfig config_;
    RoadLoadBounds load_;
};
} // namespace stratadrive::central
