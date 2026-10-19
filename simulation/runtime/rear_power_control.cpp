#include "rear_power_control.hpp"

namespace stratadrive::simulation {
bool RearPowerControl::start_session(std::uint32_t epoch) {
    if(epoch==0 || epoch<=epoch_) return false;
    epoch_=epoch; issued_={}; next_=0; return true;
}
bool RearPowerControl::stage_context(const can::BmsFrame& frame,const zone::RearPowerDelivery& delivery) noexcept {
    if(epoch_==0 || drive_.application_epoch()!=epoch_ || power_.application_epoch()!=epoch_ || delivery.message.epoch!=epoch_ || delivery.expires_at_ns<=delivery.message.source_time_ns) return false;
    const auto message=can::decode_bms_frame(frame);
    if(!message || message->epoch!=epoch_ || message->sequence!=delivery.message.sequence || message->source_time_ns!=delivery.message.source_time_ns) return false;
    if(message->kind==can::BmsFrameKind::DriveBatteryLimits) return delivery.message.kind==can::BmsFrameKind::PowerLimits;
    if(message->kind!=delivery.message.kind || (message->kind!=can::BmsFrameKind::PowerRequest && message->kind!=can::BmsFrameKind::DrivePermission)) return false;
    issued_[next_]=Entry{frame,delivery}; next_=(next_+1)%issued_.size(); return true;
}
std::optional<zone::RearPowerDelivery> RearPowerControl::context_for(const can::BmsFrame& frame,std::uint64_t now) const {
    for(const auto& e:issued_) {
        if(e && now>=e->delivery.message.source_time_ns && now<e->delivery.expires_at_ns && e->frame.can_id==frame.can_id &&
            e->frame.is_fd==frame.is_fd && (e->frame.fd_flags & ~0x04U)==(frame.fd_flags & ~0x04U) &&
            e->frame.payload_length==frame.payload_length && e->frame.payload==frame.payload) return e->delivery;
    }
    return std::nullopt;
}
bool RearPowerControl::arm_normal_commands(std::uint32_t epoch,std::uint64_t now) noexcept {
    return epoch_!=0 && epoch==epoch_ && drive_.application_epoch()==epoch_ && power_.application_epoch()==epoch_ && drive_.arm_normal_commands(now);
}
bool RearPowerControl::protect(zone::ZoneScope scope,zone::ProtectionCause cause,std::uint64_t now) noexcept {
    if(epoch_==0 || scope!=zone::ZoneScope::Rear || cause==zone::ProtectionCause::None) return false;
    drive_.request_local_protection(now); const bool power=power_.request_local_protection(now);
    return power && drive_.decision().fault!=vecu::DriveGateFault::None && drive_.output().mode==drive::ActuationMode::Zero;
}
} // namespace stratadrive::simulation
