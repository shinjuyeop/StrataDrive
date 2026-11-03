#pragma once
#include "speed_pi.hpp"
#include "allocated_commands.hpp"

namespace stratadrive::central {
enum class SpeedRequestFault { None, Session, Permission, Feedback, Source, Controller, Sequence, PropulsionSelection };
struct SpeedRequestFaultObservation {
    SpeedRequestFault fault;
    SpeedPIReason controller_reason;
    std::uint32_t epoch;
    std::uint64_t enable_ns, detected_ns;
    std::optional<can::DriveMessage> input;
    std::optional<SpeedSample> previous_input;
};
// Central-owner adapter. Input MUST be the trusted DriveReceiver current_sample,
// never last_accepted or plant truth. This class grants no driving authority.
class SpeedRequest {
public:
    explicit SpeedRequest(double wheel_radius_m = kWheelRadiusM, bool propulsion_antiwindup = false);
    bool start_session(std::uint32_t epoch, std::uint64_t enable_ns) noexcept;
    std::optional<VehicleRequest> step(std::uint64_t now_ns, double target_mps,
        const std::optional<can::DriveMessage>& current, bool permission,
        std::optional<PropulsionSelection> selection = std::nullopt) noexcept;
    std::optional<DerivedVehicleRequest> step_derived(std::uint64_t now_ns, double target_mps,
        const std::optional<can::DriveMessage>& current, bool permission,
        std::optional<PropulsionSelection> selection = std::nullopt) noexcept;
    SpeedRequestFault fault() const noexcept { return fault_; }
    const SpeedPIState& state() const noexcept { return pi_.state(); }
    const std::optional<SpeedRequestFaultObservation>& fault_observation() const noexcept { return observation_; }
    static constexpr double kWheelRadiusM = .3;
    static constexpr std::uint64_t kSourceAgeNs = 30000000;
private:
    void fail(SpeedRequestFault, std::uint64_t, const std::optional<can::DriveMessage>&,
              SpeedPIReason = SpeedPIReason::Normal) noexcept;
    const double wheel_radius_m_;
    const bool propulsion_antiwindup_;
    std::optional<std::uint64_t> last_selection_ns_;
    SpeedPI pi_;
    std::uint64_t enable_ns_{0}, sequence_{0};
    SpeedRequestFault fault_{SpeedRequestFault::None};
    std::optional<SpeedRequestFaultObservation> observation_;
};
} // namespace stratadrive::central
