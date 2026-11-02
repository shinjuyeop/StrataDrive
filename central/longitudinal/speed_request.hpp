#pragma once
#include "speed_pi.hpp"
#include "allocated_commands.hpp"

namespace stratadrive::central {
enum class SpeedRequestFault { None, Session, Permission, Feedback, Source, Controller, Sequence, PropulsionSelection };
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
    static constexpr double kWheelRadiusM = .3;
    static constexpr std::uint64_t kSourceAgeNs = 30000000;
private:
    const double wheel_radius_m_;
    const bool propulsion_antiwindup_;
    std::optional<std::uint64_t> last_selection_ns_;
    SpeedPI pi_;
    std::uint64_t enable_ns_{0}, sequence_{0};
    SpeedRequestFault fault_{SpeedRequestFault::None};
};
} // namespace stratadrive::central
