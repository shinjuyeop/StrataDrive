#pragma once
#include "owner_message_binding.hpp"
#include <algorithm>
#include <deque>

namespace stratadrive::someip {
struct QueuedCredit {session::Plan plan;session::Role peer;std::uint64_t clock;};
struct OwnerEgressPacket {remote::OwnerPacket packet;unsigned method;std::optional<QueuedCredit> credit;};
inline std::optional<OwnerEgressPacket> owner_egress(const remote::OwnerMessage& m) {
    const auto packet=remote::encode_owner_message(m);if(!packet)return std::nullopt;
    OwnerEgressPacket out{*packet,method(m.payload),std::nullopt};
    if(m.from==session::Role::CentralIngress)if(const auto* c=std::get_if<remote::RunLease>(&m.payload))out.credit=QueuedCredit{c->plan,m.to,m.clock_domain};
    return out;
}
// Only unsent credit for the exact protected peer/session/clock is superseded.
// Control/command/ACK packets are never removed, nor anything already in SDK IO.
inline bool superseded_credit(const QueuedCredit& c,const remote::OwnerMessage& action) {
    if(action.from!=session::Role::CentralIngress || action.to!=c.peer || action.clock_domain!=c.clock)return false;
    if(const auto* abort=std::get_if<session::Control>(&action.payload))
        return abort->phase==session::Phase::Abort && session::same_plan(abort->plan,c.plan);
    if(const auto* protect=std::get_if<remote::ProtectionRequest>(&action.payload))
        return protect->epoch==c.plan.epoch && protect->token && protect->source_time_ns>=c.plan.enable_ns &&
            protect->deadline_ns>protect->source_time_ns && protect->deadline_ns-protect->source_time_ns<=transport::kResultBudgetNs;
    return false;
}
inline std::size_t retire_run_credits(std::deque<OwnerEgressPacket>& queue,const remote::OwnerMessage& action) {
    const auto count=queue.size();queue.erase(std::remove_if(queue.begin(),queue.end(),[&](const auto& p){return p.credit && superseded_credit(*p.credit,action);}),queue.end());return count-queue.size();
}
enum class EgressResult { Queued, PeerUnavailable, Full };
struct EgressAdmission { EgressResult result;std::size_t retired; };
inline EgressAdmission enqueue_owner_egress(std::deque<OwnerEgressPacket>& queue,
        const remote::OwnerMessage& message,const OwnerEgressPacket& packet,bool available) {
    // Availability loss must not feed the SDK's disconnected-endpoint backlog.
    // No packet is acknowledged, re-stamped or retained for a later peer here.
    if(!available)return {EgressResult::PeerUnavailable,0};
    const auto retired=retire_run_credits(queue,message);
    if(queue.size()>=8)return {EgressResult::Full,retired};
    queue.push_back(packet);return {EgressResult::Queued,retired};
}
inline std::size_t retire_received_credits(std::deque<remote::OwnerMessage>& queue,const remote::OwnerMessage& action) {
    const auto count=queue.size();
    queue.erase(std::remove_if(queue.begin(),queue.end(),[&](const auto& p) {
        const auto* credit=std::get_if<remote::RunLease>(&p.payload);
        return credit && p.from==session::Role::CentralIngress && superseded_credit({credit->plan,p.to,p.clock_domain},action);
    }),queue.end());return count-queue.size();
}
} // namespace stratadrive::someip
