#pragma once
#include "owner_messages.hpp"
#include <type_traits>
#include <utility>

namespace stratadrive::transport {
// Optional diagnostic port. Installed before launch; one caller/owner per sink.
// Implementations must be bounded/nonblocking, with overflow reported after join.
struct TransportTraceRow {
    std::uint64_t time_ns{0};const char* stage{""};std::size_t owner{0},peer{0};
    std::uint32_t epoch{0};std::uint64_t token{0};int operation{0};
    std::uint64_t original_source_ns{0},inner_deadline_ns{0},sent_ns{0},deadline_ns{0},result_source_ns{0},payload_source_ns{0};
    int outcome{0};
};
class TransportTrace {
public:
    virtual ~TransportTrace()=default;
    virtual void record(TransportTraceRow row) noexcept=0;
};
inline std::pair<std::uint64_t,std::uint64_t> source_expiry(const ZoneRequest& r) {
    if(const auto* v=std::get_if<central::VehicleRequest>(&r.work))return {v->source_time_ns,v->expires_at_ns};
    if(const auto* v=std::get_if<central::LifecycleRequest>(&r.work))return {v->identity.source_time_ns,v->identity.expires_at_ns};
    if(const auto* v=std::get_if<central::ScopedCommands>(&r.work))return std::visit([](const auto& c){return std::make_pair(c.parent.source_time_ns,c.expires_at_ns);},*v);
    if(const auto* v=std::get_if<central::NormalStopPlan>(&r.work))return {v->lease.source_time_ns,v->lease.expires_at_ns};
    if(const auto* v=std::get_if<central::VehicleManagementOutput>(&r.work)) {
        const auto* power=std::get_if<can::BmsPowerRequest>(&v->power_request.content);
        return {v->power_request.source_time_ns,power?power->expires_at_ns:0};
    }
    return {r.sent_ns,r.deadline_ns};
}
inline void trace(TransportTrace* sink,const char* stage,std::uint64_t now,std::size_t peer,const ZoneRequest& r,int outcome=0,std::uint64_t result_source=0) noexcept {
    if(!sink)return;
    const auto source=source_expiry(r);
    TransportTraceRow row{now,stage,0,peer,r.epoch,r.token,static_cast<int>(operation(r.work)),source.first,source.second,r.sent_ns,r.deadline_ns,result_source,0,outcome};
    if(const auto* v=std::get_if<central::ScopedCommands>(&r.work))row.payload_source_ns=std::visit([](const auto& c){
        if constexpr(std::is_same_v<std::decay_t<decltype(c)>,central::FrontCommands>)return c.steering.source_time_ns;
        else return c.drive.source_time_ns;
    },*v);
    sink->record(row);
}
inline void trace(TransportTrace* sink,const char* stage,std::uint64_t now,std::size_t peer,const LeafRequest& r,int outcome=0) noexcept {
    if(!sink)return;
    std::uint64_t source=r.sent_ns,expiry=r.deadline_ns;
    if(r.command){source=r.command->parent.source_time_ns;expiry=r.command->expires_at_ns;}
    else if(r.lease){source=r.lease->source_time_ns;expiry=r.lease->expires_at_ns;}
    else if(r.parent){source=r.parent->source_time_ns;expiry=r.parent->expires_at_ns;}
    TransportTraceRow row{now,stage,0,peer,r.epoch,r.token,static_cast<int>(r.operation),source,expiry,r.sent_ns,r.deadline_ns,0,0,outcome};
    if(const auto* f=std::get_if<can::SteeringFrame>(&r.frame)){if(const auto m=can::decode_steering_frame(*f))row.payload_source_ns=m->source_time_ns;}
    else if(const auto* f=std::get_if<can::BrakeFrame>(&r.frame)){if(const auto m=can::decode_brake_frame(*f))row.payload_source_ns=m->source_time_ns;}
    else if(const auto* f=std::get_if<can::DriveFrame>(&r.frame)){if(const auto m=can::decode_drive_frame(*f))row.payload_source_ns=m->source_time_ns;}
    else if(const auto* f=std::get_if<can::BmsFrame>(&r.frame)){if(const auto m=can::decode_bms_frame(*f))row.payload_source_ns=m->source_time_ns;}
    sink->record(row);
}
} // namespace stratadrive::transport
