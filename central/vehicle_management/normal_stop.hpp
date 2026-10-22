#pragma once

#include "vehicle_management.hpp"
#include "normal_stop_contract.hpp"

namespace stratadrive::central {
// Trusted continuation of the existing lifecycle/vehicle issuers, never learned from CAN.
struct StopIssuerSeed { std::uint32_t lifecycle_next, vehicle_next; };
struct NormalStopConfig {
    double deceleration_mps2{1};
    std::uint64_t confirmation_ns{60000000}, braking_timeout_ns{5000000000ULL}, shutdown_timeout_ns{2000000000};
    std::uint64_t minimum_tick_interval_ns{10000000ULL};
};
enum class NormalStopFault { None, ClockError, ControlDeadline, RequestLost, FeedbackUnavailable, StopEvidenceLost, HandoffExpired, ShutdownTimeout, BrakingTimeout, SequenceExhausted, UpstreamProtection };
enum class StopReceiveResult { Accepted, Unchanged, Rejected, Latched };
struct NormalStopDecision { NormalStopState state{NormalStopState::NotInitialized}; NormalStopFault fault{NormalStopFault::None}; bool protection_required{false}; };
class NormalStop {
public:
    explicit NormalStop(const NormalStopConfig& config = {});
    bool start_session(std::uint32_t epoch, std::uint64_t enable_ns);
    bool begin(const NormalStopRequest& request, StopIssuerSeed seed, std::uint64_t now_ns);
    StopReceiveResult receive_request(const NormalStopRequest& request, std::uint64_t now_ns);
    std::optional<NormalStopPlan> tick(const NormalDriveReadinessInputs& inputs, const VehicleManagementDecision& management, std::uint64_t now_ns);
    bool acknowledge_handoff(const ActuatorStopLease& lease, std::uint64_t now_ns);
    const NormalStopDecision& decision() const { return decision_; }
private:
    bool advance(std::uint64_t now_ns);
    void fail(NormalStopFault fault);
    const NormalStopConfig config_;
    NormalStopDecision decision_{};
    std::optional<NormalStopRequest> request_;
    std::optional<NormalStopRequest> pending_request_;
    std::optional<ActuatorStopLease> pending_;
    std::optional<double> confirmation_pressure_;
    std::optional<std::uint64_t> last_tick_, confirmation_start_, last_evidence_;
    std::uint32_t epoch_{0};
    std::uint64_t enable_{0}, observed_{0}, phase_start_{0}, lifecycle_next_{0}, vehicle_next_{0};
};
} // namespace stratadrive::central
