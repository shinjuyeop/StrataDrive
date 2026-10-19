#pragma once

#include "session_coordinator.hpp"
#include "session_participant.hpp"
#include "session_mailbox.hpp"

namespace stratadrive::simulation {
// Externally clocked session runnables, one owner each. These do not run the
// normal VM/Zone/Leaf cycles. Those need separate asynchronous ports before
// sharing actual actors across threads. No clock, sensor or packet restamping.
class SessionOwnerLoop {
public:
    SessionOwnerLoop(session::Role role,session::ParticipantPort& port,session::SessionLink& link)
        :port_(port),participant_(role,port),link_(link) {}
    void step() {
        if(link_.failed()) participant_.continuity_lost(port_.now_ns());
        for(std::size_t i=0;i<session::kSessionQueueCapacity;++i) {
            const auto control=link_.controls.pop(); if(!control) break;
            publish(participant_.receive(*control,port_.now_ns()));
        }
        publish(participant_.poll(port_.now_ns()));
        if(link_.failed()) participant_.continuity_lost(port_.now_ns());
    }
    bool run_enabled() const { return participant_.run_enabled() && !link_.failed(); }
    session::ParticipantFault fault() const { return participant_.fault(); }
private:
    void publish(const std::optional<session::Ack>& ack) {
        if(ack && !link_.acks.push(*ack)) participant_.continuity_lost(port_.now_ns());
    }
    session::ParticipantPort& port_; session::SessionParticipant participant_;
    session::SessionLink& link_;
};

// The host supplies trusted startup callbacks; only this owner consumes ACKs.
// EpochStore::issue() belongs to explicit startup outside step(), never to CAN
// ingress or an ordinary control/monitor cycle. No implicit store bootstrap.
class SessionCentralLoop final : private session::CoordinatorPort {
public:
    SessionCentralLoop(session::CoordinatorPort& port,session::SessionLinks& links)
        :port_(port),links_(links),coordinator_(*this) {}
    bool begin(std::uint32_t granted_epoch,std::uint64_t now) { return coordinator_.begin(granted_epoch,now); }
    void cancel(std::uint64_t now) { coordinator_.cancel(now); }
    void step() {
        for(std::size_t role=0;role<links_.size();++role) {
            auto& link=links_[role];
            if(link.failed()) coordinator_.continuity_lost(port_.now_ns());
            for(std::size_t i=0;i<session::kSessionQueueCapacity;++i) {
                const auto ack=link.acks.pop(); if(!ack) break;
                if(static_cast<std::size_t>(ack->role)!=role) coordinator_.continuity_lost(port_.now_ns());
                else coordinator_.receive(*ack,port_.now_ns());
            }
        }
        coordinator_.poll(port_.now_ns());
    }
    bool run_enabled() const {
        if(!coordinator_.run_enabled()) return false;
        for(const auto& link:links_) if(link.failed()) return false;
        return true;
    }
    session::State state() const { return coordinator_.state(); }
    session::Fault fault() const { return coordinator_.fault(); }
    const session::Plan& plan() const { return coordinator_.plan(); }
private:
    std::uint64_t now_ns() noexcept override { return port_.now_ns(); }
    bool quiesce_central() noexcept override { return port_.quiesce_central(); }
    bool commit_central(central::CoordinatorSession session) noexcept override { return port_.commit_central(session); }
    void protect_central() noexcept override { port_.protect_central(); }
    bool send(const session::Control& c) noexcept override {
        const auto i=static_cast<std::size_t>(c.role);
        return i<links_.size() && links_[i].controls.push(c);
    }
    session::CoordinatorPort& port_; session::SessionLinks& links_;
    session::SessionCoordinator coordinator_;
};
}  // namespace stratadrive::simulation
