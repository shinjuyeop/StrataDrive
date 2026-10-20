#pragma once
#include "session_coordinator.hpp"
#include "run_lease_gate.hpp"

namespace stratadrive::central {
// Called only by the Central owner after servicing all actual session ACKs.
class RunLeaseIssuer {
public:
    explicit RunLeaseIssuer(const session::SessionCoordinator& owner):owner_(owner) {}
    std::optional<remote::RunLease> issue(std::uint64_t now);
private:
    const session::SessionCoordinator& owner_;
    std::uint32_t epoch_{0}; std::uint64_t next_{0},last_source_{0};
};
} // namespace stratadrive::central
