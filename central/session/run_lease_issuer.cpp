#include "run_lease_issuer.hpp"

namespace stratadrive::central {
std::optional<remote::RunLease> RunLeaseIssuer::issue(std::uint64_t now) {
    const auto plan=owner_.plan();
    if(!owner_.run_enabled() || now<plan.enable_ns || now>UINT64_MAX-remote::kRunLeaseLifetimeNs) return std::nullopt;
    if(epoch_!=plan.epoch) { epoch_=plan.epoch;next_=0;last_source_=0; }
    if(now<=last_source_ || next_>UINT32_MAX) return std::nullopt;
    remote::RunLease lease{plan,static_cast<std::uint32_t>(next_++),now,now+remote::kRunLeaseLifetimeNs};
    last_source_=now;return lease;
}
} // namespace stratadrive::central
