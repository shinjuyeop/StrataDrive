#pragma once

#include "vehicle_management.hpp"
#include "actuator_stop_lease.hpp"
#include "allocated_commands.hpp"

namespace stratadrive::central {
struct AllocationConfig {
    // First functional-SIL calibration, NOT vehicle/OEM parameters.
    double mass_kg{1000}, wheel_radius_m{0.3}, wheelbase_m{2.7};
    double friction_nm_per_pa{0.001}, max_pressure_pa{1500000}, max_steering_rad{0.3};
    double max_propulsion_nm{300}, max_regen_nm{200}, max_service_braking_nm{1500};
    double max_acceleration_mps2{2}, max_deceleration_mps2{5}, max_curvature_inv_m{1};
    double max_wheel_speed_rad_s{100}, low_speed_enter_rad_s{2}, low_speed_exit_rad_s{3};
    double hold_speed_rad_s{0.5}, hold_braking_nm{100};
    double release_friction_nm{1}, release_motor_nm{0.1}, response_tolerance_nm{50};
    // Same conservative DC-load model as the local Drive gate. Local limits
    // remain independent; Central does not replace that gate or read its plant.
    double motoring_efficiency_lower_bound{0.9}, copper_loss_w_per_nm2{0.01}, reserve_power_w{200};
    double propulsion_mechanical_power_w{20000}, regen_mechanical_power_w{10000};
    ReadinessTiming readiness{};
    std::uint64_t max_tick_gap_ns{30000000ULL}; // fixed 20 ms allocation period
    std::uint64_t request_source_age_ns{30000000ULL}, response_dwell_ns{700000000ULL};
    std::uint64_t feedback_skew_ns{20000000ULL};
};
struct AllocationInputs {
    NormalDriveReadinessInputs feedback;
    VehicleManagementDecision management; // trusted local owner decision, not inferred from wire
    std::optional<can::BmsCurrentSample> permission;
    std::optional<can::BmsParentContext> permission_parent; // separately trusted lifecycle root
};
enum class AllocationReceiveDecision {
    Accepted, Unchanged, NotInitialized, Latched, Invalid, EpochMismatch,
    Expired, SequenceRejected, MutationRejected
};
enum class AllocationState { NotInitialized, Waiting, Active, FailSafe, Quiesced };
enum class AllocationFault {
    None, ClockError, ControlDeadline, SessionMismatch, RequestLost, SupportExpired,
    PermissionUnavailable, CriticalFeedback, WheelSpeedUnavailable, FeedbackSkew,
    BrakingCapacity, BrakingDeficit, BrakingExcess, ContinuityLost, SequenceExhausted
};
enum class RegenAvailability { Usable, Unavailable, Stale, Invalid, Expiring, LowSpeed };
struct AllocationDecision {
    AllocationState state{AllocationState::NotInitialized};
    AllocationFault fault{AllocationFault::None};
    bool protection_required{false}, brake_priority{false}, propulsion_waiting_release{false}, hold_active{false};
    RegenAvailability regen{RegenAvailability::Unavailable};
    std::optional<double> requested_braking_nm, actual_braking_nm, deficit_nm, excess_nm;
    std::optional<std::uint64_t> actual_source_time_ns;
    double regen_limit_nm{0}, selected_regen_nm{0}, capacity_deficit_nm{0}, propulsion_deficit_nm{0};
    bool steering_limited{false}, response_pending{false};
};
// Single-owner normal-path allocator. No plant/socket/controller PID/ABS/ESC.
// All current inputs share a monotonic domain and obey receiver continuity /
// current_sample contracts. Failure means no new normal output, NOT brake
// release or a safe-stop claim. The coordinator must route protection_required
// to the separate local/vehicle protection path. Only newer trusted INIT clears it.
class ControlAllocation {
public:
    explicit ControlAllocation(const AllocationConfig& config = {});
    bool start_session(std::uint32_t epoch, std::uint64_t enable_ns);
    AllocationReceiveDecision receive_request(const VehicleRequest& request, std::uint64_t now_ns);
    void mark_continuity_lost(std::uint64_t now_ns);
    bool select_normal_stop(const ActuatorStopLease& lease, std::uint64_t now_ns);
    std::uint32_t application_epoch() const { return epoch_; }
    std::optional<AllocatedCommands> tick(const AllocationInputs& inputs, std::uint64_t now_ns);
    const AllocationDecision& decision() const { return decision_; }
private:
    struct Dwell {
        std::optional<std::uint64_t> first;
        bool observe(bool outside, std::uint64_t source_ns, std::uint64_t duration_ns);
    };
    void fail(AllocationFault fault);
    bool advance(std::uint64_t now_ns);
    bool live_request(std::uint64_t now_ns) const;
    bool permission_valid(const AllocationInputs& inputs, std::uint64_t now_ns) const;
    const AllocationConfig config_;
    AllocationDecision decision_{};
    StopLeaseState stop_;
    std::uint32_t epoch_{0};
    std::uint64_t enable_ns_{0}, last_observed_ns_{0}, sequence_{0};
    std::optional<std::uint64_t> last_tick_ns_, critical_expiry_ns_, regen_expiry_ns_;
    std::optional<VehicleRequest> request_;
    Dwell deficit_, excess_;
    bool armed_{false}, stopped_{false}, braking_{false}, low_speed_{false}, holding_{false};
    double episode_regen_nm_{0}; // nonincreasing until observed release of a braking interval
};
}  // namespace stratadrive::central
