#include "async_coordinator_port.hpp"

#include <algorithm>
#include <limits>

namespace stratadrive::central {
namespace {
const can::BmsPhysicalRanges kRanges{{0,1000},{-3000,3000},{-50,150},100000};
}
AsyncCoordinatorPort::AsyncCoordinatorPort(transport::Clock& clock,transport::RunGate& gate,transport::ZoneLink& front,transport::ZoneLink& rear)
    :clock_(clock),gate_(gate),links_{&front,&rear},status_({can::BmsFrameKind::PowerStatus,kRanges}),
    limits_({can::BmsFrameKind::PowerLimits,kRanges}),permission_({can::BmsFrameKind::DrivePermission,kRanges}) {}
bool AsyncCoordinatorPort::initialize(CoordinatorSession s) {
    const auto now=now_ns();
    if(s.epoch==0 || s.epoch<=session_.epoch || now<s.enable_ns || s.enable_ns<observed_ || links_[0]->failed() || links_[1]->failed()) return false;
    if(!steering_.start_session(s.epoch,s.enable_ns) || !brake_.start_session(s.epoch,s.enable_ns) || !drive_.start_session(s.epoch,s.enable_ns) ||
        !status_.start_session(s.epoch,s.enable_ns) || !limits_.start_session(s.epoch,s.enable_ns) || !permission_.start_session(s.epoch,s.enable_ns) ||
        !front_.start_session(s.epoch,s.enable_ns) || !rear_.start_session(s.epoch,s.enable_ns)) return false;
    session_=s; observed_=now; failed_=false; fault_=AsyncTransportFault::None; failed_operation_=-1; pending_={}; issued_={}; issued_next_=0; commands_.reset();
    armed_={}; stopped_={}; arm_sent_=false; stop_.reset(); command_source_ns_=0; command_root_sequence_=0; return true;
}
bool AsyncCoordinatorPort::session_ready(CoordinatorSession s) noexcept {
    return !failed_ && s.epoch!=0 && s.epoch==session_.epoch && s.enable_ns==session_.enable_ns && !gate_.allows(s.epoch) &&
        !links_[0]->failed() && !links_[1]->failed();
}
void AsyncCoordinatorPort::fail(AsyncTransportFault fault) { if(!failed_) fault_=fault; failed_=true; gate_.close(); protect(); }
bool AsyncCoordinatorPort::protect() noexcept {
    if(session_.epoch==0) return false;
    gate_.close();
    for(auto* link:links_) link->protection.request(session_.epoch);
    return links_[0]->protection.acknowledged(session_.epoch) && links_[1]->protection.acknowledged(session_.epoch);
}
bool AsyncCoordinatorPort::post(std::size_t zone,const transport::ZoneWork& work,std::uint64_t expiry) noexcept {
    const auto now=now_ns();
    if(failed_ || !gate_.allows(session_.epoch) || expiry<=now || next_token_==std::numeric_limits<std::uint64_t>::max()) return false;
    const auto deadline=now+std::min(transport::kResultBudgetNs,expiry-now);
    auto slot=std::find_if(pending_.begin(),pending_.end(),[](const auto& p) { return !p; });
    if(slot==pending_.end()) { fail(); return false; }
    transport::ZoneRequest request{session_.epoch,next_token_++,now,deadline,work};
    *slot=Pending{request,zone};
    if(!links_[zone]->work.push(request)) { fail(); return false; }
    return true;
}
bool AsyncCoordinatorPort::authorize_lifecycle(const LifecycleRequest& root) noexcept { return post(1,root,root.identity.expires_at_ns); }
bool AsyncCoordinatorPort::authorize_vehicle(const VehicleRequest& root) noexcept {
    return post(0,root,root.expires_at_ns) && post(1,root,root.expires_at_ns);
}
OperationStatus AsyncCoordinatorPort::arm_status(std::uint32_t epoch) noexcept {
    if(epoch!=session_.epoch || failed_ || !gate_.allows(epoch)) return OperationStatus::Rejected;
    if(!arm_sent_) {
        arm_sent_=true;
        const auto now=now_ns();
        if(now>std::numeric_limits<std::uint64_t>::max()-transport::kResultBudgetNs ||
            !post(0,transport::Arm{},now+transport::kResultBudgetNs) || !post(1,transport::Arm{},now+transport::kResultBudgetNs)) return OperationStatus::Rejected;
    }
    return armed_[0] && armed_[1]?OperationStatus::Accepted:OperationStatus::Pending;
}
bool AsyncCoordinatorPort::deliver_power(const VehicleManagementOutput& out) noexcept {
    const auto* request=std::get_if<can::BmsPowerRequest>(&out.power_request.content);
    const auto* grant=std::get_if<can::BmsDriveGrant>(&out.drive_permission.content);
    if(!request || !grant || out.power_request.epoch!=session_.epoch || out.drive_permission.epoch!=session_.epoch) return false;
    if(!post(1,out,std::min(request->expires_at_ns,grant->expires_at_ns))) return false;
    issued_[issued_next_]=IssuedPermission{out.drive_permission,out.permission_parent}; issued_next_=(issued_next_+1)%issued_.size();
    return true;
}
bool AsyncCoordinatorPort::deliver_commands(const AllocatedCommands& commands) noexcept {
    if(commands_ || commands.parent.epoch!=session_.epoch) return false;
    commands_=commands;
    if(!post(0,ScopedCommands{front_commands(commands)},commands.expires_at_ns)) { commands_.reset(); return false; }
    command_source_ns_=commands.steering.source_time_ns; command_root_sequence_=commands.parent.sequence;
    return true;
}
bool AsyncCoordinatorPort::allocation_ready(const VehicleManagementOutput& out,std::uint64_t release) noexcept {
    const auto* grant=std::get_if<can::BmsDriveGrant>(&out.drive_permission.content);
    if(!grant || grant->permission!=can::BmsDrivePermission::AllowNormal) return true;
    if(out.drive_permission.source_time_ns<release || grant->expires_at_ns<=release || grant->expires_at_ns-release<=20000000ULL) return false;
    const auto received=current_permission();
    return received && received->message.epoch==out.drive_permission.epoch && received->message.sequence==out.drive_permission.sequence &&
        received->message.source_time_ns==out.drive_permission.source_time_ns;
}
OperationStatus AsyncCoordinatorPort::stop_status(const NormalStopPlan& plan) noexcept {
    if(failed_ || !gate_.allows(session_.epoch)) return OperationStatus::Rejected;
    if(!stop_ || !same_stop_lease(*stop_,plan.lease)) {
        if(stop_ && (!stopped_[0] || !stopped_[1])) return OperationStatus::Rejected;
        stop_=plan.lease; stopped_={};
        if(!post(0,plan,plan.lease.expires_at_ns) || !post(1,plan,plan.lease.expires_at_ns)) return OperationStatus::Rejected;
    }
    return stopped_[0] && stopped_[1]?OperationStatus::Accepted:OperationStatus::Pending;
}
void AsyncCoordinatorPort::result(std::size_t zone,const transport::TxResult& r) {
    auto slot=std::find_if(pending_.begin(),pending_.end(),[&](const auto& p) { return p && p->request.epoch==r.epoch && p->request.token==r.token; });
    if(slot==pending_.end()) return; // duplicate/old result cannot complete a new operation
    const auto p=**slot; const auto now=now_ns();
    if(zone!=p.zone || r.operation!=transport::operation(p.request.work) || r.source_ns<p.request.sent_ns || r.source_ns>now || now>=p.request.deadline_ns || !r.accepted) {
        if(!failed_) failed_operation_=static_cast<int>(r.operation);
        fail(now>=p.request.deadline_ns?AsyncTransportFault::ResultLate:!r.accepted?AsyncTransportFault::ResultRejected:AsyncTransportFault::ResultMismatch); return;
    }
    slot->reset();
    if(r.operation==transport::Operation::Arm) armed_[zone]=true;
    if(r.operation==transport::Operation::Stop) stopped_[zone]=true;
    if(r.operation==transport::Operation::Power && (r.frames<2 || r.frames>3)) { fail(AsyncTransportFault::FrameCount); return; }
    if(r.operation==transport::Operation::Commands) {
        if(!commands_ || r.frames!=(zone==0?2U:1U)) { fail(); return; }
        if(zone==0) {
            if(!post(1,ScopedCommands{rear_commands(*commands_)},commands_->expires_at_ns)) fail();
        } else { commands_.reset(); ++completed_batches_; }
    }
}
std::optional<can::BmsCurrentSample> AsyncCoordinatorPort::current_permission() noexcept { return permission_.current_sample(now_ns()); }
std::optional<can::BmsParentContext> AsyncCoordinatorPort::received_permission_parent() noexcept {
    const auto sample=current_permission(); if(!sample) return std::nullopt;
    for(const auto& e:issued_) if(e && e->message.epoch==sample->message.epoch && e->message.sequence==sample->message.sequence &&
        e->message.source_time_ns==sample->message.source_time_ns) return e->parent;
    return std::nullopt;
}
void AsyncCoordinatorPort::receive(std::size_t zone,const transport::Feedback& f) {
    const auto now=now_ns();
    if(const auto* s=std::get_if<can::SteeringFrame>(&f)) { if(zone==0) steering_.receive(*s,now); }
    else if(const auto* b=std::get_if<can::BrakeFrame>(&f)) { if(zone==0) brake_.receive(*b,now); }
    else if(const auto* d=std::get_if<can::DriveFrame>(&f)) { if(zone==1) drive_.receive(*d,now); }
    else if(const auto* h=std::get_if<zone::ZoneHealthSnapshot>(&f)) {
        if(zone==0) front_.receive(*h,now); else rear_.receive(*h,now);
    } else if(const auto* b=std::get_if<can::BmsFrame>(&f); b && zone==1) {
        const auto m=can::decode_bms_frame(*b); if(!m) return;
        if(m->kind==can::BmsFrameKind::PowerStatus) status_.receive(*b,now);
        if(m->kind==can::BmsFrameKind::PowerLimits) limits_.receive(*b,now);
        if(m->kind==can::BmsFrameKind::DrivePermission) {
            const can::BmsParentContext* parent=nullptr;
            for(const auto& e:issued_) if(e && e->message.epoch==m->epoch && e->message.sequence==m->sequence &&
                e->message.source_time_ns==m->source_time_ns && e->parent) { parent=&*e->parent; break; }
            permission_.receive(*b,now,parent);
        }
    }
}
void AsyncCoordinatorPort::service() {
    const auto now=now_ns(); if(now<observed_) { fail(AsyncTransportFault::Clock); return; } observed_=now;
    for(std::size_t z=0;z<links_.size();++z) {
        if(links_[z]->failed()) fail(AsyncTransportFault::Continuity);
        for(std::size_t i=0;i<transport::kBudget;++i) { const auto r=links_[z]->results.pop(); if(!r) break; result(z,*r); }
        for(std::size_t i=0;i<transport::kBudget;++i) { const auto f=links_[z]->feedback.pop(); if(!f) break; receive(z,*f); }
    }
    for(const auto& p:pending_) if(p && now_ns()>=p->request.deadline_ns) { if(!failed_) failed_operation_=static_cast<int>(transport::operation(p->request.work)); fail(AsyncTransportFault::ResultTimeout); }
}
NormalDriveReadinessInputs AsyncCoordinatorPort::feedback() {
    const auto now=now_ns(); NormalDriveReadinessInputs in; in.epoch=session_.epoch; in.session_enable_ns=session_.enable_ns;
    in.front={front_.current_sample(now),steering_.current_sample(now),brake_.current_sample(now)};
    in.rear={rear_.current_sample(now),drive_.current_sample(now),status_.current_sample(now),limits_.current_sample(now)};
    return in;
}
bool AsyncCoordinatorPort::healthy(std::uint32_t epoch) noexcept {
    service(); return epoch==session_.epoch && !failed_ && gate_.allows(epoch);
}
}  // namespace stratadrive::central
