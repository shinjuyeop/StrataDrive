#pragma once
#include "diagnostic_wire.hpp"

namespace stratadrive::someip::diagnostic {
enum class Role { Publisher, Replica };
constexpr std::uint16_t kPublisher=0x5d10,kReplica=0x5d11,kData=0x0101,kAck=0x0102;
struct Services {std::uint16_t publisher{kPublisher},replica{kReplica};};
constexpr bool valid(Services s) {return s.publisher>=0x5d00 && s.publisher<=0x5eff && s.replica>=0x5d00 && s.replica<=0x5eff && s.publisher!=s.replica;}
constexpr std::uint16_t local(Role r,Services s) {return r==Role::Publisher?s.publisher:s.replica;}
constexpr std::uint16_t peer(Role r,Services s) {return r==Role::Publisher?s.replica:s.publisher;}
constexpr std::uint16_t local(Role r) { return r==Role::Publisher?kPublisher:kReplica; }
constexpr std::uint16_t peer(Role r) { return r==Role::Publisher?kReplica:kPublisher; }
inline bool binding(Role role,std::uint16_t service,std::uint16_t instance,std::uint16_t method,
    unsigned type,unsigned version,bool reliable,const diagnostics::wire::Message& message,std::uint64_t stream,std::uint32_t registry,Services services={}) {
    if((role!=Role::Publisher && role!=Role::Replica) || !valid(services) || !stream || registry<1 || registry>4 || service!=local(role,services) || instance!=1 || type!=1 || version!=1 || !reliable) return false;
    if(role==Role::Publisher) {
        const auto* a=std::get_if<diagnostics::wire::Ack>(&message);
        return method==kAck && a && a->stream==stream && a->registry==registry;
    }
    const auto* d=std::get_if<diagnostics::wire::Data>(&message);
    return method==kData && d && d->stream==stream && d->registry==registry;
}
} // namespace stratadrive::someip::diagnostic
