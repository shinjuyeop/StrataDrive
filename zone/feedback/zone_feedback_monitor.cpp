#include "zone_feedback_monitor.hpp"

#include <algorithm>
#include <limits>
#include <stdexcept>

namespace stratadrive::zone {
namespace {
template<class M> bool protected_source(const std::optional<M>& m) {
    return m && (m->local_state==can::ActuatorLocalState::FailSafe || m->origin==can::ActuatorOrigin::LocalProtection);
}
bool protected_source(const std::optional<can::BmsCurrentSample>& m) {
    return m && (m->message.local_state==can::ActuatorLocalState::FailSafe || m->message.origin==can::ActuatorOrigin::LocalProtection);
}
}
ZoneFeedbackMonitor::ZoneFeedbackMonitor(CommandGateway& commands,RearPowerGateway* power):commands_(commands),power_(power) {
    if((commands.scope()==ZoneScope::Rear)!=(power!=nullptr)) throw std::invalid_argument("Zone feedback scope/power binding");
}
bool ZoneFeedbackMonitor::start_session(std::uint32_t epoch,std::uint64_t enable) {
    if(epoch==0 || epoch<=epoch_ || (epoch_!=0 && enable<observed_ns_) || commands_.application_epoch()!=epoch ||
        (power_ && power_->application_epoch()!=epoch) || commands_.observed_time_ns()<enable ||
        (power_ && power_->observed_time_ns()<enable)) return false;
    epoch_=epoch; enable_ns_=enable;
    observed_ns_=std::max(commands_.observed_time_ns(),power_?power_->observed_time_ns():enable);
    sequence_=0; tick_ns_.reset(); seen_={}; fault_=ZoneFeedbackFault::None; return true;
}
void ZoneFeedbackMonitor::fail(ZoneFeedbackFault fault) {
    if(fault_==ZoneFeedbackFault::None || fault==ZoneFeedbackFault::ClockError) fault_=fault;
    commands_.request_protection();
    if(power_) power_->mark_continuity_lost();
}
std::optional<ZoneHealthSnapshot> ZoneFeedbackMonitor::tick(const ZoneFeedbackInputs& in,std::uint64_t now) {
    if(epoch_==0) return std::nullopt;
    if(now<observed_ns_) { fail(ZoneFeedbackFault::ClockError); return std::nullopt; }
    observed_ns_=now;
    if(tick_ns_ && now-*tick_ns_<10000000ULL) return std::nullopt;
    if(now-tick_ns_.value_or(enable_ns_)>30000000ULL) fail(ZoneFeedbackFault::ControlDeadline);
    tick_ns_=now;
    const auto gateway=commands_.poll();
    const auto power=power_?std::optional<RearPowerDecision>{power_->poll()}:std::nullopt;
    // A real clock may advance during port callbacks. Keep that observation;
    // never stamp the result earlier or require nanosecond equality.
    if(commands_.observed_time_ns()<now || (power_ && power_->observed_time_ns()<now)) {
        fail(ZoneFeedbackFault::ClockError); return std::nullopt;
    }
    const auto completed=std::max(commands_.observed_time_ns(),power_?power_->observed_time_ns():now);
    observed_ns_=completed;
    if(completed-now>30000000ULL) fail(ZoneFeedbackFault::ControlDeadline);
    if(commands_.application_epoch()!=epoch_ || (power_ && power_->application_epoch()!=epoch_) ||
        gateway.safety.cause!=ProtectionCause::None || gateway.admission.state==AdmissionState::NotInitialized ||
        gateway.admission.state==AdmissionState::FailSafe || (power && power->safety.cause!=ProtectionCause::None)) fail(ZoneFeedbackFault::GatewayProtection);
    const feedback::SourceContext context{epoch_,enable_ns_,completed};
    const bool front=commands_.scope()==ZoneScope::Front;
    const std::array<bool,5> healthy{feedback::steering_available(in.steering,context),feedback::brake_available(in.brake,context),
        feedback::drive_available(in.drive,context),feedback::power_available(in.power_status,context,false),feedback::limits_available(in.power_limits,context,false)};
    if(front?(protected_source(in.steering)||protected_source(in.brake)):
        (protected_source(in.drive)||protected_source(in.power_status)||protected_source(in.power_limits))) fail(ZoneFeedbackFault::SourceProtection);
    bool all=true;
    for(std::size_t i=front?0:2;i<(front?2U:5U);++i) {
        if(!healthy[i] && (seen_[i] || completed-enable_ns_>=80000000ULL)) fail(ZoneFeedbackFault::InputsUnavailable);
        seen_[i]=seen_[i]||healthy[i]; all=all&&healthy[i];
    }
    if(sequence_>std::numeric_limits<std::uint32_t>::max()) { fail(ZoneFeedbackFault::SequenceExhausted); return std::nullopt; }
    ZoneHealthSnapshot result;
    result.scope=commands_.scope(); result.epoch=epoch_; result.sequence=static_cast<std::uint32_t>(sequence_++); result.source_time_ns=completed;
    if(fault_!=ZoneFeedbackFault::None) {
        result.phase=ZonePhase::FailSafe; result.local_state=can::ActuatorLocalState::FailSafe; result.origin=can::ActuatorOrigin::LocalProtection;
    } else if(!all) {
        result.phase=ZonePhase::Waiting; result.local_state=can::ActuatorLocalState::Init; result.origin=can::ActuatorOrigin::NoAcceptedInput;
    } else {
        const bool terminal=commands_.normal_stop_selected();
        if(power_ && power_->normal_stop_selected()!=terminal) {
            fail(ZoneFeedbackFault::GatewayProtection);
            result.phase=ZonePhase::FailSafe; result.local_state=can::ActuatorLocalState::FailSafe; result.origin=can::ActuatorOrigin::LocalProtection;
            return result;
        }
        result.phase=terminal?ZonePhase::Terminal:gateway.admission.state==AdmissionState::Idle?ZonePhase::Ready:ZonePhase::Active;
        result.ready_for_normal=!terminal; result.local_state=can::ActuatorLocalState::Normal; result.origin=can::ActuatorOrigin::NormalPath;
    }
    return result;
}
}  // namespace stratadrive::zone
