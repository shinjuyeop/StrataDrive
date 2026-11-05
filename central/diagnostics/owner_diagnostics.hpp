#pragma once
#include "control_diagnostics.hpp"
#include "leaf_authority_observation.hpp"
#include "zone_feedback_monitor.hpp"

namespace stratadrive::diagnostics {
// One instance/queue per real owner. The global Session is issued only by
// Central; per-owner INIT never masquerades as a new global session.
class OwnerDiagnostics {
public:
    OwnerDiagnostics(EventQueue&,ControlContext,Component,std::uint64_t first_sequence=1);
    bool start_session(std::uint32_t epoch,std::uint64_t enable) noexcept;
    void zone(const zone::ZoneFeedbackMonitor&,bool normal_gate,std::optional<std::uint64_t> ack,std::uint64_t now) noexcept;
    void leaf(const std::optional<transport::LeafAuthorityObservation>& expired,
        const std::optional<transport::LeafAuthorityObservation>& success,bool healthy,bool normal_gate,
        std::optional<std::uint64_t> selected,std::uint64_t now) noexcept;
    bool healthy() const noexcept { return healthy_; }
    bool revalidate_clock(const ClockRevalidation& check) noexcept {return clock_recovery_.revalidate(check,context_.domain,context_.clock_instance);}
    void observe_clock(const ClockRecoverySample& sample) noexcept {
        if(!healthy_)return;
        auto checked=sample;checked.native_healthy=checked.native_healthy && (sample.session==session_ && sample.released.enable_ns==enable_);
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
    Event base(std::uint64_t) const noexcept;
    EventId publish(Event) noexcept;
    void selection(std::optional<std::uint64_t>,bool ack) noexcept;
    void passed(Event) noexcept;
    EventQueue& queue_; const ControlContext context_; const Component actor_;
    Session session_{}; std::uint64_t enable_{0},next_{1};
    bool healthy_{true},seen_{false},selected_{false},recovered_{false};
    std::optional<Event> target_;
    struct Pending { Event event; bool recovered{false}; };
    // Different missing-stream masks/codes remain separate retained records.
    // Known Front/Rear keys fit in32 slots; never silently evict older keys.
    std::array<std::optional<Pending>,32> zone_pending_{};
};
} // namespace stratadrive::diagnostics
