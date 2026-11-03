#include "command_gateway.hpp"

namespace stratadrive::zone {
namespace {
const central::CommandContext& context(const central::ScopedCommands& commands) {
    return std::visit([](const auto& c) -> const central::CommandContext& { return c; }, commands);
}
std::uint32_t sequence(const central::ScopedCommands& commands) {
    if (const auto* front = std::get_if<central::FrontCommands>(&commands)) return front->steering.sequence;
    return std::get<central::RearCommands>(commands).drive.sequence;
}
}  // namespace
CommandGateway::CommandGateway(ZoneScope scope, GatewayPort& port, const AdmissionConfig& config)
    : scope_(scope), port_(port), admission_(scope, config),config_(config) {}
bool CommandGateway::start_session(std::uint32_t epoch, std::uint64_t enable) {
    const auto now = port_.now_ns();
    if (epoch == 0 || epoch <= epoch_ || enable > now || (epoch_ != 0 && (enable < observed_ns_ || now < observed_ns_))) return false;
    if (!admission_.start_session(epoch, enable)) return false;
    queue_.start_session(epoch); safety_.start_session(epoch); stop_.reset(enable);
    e2e::p05_protect_init(steering_tx_.protection); e2e::p05_protect_init(brake_tx_.protection); e2e::p05_protect_init(drive_tx_.protection);
    epoch_ = epoch; observed_ns_ = call_ns_=now; enable_ns_=enable; armed_since_=enable;
    last_context_.reset(); first_fault_.reset(); success_.reset(); return true;
}
NativeObservation CommandGateway::observation(ProtectionCause cause,bool propagation) const {
    NativeObservation o; o.epoch=epoch_; o.enable_ns=enable_ns_; o.observed_ns=call_ns_; o.phase_origin_ns=armed_since_;
    o.reason=static_cast<std::uint32_t>(cause); o.detail=static_cast<std::uint32_t>(admission_.decision().fault);
    o.state=static_cast<std::uint32_t>(admission_.decision().state); o.propagation=propagation; o.writes=writes_in_dispatch_;
    o.timing={config_.command_source_age_ns,config_.dependency_age_ns,config_.command_timeout_ns};
    if(last_context_) { const auto& c=*last_context_; const auto& p=c.parent; o.root=NativeRoot{p.epoch,p.sequence,p.source_time_ns,c.expires_at_ns,c.oldest_input_time_ns};
        o.valid_until_ns=c.expires_at_ns;
        if(cause==ProtectionCause::CommandExpired && call_ns_>=c.expires_at_ns) o.violation_ns=c.expires_at_ns; }
    return o;
}
void CommandGateway::fail(ProtectionCause cause,bool propagation) {
    if(!first_fault_ && cause!=ProtectionCause::None) first_fault_=observation(cause,propagation);
    safety_.request(cause); admission_.mark_continuity_lost(observed_ns_);
    for (std::size_t i = 0; i < kCapacity; ++i) if (!queue_.pop()) break;
    safety_.dispatch(port_, scope_, observed_ns_);
}
bool CommandGateway::refresh() {
    if (epoch_ == 0) return false;
    const auto now = port_.now_ns();
    call_ns_=now;
    if (now < observed_ns_) { admission_.poll(now); fail(ProtectionCause::ClockError); return false; }
    observed_ns_ = now;
    if(stop_.active()) {
        if(!stop_.live(now)) fail(ProtectionCause::CommandExpired);
        safety_.dispatch(port_,scope_,now); return safety_.decision().cause==ProtectionCause::None;
    }
    const auto state = admission_.poll(now);
    if (state.protection_required) {
        const auto cause = state.fault == AdmissionFault::CommandExpired ? ProtectionCause::CommandExpired :
            state.fault == AdmissionFault::ClockError ? ProtectionCause::ClockError : ProtectionCause::UpstreamLost;
        fail(cause); return false;
    }
    safety_.dispatch(port_, scope_, now);
    return safety_.decision().cause == ProtectionCause::None;
}
bool CommandGateway::arm() {
    const bool ok=refresh() && !stop_.active() && admission_.arm(observed_ns_);
    if(ok) { armed_since_=observed_ns_; }
    return ok;
}
bool CommandGateway::select_normal_stop(const ActuatorStopLease& lease) {
    if(!refresh() || (!stop_.active() && admission_.decision().state!=AdmissionState::Active)) return false;
    if(!stop_.accept(lease,epoch_,observed_ns_)) return false;
    for(std::size_t i=0;i<kCapacity;++i) if(!queue_.pop()) break;
    return true;
}
AdmissionResult CommandGateway::authorize_request(const central::VehicleRequest& parent) {
    if (!refresh()) return epoch_ == 0 ? AdmissionResult::NotInitialized : AdmissionResult::Latched;
    if(stop_.active()) return AdmissionResult::NotArmed;
    return admission_.authorize_request(parent, observed_ns_);
}
AdmissionResult CommandGateway::enqueue(const central::ScopedCommands& commands) {
    if (!refresh()) return epoch_ == 0 ? AdmissionResult::NotInitialized : AdmissionResult::Latched;
    if(stop_.active()) return AdmissionResult::NotArmed;
    const auto result = admission_.receive(commands, observed_ns_);
    if(result==AdmissionResult::Accepted) last_context_=context(commands);
    if (result == AdmissionResult::Accepted && !queue_.push(commands)) {
        fail(ProtectionCause::QueueOverflow); return AdmissionResult::Latched;
    }
    return result;
}
GatewayDispatch CommandGateway::dispatch() {
    writes_in_dispatch_=0;
    GatewayDispatch result;
    if (!refresh() || stop_.active()) return result;
    const auto current = admission_.current_command(observed_ns_);
    if (!current) return result;
    for (std::size_t i = 0; i < kCapacity; ++i) {
        auto item = queue_.pop(); if (!item) return result;
        if (sequence(*item) != sequence(*current)) { ++result.superseded; continue; }
        const auto send = [&](const CommandFrame& frame) {
            if (!refresh()) return false;
            if (observed_ns_ >= context(*item).expires_at_ns) { fail(ProtectionCause::CommandExpired); return false; }
            const bool sent = port_.send(frame, context(*item));
            if (sent) { ++result.frames_enqueued; ++writes_in_dispatch_; }
            // The write may consume time or expose a partial Front dispatch.
            const bool live = refresh();
            if (!sent && live) fail(ProtectionCause::SendFailure);
            return sent && live;
        };
        if (const auto* front = std::get_if<central::FrontCommands>(&*item)) {
            const auto steering = can::encode_steering_frame(front->steering, steering_tx_);
            const auto brake = can::encode_brake_frame(front->brake, brake_tx_);
            if (!steering || !brake) { fail(ProtectionCause::SendFailure); return result; }
            if (send(*steering)) send(*brake);
            result.partial_front = result.frames_enqueued == 1;
        } else {
            const auto frame = can::encode_drive_frame(std::get<central::RearCommands>(*item).drive, drive_tx_);
            if (!frame) fail(ProtectionCause::SendFailure);
            else send(*frame);
        }
        if(safety_.decision().cause==ProtectionCause::None && !result.partial_front &&
           result.frames_enqueued==(scope_==ZoneScope::Front?2U:1U)) {
            success_=observation(ProtectionCause::None); success_->observed_ns=observed_ns_;
            success_->writes=static_cast<std::uint32_t>(result.frames_enqueued); success_->qualified=true;
        }
        writes_in_dispatch_=0;
        return result;
    }
    return result;
}
GatewayDecision CommandGateway::poll() {
    refresh(); return {admission_.decision(), safety_.decision(), queue_.size()};
}
void CommandGateway::mark_continuity_lost() { if (epoch_ != 0) { refresh(); fail(ProtectionCause::UpstreamLost,true); } }
void CommandGateway::request_protection() { if (epoch_ != 0) { refresh(); fail(ProtectionCause::CoordinatorRequest,true); } }
}  // namespace stratadrive::zone
