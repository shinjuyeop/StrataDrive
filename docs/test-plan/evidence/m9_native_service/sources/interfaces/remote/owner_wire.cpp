#include "owner_wire.hpp"
#include <cmath>
#include <cstring>
#include <limits>
#include <type_traits>

namespace stratadrive::remote {
namespace {
constexpr std::uint32_t kMagic=0x56524453; // "SDRV" in little endian
static_assert(sizeof(double)==8 && std::numeric_limits<double>::is_iec559);
template<class T> struct Optional : std::false_type {};
template<class T> struct Optional<std::optional<T>> : std::true_type {};
template<class T> struct Variant : std::false_type {};
template<class... T> struct Variant<std::variant<T...>> : std::true_type {};
template<class T> struct Array : std::false_type {};
template<class T,std::size_t N> struct Array<std::array<T,N>> : std::true_type {};
template<class E> bool valid_enum(E value) {
    const auto n=static_cast<std::uint32_t>(value);
    if constexpr(std::is_same_v<E,session::Role>) return n<session::kRoleCount;
    else if constexpr(std::is_same_v<E,session::Phase>) return n<=3;
    else if constexpr(std::is_same_v<E,can::ActuatorLocalState>) return n<=3;
    else if constexpr(std::is_same_v<E,can::ActuatorOrigin>) return n<=2;
    else if constexpr(std::is_same_v<E,can::SteeringFrameKind>) return n==0x180 || n==0x280;
    else if constexpr(std::is_same_v<E,can::BrakeFrameKind>) return n==0x181 || n==0x281;
    else if constexpr(std::is_same_v<E,can::DriveFrameKind>) return n==0x182 || n==0x282;
    else if constexpr(std::is_same_v<E,can::BmsFrameKind>) return n==0x183 || n==0x283 || n==0x284 || n==0x285 || n==0x193 || n==0x194;
    else if constexpr(std::is_same_v<E,can::BmsPowerAction>) return n<=2;
    else if constexpr(std::is_same_v<E,can::BmsPowerState>) return n<=4;
    else if constexpr(std::is_same_v<E,can::BmsDrivePermission>) return n<=1;
    else if constexpr(std::is_same_v<E,can::BmsLimitReason>) return n<=5;
    else if constexpr(std::is_same_v<E,can::DriveRegenLimitReason>) return n<=4;
    else if constexpr(std::is_same_v<E,zone::ZoneScope>) return n<=1;
    else if constexpr(std::is_same_v<E,zone::ZonePhase>) return n<=4;
    else if constexpr(std::is_same_v<E,central::NormalStopState>) return n<=6;
    else if constexpr(std::is_same_v<E,transport::Operation>) return n<=5;
    else if constexpr(std::is_same_v<E,transport::LeafOperation>) return n<=2;
    else { static_assert(!sizeof(E),"unregistered owner wire enum"); }
}
// Domain field catalogue. No C++ object layout/padding or mutable controller is serialized.
#define FIELDS(Type,...) \
 template<class A> void fields(A& a,Type& v) { static_cast<void>(v); a(__VA_ARGS__); } \
 template<class A> void fields(A& a,const Type& v) { static_cast<void>(v); a(__VA_ARGS__); }
#define META v.sequence,v.epoch,v.source_time_ns,v.causal_sequence,v.local_state,v.origin
FIELDS(session::Plan,v.epoch,v.requested_ns,v.prepare_deadline_ns,v.enable_ns,v.commit_deadline_ns)
FIELDS(session::Control,v.role,v.phase,v.plan,v.source_ns)
FIELDS(session::Ack,v.role,v.phase,v.plan,v.source_ns,v.accepted)
FIELDS(RunLease,v.plan,v.sequence,v.source_time_ns,v.expires_at_ns)
FIELDS(ProtectionRequest,v.epoch,v.token,v.source_time_ns,v.deadline_ns)
FIELDS(ProtectionAck,v.request,v.selected_ns,v.selected)
FIELDS(can::BmsParentContext,v.epoch,v.sequence,v.source_time_ns,v.expires_at_ns)
FIELDS(ActuatorStopLease,v.epoch,v.sequence,v.source_time_ns,v.expires_at_ns)
FIELDS(central::VehicleRequest,v.epoch,v.sequence,v.source_time_ns,v.expires_at_ns,v.acceleration_mps2,v.curvature_inv_m,v.braking_demand,v.standstill_hold)
FIELDS(central::LifecycleRequest,v.identity,v.action)
FIELDS(central::CommandContext,v.parent,v.oldest_input_time_ns,v.expires_at_ns)
FIELDS(central::FrontCommands,v.parent,v.oldest_input_time_ns,v.expires_at_ns,v.steering,v.brake)
FIELDS(central::RearCommands,v.parent,v.oldest_input_time_ns,v.expires_at_ns,v.drive)
FIELDS(can::SteeringMessage,v.kind,v.angle_rad,META)
FIELDS(can::BrakeMessage,v.kind,v.pressure_pa,META)
FIELDS(can::DriveWheelSpeed,v.value_rad_s,v.source_time_ns)
FIELDS(can::DriveRegenCapability,v.torque_limit_nm,v.source_time_ns,v.input_time_ns)
FIELDS(can::DriveMessage,v.kind,v.torque_nm,v.wheel_speed,v.regen_capability,v.regen_limit_reason,META)
FIELDS(can::BmsPowerRequest,v.action,v.expires_at_ns,v.parent_source_time_ns)
FIELDS(can::BmsPowerLimits,v.charge_power_w,v.discharge_power_w,v.charge_reason,v.discharge_reason,v.input_time_ns)
FIELDS(can::BmsSocSample,v.fraction,v.source_time_ns)
FIELDS(can::BmsElectricalSample,v.voltage_v,v.current_a,v.source_time_ns)
FIELDS(can::BmsTemperatureSample,v.celsius,v.source_time_ns)
FIELDS(can::BmsBatteryState,v.soc,v.electrical,v.temperature)
FIELDS(can::BmsPowerStatus,v.state,v.positive_contactor_closed,v.negative_contactor_closed,v.precharge_contactor_closed,v.condition_bits,v.condition_validity,v.hv_bus_voltage_v,v.input_time_ns,v.accepted_request_source_time_ns,v.input_sequence)
FIELDS(can::BmsDriveGrant,v.permission,v.power_status_sequence,v.power_status_source_time_ns,v.input_time_ns,v.expires_at_ns)
FIELDS(can::BmsMessage,v.kind,v.content,META)
FIELDS(central::VehicleManagementOutput,v.power_request,v.drive_permission,v.power_parent,v.permission_parent)
FIELDS(central::NormalStopRequest,v.identity,v.curvature_inv_m)
FIELDS(central::NormalStopPlan,v.state,v.ancestor,v.lifecycle,v.vehicle,v.lease,v.handoff_required)
FIELDS(transport::Arm)
FIELDS(transport::ZoneRequest,v.epoch,v.token,v.sent_ns,v.deadline_ns,v.work)
FIELDS(transport::LeafRequest,v.epoch,v.token,v.sent_ns,v.deadline_ns,v.operation,v.frame,v.command,v.parent,v.lease)
FIELDS(transport::LeafResult,v.epoch,v.token,v.source_ns,v.operation,v.accepted)
FIELDS(can::SteeringFrame,v.can_id,v.is_fd,v.fd_flags,v.payload_length,v.payload)
FIELDS(can::BrakeFrame,v.can_id,v.is_fd,v.fd_flags,v.payload_length,v.payload)
FIELDS(can::DriveFrame,v.can_id,v.is_fd,v.fd_flags,v.payload_length,v.payload)
FIELDS(can::BmsFrame,v.can_id,v.is_fd,v.fd_flags,v.payload_length,v.payload)
FIELDS(zone::ZoneHealthSnapshot,META,v.scope,v.phase,v.ready_for_normal)
FIELDS(OwnerMessage,v.from,v.to,v.clock_domain,v.payload)
#undef META
#undef FIELDS
// size_t has no wire ABI. Frame counts are fixed-width64 on every architecture.
template<class A> void fields(A& a,const transport::TxResult& v) { a(v.epoch,v.token,v.source_ns,v.operation,v.accepted,static_cast<std::uint64_t>(v.frames)); }
template<class A> void fields(A& a,transport::TxResult& v) {
    std::uint64_t frames=0; a(v.epoch,v.token,v.source_ns,v.operation,v.accepted,frames);
    if(frames>std::numeric_limits<std::size_t>::max()) a.ok=false; else v.frames=static_cast<std::size_t>(frames);
}
struct Writer {
    OwnerPacket packet; bool ok{true};
    template<class... T> void operator()(const T&... values) { (item(values),...); }
    template<class T> void item(const T& value) {
        if constexpr(std::is_same_v<T,bool>) item(static_cast<std::uint8_t>(value));
        else if constexpr(std::is_integral_v<T>) {
            for(std::size_t i=0;i<sizeof(T);++i) { if(packet.size>=packet.bytes.size()) { ok=false;return; } packet.bytes[packet.size++]=static_cast<std::uint8_t>(static_cast<std::uint64_t>(value)>>(8*i)); }
        } else if constexpr(std::is_enum_v<T>) { if(!valid_enum(value)) ok=false; item(static_cast<std::uint32_t>(value)); }
        else if constexpr(std::is_same_v<T,double>) { if(!std::isfinite(value)) ok=false; std::uint64_t bits; std::memcpy(&bits,&value,8);item(bits); }
        else if constexpr(Optional<T>::value) { item(value.has_value());if(value) item(*value); }
        else if constexpr(Variant<T>::value) { item(static_cast<std::uint8_t>(value.index()));std::visit([&](const auto& v){item(v);},value); }
        else if constexpr(Array<T>::value) { for(const auto& v:value) item(v); }
        else fields(*this,value);
    }
};
struct Reader {
    const std::uint8_t* bytes; std::size_t size,pos{0}; bool ok{true};
    template<class... T> void operator()(T&... values) { (item(values),...); }
    template<std::size_t I=0,class V> void alternative(V& value,std::uint8_t tag) {
        if constexpr(I<std::variant_size_v<V>) { if(tag==I) { value.template emplace<I>();item(std::get<I>(value)); } else alternative<I+1>(value,tag); }
        else ok=false;
    }
    template<class T> void item(T& value) {
        if constexpr(std::is_same_v<T,bool>) { std::uint8_t byte=0;item(byte);if(byte>1) ok=false;value=byte!=0; }
        else if constexpr(std::is_integral_v<T>) {
            if(sizeof(T)>size-pos) { ok=false;return; } std::uint64_t number=0;
            for(std::size_t i=0;i<sizeof(T);++i) number|=static_cast<std::uint64_t>(bytes[pos++])<<(8*i);
            value=static_cast<T>(number);
        } else if constexpr(std::is_enum_v<T>) { std::uint32_t number=0;item(number);value=static_cast<T>(number);if(static_cast<std::uint32_t>(value)!=number || !valid_enum(value)) ok=false; }
        else if constexpr(std::is_same_v<T,double>) { std::uint64_t bits=0;item(bits);std::memcpy(&value,&bits,8);if(!std::isfinite(value)) ok=false; }
        else if constexpr(Optional<T>::value) { bool present=false;item(present);value.reset();if(present) { value.emplace();item(*value); } }
        else if constexpr(Variant<T>::value) { std::uint8_t tag=0;item(tag);alternative(value,tag); }
        else if constexpr(Array<T>::value) { for(auto& v:value) item(v); }
        else fields(*this,value);
    }
};
bool route_valid(const OwnerMessage& m) {
    if(!m.clock_domain || !valid_enum(m.from) || !valid_enum(m.to)) return false;
    const auto central=session::Role::CentralIngress;
    const auto zone=[](session::Role r){return r==session::Role::FrontZone || r==session::Role::RearZone;};
    const auto leaf=[](session::Role r){return r>=session::Role::Steering && r<=session::Role::Power;};
    const auto owner_zone=[](session::Role r){return r==session::Role::Steering || r==session::Role::Brake?session::Role::FrontZone:session::Role::RearZone;};
    return std::visit([&](const auto& body) {
        using T=std::decay_t<decltype(body)>;
        if constexpr(std::is_same_v<T,session::Control>) return m.from==central && body.role==m.to;
        else if constexpr(std::is_same_v<T,session::Ack>) return m.to==central && body.role==m.from;
        else if constexpr(std::is_same_v<T,RunLease>) return m.from==central && m.to!=central;
        else if constexpr(std::is_same_v<T,transport::ZoneRequest>) return m.from==central && zone(m.to);
        else if constexpr(std::is_same_v<T,transport::TxResult> || std::is_same_v<T,transport::Feedback>) return zone(m.from) && m.to==central;
        else if constexpr(std::is_same_v<T,transport::LeafRequest>) return leaf(m.to) && m.from==owner_zone(m.to);
        else if constexpr(std::is_same_v<T,transport::LeafReport>) return leaf(m.from) && m.to==owner_zone(m.from);
        else if constexpr(std::is_same_v<T,ProtectionRequest>) return (m.from==central && m.to!=central) || (leaf(m.to) && m.from==owner_zone(m.to));
        else return (m.to==central && m.from!=central) || (leaf(m.from) && m.to==owner_zone(m.from));
    },m.payload);
}
} // namespace
std::uint32_t owner_crc32c(const std::uint8_t* bytes,std::size_t size) {
    std::uint32_t crc=0xffffffffU;
    for(std::size_t i=0;i<size;++i) { crc^=bytes[i];for(unsigned bit=0;bit<8;++bit) crc=(crc>>1)^((crc&1U)?0x82f63b78U:0U); }
    return crc^0xffffffffU;
}
std::optional<OwnerPacket> encode_owner_message(const OwnerMessage& message) {
    if(!route_valid(message)) return std::nullopt;
    Writer out; out(kMagic,kOwnerWireVersion,std::uint16_t{0},message);
    if(!out.ok || out.packet.size>kOwnerWireCapacity-4) return std::nullopt;
    out(owner_crc32c(out.packet.bytes.data(),out.packet.size));return out.ok?std::optional<OwnerPacket>{out.packet}:std::nullopt;
}
std::optional<OwnerMessage> decode_owner_message(const std::uint8_t* bytes,std::size_t size) {
    if(!bytes || size<12 || size>kOwnerWireCapacity) return std::nullopt;
    Reader crc{bytes+size-4,4};std::uint32_t claimed=0;crc(claimed);
    if(owner_crc32c(bytes,size-4)!=claimed) return std::nullopt;
    Reader in{bytes,size-4};std::uint32_t magic=0;std::uint16_t version=0,reserved=0;OwnerMessage result;
    in(magic,version,reserved,result);
    if(!in.ok || in.pos!=in.size || magic!=kMagic || version!=kOwnerWireVersion || reserved || !route_valid(result)) return std::nullopt;
    return result;
}
} // namespace stratadrive::remote
