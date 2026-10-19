#include "zone_status.hpp"

namespace stratadrive::zone {
bool valid_zone_status(const ZoneHealthSnapshot& s) {
    if(s.scope!=ZoneScope::Front && s.scope!=ZoneScope::Rear) return false;
    switch(s.phase) {
    case ZonePhase::Waiting:
        return !s.ready_for_normal && s.local_state==can::ActuatorLocalState::Init && s.origin==can::ActuatorOrigin::NoAcceptedInput;
    case ZonePhase::Ready:
    case ZonePhase::Active:
        return s.ready_for_normal && s.local_state==can::ActuatorLocalState::Normal && s.origin==can::ActuatorOrigin::NormalPath;
    case ZonePhase::Terminal:
        return !s.ready_for_normal && s.local_state==can::ActuatorLocalState::Normal && s.origin==can::ActuatorOrigin::NormalPath;
    case ZonePhase::FailSafe:
        return !s.ready_for_normal && s.local_state==can::ActuatorLocalState::FailSafe && s.origin==can::ActuatorOrigin::LocalProtection;
    }
    return false;
}
bool zone_inputs_healthy(const ZoneHealthSnapshot& s) {
    return valid_zone_status(s) && (s.phase==ZonePhase::Ready || s.phase==ZonePhase::Active || s.phase==ZonePhase::Terminal);
}
ZoneStatusReceiver::ZoneStatusReceiver(ZoneScope scope):scope_(scope) {}
bool ZoneStatusReceiver::start_session(std::uint32_t epoch,std::uint64_t enable) {
    if(!state_.start_session(epoch,enable)) return false;
    accepted_.reset(); protection_seen_=terminal_seen_=inputs_seen_=false; return true;
}
can::ActuatorReceiveDecision ZoneStatusReceiver::receive(const ZoneHealthSnapshot& s,std::uint64_t now) {
    // Check the old source deadline before considering a late replacement.
    if(accepted_ && now>=accepted_->source_time_ns && now-accepted_->source_time_ns>30000000ULL) state_.mark_continuity_lost(now);
    if(const auto rejected=state_.begin_receive(now)) return *rejected;
    if(s.scope!=scope_ || !valid_zone_status(s)) return can::ActuatorReceiveDecision::MalformedPayload;
    if(const auto rejected=state_.check_metadata(s,now)) return *rejected;
    if(protection_seen_ && s.phase!=ZonePhase::FailSafe) return can::ActuatorReceiveDecision::ModeRejected;
    if((terminal_seen_ && s.phase!=ZonePhase::Terminal && s.phase!=ZonePhase::FailSafe) ||
        (inputs_seen_ && s.phase==ZonePhase::Waiting)) return can::ActuatorReceiveDecision::ModeRejected;
    state_.commit(s,now); accepted_=s;
    protection_seen_=protection_seen_ || s.phase==ZonePhase::FailSafe;
    terminal_seen_=terminal_seen_ || s.phase==ZonePhase::Terminal;
    inputs_seen_=inputs_seen_ || zone_inputs_healthy(s);
    return can::ActuatorReceiveDecision::Accepted;
}
void ZoneStatusReceiver::mark_continuity_lost(std::uint64_t now) { state_.mark_continuity_lost(now); }
std::optional<ZoneHealthSnapshot> ZoneStatusReceiver::current_sample(std::uint64_t now) {
    if(accepted_ && now>=accepted_->source_time_ns && now-accepted_->source_time_ns>30000000ULL) state_.mark_continuity_lost(now);
    return state_.has_current_sample(now)?accepted_:std::nullopt;
}
}  // namespace stratadrive::zone
