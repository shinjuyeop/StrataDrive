#include "remote_leaf_endpoint.hpp"
#include <algorithm>
#include <stdexcept>

namespace stratadrive::simulation {
RemoteLeafEndpoint::RemoteLeafEndpoint(session::Role role,AsyncLeafOwner& actor,transport::RunGate& gate,
    transport::LeafLink& link,remote::ClockAgreement clock)
    :role_(role),zone_(role==session::Role::Steering || role==session::Role::Brake?session::Role::FrontZone:session::Role::RearZone),
    actor_(actor),local_gate_(gate),link_(link),clock_(clock),session_(role,*this) {
    if(role<session::Role::Steering || role>session::Role::Power ||
        static_cast<std::size_t>(role)-2!=static_cast<std::size_t>(actor.leaf()) || !clock.established ||
        !clock.local_domain || clock.local_domain!=clock.source_domain || clock.offset_ns || clock.uncertainty_ns)
        throw std::invalid_argument("remote Leaf Host clock/role");
    local_gate_.close();
}
remote::OwnerMessage RemoteLeafEndpoint::reply(remote::OwnerPayload payload,session::Role to) const {
    return {role_,to,clock_.local_domain,std::move(payload)};
}
session::Preparation RemoteLeafEndpoint::prepare(const session::Plan& plan) noexcept {
    local_gate_.close(); return actor_.prepare(plan);
}
bool RemoteLeafEndpoint::initialize(const session::Plan& plan) noexcept {
    local_gate_.close();
    if(!actor_.initialize(plan) || !credit_.bind(plan,clock_,now_ns())) return false;
    epoch_=plan.epoch; protection_acks_={}; return true;
}
void RemoteLeafEndpoint::protect() noexcept { local_gate_.close(); credit_.protect(epoch_); actor_.protect(); }
bool RemoteLeafEndpoint::allowed() {
    const bool ok=credit_.allows(session_,now_ns()) && !actor_.faulted() && !link_.failed();
    if(ok) local_gate_.release(epoch_); else local_gate_.close();
    return ok;
}
void RemoteLeafEndpoint::service() noexcept {
    if(!allowed() && credit_.fault()!=remote::RunLeaseFault::None) protect();
    actor_.service(); // sensor/protection monitoring runs even before arm/credit
    if(actor_.faulted() || link_.failed()) protect();
}
std::optional<remote::OwnerMessage> RemoteLeafEndpoint::poll() {
    if(const auto ack=session_.poll(now_ns())) return reply(*ack,session::Role::CentralIngress);
    return std::nullopt;
}
void RemoteLeafEndpoint::continuity_lost() { session_.continuity_lost(now_ns()); }
std::optional<remote::OwnerMessage> RemoteLeafEndpoint::take_report() {
    if(const auto report=link_.reports.pop()) return reply(*report,zone_);
    return std::nullopt;
}
std::optional<remote::OwnerMessage> RemoteLeafEndpoint::receive(const remote::OwnerMessage& m) {
    const auto now=now_ns();
    if(m.to!=role_ || m.clock_domain!=clock_.source_domain) return std::nullopt;
    if(const auto* c=std::get_if<session::Control>(&m.payload)) {
        if(m.from!=session::Role::CentralIngress) return std::nullopt;
        if(const auto ack=session_.receive(*c,now)) return reply(*ack,session::Role::CentralIngress);
    } else if(const auto* credit=std::get_if<remote::RunLease>(&m.payload)) {
        if(m.from==session::Role::CentralIngress) { credit_.receive(*credit,m.clock_domain,session_,now); service(); }
    } else if(const auto* r=std::get_if<remote::ProtectionRequest>(&m.payload)) {
        if((m.from==session::Role::CentralIngress || m.from==zone_) && r->epoch==epoch_ && r->token &&
            r->source_time_ns<=now && now<r->deadline_ns && r->deadline_ns-r->source_time_ns<=transport::kResultBudgetNs &&
            now-r->source_time_ns<=session::kMessageAgeNs) {
            auto& cache=protection_acks_[m.from==session::Role::CentralIngress?0:1];
            const auto duplicate=std::find_if(cache.begin(),cache.end(),[&](const auto& ack) {
                return ack && ack->request.epoch==r->epoch && ack->request.token==r->token;
            });
            if(duplicate!=cache.end()) {
                const auto& old=(*duplicate)->request;
                if(old.epoch!=r->epoch || old.source_time_ns!=r->source_time_ns || old.deadline_ns!=r->deadline_ns) return std::nullopt;
                return reply(**duplicate,m.from);
            }
            protect();
            const auto empty=std::find_if(cache.begin(),cache.end(),[](const auto& ack) { return !ack; });
            if(empty==cache.end()) return std::nullopt;
            *empty=remote::ProtectionAck{*r,now,actor_.faulted()}; return reply(**empty,m.from);
        }
    } else if(const auto* r=std::get_if<transport::LeafRequest>(&m.payload)) {
        // Check old expiry before accepting a newly arrived packet. No RX time
        // rewriting; actor still checks inner CAN/P05 and composite authority.
        if(m.from!=zone_) return std::nullopt;
        // Preserve the legacy negative reply, but keep its original identity.
        // Old-session traffic must not poll/mutate this session's credit or actor.
        if(r->epoch!=epoch_)
            return reply(transport::LeafReport{transport::LeafResult{r->epoch,r->token,now,r->operation,false}},zone_);
        if(!allowed() && credit_.fault()!=remote::RunLeaseFault::None) protect();
        const bool eligible=allowed() && r->epoch==epoch_ && r->sent_ns<=now && now<r->deadline_ns &&
            r->deadline_ns-r->sent_ns<=transport::kResultBudgetNs;
        if(!eligible) return reply(transport::LeafReport{transport::LeafResult{r->epoch,r->token,now,r->operation,false}},zone_);
        if(!link_.work.push(*r)) continuity_lost();
    }
    return std::nullopt;
}
} // namespace stratadrive::simulation
