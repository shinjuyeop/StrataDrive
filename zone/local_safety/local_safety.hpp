#pragma once

#include "command_admission.hpp"

namespace stratadrive::zone {
enum class ProtectionCause { None, UpstreamLost, CommandExpired, QueueOverflow, SendFailure, ClockError, CoordinatorRequest };
class ProtectionPort {
public:
    virtual ~ProtectionPort() = default;
    // Trusted local handoff, separate from normal CAN commands. True means
    // selected by the recipient, not physically achieved. Must not block/throw.
    virtual bool protect(ZoneScope scope, ProtectionCause cause, std::uint64_t now_ns) noexcept = 0;
};
struct SafetyDecision {
    ProtectionCause cause{ProtectionCause::None};
    bool handoff_accepted{false};
};
class LocalSafety {
public:
    bool start_session(std::uint32_t epoch);
    void request(ProtectionCause cause);
    void dispatch(ProtectionPort& port, ZoneScope scope, std::uint64_t now_ns);
    const SafetyDecision& decision() const { return decision_; }
private:
    std::uint32_t epoch_{0};
    SafetyDecision decision_{};
};
}  // namespace stratadrive::zone
