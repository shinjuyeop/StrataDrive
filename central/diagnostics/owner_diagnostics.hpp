#pragma once
#include "diagnostic_publisher.hpp"
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
    bool healthy() const noexcept { return publisher_.healthy(); }
    bool revalidate_clock(const ClockRevalidation& check) noexcept { return publisher_.revalidate_clock(check); }
    void observe_clock(const ClockRecoverySample& sample) noexcept {
        publisher_.observe_clock(sample,sample.session==session_ && sample.released.enable_ns==enable_);
    }

private:
    DiagnosticPublisher publisher_;
    const ControlContext& capture_context() const noexcept { return publisher_.context(); }
    Stamp stamp(std::uint64_t ns,bool trusted=true) const noexcept { return publisher_.stamp(ns,trusted); }
    Event base(std::uint64_t) const noexcept;
    EventId publish(const Event& e) noexcept { return publisher_.publish(e,session_); }
    void selection(std::optional<std::uint64_t>,bool ack) noexcept;
    void passed(Event) noexcept;
    const Component actor_;
    Session session_{}; std::uint64_t enable_{0};
    bool seen_{false},selected_{false},recovered_{false};
    std::optional<Event> target_;
    struct Pending { Event event; bool recovered{false}; };
    // Different missing-stream masks/codes remain separate retained records.
    // Known Front/Rear keys fit in32 slots; never silently evict older keys.
    std::array<std::optional<Pending>,32> zone_pending_{};
};
} // namespace stratadrive::diagnostics
