#pragma once
#include "owner_wire.hpp"
namespace stratadrive::someip {
inline constexpr std::uint64_t kDomain=0x53444d4f4e4fULL;
enum class Ecu { Central, Front, Rear };
inline bool owns_role(Ecu ecu,session::Role r) {
    if(ecu==Ecu::Central)return r==session::Role::CentralIngress;
    if(ecu==Ecu::Front)return r==session::Role::FrontZone || r==session::Role::Steering || r==session::Role::Brake;
    return r==session::Role::RearZone || r==session::Role::Drive || r==session::Role::Bms || r==session::Role::Power;
}
inline bool remote_role(session::Role r) { return owns_role(Ecu::Front,r); }
inline session::Role zone_role(Ecu e) {return e==Ecu::Rear?session::Role::RearZone:session::Role::FrontZone;}
inline unsigned method(const remote::OwnerPayload& p) {
    if(std::holds_alternative<session::Control>(p) || std::holds_alternative<session::Ack>(p)) return 0x40;
    if(std::holds_alternative<remote::RunLease>(p)) return 0x50;
    if(std::holds_alternative<remote::ProtectionRequest>(p) || std::holds_alternative<remote::ProtectionAck>(p)) return 0x60;
    if(std::holds_alternative<transport::Feedback>(p)) return 0x70;
    if(std::holds_alternative<transport::TxResult>(p)) return 0x80;
    return 0x20;
}
inline bool authority(unsigned m) { return m==0x40 || m==0x50 || m==0x60; }
// Service identity binds each Zone/Leaf payload to its one owning ECU.
inline bool binding(Ecu ecu,std::uint16_t sid,std::uint16_t iid,std::uint16_t mid,
                    unsigned type,unsigned version,const remote::OwnerMessage& m) {
    const bool front=ecu!=Ecu::Central;
    const auto zone=ecu==Ecu::Rear || (ecu==Ecu::Central && sid>=0x534a)?Ecu::Rear:Ecu::Front;
    const auto base=(front?0x5344:0x5346)+(zone==Ecu::Rear?4:0);
    if(version!=1 || iid!=1 || type!=1 || m.clock_domain!=kDomain || mid!=method(m.payload) ||
       sid!=base+(authority(mid)?1:0)) return false;
    if(front) {
        if(m.from!=session::Role::CentralIngress || !owns_role(zone,m.to)) return false;
        if(const auto* c=std::get_if<session::Control>(&m.payload)) return c->role==m.to;
        if(std::holds_alternative<remote::RunLease>(m.payload) || std::holds_alternative<remote::ProtectionRequest>(m.payload)) return true;
        return m.to==zone_role(zone) && std::holds_alternative<transport::ZoneRequest>(m.payload);
    }
    if(m.to!=session::Role::CentralIngress || !owns_role(zone,m.from)) return false;
    if(const auto* a=std::get_if<session::Ack>(&m.payload)) return a->role==m.from;
    if(std::holds_alternative<remote::ProtectionAck>(m.payload)) return true;
    return m.from==zone_role(zone) && (std::holds_alternative<transport::TxResult>(m.payload) || std::holds_alternative<transport::Feedback>(m.payload));
}
inline bool binding(bool front,std::uint16_t sid,std::uint16_t iid,std::uint16_t mid,
                    unsigned type,unsigned version,const remote::OwnerMessage& m) {
    // Retain the original two-process boundary; Rear is opt-in, never widened here.
    return sid<0x5348 && binding(front?Ecu::Front:Ecu::Central,sid,iid,mid,type,version,m);
}
}
