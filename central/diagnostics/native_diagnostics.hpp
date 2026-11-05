#pragma once
#include "control_diagnostics.hpp"
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
    void failure(NativeMonitor,const NativeObservation&,std::uint64_t) noexcept;
    EventQueue& queue_; const ControlContext context_; const Component actor_;
    Session session_{}; std::uint64_t enable_{0},next_{1}; bool healthy_{true};
    std::array<std::array<bool,2>,4> seen_{};
    struct Pending { Event event; bool recovered,selected; };
    std::array<std::optional<Pending>,64> pending_{};
};
} // namespace stratadrive::diagnostics
