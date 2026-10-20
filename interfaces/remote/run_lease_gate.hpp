#pragma once
#include "owner_wire.hpp"
#include "session_participant.hpp"

namespace stratadrive::remote {
// Fixed trusted agreement, never learned from an incoming timestamp. Positive
// offset maps sender time to receiver time. Target synchronization is separate.
struct ClockAgreement {
    std::uint64_t local_domain{0},source_domain{0};
    std::int64_t offset_ns{0}; std::uint64_t uncertainty_ns{0}; bool established{false};
};
struct TimeBounds { std::uint64_t earliest,latest; };
std::optional<TimeBounds> mapped_time(std::uint64_t source,const ClockAgreement& agreement);
bool source_and_expiry_current(std::uint64_t source,std::uint64_t expiry,std::uint64_t now,
    std::uint64_t max_source_age,const ClockAgreement& agreement);
enum class RunLeaseFault { None,Clock,Session,AcquisitionTimeout,Expired,Protection };
// Single local owner. SessionParticipant owns INIT/Release and physical checks;
// this additional gate owns separately issued global run credit. No atomic bypass.
class RunLeaseGate {
public:
    // Only the trusted local INIT callback invokes bind after physical checks.
    // First profile supports a common kernel monotonic clock; mapped Target
    // timestamps are rejected here until inner CAN/RX clock integration exists.
    bool bind(const session::Plan& plan,const ClockAgreement& agreement,std::uint64_t now);
    bool receive(const RunLease& lease,std::uint64_t clock_domain,const session::SessionParticipant& local,std::uint64_t now);
    bool allows(const session::SessionParticipant& local,std::uint64_t now);
    void protect(std::uint32_t epoch);
    RunLeaseFault fault() const { return fault_; }
    const std::optional<RunLease>& accepted() const { return accepted_; }
private:
    bool observe(const session::SessionParticipant& local,std::uint64_t now);
    session::Plan plan_{}; ClockAgreement clock_{};
    std::uint64_t observed_{0},acquisition_deadline_{0};
    RunLeaseFault fault_{RunLeaseFault::None}; std::optional<RunLease> accepted_;
};
inline constexpr std::uint64_t kRunLeaseLifetimeNs=60000000ULL;
// Correlation only. A receipt never opens a run gate or manufactures selection.
// A stopped peer produces no ACK; an observer/driver action has a different role.
class ProtectionReceipt {
public:
    bool expect(const ProtectionRequest& request,session::Role peer,std::uint64_t clock_domain,std::uint64_t now);
    bool receive(const OwnerMessage& message,std::uint64_t now);
    bool acknowledged() const { return selected_ns_.has_value(); }
private:
    std::optional<ProtectionRequest> request_; session::Role peer_{};
    std::uint64_t clock_domain_{0}; std::optional<std::uint64_t> selected_ns_;
};
} // namespace stratadrive::remote
