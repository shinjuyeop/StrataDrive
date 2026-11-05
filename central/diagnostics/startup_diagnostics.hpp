#pragma once
#include "control_diagnostics.hpp"
#include "session_coordinator.hpp"
#include "session_participant.hpp"

namespace stratadrive::diagnostics {
// Same-owner observer. Attempts admit diagnostics, never control authority.
class StartupDiagnostics {
public:
    StartupDiagnostics(EventQueue&,ControlContext,Component,unsigned role,bool global=false);
    void attempt(const session::Plan&) noexcept;
    void observe(const std::optional<session::Observation>& fault,const std::optional<session::Observation>& success,
                 bool source_ready,bool globally_released,std::uint64_t now) noexcept;
    bool healthy() const noexcept { return healthy_; }
    bool revalidate_clock(const ClockRevalidation& check) noexcept {return clock_recovery_.revalidate(check,context_.domain,context_.clock_instance);}
    void observe_clock(const ClockRecoverySample& sample) noexcept {
        if(!healthy_)return;
        auto checked=sample;checked.native_healthy=checked.native_healthy && (sample.session.run==context_.run && sample.session.epoch==epoch_);
        clock_recovery_.observe(checked);
        while(auto e=clock_recovery_.take_ready()) {
            const auto id=publish(*e);
            if(!healthy_)return;
            e->kind=Kind::Passed;e->proof_event=id;publish(*e);
        }
    }
private:
    ClockRecovery clock_recovery_;
    Stamp stamp(std::uint64_t,bool trusted=true) const noexcept;
    Event base(const session::Plan&,std::uint64_t) const noexcept;
    EventId publish(Event) noexcept;
    EventQueue& queue_; const ControlContext context_; const Component actor_; const unsigned role_; const bool global_;
    std::uint32_t epoch_{0},released_{0}; std::uint64_t next_{1}; bool seen_{false},healthy_{true};
    struct Pending { Event fault; bool recovered; };
    std::array<std::optional<Pending>,32> pending_{};
};
} // namespace stratadrive::diagnostics
