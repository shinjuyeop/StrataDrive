#include "rear_power_gateway.hpp"

#include <algorithm>
#include <limits>

namespace stratadrive::zone {
namespace {
constexpr std::uint64_t kSourceAge=50000000, kDependencyAge=70000000;
const can::BmsPhysicalRanges kRanges{{0,1000},{-3000,3000},{-50,150},100000};
std::uint64_t add(std::uint64_t a,std::uint64_t b) { return std::numeric_limits<std::uint64_t>::max()-a<b?std::numeric_limits<std::uint64_t>::max():a+b; }
bool same_parent(const can::BmsParentContext& a,const can::BmsParentContext& b) {
    return a.epoch==b.epoch && a.sequence==b.sequence && a.source_time_ns==b.source_time_ns && a.expires_at_ns==b.expires_at_ns;
}
bool usable(const std::optional<can::BmsCurrentSample>& s,bool pair=false) {
    return s && s->quality[0]==can::BmsFieldQuality::Usable && (!pair || s->quality[1]==can::BmsFieldQuality::Usable);
}
bool normal_status(const can::BmsCurrentSample& s) {
    return s.message.origin==can::ActuatorOrigin::NormalPath && s.message.local_state==can::ActuatorLocalState::Normal;
}
std::size_t index(can::BmsFrameKind kind) {
    return kind==can::BmsFrameKind::PowerRequest?0:kind==can::BmsFrameKind::DrivePermission?1:kind==can::BmsFrameKind::PowerLimits?2:3;
}
std::uint64_t deadline(const can::BmsMessage& m) {
    auto result=add(m.source_time_ns,kSourceAge+1);
    if(const auto* p=std::get_if<can::BmsPowerRequest>(&m.content)) return std::min(result,p->expires_at_ns);
    if(const auto* g=std::get_if<can::BmsDriveGrant>(&m.content)) {
        result=std::min(result,g->expires_at_ns);
        if(g->permission==can::BmsDrivePermission::AllowNormal) result=std::min({result,add(g->input_time_ns,kDependencyAge+1),add(g->power_status_source_time_ns,kSourceAge+1)});
    }
    if(const auto* l=std::get_if<can::BmsPowerLimits>(&m.content)) result=std::min(result,add(l->input_time_ns,kDependencyAge+1));
    if(const auto* s=std::get_if<can::BmsPowerStatus>(&m.content)) result=std::min(result,add(s->input_time_ns,kDependencyAge+1));
    return result;
}
} // namespace
RearPowerGateway::RearPowerGateway(RearPowerPort& port):port_(port),
    power_rx_({can::BmsFrameKind::PowerRequest,kRanges}),permission_rx_({can::BmsFrameKind::DrivePermission,kRanges}),
    limits_rx_({can::BmsFrameKind::PowerLimits,kRanges}),status_rx_({can::BmsFrameKind::PowerStatus,kRanges}) {}
bool RearPowerGateway::start_session(std::uint32_t epoch,std::uint64_t enable) {
    const auto now=port_.now_ns();
    if(epoch==0 || epoch<=epoch_ || enable>now || (epoch_!=0 && (enable<observed_ns_ || now<observed_ns_))) return false;
    if(!power_rx_.start_session(epoch,enable) || !permission_rx_.start_session(epoch,enable) || !limits_rx_.start_session(epoch,enable) || !status_rx_.start_session(epoch,enable)) return false;
    queue_.start_session(epoch); safety_.start_session(epoch); stop_.reset(enable); root_.reset(); status_history_={}; sent_power_={}; expiry_={};
    for(auto* tx:{&power_validation_,&permission_validation_,&power_tx_,&permission_tx_,&limits_tx_}) e2e::p05_protect_init(tx->protection);
    epoch_=epoch; enable_ns_=enable; observed_ns_=now; normal_armed_=false; return true;
}
void RearPowerGateway::fail(ProtectionCause cause) {
    safety_.request(cause);
    for(std::size_t i=0;i<kCapacity;++i) if(!queue_.pop()) break;
    safety_.dispatch(port_,ZoneScope::Rear,observed_ns_);
}
bool RearPowerGateway::refresh() {
    if(epoch_==0) return false;
    const auto now=port_.now_ns();
    if(now<observed_ns_) { fail(ProtectionCause::ClockError); return false; }
    observed_ns_=now;
    if(safety_.decision().cause!=ProtectionCause::None) { safety_.dispatch(port_,ZoneScope::Rear,now); return false; }
    if(stop_.active() && !stop_.live(now)) { fail(ProtectionCause::CommandExpired); return false; }
    for(const auto& bound:expiry_) if(bound && now>=*bound) { fail(ProtectionCause::CommandExpired); return false; }
    auto power=power_rx_.current_sample(now), permission=permission_rx_.current_sample(now), limits=limits_rx_.current_sample(now), status=status_rx_.current_sample(now);
    const std::array<bool,4> live{usable(power),usable(permission),usable(limits,true),usable(status,true)};
    for(std::size_t i=0;i<live.size();++i) {
        if(!live[i] && (expiry_[i] || now-enable_ns_>=80000000)) { fail(ProtectionCause::UpstreamLost); return false; }
    }
    for(const auto* s:{&power,&permission,&limits,&status}) {
        if(*s && ((*s)->message.local_state==can::ActuatorLocalState::FailSafe || (*s)->message.origin==can::ActuatorOrigin::LocalProtection)) {
            fail(ProtectionCause::UpstreamLost); return false;
        }
    }
    if(normal_armed_ && !stop_.active() && (!status || !normal_status(*status) || !can::bms_power_is_ready(*status))) { fail(ProtectionCause::UpstreamLost); return false; }
    return true;
}
RearPowerResult RearPowerGateway::authorize_request(const central::LifecycleRequest& r) {
    if(!refresh()) return epoch_==0?RearPowerResult::NotInitialized:RearPowerResult::Latched;
    if(stop_.active() && r.action!=can::BmsPowerAction::Shutdown) return RearPowerResult::ParentRejected;
    const auto& p=r.identity;
    if(p.epoch!=epoch_ || p.source_time_ns<enable_ns_ || p.source_time_ns>observed_ns_ || observed_ns_-p.source_time_ns>kSourceAge ||
        p.expires_at_ns<=observed_ns_ || p.expires_at_ns<=p.source_time_ns || p.expires_at_ns-p.source_time_ns>can::kBmsMaxLifetimeNs ||
        (r.action!=can::BmsPowerAction::Enable && r.action!=can::BmsPowerAction::Shutdown && r.action!=can::BmsPowerAction::KeepOff)) return RearPowerResult::ParentRejected;
    if(root_ && p.sequence==root_->identity.sequence) return same_parent(p,root_->identity) && r.action==root_->action?RearPowerResult::Accepted:RearPowerResult::ParentRejected;
    if(!can::actuator_sequence_progresses(root_?std::optional<std::uint32_t>{root_->identity.sequence}:std::nullopt,p.sequence) ||
        (root_ && p.source_time_ns<=root_->identity.source_time_ns)) return RearPowerResult::ParentRejected;
    root_=r; return RearPowerResult::Accepted;
}
bool RearPowerGateway::ready() const {
    if(!root_ || root_->action!=can::BmsPowerAction::Enable || observed_ns_>=root_->identity.expires_at_ns || observed_ns_-root_->identity.source_time_ns>kSourceAge) return false;
    // refresh() has already checked the original source/dependency expiry.
    const auto& status=status_rx_.last_accepted(); const auto& permission=permission_rx_.last_accepted();
    const auto& limits=limits_rx_.last_accepted();
    if(!status || !permission || !limits || limits->message.origin!=can::ActuatorOrigin::NormalPath ||
        (limits->message.local_state!=can::ActuatorLocalState::Normal && limits->message.local_state!=can::ActuatorLocalState::Degraded)) return false;
    const auto* grant=std::get_if<can::BmsDriveGrant>(&permission->message.content);
    return grant && grant->permission==can::BmsDrivePermission::Inhibit && std::any_of(status_history_.begin(),status_history_.end(),[&](const auto& s){
        return s && s->message.sequence==status->message.sequence && s->message.source_time_ns==status->message.source_time_ns && acknowledged(*s);
    });
}
const RearPowerGateway::SentPower* RearPowerGateway::acknowledged(const can::BmsCurrentSample& s) const {
    if(observed_ns_>=deadline(s.message) || !normal_status(s) || !can::bms_power_is_ready(s)) return nullptr;
    const auto& actual=std::get<can::BmsPowerStatus>(s.message.content);
    for(const auto& sent:sent_power_) {
        if(!sent || !sent->parent || sent->message.sequence!=s.message.causal_sequence || sent->message.source_time_ns!=actual.accepted_request_source_time_ns ||
            observed_ns_>=sent->expires_at_ns || observed_ns_-sent->parent->source_time_ns>kSourceAge) continue;
        if(std::get<can::BmsPowerRequest>(sent->message.content).action==can::BmsPowerAction::Enable) return &*sent;
    }
    return nullptr;
}
bool RearPowerGateway::select_normal_stop(const ActuatorStopLease& lease) {
    if(!refresh() || !normal_armed_) return false;
    const bool first=!stop_.active();
    if(!stop_.accept(lease,epoch_,observed_ns_)) return false;
    if(first) for(std::size_t i=0;i<kCapacity;++i) if(!queue_.pop()) break;
    return true;
}
bool RearPowerGateway::arm_normal_commands() {
    if(!refresh() || normal_armed_ || !ready()) return false;
    if(!port_.arm_normal_commands(epoch_,observed_ns_)) { fail(ProtectionCause::UpstreamLost); return false; }
    normal_armed_=true; return true;
}
bool RearPowerGateway::grant_supported(const can::BmsMessage& message) const {
    const auto* grant=std::get_if<can::BmsDriveGrant>(&message.content);
    if(!grant || !normal_armed_ || stop_.active()) return false;
    for(const auto& s:status_history_) {
        if(!s || s->message.sequence!=grant->power_status_sequence || s->message.source_time_ns!=grant->power_status_source_time_ns ||
            observed_ns_>=deadline(s->message) || !can::bms_power_is_ready(*s)) continue;
        const auto* sent=acknowledged(*s); if(!sent) continue;
        const auto& actual=std::get<can::BmsPowerStatus>(s->message.content);
        if(grant->input_time_ns>actual.input_time_ns || grant->expires_at_ns>deadline(s->message)) continue;
        if(grant->expires_at_ns<=sent->expires_at_ns) return true;
    }
    return false;
}
RearPowerResult RearPowerGateway::enqueue(const can::BmsMessage& m,bool permission) {
    if(!refresh()) return epoch_==0?RearPowerResult::NotInitialized:RearPowerResult::Latched;
    const auto kind=permission?can::BmsFrameKind::DrivePermission:can::BmsFrameKind::PowerRequest;
    if(m.kind!=kind) return RearPowerResult::Rejected;
    std::optional<can::BmsParentContext> parent;
    if(permission) {
        const auto* g=std::get_if<can::BmsDriveGrant>(&m.content); if(!g) return RearPowerResult::Rejected;
        if(g->permission==can::BmsDrivePermission::AllowNormal) {
            if(!root_ || root_->action!=can::BmsPowerAction::Enable) return RearPowerResult::ParentRejected;
            parent=root_->identity;
            if(!grant_supported(m)) return RearPowerResult::NotReady;
        }
    } else {
        const auto* r=std::get_if<can::BmsPowerRequest>(&m.content); if(!r) return RearPowerResult::Rejected;
        if(stop_.active() && r->action==can::BmsPowerAction::Enable) return RearPowerResult::NotReady;
        if(m.origin==can::ActuatorOrigin::NormalPath) {
            if(!root_ || root_->action!=r->action) return RearPowerResult::ParentRejected;
            parent=root_->identity;
        }
    }
    auto& tx=permission?permission_validation_:power_validation_; auto& rx=permission?permission_rx_:power_rx_;
    const auto frame=can::encode_bms_frame(m,tx); if(!frame) return RearPowerResult::Rejected;
    const auto result=rx.receive(*frame,observed_ns_,parent?&*parent:nullptr);
    if(result.decision!=can::ActuatorReceiveDecision::Accepted || result.quality[0]!=can::BmsFieldQuality::Usable) return RearPowerResult::Rejected;
    auto bound=deadline(m); if(parent) bound=std::min({bound,parent->expires_at_ns,add(parent->source_time_ns,kSourceAge+1)});
    expiry_[permission?1:0]=bound;
    if(!queue_.push({m,parent,bound})) { fail(ProtectionCause::QueueOverflow); return RearPowerResult::Latched; }
    return RearPowerResult::Accepted;
}
RearPowerResult RearPowerGateway::enqueue_power(const can::BmsMessage& m) { return enqueue(m,false); }
RearPowerResult RearPowerGateway::enqueue_permission(const can::BmsMessage& m) { return enqueue(m,true); }
RearPowerResult RearPowerGateway::receive_limits(const can::BmsFrame& frame) {
    if(!refresh()) return epoch_==0?RearPowerResult::NotInitialized:RearPowerResult::Latched;
    const auto result=limits_rx_.receive(frame,observed_ns_);
    if(result.decision!=can::ActuatorReceiveDecision::Accepted || result.quality[0]!=can::BmsFieldQuality::Usable || result.quality[1]!=can::BmsFieldQuality::Usable) return RearPowerResult::Rejected;
    const auto current=limits_rx_.current_sample(observed_ns_); if(!current) return RearPowerResult::Rejected;
    const auto bound=deadline(current->message); expiry_[2]=bound;
    if(!queue_.push({current->message,std::nullopt,bound})) { fail(ProtectionCause::QueueOverflow); return RearPowerResult::Latched; }
    return RearPowerResult::Accepted;
}
RearPowerResult RearPowerGateway::receive_status(const can::BmsFrame& frame) {
    if(!refresh()) return epoch_==0?RearPowerResult::NotInitialized:RearPowerResult::Latched;
    const auto result=status_rx_.receive(frame,observed_ns_);
    if(result.decision!=can::ActuatorReceiveDecision::Accepted || result.quality[0]!=can::BmsFieldQuality::Usable || result.quality[1]!=can::BmsFieldQuality::Usable) return RearPowerResult::Rejected;
    const auto current=status_rx_.current_sample(observed_ns_); if(!current) return RearPowerResult::Rejected;
    expiry_[3]=deadline(current->message); status_history_[current->message.sequence%status_history_.size()]=current;
    return RearPowerResult::Accepted;
}
std::size_t RearPowerGateway::dispatch() {
    if(!refresh()) return 0;
    std::size_t sent_count=0;
    std::array<std::optional<RearPowerDelivery>,3> selected{};
    for(std::size_t i=0;i<kCapacity;++i) {
        const auto item=queue_.pop(); if(!item) break;
        const auto& m=item->message; const auto slot=index(m.kind);
        const auto& latest=slot==0?power_rx_.last_accepted():slot==1?permission_rx_.last_accepted():limits_rx_.last_accepted();
        if(!latest || m.sequence!=latest->message.sequence) continue;
        selected[slot]=item;
    }
    const bool inhibit=selected[1] && std::get<can::BmsDriveGrant>(selected[1]->message.content).permission==can::BmsDrivePermission::Inhibit;
    const std::array<std::size_t,3> order=inhibit?std::array<std::size_t,3>{1,2,0}:std::array<std::size_t,3>{2,0,1};
    for(const auto slot:order) {
        const auto& item=selected[slot]; if(!item) continue;
        const auto& m=item->message;
        if(!refresh()) break;
        if(observed_ns_>=item->expires_at_ns) { fail(ProtectionCause::CommandExpired); break; }
        if(slot==1 && can::bms_permission_allows_normal({m,{can::BmsFieldQuality::Usable,can::BmsFieldQuality::NotApplicable,can::BmsFieldQuality::NotApplicable}}) && !grant_supported(m)) { fail(ProtectionCause::CommandExpired); break; }
        const auto frame=slot==0?can::encode_bms_frame(m,power_tx_):slot==1?can::encode_bms_frame(m,permission_tx_):can::forward_bms_limits(m,limits_tx_);
        if(!frame || !port_.send(*frame,*item)) { if(refresh()) fail(ProtectionCause::SendFailure); break; }
        ++sent_count;
        if(slot==0) sent_power_[m.sequence%sent_power_.size()]=SentPower{m,item->parent,item->expires_at_ns};
        if(!refresh()) break;
    }
    return sent_count;
}
RearPowerDecision RearPowerGateway::poll() { refresh(); return {safety_.decision(),normal_armed_,queue_.size()}; }
void RearPowerGateway::mark_continuity_lost() { if(epoch_!=0) { refresh(); fail(ProtectionCause::UpstreamLost); } }
std::optional<can::BmsCurrentSample> RearPowerGateway::power_status() { refresh(); return epoch_!=0?status_rx_.current_sample(observed_ns_):std::nullopt; }
std::optional<can::BmsCurrentSample> RearPowerGateway::power_limits() { refresh(); return epoch_!=0?limits_rx_.current_sample(observed_ns_):std::nullopt; }
} // namespace stratadrive::zone
