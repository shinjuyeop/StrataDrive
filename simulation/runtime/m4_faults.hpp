#pragma once
#include "owner_transport.hpp"
#include <string>
#include <vector>

namespace stratadrive::simulation {
// Stable logical endpoint names, independent of mailbox/CAN/DDS transport.
enum class M4Owner : std::size_t { Front,Rear,Steering,Brake,Drive,Bms,Power,Central,Physical,Monitor,Count };
enum class FaultPath { Owner,CentralToZone,ZoneToCentral,ZoneToLeaf,LeafToZone,SessionControl,SessionAck };
enum class FaultKind { Pause,Drop,Delay,Overflow,Overrun };
enum class FaultPhase { Any,Prepare,Initialize,Release,Arm,Stop };
struct M4Fault {
    FaultPath path{FaultPath::Owner}; FaultKind kind{FaultKind::Pause}; M4Owner target{M4Owner::Central};
    std::uint64_t start_ns{1200000000},duration_ns{200000000},delay_ns{40000000};
    FaultPhase phase{FaultPhase::Any};
    bool active(std::uint64_t elapsed) const { return elapsed>=start_ns && (duration_ns==0 || elapsed-start_ns<duration_ns); }
};
struct M4Event {
    std::uint64_t time_ns{0}; const char* kind{""}; std::size_t owner{0};
    std::uint32_t epoch{0}; std::uint64_t source_ns{0},deadline_ns{0},reference_ns{0}; int code{0};
};
const char* m4_owner_name(M4Owner owner);
const char* fault_path_name(FaultPath path);
const char* fault_kind_name(FaultKind kind);
void validate_fault(const M4Fault& fault);
// path:kind:target:start_ms:duration_ms:delay_ms[:phase]; strict integers.
M4Fault parse_m4_fault(const std::string& value);
struct FaultMessage { std::uint32_t epoch{0}; std::uint64_t source{0},deadline{0}; FaultPhase phase{FaultPhase::Any}; };
FaultMessage fault_message(const transport::ZoneRequest& value);
FaultMessage fault_message(const transport::TxResult& value);
FaultMessage fault_message(const transport::LeafRequest& value);
FaultMessage fault_message(const transport::LeafReport& value);
FaultMessage fault_message(const transport::Feedback& value);
FaultMessage fault_message(const session::Control& value);
FaultMessage fault_message(const session::Ack& value);

class FaultEvidence {
public:
    virtual ~FaultEvidence() = default;
    virtual bool collect(std::vector<M4Event>& result) const = 0;
};
template<class T> class FaultDelivery final : public session::MailboxDelivery<T>, public FaultEvidence {
public:
    FaultDelivery(transport::Clock& clock,std::uint64_t start,const std::vector<M4Fault>& faults,FaultPath path,M4Owner target)
        :clock_(clock),start_(start),faults_(faults),path_(path),target_(target) { tx.reserve(12000); rx.reserve(12000); }
    std::uint64_t now_ns() const noexcept override { return clock_.now_ns(); }
    session::Delivery send(const T& value) noexcept override {
        const auto now=now_ns(); const auto m=fault_message(value);
        session::Delivery decision;
        for(const auto& f:faults_) if(matches(f,now) && (f.phase==FaultPhase::Any || f.phase==m.phase)) {
            if(f.kind==FaultKind::Drop) decision.discard=true;
            if(f.kind==FaultKind::Delay) decision.available_ns=now+f.delay_ns;
        }
        append(tx,{now,decision.discard?"dropped":decision.available_ns?"delayed":"sent",index(),m.epoch,m.source,m.deadline,decision.available_ns,static_cast<int>(path_)});
        return decision;
    }
    bool blocked() noexcept override {
        bool blocked=false;
        for(const auto& f:faults_) if(matches(f,now_ns()) && f.kind==FaultKind::Overflow) blocked=true;
        if(blocked && !blocked_seen_) append(rx,{now_ns(),"receive-blocked",index(),0,0,0,0,static_cast<int>(path_)});
        blocked_seen_=blocked; return blocked;
    }
    void delivered(const T& value) noexcept override { const auto m=fault_message(value); append(rx,{now_ns(),"delivered",index(),m.epoch,m.source,m.deadline,0,static_cast<int>(path_)}); }
    void overflow(const T& value) noexcept override { const auto m=fault_message(value); append(tx,{now_ns(),"overflow",index(),m.epoch,m.source,m.deadline,0,static_cast<int>(path_)}); }
    std::vector<M4Event> tx,rx; bool tx_dropped{false},rx_dropped{false}; // inspect after join
    bool collect(std::vector<M4Event>& out) const override {
        out.insert(out.end(),tx.begin(),tx.end()); out.insert(out.end(),rx.begin(),rx.end()); return !tx_dropped && !rx_dropped;
    }
private:
    bool matches(const M4Fault& f,std::uint64_t now) const { return f.path==path_ && f.target==target_ && f.active(now-start_); }
    std::size_t index() const { return static_cast<std::size_t>(target_); }
    void append(std::vector<M4Event>& out,const M4Event& event) noexcept {
        if(out.size()<out.capacity()) out.push_back(event); else if(&out==&tx) tx_dropped=true; else rx_dropped=true;
    }
    transport::Clock& clock_; std::uint64_t start_; const std::vector<M4Fault>& faults_; FaultPath path_; M4Owner target_;
    bool blocked_seen_{false}; // consumer only
};
} // namespace stratadrive::simulation
