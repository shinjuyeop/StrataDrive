#pragma once
// M7 opt-in functional admission. Trusted local launch binds the native owner;
// CRC/ACK packets do not authenticate arbitrary clients. No M6 wire changes.
#include "owner_wire.hpp"
#include "steering_receiver.hpp"
#include "brake_receiver.hpp"
#include "drive_receiver.hpp"
#include "bms_receiver.hpp"
#include <algorithm>
#include <memory>
#include <string>

namespace stratadrive::m7_native {
using Time=std::uint64_t;
constexpr Time domain=0x4d3746554e435449ULL,step=10000000,age=30000000;
constexpr Time init_offset=8000000; // explicit M7-only INIT phase, all native periods unchanged
using Packet=std::optional<remote::OwnerPacket>;
struct Input {
    Time observed=0,enable=0;
    bool normal=false;
    unsigned service_mask=0,credit_mask=0,release_mask=0;
    std::array<Packet,3> actual,commands;
    std::array<Packet,8> release;
    std::array<Packet,7> credit;
    Packet permission;
};
struct Output {
    bool empty=true,normal=false;
    double angle=0,torque=0,pressure=0;
    std::array<Time,3> sources{};
    Time oldest_actuator=0,oldest_dependency=0,exclusive_expiry=0;
};
inline bool same(const Packet& a,const Packet& b) {
    return a && b && a->size==b->size && std::equal(a->bytes.begin(),a->bytes.begin()+a->size,b->bytes.begin());
}
class Admission {
public:
    Admission(std::uint32_t application,Time initial):application_(application),initial_(initial) {}
    bool accept(const Input& in,Time now,Output& output) {
        if(!error_.empty())return false;
        if(!application_ || !initial_ || now>UINT64_MAX-step || in.observed!=now ||
           now<initial_ || (last_ && (now<=last_ || now-last_<step-999 || now-last_>step+999)) ||
           in.service_mask!=255)return fail("native_clock_or_service");
        last_=now;
        const Time end=now+step;
        const bool empty=std::all_of(in.actual.begin(),in.actual.end(),[](const Packet& p){return !p;});
        if(empty) {
            if(started_ || normal_ || in.normal || now-initial_>=80000000)return fail("bootstrap_missing_actual");
            output={};return true; // bounded INIT tick with NO actuation, not a synthetic Actual
        }
        if(!authority(in,now,end))return false;
        if(!started_) {
            if(!in.enable || in.enable<initial_ || in.enable>now ||
               !steering_->start_session(application_,in.enable) || !brake_->start_session(application_,in.enable) ||
               !drive_->start_session(application_,in.enable) || !permission_->start_session(application_,in.enable))return fail("native_receiver_init");
            enable_=in.enable;started_=true;
        }
        if(in.enable!=enable_)return fail("native_enable_changed");
        can::SteeringFrame sf;can::BrakeFrame bf;can::DriveFrame df;
        if(!actual(in.actual[0],0,sf) || !actual(in.actual[1],1,bf) || !actual(in.actual[2],2,df))return false;
        const auto accepted=can::ActuatorReceiveDecision::Accepted;
        if((!same(in.actual[0],cached_[0]) && steering_->receive(sf,now).decision!=accepted) ||
           (!same(in.actual[1],cached_[1]) && brake_->receive(bf,now).decision!=accepted) ||
           (!same(in.actual[2],cached_[2]) && drive_->receive(df,now).decision!=accepted))return fail("native_actual_receiver");
        auto s=steering_->current_sample(now);auto b=brake_->current_sample(now);auto d=drive_->current_sample(now);
        if(!s || !b || !d)return fail("native_current_actual_missing");
        Output out;out.empty=false;out.normal=in.normal;
        out.angle=*s->angle_rad;out.pressure=*b->pressure_pa;out.torque=*d->torque_nm;
        out.sources={s->source_time_ns,b->source_time_ns,d->source_time_ns};
        const auto bounds=std::minmax_element(out.sources.begin(),out.sources.end());
        if(*bounds.second-*bounds.first>10000000)return fail("native_actual_skew");
        for(auto source:out.sources)if(!covers(source,now,end,age))return fail("native_actual_interval");
        out.oldest_actuator=*bounds.first;out.exclusive_expiry=credit_->expires_at_ns;
        if(!d->wheel_speed || !covers(d->wheel_speed->source_time_ns,now,end,age))return fail("native_wheel_interval");
        out.oldest_actuator=std::min(out.oldest_actuator,d->wheel_speed->source_time_ns);
        out.oldest_dependency=out.oldest_actuator;
        if(in.permission && !grant(in.permission,now,end,out,in.normal))return false;
        if(in.normal) {
            if(!normal_mode(*s) || !normal_mode(*b) || !normal_mode(*d))return fail("native_actual_mode");
            if(!in.permission)return fail("native_permission_missing");
            if(!command(in.commands[0],0,*s,now,end,out) || !command(in.commands[1],1,*b,now,end,out) ||
               !command(in.commands[2],2,*d,now,end,out))return false;
            if(!d->regen_capability || !covers(d->regen_capability->source_time_ns,now,end,age) ||
               !covers(d->regen_capability->input_time_ns,now,end,70000000))return fail("native_capability_interval");
            out.oldest_dependency=std::min(out.oldest_dependency,d->regen_capability->input_time_ns);
            normal_=true;
        } else if(normal_ || out.torque!=0 || !init_mode(*s) || !init_mode(*b) || !init_mode(*d))
            return fail("bootstrap_cannot_drive_or_resume");
        cached_=in.actual;output=out;return true;
    }
    const std::string& error() const {return error_;}
private:
    bool fail(const char* why) {if(error_.empty())error_=why;return false;}
    bool covers(Time source,Time now,Time end,Time budget) const {
        return source>=enable_ && source<=now && end>=source && end-source<=budget;
    }
    template<class T> static bool normal_mode(const T& m) {
        return m.origin==can::ActuatorOrigin::NormalPath &&
            (m.local_state==can::ActuatorLocalState::Normal || m.local_state==can::ActuatorLocalState::Degraded);
    }
    template<class T> static bool init_mode(const T& m) {
        return m.origin==can::ActuatorOrigin::NoAcceptedInput && m.local_state==can::ActuatorLocalState::Init;
    }
    template<class T> std::optional<T> decode(const Packet& p,session::Role from,session::Role to) {
        const auto m=p?remote::decode_owner_message(p->bytes.data(),p->size):std::nullopt;
        if(!m || m->clock_domain!=domain || m->from!=from || m->to!=to || !std::holds_alternative<T>(m->payload)) {
            fail("native_owner_wire_route_crc");return {};
        }
        return std::get<T>(m->payload);
    }
    bool authority(const Input& in,Time now,Time end) {
        if(in.release_mask!=255 || in.credit_mask!=255)return fail("native_authority_mask");
        std::optional<session::Plan> plan;
        Time newest_ack=0;
        for(unsigned i=0;i<8;++i) {
            const auto a=decode<session::Ack>(in.release[i],static_cast<session::Role>(i),session::Role::CentralIngress);
            if(!a)return false;
            if(!a->accepted || a->phase!=session::Phase::Release || a->role!=static_cast<session::Role>(i) ||
               a->plan.epoch!=application_ || a->plan.requested_ns!=initial_+init_offset ||
               a->plan.prepare_deadline_ns!=initial_+init_offset+session::kPrepareBudgetNs || a->plan.enable_ns!=in.enable ||
               a->plan.commit_deadline_ns!=in.enable+session::kInitWindowNs || a->source_ns<in.enable ||
               a->plan.enable_ns<a->plan.requested_ns+session::kInitLeadNs ||
               a->plan.commit_deadline_ns>a->plan.prepare_deadline_ns ||
               a->source_ns>=a->plan.commit_deadline_ns || a->source_ns>now ||
               (plan && !session::same_plan(*plan,a->plan)))return fail("native_release_ack");
            if(started_ && !same(in.release[i],release_[i]))return fail("native_release_mutated");
            plan=a->plan;newest_ack=std::max(newest_ack,a->source_ns);
        }
        std::optional<remote::RunLease> first;
        for(unsigned i=0;i<7;++i) {
            const auto c=decode<remote::RunLease>(in.credit[i],session::Role::CentralIngress,static_cast<session::Role>(i));
            if(!c)return false;
            if(!session::same_plan(*plan,c->plan) || c->source_time_ns<newest_ack || c->source_time_ns>now ||
               c->source_time_ns>UINT64_MAX-60000000 || c->expires_at_ns!=c->source_time_ns+60000000 || c->expires_at_ns<=end ||
               (first && (c->sequence!=first->sequence || c->source_time_ns!=first->source_time_ns || c->expires_at_ns!=first->expires_at_ns)))return fail("native_run_credit");
            if(credit_ && (c->sequence<credit_->sequence || c->source_time_ns<credit_->source_time_ns ||
               ((c->sequence==credit_->sequence)!=(c->source_time_ns==credit_->source_time_ns))))return fail("native_credit_cursor");
            first=c;
        }
        release_=in.release;credit_=first;return true;
    }
    template<class F> bool actual(const Packet& packet,unsigned role,F& frame) {
        const auto feedback=decode<transport::Feedback>(packet,role<2?session::Role::FrontZone:session::Role::RearZone,session::Role::CentralIngress);
        if(!feedback)return false;
        const auto* p=std::get_if<F>(&*feedback);
        if(!p)return fail("native_actual_role");
        frame=*p;return true;
    }
    template<class M> bool command(const Packet& packet,unsigned role,const M& actual,Time now,Time end,Output& out) {
        const auto q=decode<transport::LeafRequest>(packet,role<2?session::Role::FrontZone:session::Role::RearZone,static_cast<session::Role>(role+2));
        if(!q)return false;
        if(q->epoch!=application_ || q->operation!=transport::LeafOperation::Frame || !q->command)return fail("native_command_context");
        const auto& ctx=*q->command;const auto& parent=ctx.parent;
        std::optional<can::ActuatorMetadata> m;
        std::visit([&](const auto& f) {
            using F=std::decay_t<decltype(f)>;
            if constexpr(std::is_same_v<F,can::SteeringFrame>) {const auto v=can::decode_steering_frame(f);if(role==0 && v && v->kind==can::SteeringFrameKind::Command)m=can::ActuatorMetadata{v->sequence,v->epoch,v->source_time_ns,v->causal_sequence,v->local_state,v->origin};}
            if constexpr(std::is_same_v<F,can::BrakeFrame>) {const auto v=can::decode_brake_frame(f);if(role==1 && v && v->kind==can::BrakeFrameKind::Command)m=*v;}
            if constexpr(std::is_same_v<F,can::DriveFrame>) {const auto v=can::decode_drive_frame(f);if(role==2 && v && v->kind==can::DriveFrameKind::Command)m=*v;}
        },q->frame);
        if(!m || m->epoch!=application_ || m->sequence!=actual.causal_sequence || m->causal_sequence!=parent.sequence ||
           parent.epoch!=application_ || !normal_mode(*m) || !covers(m->source_time_ns,now,end,age) ||
           !covers(parent.source_time_ns,now,end,age) || !covers(ctx.oldest_input_time_ns,now,end,70000000) ||
           ctx.oldest_input_time_ns>parent.source_time_ns || parent.source_time_ns>m->source_time_ns ||
           m->source_time_ns>actual.source_time_ns || ctx.expires_at_ns<=end || ctx.expires_at_ns>parent.expires_at_ns ||
           ctx.expires_at_ns>m->source_time_ns+age+1 || ctx.expires_at_ns>parent.source_time_ns+age+1 ||
           ctx.expires_at_ns>ctx.oldest_input_time_ns+70000001)return fail("native_command_interval_or_causal");
        out.oldest_dependency=std::min(out.oldest_dependency,ctx.oldest_input_time_ns);
        out.exclusive_expiry=std::min(out.exclusive_expiry,ctx.expires_at_ns);return true;
    }
    bool grant(const Packet& packet,Time now,Time end,Output& out,bool normal) {
        const auto q=decode<transport::LeafRequest>(packet,session::Role::RearZone,session::Role::Drive);
        if(!q)return false;
        const auto* frame=std::get_if<can::BmsFrame>(&q->frame);
        if(!frame || (normal && !q->parent) || q->epoch!=application_ || q->operation!=transport::LeafOperation::Frame)return fail("native_permission_parent_missing");
        if(!same(packet,permission_packet_) && permission_->receive(*frame,now,q->parent?&*q->parent:nullptr).decision!=can::ActuatorReceiveDecision::Accepted)return fail("native_permission_receiver");
        const auto current=permission_->current_sample(now);
        permission_packet_=packet;
        if(!normal)return true; // consume original inhibit traffic too; never reset RX timeout at arm
        if(!current || !can::bms_permission_allows_normal(*current))return fail("native_permission_unavailable");
        const auto& message=current->message;const auto& grant=std::get<can::BmsDriveGrant>(message.content);
        if(grant.expires_at_ns<=end || q->parent->expires_at_ns<=end ||
           !covers(message.source_time_ns,now,end,50000000) || !covers(grant.input_time_ns,now,end,70000000) ||
           !covers(q->parent->source_time_ns,now,end,50000000))return fail("native_permission_interval");
        out.oldest_dependency=std::min(out.oldest_dependency,grant.input_time_ns);
        out.exclusive_expiry=std::min(out.exclusive_expiry,grant.expires_at_ns);return true;
    }
    std::uint32_t application_;Time initial_,last_=0,enable_=0;bool started_=false,normal_=false;
    std::string error_;
    std::array<Packet,3> cached_;std::array<Packet,8> release_;Packet permission_packet_;
    std::optional<remote::RunLease> credit_;
    std::unique_ptr<can::SteeringReceiver> steering_{new can::SteeringReceiver({can::SteeringFrameKind::Actual,-.3,.3})};
    std::unique_ptr<can::BrakeReceiver> brake_{new can::BrakeReceiver({can::BrakeFrameKind::Actual,0,1500000})};
    std::unique_ptr<can::DriveReceiver> drive_{new can::DriveReceiver({can::DriveFrameKind::Actual,{-200,300},100,200,age,80000000,age,70000000})};
    std::unique_ptr<can::BmsReceiver> permission_{new can::BmsReceiver({can::BmsFrameKind::DrivePermission,{{0,1000},{-3000,3000},{-50,150},100000}})};
};
} // namespace stratadrive::m7_native
