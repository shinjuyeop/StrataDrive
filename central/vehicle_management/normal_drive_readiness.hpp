#pragma once

#include "feedback_health.hpp"
#include "zone_status.hpp"
#include "brake_frame_codec.hpp"
#include "drive_frame_codec.hpp"
#include "steering_frame_codec.hpp"

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>

namespace stratadrive::central {
using ZoneHealthSnapshot = zone::ZoneHealthSnapshot;
struct FrontReadinessInputs {
    std::optional<ZoneHealthSnapshot> health;
    std::optional<can::SteeringMessage> steering_actual;
    std::optional<can::BrakeMessage> brake_actual;
};
struct RearReadinessInputs {
    std::optional<ZoneHealthSnapshot> health;
    std::optional<can::DriveMessage> drive_actual;
    std::optional<can::BmsCurrentSample> power_status;
    std::optional<can::BmsCurrentSample> power_limits;
};
struct NormalDriveReadinessInputs {
    // Supplied by trusted session setup, never learned from received samples.
    std::uint32_t epoch{0};
    std::uint64_t session_enable_ns{0};
    FrontReadinessInputs front;
    RearReadinessInputs rear;
};
using ReadinessTiming = feedback::FeedbackTiming;
enum class ReadinessBlock : std::size_t {
    Context, FrontZone, RearZone, SteeringActual, BrakeActual, DriveActual,
    PowerStatus, PowerLimits, Count
};
struct NormalDriveReadiness {
    // Default construction also fails closed. Report all blockers in one pass.
    std::array<bool, static_cast<std::size_t>(ReadinessBlock::Count)> blocked{
        true, true, true, true, true, true, true, true};
    std::optional<std::uint64_t> oldest_input_time_ns;
    bool ready() const;
    bool is_blocked(ReadinessBlock reason) const;
};

// Stateless prerequisite check only, NOT a DrivePermission or system state.
// Caller must query each trusted ingress receiver's current_sample(now_ns) in
// the same cycle, preserving epoch/sequence/source time and timeout/continuity
// latches. Repackaging last_accepted() as a current sample is not permitted.
// Clock values must share one monotonic domain; cross-node clock mapping is M5.
// Lifecycle request/expiry, INIT/rejoin and FAIL_SAFE recovery remain the
// vehicle-management owner's responsibility, even when ready() is true.
NormalDriveReadiness evaluate_normal_drive_readiness(
    const NormalDriveReadinessInputs& inputs, std::uint64_t now_ns,
    const ReadinessTiming& timing = {});
// Startup/shutdown input health: the same independent source/quality checks,
// but known INIT BMS feedback and non-ready power phases are legitimate.
// This does not assert HV readiness or authorize energizing/driving.
NormalDriveReadiness evaluate_vehicle_input_health(
    const NormalDriveReadinessInputs& inputs, std::uint64_t now_ns,
    const ReadinessTiming& timing = {});
}  // namespace stratadrive::central
