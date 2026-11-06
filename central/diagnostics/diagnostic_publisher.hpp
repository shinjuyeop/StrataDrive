#pragma once
#include "clock_recovery.hpp"
#include <limits>
#include <stdexcept>

namespace stratadrive::diagnostics {
// Shared numeric dictionary; these are neither CAN IDs nor producer identities.
enum class Component : std::uint32_t { Speed=1, Stop=2, Coordinator=3, Drive=4, Brake=5, Power=6, Front=7, Rear=8, Steering=9, Bms=10, DriveWheel=11 };
enum class Monitor : std::uint32_t { Speed=1, Stop=2, Coordinator=3, SupervisedSpeed=4 };
enum class Subject : std::uint32_t { Wheel=1, StopCycle=2, Handoff=3, Protection=4, Torque=5, Pressure=6, Power=7 };
struct ControlContext {
    std::uint64_t run,producer;
    Domain domain;
    std::uint64_t clock_instance,profile;
};

// One real owner and one bounded queue. Domain adapters retain their fault,
// session and recovery predicates; this class only assigns identities, records
// capture failures and publishes explicitly qualified Clock recovery evidence.
class DiagnosticPublisher {
public:
    DiagnosticPublisher(EventQueue& queue,ControlContext context,std::uint64_t first,
                        const char* error,std::optional<std::uint32_t> exhausted_reason={})
        :queue_(queue),context_(context),next_(first),exhausted_reason_(exhausted_reason) {
        if(!first || !context.run || !context.producer || !context.clock_instance || !context.profile ||
           (context.domain!=Domain::Simulation && context.domain!=Domain::Monotonic))
            throw std::invalid_argument(error);
    }
    const ControlContext& context() const noexcept { return context_; }
    bool healthy() const noexcept { return healthy_; }
    void incomplete() noexcept { healthy_=false; }
    Stamp stamp(std::uint64_t ns,bool trusted=true) const noexcept {
        return {context_.domain,context_.clock_instance,ns,true,trusted};
    }
    EventId publish(Event event,Session occurrence_session) noexcept {
        if(!next_) { incomplete(); return {}; }
        event.id={context_.run,context_.producer,next_};
        if(next_==std::numeric_limits<std::uint64_t>::max()) {
            next_=0;incomplete();event.kind=Kind::Gap;event.key={};event.occurrence={};
            if(exhausted_reason_)event.native_reason=*exhausted_reason_;
        } else ++next_;
        if(event.kind==Kind::Fault)
            event.occurrence={occurrence_session.run,context_.producer,occurrence_session.epoch,event.key.monitor,event.id.sequence};
        if(!queue_.publish(event))incomplete();
        if(!clock_recovery_.remember(event)) {
            incomplete();auto gap=event;gap.kind=Kind::Gap;gap.key={};gap.occurrence={};
            publish(gap,occurrence_session);
        }
        return event.id;
    }
    bool revalidate_clock(const ClockRevalidation& check) noexcept {
        return clock_recovery_.revalidate(check,context_.domain,context_.clock_instance);
    }
    void observe_clock(const ClockRecoverySample& sample,bool matching_session) noexcept {
        if(!healthy())return;
        auto checked=sample;checked.native_healthy=checked.native_healthy && matching_session;
        clock_recovery_.observe(checked);
        while(auto event=clock_recovery_.take_ready()) {
            const auto id=publish(*event,event->session);
            if(!healthy())return;
            event->kind=Kind::Passed;event->proof_event=id;publish(*event,event->session);
        }
    }
private:
    EventQueue& queue_;const ControlContext context_;
    ClockRecovery clock_recovery_;
    std::uint64_t next_;const std::optional<std::uint32_t> exhausted_reason_;
    bool healthy_=true;
};
} // namespace stratadrive::diagnostics
