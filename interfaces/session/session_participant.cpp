#include "session_participant.hpp"

#include <limits>

namespace stratadrive::session {
namespace {
bool transition(ParticipantState state) {
    return state==ParticipantState::Preparing || state==ParticipantState::Prepared ||
        state==ParticipantState::Initializing || state==ParticipantState::Initialized;
}
}
void SessionParticipant::fail(ParticipantFault fault) {
    const bool first=state_!=ParticipantState::Failed; state_=ParticipantState::Failed;
    if(first || fault==ParticipantFault::Clock) fault_=fault;
    if(first) port_.protect();
}
bool SessionParticipant::observe(std::uint64_t now) {
    if(now<observed_ns_ || now==std::numeric_limits<std::uint64_t>::max()) { fail(ParticipantFault::Clock); return false; }
    const auto gap=now-observed_ns_; observed_ns_=now;
    if(transition(state_) && gap>kOwnerGapNs) fail(ParticipantFault::OwnerGap);
    const auto deadline=(state_==ParticipantState::Preparing || state_==ParticipantState::Prepared)?plan_.prepare_deadline_ns:plan_.commit_deadline_ns;
    if(transition(state_) && now>=deadline) fail(ParticipantFault::Timeout);
    return state_!=ParticipantState::Failed;
}
bool SessionParticipant::checkpoint() { return observe(port_.now_ns()); }
std::optional<Ack> SessionParticipant::ack(Phase p,bool accepted) {
    const auto index=static_cast<std::size_t>(p);
    if(!acks_[index]) acks_[index]=Ack{role_,p,plan_,observed_ns_,accepted};
    return acks_[index];
}
std::optional<Ack> SessionParticipant::progress() {
    if(state_==ParticipantState::Preparing) {
        const auto ready=port_.prepare(plan_);
        if(!checkpoint()) return std::nullopt;
        if(ready==Preparation::Rejected) { fail(ParticipantFault::Rejected); return ack(Phase::Prepare,false); }
        if(ready==Preparation::Ready) { state_=ParticipantState::Prepared; return ack(Phase::Prepare,true); }
    } else if(state_==ParticipantState::Initializing && observed_ns_>=plan_.enable_ns) {
        const bool initialized=port_.initialize(plan_);
        if(!checkpoint()) return std::nullopt;
        if(!initialized) { fail(ParticipantFault::Initialize); return ack(Phase::Initialize,false); }
        state_=ParticipantState::Initialized; return ack(Phase::Initialize,true);
    }
    return std::nullopt;
}
std::optional<Ack> SessionParticipant::receive(const Control& c,std::uint64_t now) {
    // Clock rollback is never hidden by a newer proposal.
    if(now<observed_ns_ || c.role!=role_) { if(now<observed_ns_) fail(ParticipantFault::Clock); return std::nullopt; }
    const auto p=static_cast<std::size_t>(c.phase);
    if(c.source_ns>now || now-c.source_ns>kMessageAgeNs || c.source_ns<c.plan.requested_ns || c.plan.epoch==0) return std::nullopt;
    if(c.phase==Phase::Abort) {
        observe(now);
        if(same_proposal(c.plan,plan_)) fail(ParticipantFault::Aborted);
        return std::nullopt;
    }
    if(p>=controls_.size()) return std::nullopt;
    if(c.phase==Phase::Prepare && c.plan.epoch>highest_epoch_) {
        if(c.plan.enable_ns!=0 || c.plan.commit_deadline_ns!=0 || c.plan.prepare_deadline_ns<=now ||
            c.plan.prepare_deadline_ns<=c.plan.requested_ns || c.plan.prepare_deadline_ns-c.plan.requested_ns>kPrepareBudgetNs) return std::nullopt;
        highest_epoch_=c.plan.epoch; observed_ns_=now; plan_=c.plan; state_=ParticipantState::Preparing;
        fault_=ParticipantFault::None; controls_={}; acks_={}; controls_[p]=c;
        return progress();
    }
    if(!observe(now) || !same_proposal(c.plan,plan_)) return std::nullopt;
    if(controls_[p]) {
        const auto& old=*controls_[p];
        return old.source_ns==c.source_ns && same_plan(old.plan,c.plan)?acks_[p]:std::nullopt;
    }
    if(c.phase==Phase::Initialize && state_==ParticipantState::Prepared) {
        if(c.plan.enable_ns<=c.source_ns || c.plan.enable_ns-c.source_ns!=kInitLeadNs ||
            c.plan.commit_deadline_ns<=c.plan.enable_ns || c.plan.commit_deadline_ns-c.plan.enable_ns>kInitWindowNs ||
            c.plan.commit_deadline_ns>c.plan.prepare_deadline_ns || now>=c.plan.commit_deadline_ns) return std::nullopt;
        plan_=c.plan; controls_[p]=c; state_=ParticipantState::Initializing; return progress();
    }
    if(c.phase==Phase::Release && state_==ParticipantState::Initialized && same_plan(c.plan,plan_) &&
        c.source_ns>=plan_.enable_ns && now<plan_.commit_deadline_ns) {
        controls_[p]=c; state_=ParticipantState::Ready; return ack(Phase::Release,true);
    }
    return std::nullopt;
}
std::optional<Ack> SessionParticipant::poll(std::uint64_t now) {
    if(!observe(now)) { port_.service(); return std::nullopt; }
    // At the scheduled boundary initialize before servicing the old actor.
    // A real runnable may wake slightly after enable; advancing the old actor
    // to that later instant first would make the agreed INIT time go backwards.
    if(state_==ParticipantState::Initializing && observed_ns_>=plan_.enable_ns) {
        const auto initialized=progress(); port_.service();
        const auto completed=port_.now_ns();
        const bool in_window=completed>=observed_ns_ && completed<plan_.commit_deadline_ns;
        const bool healthy=checkpoint();
        // A bounded negative INIT ACK must still reach Central. Failed state
        // makes observe() return false even when the clock/window are valid.
        if(!healthy && !(initialized && !initialized->accepted && fault_==ParticipantFault::Initialize && in_window)) return std::nullopt;
        return initialized;
    }
    port_.service(); if(!checkpoint()) return std::nullopt;
    return progress();
}
void SessionParticipant::continuity_lost(std::uint64_t now) { observe(now); fail(ParticipantFault::Continuity); }
}  // namespace stratadrive::session
