#include "session_coordinator.hpp"

#include <algorithm>
#include <limits>

namespace stratadrive::session {
namespace {
bool transitioning(State state) { return state==State::Preparing || state==State::Initializing || state==State::Releasing; }
Phase phase(State state) { return state==State::Preparing?Phase::Prepare:state==State::Initializing?Phase::Initialize:Phase::Release; }
}
void SessionCoordinator::fail(Fault fault) {
    const bool first=state_!=State::Failed;
    state_=State::Failed;
    if(first || fault==Fault::Clock) fault_=fault;
    if(!first) return;
    port_.protect_central();
    // Best effort Abort. A broken owner link must also close locally; its
    // original deadline stays armed even when this Abort cannot be delivered.
    for(std::size_t i=0;i<kRoleCount;++i) port_.send({static_cast<Role>(i),Phase::Abort,plan_,observed_ns_});
}
bool SessionCoordinator::observe(std::uint64_t now) {
    if(now<observed_ns_ || now==std::numeric_limits<std::uint64_t>::max()) { fail(Fault::Clock); return false; }
    const auto gap=now-observed_ns_; observed_ns_=now;
    if(transitioning(state_) && gap>kOwnerGapNs) fail(Fault::OwnerGap);
    const auto deadline=state_==State::Preparing?plan_.prepare_deadline_ns:plan_.commit_deadline_ns;
    if(transitioning(state_) && now>=deadline) fail(Fault::Timeout);
    return state_!=State::Failed;
}
bool SessionCoordinator::checkpoint() { return observe(port_.now_ns()); }
bool SessionCoordinator::broadcast(Phase p) {
    phase_source_ns_=observed_ns_;
    for(std::size_t i=0;i<kRoleCount;++i) {
        if(!port_.send({static_cast<Role>(i),p,plan_,phase_source_ns_})) { fail(Fault::Send); return false; }
        if(!checkpoint()) return false;
    }
    return true;
}
bool SessionCoordinator::begin(std::uint32_t epoch,std::uint64_t now) {
    if(epoch==0 || epoch<=highest_epoch_ || transitioning(state_) || state_==State::Running || now<observed_ns_ ||
        now>std::numeric_limits<std::uint64_t>::max()-kPrepareBudgetNs) return false;
    highest_epoch_=epoch; observed_ns_=now; accepted_={}; fault_=Fault::None;
    plan_={epoch,now,now+kPrepareBudgetNs,0,0}; state_=State::Preparing;
    if(!port_.quiesce_central()) { fail(Fault::Quiesce); return false; }
    return checkpoint() && broadcast(Phase::Prepare);
}
void SessionCoordinator::next_phase() {
    if(!std::all_of(accepted_.begin(),accepted_.end(),[](const auto& ack) { return ack.has_value(); })) return;
    if(state_==State::Preparing) {
        // Enable is assigned only after all owners are quiesced. It is not the
        // potentially old start of the physical recovery/prepare phase.
        const auto remaining=plan_.prepare_deadline_ns-observed_ns_;
        if(remaining<=kInitLeadNs) { fail(Fault::Timeout); return; }
        plan_.enable_ns=observed_ns_+kInitLeadNs;
        plan_.commit_deadline_ns=plan_.enable_ns+std::min(kInitWindowNs,remaining-kInitLeadNs);
        if(plan_.enable_ns>=plan_.commit_deadline_ns) { fail(Fault::Timeout); return; }
        state_=State::Initializing; accepted_={}; broadcast(Phase::Initialize);
    } else if(state_==State::Initializing) {
        if(!port_.commit_central({plan_.epoch,plan_.enable_ns})) { fail(Fault::CentralCommit); return; }
        if(!checkpoint()) return;
        state_=State::Releasing; accepted_={}; broadcast(Phase::Release);
    } else if(state_==State::Releasing) state_=State::Running;
}
AckResult SessionCoordinator::receive(const Ack& ack,std::uint64_t now) {
    if(!observe(now)) return AckResult::Latched;
    const auto index=static_cast<std::size_t>(ack.role);
    if(index>=kRoleCount || state_==State::Quiet || ack.phase!=phase(state_) || !same_plan(ack.plan,plan_) ||
        ack.source_ns<phase_source_ns_ || ack.source_ns>now || now-ack.source_ns>kMessageAgeNs ||
        (ack.phase!=Phase::Prepare && ack.source_ns<plan_.enable_ns)) return AckResult::Rejected;
    if(accepted_[index]) return same_ack(*accepted_[index],ack)?AckResult::Unchanged:AckResult::Rejected;
    if(state_==State::Running) return AckResult::Rejected;
    if(!ack.accepted) { fail(Fault::Participant); return AckResult::Latched; }
    accepted_[index]=ack; next_phase();
    return state_==State::Failed?AckResult::Latched:AckResult::Accepted;
}
void SessionCoordinator::poll(std::uint64_t now) { observe(now); }
void SessionCoordinator::cancel(std::uint64_t now) { observe(now); fail(Fault::Cancelled); }
void SessionCoordinator::continuity_lost(std::uint64_t now) { observe(now); fail(Fault::Continuity); }
}  // namespace stratadrive::session
