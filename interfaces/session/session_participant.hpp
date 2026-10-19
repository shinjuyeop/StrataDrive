#pragma once

#include "session_control.hpp"

#include <array>
#include <optional>

namespace stratadrive::session {
enum class Preparation { Pending, Ready, Rejected };
class ParticipantPort {
public:
    virtual ~ParticipantPort() = default;
    virtual std::uint64_t now_ns() noexcept = 0;
    // Close normal ingress/flush old work, preserve physical state. This may
    // wait for independent protection/physical recovery; never reset to pass.
    virtual Preparation prepare(const Plan& plan) noexcept = 0;
    virtual bool initialize(const Plan& plan) noexcept = 0;
    virtual void protect() noexcept = 0;
    // Always service the local protection/control plane even with run gate shut.
    virtual void service() noexcept = 0;
};
enum class ParticipantState { Quiet, Preparing, Prepared, Initializing, Initialized, Ready, Failed };
enum class ParticipantFault { None, Clock, OwnerGap, Timeout, Rejected, Initialize, Aborted, Continuity };
class SessionParticipant {
public:
    SessionParticipant(Role role,ParticipantPort& port):role_(role),port_(port) {}
    std::optional<Ack> receive(const Control& control,std::uint64_t now_ns);
    std::optional<Ack> poll(std::uint64_t now_ns);
    void continuity_lost(std::uint64_t now_ns);
    bool run_enabled() const { return state_==ParticipantState::Ready; }
    ParticipantState state() const { return state_; }
    ParticipantFault fault() const { return fault_; }
private:
    bool observe(std::uint64_t now_ns);
    bool checkpoint();
    void fail(ParticipantFault fault);
    std::optional<Ack> progress();
    std::optional<Ack> ack(Phase phase,bool accepted);
    Role role_; ParticipantPort& port_;
    Plan plan_{}; ParticipantState state_{ParticipantState::Quiet}; ParticipantFault fault_{ParticipantFault::None};
    std::uint32_t highest_epoch_{0}; std::uint64_t observed_ns_{0};
    std::array<std::optional<Control>,3> controls_{};
    std::array<std::optional<Ack>,3> acks_{};
};
}  // namespace stratadrive::session
