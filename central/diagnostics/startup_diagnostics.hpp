#pragma once
#include "diagnostic_publisher.hpp"
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
    bool healthy() const noexcept { return publisher_.healthy(); }
    bool revalidate_clock(const ClockRevalidation& check) noexcept { return publisher_.revalidate_clock(check); }
    void observe_clock(const ClockRecoverySample& sample) noexcept {
        publisher_.observe_clock(sample,sample.session.run==capture_context().run && sample.session.epoch==epoch_);
    }

private:
    DiagnosticPublisher publisher_;
    const ControlContext& capture_context() const noexcept { return publisher_.context(); }
    Stamp stamp(std::uint64_t ns,bool trusted=true) const noexcept { return publisher_.stamp(ns,trusted); }
    Event base(const session::Plan&,std::uint64_t) const noexcept;
    EventId publish(const Event& e) noexcept { return publisher_.publish(e,e.session); }
    const Component actor_; const unsigned role_; const bool global_;
    std::uint32_t epoch_{0},released_{0}; bool seen_{false};
    struct Pending { Event fault; bool recovered; };
    std::array<std::optional<Pending>,32> pending_{};
};
} // namespace stratadrive::diagnostics
