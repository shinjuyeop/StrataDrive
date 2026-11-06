#pragma once
#include "diagnostic_publisher.hpp"
#include "native_fault_observation.hpp"

namespace stratadrive::diagnostics {
enum class NativeMonitor : std::uint32_t { CommandGateway=6,RearPowerGateway=7,Bms=8,Power=9 };
// Same-owner bounded publisher. Native reason/config evidence is not a command.
class NativeDiagnostics {
public:
    NativeDiagnostics(EventQueue&,ControlContext,Component,std::uint64_t first_sequence=1);
    bool start_session(std::uint32_t,std::uint64_t) noexcept;
    void selection(NativeMonitor,std::optional<std::uint64_t>,bool acknowledgement) noexcept;
    void observe(NativeMonitor,const std::optional<NativeObservation>& fault,const std::optional<NativeObservation>& propagation,
        const std::optional<NativeObservation>& success,bool currently_healthy,bool normal_gate,std::uint64_t now) noexcept;
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
    void failure(NativeMonitor,const NativeObservation&,std::uint64_t) noexcept;
    const Component actor_;
    Session session_{}; std::uint64_t enable_{0};
    std::array<std::array<bool,2>,4> seen_{};
    struct Pending { Event event; bool recovered,selected; };
    std::array<std::optional<Pending>,64> pending_{};
};
} // namespace stratadrive::diagnostics
