#pragma once

#include "normal_drive_readiness.hpp"
#include "power_commands.hpp"

namespace stratadrive::central {
enum class LifecycleReceiveDecision {
    Accepted, Unchanged, NotInitialized, Latched, Invalid, EpochMismatch,
    Expired, SequenceRejected, MutationRejected, RestartRequired
};
enum class VehicleManagementState { NotInitialized, Init, Off, Starting, Normal, Stopping, Stopped, FailSafe };
enum class VehicleManagementFault {
    None, ClockError, ControlDeadline, SessionMismatch, InputsUnavailable,
    SourceProtection, StartupEnergized, UnsafePowerConditions, RequestLost,
    PowerAcknowledgement, PowerNotReady, GrantExpired, StartupTimeout,
    ShutdownTimeout, ContinuityLost, SequenceExhausted
};
struct VehicleManagementConfig {
    ReadinessTiming readiness{};
    std::uint64_t max_tick_gap_ns{30000000ULL}; // fixed 10 ms component period
    std::uint64_t initial_input_timeout_ns{80000000ULL};
    std::uint64_t request_source_age_ns{50000000ULL};
    std::uint64_t output_lifetime_ns{60000000ULL};
    std::uint64_t acknowledgement_timeout_ns{80000000ULL};
    std::uint64_t startup_timeout_ns{3000000000ULL}, shutdown_timeout_ns{2000000000ULL};
    double off_bus_max_v{30}; // functional-SIL fixture, not an OEM calibration
};
struct VehicleManagementDecision {
    VehicleManagementState state{VehicleManagementState::NotInitialized};
    VehicleManagementFault fault{VehicleManagementFault::None};
    NormalDriveReadiness input_health{}, normal_readiness{};
    bool normal_allowed{false};
    bool power_off_confirmed{false}; // actual OFF + acknowledgement, not a coil command
};
// Single-owner, externally clocked Central runnable. No plant, socket, scheduler
// or Epoch issuance. Inputs obey the readiness API's trusted-current-sample
// contract; all values currently share one monotonic domain.
class VehicleManagement {
public:
    explicit VehicleManagement(VehicleManagementConfig config = {});
    // Trusted INIT only. A newer application epoch is mandatory; this neither
    // resets physical power nor resets remote receivers/Leaf controllers.
    bool start_session(std::uint32_t epoch, std::uint64_t enable_ns);
    LifecycleReceiveDecision receive_request(const LifecycleRequest& request, std::uint64_t now_ns);
    void mark_continuity_lost(std::uint64_t now_ns);
    // No output before INIT, on an early call, clock rollback or sequence exhaustion.
    std::optional<VehicleManagementOutput> tick(const NormalDriveReadinessInputs& inputs, std::uint64_t now_ns);
    const VehicleManagementDecision& decision() const { return decision_; }
private:
    struct IssuedRequest {
        can::BmsMessage message;
        std::optional<LifecycleRequest> parent;
    };
    void fail(VehicleManagementFault fault);
    bool advance(std::uint64_t now_ns);
    bool live_request(std::uint64_t now_ns) const;
    const IssuedRequest* acknowledgement(const NormalDriveReadinessInputs& inputs,
                                       std::uint64_t now_ns, can::BmsPowerAction action) const;
    std::uint64_t permission_expiry(const NormalDriveReadinessInputs& inputs,
                                   const IssuedRequest& acknowledged, std::uint64_t now_ns) const;
    const VehicleManagementConfig config_;
    VehicleManagementDecision decision_{};
    std::uint32_t epoch_{0};
    std::uint64_t enable_ns_{0}, last_observed_ns_{0}, phase_since_ns_{0}, sequence_{0};
    std::optional<std::uint64_t> last_tick_ns_, last_ack_source_ns_, grant_expiry_ns_;
    std::optional<LifecycleRequest> request_;
    std::array<std::optional<IssuedRequest>, 16> issued_{}; // bounded 160 ms at 10 ms cadence
    bool inputs_seen_{false}, stopped_{false};
};
}  // namespace stratadrive::central
