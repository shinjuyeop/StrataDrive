#include "m4_faults.hpp"
#include <array>
#include <charconv>
#include <limits>
#include <stdexcept>

namespace stratadrive::simulation {
namespace {
constexpr std::array<const char*,10> kOwners{"front","rear","steering","brake","drive","bms","power","central","physical","monitor"};
constexpr std::array<const char*,7> kPaths{"owner","central-zone","zone-central","zone-leaf","leaf-zone","session-control","session-ack"};
constexpr std::array<const char*,5> kKinds{"pause","drop","delay","overflow","overrun"};
constexpr std::array<const char*,6> kPhases{"any","prepare","init","release","arm","stop"};
template<std::size_t N> std::size_t find(const std::array<const char*,N>& names,const std::string& key) {
    for(std::size_t i=0;i<N;++i) if(names[i]==key) return i;
    throw std::invalid_argument("unknown fault token: "+key);
}
FaultPhase phase(session::Phase p) {
    return p==session::Phase::Prepare?FaultPhase::Prepare:p==session::Phase::Initialize?FaultPhase::Initialize:p==session::Phase::Release?FaultPhase::Release:FaultPhase::Any;
}
}
const char* m4_owner_name(M4Owner o) { return kOwners.at(static_cast<std::size_t>(o)); }
const char* fault_path_name(FaultPath p) { return kPaths.at(static_cast<std::size_t>(p)); }
const char* fault_kind_name(FaultKind k) { return kKinds.at(static_cast<std::size_t>(k)); }
void validate_fault(const M4Fault& f) {
    const auto target=static_cast<std::size_t>(f.target);
    if(target>=10 || static_cast<std::size_t>(f.phase)>=kPhases.size() || f.start_ns>60000000000ULL || f.duration_ns>60000000000ULL || f.delay_ns>2000000000ULL ||
       (f.path==FaultPath::Owner && f.kind!=FaultKind::Pause && f.kind!=FaultKind::Overrun) ||
       (f.path!=FaultPath::Owner && (f.kind==FaultKind::Pause || f.kind==FaultKind::Overrun)) ||
       ((f.path==FaultPath::CentralToZone || f.path==FaultPath::ZoneToCentral) && target>=2) ||
       ((f.path==FaultPath::ZoneToLeaf || f.path==FaultPath::LeafToZone) && (target<2 || target>6)) ||
       ((f.path==FaultPath::SessionControl || f.path==FaultPath::SessionAck) && target>=8)) throw std::invalid_argument("invalid M4 fault contract");
}
M4Fault parse_m4_fault(const std::string& input) {
    std::vector<std::string> parts;
    for(std::size_t begin=0;;) { const auto end=input.find(':',begin); parts.push_back(input.substr(begin,end-begin)); if(end==std::string::npos) break; begin=end+1; }
    if(parts.size()!=6 && parts.size()!=7) throw std::invalid_argument("fault requires path:kind:target:start_ms:duration_ms:delay_ms[:phase]");
    const auto number=[](const std::string& value) {
        std::uint64_t n=0; const auto parsed=std::from_chars(value.data(),value.data()+value.size(),n);
        if(parsed.ec!=std::errc{} || parsed.ptr!=value.data()+value.size() || n>60000) throw std::invalid_argument("fault time must be integer 0..60000 ms");
        return n*1000000;
    };
    M4Fault f{static_cast<FaultPath>(find(kPaths,parts[0])),static_cast<FaultKind>(find(kKinds,parts[1])),static_cast<M4Owner>(find(kOwners,parts[2])),number(parts[3]),number(parts[4]),number(parts[5]),parts.size()==7?static_cast<FaultPhase>(find(kPhases,parts[6])):FaultPhase::Any};
    validate_fault(f);return f;
}
FaultMessage fault_message(const transport::ZoneRequest& r) {
    auto phase=FaultPhase::Any;
    if(std::holds_alternative<transport::Arm>(r.work)) phase=FaultPhase::Arm;
    if(std::holds_alternative<central::NormalStopPlan>(r.work)) phase=FaultPhase::Stop;
    return {r.epoch,r.sent_ns,r.deadline_ns,phase};
}
FaultMessage fault_message(const transport::TxResult& r) { return {r.epoch,r.source_ns,0,r.operation==transport::Operation::Arm?FaultPhase::Arm:r.operation==transport::Operation::Stop?FaultPhase::Stop:FaultPhase::Any}; }
FaultMessage fault_message(const transport::LeafRequest& r) { return {r.epoch,r.operation==transport::LeafOperation::Frame?fault_message(r.frame).source:r.sent_ns,r.deadline_ns,r.operation==transport::LeafOperation::Arm?FaultPhase::Arm:r.operation==transport::LeafOperation::Stop?FaultPhase::Stop:FaultPhase::Any}; }
FaultMessage fault_message(const transport::Feedback& f) {
    if(const auto* s=std::get_if<can::SteeringFrame>(&f)) { const auto m=can::decode_steering_frame(*s); if(m) return {m->epoch,m->source_time_ns,0,FaultPhase::Any}; }
    if(const auto* s=std::get_if<can::BrakeFrame>(&f)) { const auto m=can::decode_brake_frame(*s); if(m) return {m->epoch,m->source_time_ns,0,FaultPhase::Any}; }
    if(const auto* s=std::get_if<can::DriveFrame>(&f)) { const auto m=can::decode_drive_frame(*s); if(m) return {m->epoch,m->source_time_ns,0,FaultPhase::Any}; }
    if(const auto* s=std::get_if<can::BmsFrame>(&f)) { const auto m=can::decode_bms_frame(*s); if(m) return {m->epoch,m->source_time_ns,0,FaultPhase::Any}; }
    if(const auto* s=std::get_if<zone::ZoneHealthSnapshot>(&f)) return {s->epoch,s->source_time_ns,0,FaultPhase::Any};
    return {};
}
FaultMessage fault_message(const transport::LeafReport& r) {
    if(const auto* f=std::get_if<transport::Feedback>(&r)) return fault_message(*f);
    const auto& a=std::get<transport::LeafResult>(r); return {a.epoch,a.source_ns,0,a.operation==transport::LeafOperation::Arm?FaultPhase::Arm:a.operation==transport::LeafOperation::Stop?FaultPhase::Stop:FaultPhase::Any};
}
FaultMessage fault_message(const session::Control& c) { return {c.plan.epoch,c.source_ns,c.phase==session::Phase::Prepare?c.plan.prepare_deadline_ns:c.plan.commit_deadline_ns,phase(c.phase)}; }
FaultMessage fault_message(const session::Ack& c) { return {c.plan.epoch,c.source_ns,c.phase==session::Phase::Prepare?c.plan.prepare_deadline_ns:c.plan.commit_deadline_ns,phase(c.phase)}; }
} // namespace stratadrive::simulation
