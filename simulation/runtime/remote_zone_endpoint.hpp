#pragma once
#include "async_zone_owner.hpp"
#include "run_lease_gate.hpp"
#include <stdexcept>

namespace stratadrive::simulation {
// One Zone session/credit endpoint, shared by Front and Rear. Owns no peer state.
class RemoteZoneEndpoint final:private session::ParticipantPort {
    const session::Role role_;remote::ClockAgreement agreement_;
    session::ParticipantPort& actor_;zone::AsyncZoneOwner& zone_;
    transport::RunGate& gate_; transport::ZoneLink& link_;
    session::SessionParticipant participant_;remote::RunLeaseGate credit_;
    std::uint32_t epoch_=0;std::uint64_t last_token_=0;
    std::array<std::optional<remote::ProtectionAck>,8> protection_{};
    std::uint64_t now_ns() noexcept override{return actor_.now_ns();}
    session::Preparation prepare(const session::Plan& p) noexcept override {gate_.close();return actor_.prepare(p);}
    bool initialize(const session::Plan& p) noexcept override {
        gate_.close();if(!actor_.initialize(p) || !credit_.bind(p,agreement_,now_ns()))return false;
        epoch_=p.epoch;last_token_=0;protection_={};return true;
    }
    void protect() noexcept override{gate_.close();credit_.protect(epoch_);actor_.protect();}
    bool allowed(){return credit_.allows(participant_,now_ns()) && !zone_.faulted() && !link_.failed();}
    void service() noexcept override {
        if(allowed())gate_.release(epoch_);else {gate_.close();if(credit_.fault()!=remote::RunLeaseFault::None)protect();}
        actor_.service();
    }
public:
    std::uint64_t rejected=0,expired=0,last_lease_expiry=0;
    RemoteZoneEndpoint(session::Role role,session::ParticipantPort& a,zone::AsyncZoneOwner& z,transport::RunGate& g,transport::ZoneLink& l,remote::ClockAgreement clock)
        :role_(role),agreement_(clock),actor_(a),zone_(z),gate_(g),link_(l),participant_(role,*this) {
        if((role!=session::Role::FrontZone && role!=session::Role::RearZone) || !clock.established || clock.local_domain!=clock.source_domain || clock.offset_ns || clock.uncertainty_ns)
            throw std::invalid_argument("remote Zone role/clock");
    }
    remote::OwnerMessage reply(remote::OwnerPayload p){return {role_,session::Role::CentralIngress,agreement_.local_domain,std::move(p)};}
    std::optional<remote::OwnerMessage> receive(const remote::OwnerMessage& m) {
        if(m.to!=role_ || m.from!=session::Role::CentralIngress || m.clock_domain!=agreement_.source_domain)return {};
        const auto t=now_ns();
        if(const auto* c=std::get_if<session::Control>(&m.payload)) {if(auto a=participant_.receive(*c,t))return reply(*a);}
        else if(const auto* l=std::get_if<remote::RunLease>(&m.payload)) {
            if(credit_.receive(*l,m.clock_domain,participant_,t))last_lease_expiry=l->expires_at_ns;
            service();
        } else if(const auto* r=std::get_if<transport::ZoneRequest>(&m.payload)) {
            // Old Epoch and duplicates cannot poll or mutate live-session state.
            const bool identity=r->epoch==epoch_ && r->token>last_token_;
            const bool timely=r->sent_ns<=t && t<r->deadline_ns && r->deadline_ns-r->sent_ns<=transport::kResultBudgetNs;
            if(!identity || !timely || !allowed()) {
                ++rejected;if(identity && !timely){++expired;protect();}
                return reply(transport::TxResult{r->epoch,r->token,t,transport::operation(r->work),false,0});
            }
            last_token_=r->token;
            if(!link_.work.push(*r)){participant_.continuity_lost(t);++rejected;}
        } else if(const auto* p=std::get_if<remote::ProtectionRequest>(&m.payload)) {
            if(p->epoch!=epoch_ || !p->token || p->source_time_ns>t || t>=p->deadline_ns || p->deadline_ns-p->source_time_ns>transport::kResultBudgetNs)return {};
            for(const auto& a:protection_)if(a && a->request.token==p->token) {
                if(a->request.source_time_ns==p->source_time_ns && a->request.deadline_ns==p->deadline_ns)return reply(*a);
                return {};
            }
            protect(); // ACK only after the actual Leaf selection, in poll().
            for(auto& a:protection_)if(!a){a=remote::ProtectionAck{*p,0,false};break;}
        }
        return {};
    }
    std::optional<remote::OwnerMessage> poll() {
        if(auto a=participant_.poll(now_ns()))return reply(*a);
        for(auto& a:protection_)if(a && !a->selected && zone_.protected_selected() && now_ns()<a->request.deadline_ns) {
            a->selected=true;a->selected_ns=now_ns();return reply(*a);
        }
        return {};
    }
    void lost(){participant_.continuity_lost(now_ns());}
    unsigned lease_fault() const{return static_cast<unsigned>(credit_.fault());}
};
}
