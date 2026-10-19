#pragma once

#include "session_control.hpp"
#include "vehicle_coordinator.hpp"

#include <array>
#include <optional>

namespace stratadrive::session {
class CoordinatorPort {
public:
    virtual ~CoordinatorPort() = default;
    virtual std::uint64_t now_ns() noexcept = 0;
    virtual bool quiesce_central() noexcept = 0;
    virtual bool send(const Control& control) noexcept = 0;
    virtual bool commit_central(central::CoordinatorSession session) noexcept = 0;
    virtual void protect_central() noexcept = 0;
};
enum class State { Quiet, Preparing, Initializing, Releasing, Running, Failed };
enum class Fault { None, Clock, OwnerGap, Timeout, Quiesce, Send, Participant, CentralCommit, Cancelled, Continuity };
enum class AckResult { Accepted, Unchanged, Rejected, Latched };
// Single Central owner. A granted Epoch comes from explicit trusted startup;
// EpochStore file IO stays outside this runnable. No ACK learns an Epoch.
class SessionCoordinator {
public:
    explicit SessionCoordinator(CoordinatorPort& port):port_(port) {}
    bool begin(std::uint32_t granted_epoch,std::uint64_t now_ns);
    AckResult receive(const Ack& ack,std::uint64_t now_ns);
    void poll(std::uint64_t now_ns);
    void cancel(std::uint64_t now_ns);
    void continuity_lost(std::uint64_t now_ns);
    State state() const { return state_; }
    Fault fault() const { return fault_; }
    const Plan& plan() const { return plan_; }
    bool run_enabled() const { return state_==State::Running; }
private:
    bool observe(std::uint64_t now_ns);
    bool checkpoint();
    bool broadcast(Phase phase);
    void fail(Fault fault);
    void next_phase();
    CoordinatorPort& port_;
    Plan plan_{};
    State state_{State::Quiet}; Fault fault_{Fault::None};
    std::uint32_t highest_epoch_{0};
    std::uint64_t observed_ns_{0}, phase_source_ns_{0};
    std::array<std::optional<Ack>,kRoleCount> accepted_{};
};
}  // namespace stratadrive::session
