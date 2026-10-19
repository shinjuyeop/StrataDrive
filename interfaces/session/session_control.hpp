#pragma once

#include <cstddef>
#include <cstdint>

namespace stratadrive::session {
enum class Role : std::size_t { FrontZone, RearZone, Steering, Brake, Drive, Bms, Power, CentralIngress, Count };
constexpr std::size_t kRoleCount=static_cast<std::size_t>(Role::Count);
constexpr std::uint64_t kPrepareBudgetNs=2000000000ULL, kInitLeadNs=20000000ULL,
    kInitWindowNs=20000000ULL, kMessageAgeNs=30000000ULL, kOwnerGapNs=30000000ULL;
enum class Phase : std::size_t { Prepare, Initialize, Release, Abort };
struct Plan {
    std::uint32_t epoch{0};
    std::uint64_t requested_ns{0}, prepare_deadline_ns{0}, enable_ns{0}, commit_deadline_ns{0};
};
inline bool same_proposal(const Plan& a,const Plan& b) {
    return a.epoch==b.epoch && a.requested_ns==b.requested_ns && a.prepare_deadline_ns==b.prepare_deadline_ns;
}
inline bool same_plan(const Plan& a,const Plan& b) {
    return same_proposal(a,b) && a.enable_ns==b.enable_ns && a.commit_deadline_ns==b.commit_deadline_ns;
}
struct Control { Role role; Phase phase; Plan plan; std::uint64_t source_ns; };
struct Ack { Role role; Phase phase; Plan plan; std::uint64_t source_ns; bool accepted; };
inline bool same_ack(const Ack& a,const Ack& b) {
    return a.role==b.role && a.phase==b.phase && same_plan(a.plan,b.plan) && a.source_ns==b.source_ns && a.accepted==b.accepted;
}
// Trusted typed control plane only: not CAN/DDS encoding or authentication.
}  // namespace stratadrive::session
