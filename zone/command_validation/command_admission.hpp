#pragma once

#include "allocated_commands.hpp"
#include "zone_status.hpp"

namespace stratadrive::zone {
enum class AdmissionState { NotInitialized, Idle, Waiting, Active, FailSafe };
enum class AdmissionFault { None, ClockError, CommandTimeout, CommandExpired, ContinuityLost };
enum class AdmissionResult {
    Accepted, Unchanged, NotInitialized, NotArmed, Latched, WrongScope,
    EpochMismatch, ParentUnavailable, ParentMismatch, InvalidContext, Expired,
    SequenceRejected, SourceNotIncreasing, MutationRejected, InvalidPayload,
    ModeRejected, ValueOutOfRange
};
struct AdmissionConfig {
    // First functional-SIL envelope, matching allocation. Not OEM calibration.
    double max_angle_rad{0.3}, max_pressure_pa{1500000};
    double max_propulsion_nm{300}, max_regen_nm{200};
    std::uint64_t command_source_age_ns{30000000ULL}, parent_source_age_ns{30000000ULL};
    std::uint64_t dependency_age_ns{70000000ULL}, command_timeout_ns{80000000ULL};
};
struct AdmissionDecision {
    AdmissionState state{AdmissionState::NotInitialized};
    AdmissionFault fault{AdmissionFault::None};
    bool protection_required{false};
};

// One independent single-owner instance per Zone; one monotonic clock domain.
// No socket/clock issuance/plant/permission or physical protection implementation.
class CommandAdmission {
public:
    explicit CommandAdmission(ZoneScope scope, const AdmissionConfig& config = {});
    // Trusted INIT only. Higher Epoch + nondecreasing time clears a latch.
    bool start_session(std::uint32_t epoch, std::uint64_t enable_ns);
    // Trusted lifecycle/coordinator callback after non-driving startup readiness.
    // No packet may arm monitoring; idle does not time out during HV precharge.
    bool arm(std::uint64_t now_ns);
    // Independent trusted root handoff, NEVER reconstructed from a command's
    // attached parent. No cryptographic authentication/transport is provided here.
    AdmissionResult authorize_request(const central::VehicleRequest& parent, std::uint64_t now_ns);
    AdmissionResult receive(const central::ScopedCommands& commands, std::uint64_t now_ns);
    AdmissionDecision poll(std::uint64_t now_ns);
    void mark_continuity_lost(std::uint64_t now_ns);
    // Recheck at dispatch time. Returned sideband must survive gateway queues;
    // bare 32-byte actuator CAN does not carry original parent/expiry.
    std::optional<central::ScopedCommands> current_command(std::uint64_t now_ns);
    const AdmissionDecision& decision() const { return decision_; }
    std::optional<std::uint64_t> last_valid_receive_time_ns() const { return last_valid_rx_ns_; }
private:
    void fail(AdmissionFault fault);
    bool advance(std::uint64_t now_ns);
    const ZoneScope scope_;
    const AdmissionConfig config_;
    AdmissionDecision decision_{};
    std::uint32_t epoch_{0};
    std::uint64_t enable_ns_{0}, last_observed_ns_{0}, armed_ns_{0};
    std::optional<central::VehicleRequest> authorized_;
    std::optional<central::ScopedCommands> accepted_;
    std::optional<std::uint64_t> last_valid_rx_ns_;
};
}  // namespace stratadrive::zone
