#pragma once
#include "control_diagnostics.hpp"
#include "native_fault_observation.hpp"

namespace stratadrive::diagnostics {
enum class NativeMonitor : std::uint32_t { CommandGateway=6,RearPowerGateway=7,Bms=8,Power=9 };
// Same-owner bounded publisher. Native reason/config evidence is not a command.
class NativeDiagnostics {
public:
    NativeDiagnostics(EventQueue&,ControlContext,Component);
    bool start_session(std::uint32_t,std::uint64_t) noexcept;
    void selection(NativeMonitor,std::optional<std::uint64_t>,bool acknowledgement) noexcept;
    void observe(NativeMonitor,const std::optional<NativeObservation>& fault,const std::optional<NativeObservation>& propagation,
        const std::optional<NativeObservation>& success,bool currently_healthy,bool normal_gate,std::uint64_t now) noexcept;
    bool healthy() const noexcept { return healthy_; }
private:
    Stamp stamp(std::uint64_t,bool trusted=true) const noexcept;
    Event base(std::uint64_t) const noexcept;
    EventId publish(Event) noexcept;
    void failure(NativeMonitor,const NativeObservation&,std::uint64_t) noexcept;
    EventQueue& queue_; const ControlContext context_; const Component actor_;
    Session session_{}; std::uint64_t enable_{0},next_{1}; bool healthy_{true};
    std::array<std::array<bool,2>,4> seen_{};
    struct Pending { Event event; bool recovered,selected; };
    std::array<std::optional<Pending>,64> pending_{};
};
} // namespace stratadrive::diagnostics
