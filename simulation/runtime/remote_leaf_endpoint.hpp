#pragma once
#include "async_leaf_owner.hpp"
#include "run_lease_gate.hpp"

namespace stratadrive::simulation {
// One remote Leaf owner. The local gate/link belong exclusively to this endpoint
// and its actor, not Central or another process. No wire packet sets an atomic.
class RemoteLeafEndpoint final : private session::ParticipantPort {
public:
    RemoteLeafEndpoint(session::Role role,AsyncLeafOwner& actor,transport::RunGate& local_gate,
        transport::LeafLink& local_link,remote::ClockAgreement clock);
    std::optional<remote::OwnerMessage> receive(const remote::OwnerMessage& message);
    std::optional<remote::OwnerMessage> poll();
    std::optional<remote::OwnerMessage> take_report();
    void continuity_lost(); // failed channel stays failed until joined replacement
    bool allowed();
    remote::RunLeaseFault lease_fault() const { return credit_.fault(); }
private:
    std::uint64_t now_ns() noexcept override { return actor_.now_ns(); }
    session::Preparation prepare(const session::Plan& plan) noexcept override;
    bool initialize(const session::Plan& plan) noexcept override;
    void protect() noexcept override;
    void service() noexcept override;
    remote::OwnerMessage reply(remote::OwnerPayload payload,session::Role to) const;
    session::Role role_,zone_; AsyncLeafOwner& actor_; transport::RunGate& local_gate_;
    transport::LeafLink& link_; remote::ClockAgreement clock_; remote::RunLeaseGate credit_;
    session::SessionParticipant session_; std::uint32_t epoch_{0};
    std::array<std::optional<remote::ProtectionAck>,2> protection_acks_{};
};
} // namespace stratadrive::simulation
