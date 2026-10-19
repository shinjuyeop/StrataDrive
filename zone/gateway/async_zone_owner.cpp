#include "async_zone_owner.hpp"

namespace stratadrive::zone {
AsyncZoneOwner::AsyncZoneOwner(ZoneScope scope,transport::Clock& clock,transport::RunGate& gate,transport::ZoneLink& central,
    const std::array<transport::LeafLink*,transport::kLeaves>& leaves)
    :scope_(scope),clock_(clock),gate_(gate),central_(central),leaves_(leaves),commands_(scope,*this),
    power_(scope==ZoneScope::Rear?std::optional<RearPowerGateway>{std::in_place,static_cast<RearPowerPort&>(*this)}:std::nullopt),health_(commands_,power_?&*power_:nullptr,1000000) {}
bool AsyncZoneOwner::initialize(std::uint32_t epoch,std::uint64_t enable) {
    if(epoch==0 || epoch<=epoch_ || central_.failed()) return false;
    const auto range=leaf_range(); for(auto i=range.first;i<range.second;++i) if(leaves_[i]->failed()) return false;
    if(!commands_.start_session(epoch,enable) || (power_ && !power_->start_session(epoch,enable)) ||
        !steering_.start_session(epoch,enable) || !brake_.start_session(epoch,enable) || !drive_.start_session(epoch,enable) || !health_.start_session(epoch,enable)) return false;
    epoch_=epoch; enable_=enable; observed_=now_ns(); last_health_=enable; last_inputs_={}; failed_=false; rejection_=0; pending_.reset(); leaf_ack_={}; drive_arm_ack_=false;
    return true;
}
std::pair<std::size_t,std::size_t> AsyncZoneOwner::leaf_range() const { return scope_==ZoneScope::Front?std::pair<std::size_t,std::size_t>{0,2}:std::pair<std::size_t,std::size_t>{2,5}; }
bool AsyncZoneOwner::leaf_selected() const {
    const auto range=leaf_range();
    for(auto i=range.first;i<range.second;++i) if(!leaves_[i]->protection.acknowledged(epoch_)) return false;
    return true;
}
bool AsyncZoneOwner::protect(ZoneScope scope,ProtectionCause cause,std::uint64_t) noexcept {
    if(scope!=scope_ || cause==ProtectionCause::None || epoch_==0) return false;
    const auto range=leaf_range(); for(auto i=range.first;i<range.second;++i) leaves_[i]->protection.request(epoch_);
    return leaf_selected();
}
void AsyncZoneOwner::protect_local() {
    if(epoch_==0) return;
    gate_.close(); // A local safety selection vetoes the shared normal path before Central observes status.
    failed_=true; pending_.reset(); commands_.request_protection(); if(power_) power_->mark_continuity_lost();
    protect(scope_,ProtectionCause::CoordinatorRequest,now_ns());
}
void AsyncZoneOwner::quiesce() {
    if(epoch_!=0) protect_local();
    for(std::size_t i=0;i<transport::kBudget;++i) if(!central_.work.pop()) break;
}
bool AsyncZoneOwner::protected_selected() const { return failed_ && leaf_selected(); }
bool AsyncZoneOwner::leaf_send(transport::Leaf leaf,transport::LeafRequest packet) {
    const auto now=now_ns();
    if(!gate_.allows(epoch_) || packet.epoch!=epoch_ || packet.deadline_ns<=now) return false;
    return leaves_[static_cast<std::size_t>(leaf)]->work.push(packet);
}
bool AsyncZoneOwner::send(const CommandFrame& frame,const central::CommandContext& context) noexcept try {
    if(context.parent.epoch!=epoch_ || now_ns()>=context.expires_at_ns) return false;
    transport::LeafRequest packet; packet.epoch=epoch_; packet.token=sending_token_; packet.sent_ns=now_ns();
    packet.deadline_ns=context.expires_at_ns; packet.command=context;
    transport::Leaf leaf;
    if(const auto* s=std::get_if<can::SteeringFrame>(&frame)) { packet.frame=*s; leaf=transport::Leaf::Steering; }
    else if(const auto* b=std::get_if<can::BrakeFrame>(&frame)) { if(fail_brake_write) return false; packet.frame=*b; leaf=transport::Leaf::Brake; }
    else { packet.frame=std::get<can::DriveFrame>(frame); leaf=transport::Leaf::Drive; }
    const bool ok=leaf_send(leaf,packet); if(ok) ++command_frames_; return ok;
} catch(...) { return false; }  // Gateway records the failed/partial write and selects protection.
bool AsyncZoneOwner::send(const can::BmsFrame& frame,const RearPowerDelivery& delivery) noexcept try {
    if(!power_ || delivery.message.epoch!=epoch_ || now_ns()>=delivery.expires_at_ns) return false;
    transport::LeafRequest packet; packet.epoch=epoch_; packet.token=sending_token_; packet.sent_ns=now_ns();
    packet.deadline_ns=delivery.expires_at_ns; packet.parent=delivery.parent; packet.frame=frame;
    const auto leaf=delivery.message.kind==can::BmsFrameKind::PowerRequest?transport::Leaf::Power:transport::Leaf::Drive;
    if(!leaf_send(leaf,packet)) return false;
    if(delivery.message.kind==can::BmsFrameKind::DrivePermission && !drop_permission_feedback) forward(frame);
    return true;
} catch(...) { return false; }
bool AsyncZoneOwner::arm_normal_commands(std::uint32_t epoch,std::uint64_t) noexcept {
    return epoch==epoch_ && drive_arm_ack_ && commands_.arm();
}
void AsyncZoneOwner::complete(const transport::ZoneRequest& r,bool accepted,std::size_t frames) {
    if(!central_.results.push({r.epoch,r.token,now_ns(),transport::operation(r.work),accepted,frames})) protect_local();
    if(!accepted && r.epoch==epoch_) protect_local();
}
void AsyncZoneOwner::forward(const transport::Feedback& f) { if(!drop_feedback && !central_.feedback.push(f)) protect_local(); }
void AsyncZoneOwner::handle(const transport::ZoneRequest& r) {
    const auto now=now_ns();
    // Old Epoch traffic is discarded without changing any new-session history.
    if(r.epoch!=epoch_) return;
    if(failed_ || !gate_.allows(epoch_) || r.sent_ns>now || now>=r.deadline_ns) { complete(r,false); return; }
    sending_token_=r.token;
    if(const auto* root=std::get_if<central::LifecycleRequest>(&r.work)) complete(r,power_ && power_->authorize_request(*root)==RearPowerResult::Accepted);
    else if(const auto* root=std::get_if<central::VehicleRequest>(&r.work)) {
        const auto result=commands_.authorize_request(*root); complete(r,result==AdmissionResult::Accepted || result==AdmissionResult::Unchanged);
    } else if(const auto* out=std::get_if<central::VehicleManagementOutput>(&r.work)) {
        if(!power_) { complete(r,false); return; }
        const auto a=power_->enqueue_power(out->power_request),b=power_->enqueue_permission(out->drive_permission);
        if(a!=RearPowerResult::Accepted || b!=RearPowerResult::Accepted) { if(!rejection_) rejection_=100+static_cast<int>(a)*10+static_cast<int>(b); complete(r,false); return; }
        const auto count=power_->dispatch(); const auto cause=power_->poll().safety.cause;
        if((count<2 || cause!=ProtectionCause::None) && !rejection_) rejection_=200+static_cast<int>(cause);
        complete(r,count>=2 && cause==ProtectionCause::None,count);
    } else if(const auto* c=std::get_if<central::ScopedCommands>(&r.work)) {
        const auto admitted=commands_.enqueue(*c);
        if(admitted!=AdmissionResult::Accepted) { if(!rejection_) rejection_=300+static_cast<int>(admitted); complete(r,false); return; }
        const auto sent=commands_.dispatch(); const bool ok=!sent.partial_front && sent.frames_enqueued==(scope_==ZoneScope::Front?2U:1U);
        if(!ok && !rejection_) rejection_=400+static_cast<int>(commands_.poll().safety.cause);
        complete(r,ok,sent.frames_enqueued);
    } else {
        if(pending_) { complete(r,false); return; }
        const auto* stop=std::get_if<central::NormalStopPlan>(&r.work);
        if(stop && (!stop->handoff_required || stop->lease.epoch!=stop->ancestor.identity.epoch ||
            stop->lease.sequence!=stop->ancestor.identity.sequence || stop->lease.source_time_ns!=stop->ancestor.identity.source_time_ns ||
            stop->lease.expires_at_ns>stop->ancestor.identity.expires_at_ns)) { complete(r,false); return; }
        pending_=r; leaf_ack_={};
        const auto begin=scope_==ZoneScope::Front?0U:2U,end=scope_==ZoneScope::Front?2U:3U;
        for(auto i=begin;i<end;++i) {
            transport::LeafRequest p; p.epoch=epoch_; p.token=r.token; p.sent_ns=now; p.deadline_ns=r.deadline_ns;
            p.operation=stop?transport::LeafOperation::Stop:transport::LeafOperation::Arm;
            if(stop) p.lease=stop->lease;
            if(!leaf_send(static_cast<transport::Leaf>(i),p)) { complete(r,false); pending_.reset(); return; }
        }
    }
}
void AsyncZoneOwner::report(transport::Leaf leaf,const transport::LeafReport& report_value) {
    if(const auto* ack=std::get_if<transport::LeafResult>(&report_value)) {
        if(ack->epoch!=epoch_) return;
        if(ack->source_ns>now_ns()) { protect_local(); return; }
        if(ack->operation==transport::LeafOperation::Frame) { if(!ack->accepted) protect_local(); return; }
        if(!pending_ || ack->token!=pending_->token) return;
        const bool stop=std::holds_alternative<central::NormalStopPlan>(pending_->work);
        if(ack->source_ns<pending_->sent_ns || now_ns()>=pending_->deadline_ns || !ack->accepted ||
            ack->operation!=(stop?transport::LeafOperation::Stop:transport::LeafOperation::Arm)) { const auto p=*pending_; pending_.reset(); complete(p,false); return; }
        leaf_ack_[static_cast<std::size_t>(leaf)]=true; return;
    }
    const auto& frame=std::get<transport::Feedback>(report_value); const auto now=now_ns();
    if(const auto* f=std::get_if<can::SteeringFrame>(&frame); f && leaf==transport::Leaf::Steering) steering_.receive(*f,now);
    if(const auto* f=std::get_if<can::BrakeFrame>(&frame); f && leaf==transport::Leaf::Brake) brake_.receive(*f,now);
    if(const auto* f=std::get_if<can::DriveFrame>(&frame); f && leaf==transport::Leaf::Drive) drive_.receive(*f,now);
    if(const auto* f=std::get_if<can::BmsFrame>(&frame); f && power_) {
        if(leaf==transport::Leaf::Bms) power_->receive_limits(*f);
        if(leaf==transport::Leaf::Power) power_->receive_status(*f);
    }
    forward(frame);
}
void AsyncZoneOwner::progress() {
    if(!pending_) return;
    const auto p=*pending_; const auto now=now_ns();
    if(now>=p.deadline_ns) { pending_.reset(); complete(p,false); return; }
    const bool selected=scope_==ZoneScope::Front?(leaf_ack_[0] && leaf_ack_[1]):leaf_ack_[2];
    if(!selected) return;
    bool ok;
    if(const auto* stop=std::get_if<central::NormalStopPlan>(&p.work)) {
        ok=commands_.select_normal_stop(stop->lease) && (!power_ || power_->select_normal_stop(stop->lease));
    } else {
        drive_arm_ack_=scope_==ZoneScope::Rear;
        ok=power_?power_->arm_normal_commands():commands_.arm();
    }
    pending_.reset(); complete(p,ok);
}
void AsyncZoneOwner::service() {
    if(epoch_==0) return;
    const auto now=now_ns(); if(now<observed_ || central_.failed() || central_.protection.pending(epoch_)) protect_local(); observed_=now;
    const auto range=leaf_range();
    for(auto l=range.first;l<range.second;++l) {
        if(leaves_[l]->failed()) protect_local();
        for(std::size_t i=0;i<transport::kBudget;++i) { const auto r=leaves_[l]->reports.pop(); if(!r) break; report(static_cast<transport::Leaf>(l),*r); }
    }
    for(std::size_t i=0;i<transport::kBudget;++i) { const auto r=central_.work.pop(); if(!r) break; handle(*r); }
    progress();
    const auto state=commands_.poll();
    if(state.safety.cause!=ProtectionCause::None || (power_ && power_->poll().safety.cause!=ProtectionCause::None)) protect_local();
    if(now-last_health_>=1000000ULL) {
        const auto sample_now=now_ns();
        const ZoneFeedbackInputs in{steering_.current_sample(sample_now),brake_.current_sample(sample_now),drive_.current_sample(sample_now),
            power_?power_->power_status():std::nullopt,power_?power_->power_limits():std::nullopt};
        const std::array<std::uint64_t,2> input_time=scope_==ZoneScope::Front?
            std::array<std::uint64_t,2>{in.steering?in.steering->source_time_ns:0,in.brake?in.brake->source_time_ns:0}:
            std::array<std::uint64_t,2>{in.drive?in.drive->source_time_ns:0,in.power_status?in.power_status->message.source_time_ns:0};
        // Prefer this acquisition round after RX; do not publish yesterday's
        // round immediately before this cycle's Leaf reports arrive. A bounded
        // fallback still runs local loss detection when input progress stops.
        if((input_time[0]>last_inputs_[0] && input_time[1]>last_inputs_[1]) || sample_now-last_health_>=20000000ULL) {
            last_health_=now_ns(); last_inputs_=input_time;
            if(const auto health=health_.tick(in,last_health_)) forward(*health);
        }
    }
    if(protected_selected()) central_.protection.selected.store(epoch_,std::memory_order_release);
}
}  // namespace stratadrive::zone
