#pragma once
#include "diagnostics.hpp"
#include "run_lease_gate.hpp"

namespace stratadrive::diagnostics {
// Issued explicitly by the trusted local clock authority after a fault. Never
// constructed from a received timestamp, normal frame, or automatic INIT.
struct ClockRevalidation {
    remote::ClockAgreement agreement;
    Stamp checked;
    std::uint32_t revision{0},recovery_epoch{0};
};
// Immutable same-owner observation. The composition supplies the actual full
// Release plan/mask and current native health, not an INIT request/receipt.
struct ClockRecoverySample {
    Session session;
    session::Plan released;
    std::uint32_t release_mask{0};
    bool normal_gate{false},native_healthy{false};
    Stamp observed,source;
};
class ClockRecovery {
public:
    static constexpr std::uint64_t window_ns=100000000,max_gap_ns=30000000;
    bool remember(const Event&) noexcept;
    bool revalidate(const ClockRevalidation&,Domain,std::uint64_t instance) noexcept;
    void observe(const ClockRecoverySample&) noexcept;
    std::optional<Event> take_ready() noexcept;
private:
    struct Pending {Event fault;bool recovered{false},ready{false};};
    std::array<std::optional<Pending>,32> pending_{};
    std::optional<ClockRevalidation> trust_;
    ClockRecoverySample current_{};
    std::uint32_t revision_{0};
    std::uint64_t first_{0},last_source_{0},last_observed_{0};
};
} // namespace stratadrive::diagnostics
