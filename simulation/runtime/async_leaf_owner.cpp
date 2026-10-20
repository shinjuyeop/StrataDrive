#include "async_leaf_owner.hpp"

#include "multirate_fixture.hpp"

namespace stratadrive::simulation {
SessionResetEvidence reset_evidence(const OwnerSensors& s) { return {s.drive.wheel_speed,s.torque,s.power}; }
AsyncLeafOwner::Actor AsyncLeafOwner::make_actor(transport::Leaf leaf) {
    switch(leaf) {
    case transport::Leaf::Steering: { auto c=vecu::SteeringActuatorConfig{-.5,.5,-.3,.3,.1,1,50000000}; c.period_ns=1000000; return Actor{std::in_place_type<vecu::SteeringActuator>,c}; }
    case transport::Leaf::Brake: { auto c=vecu::BrakeActuatorConfig{2000000,1500000,200000,5000000,10000000,1000000,50000000}; c.period_ns=1000000; return Actor{std::in_place_type<vecu::BrakeActuator>,c}; }
    case transport::Leaf::Drive: { auto c=vecu::DriveControllerConfig{}; c.period_ns=1000000; return Actor{std::in_place_type<vecu::DriveController>,c}; }
    case transport::Leaf::Bms: return Actor{std::in_place_type<vecu::BmsController>,multirate_fixture::bms_config()};
    case transport::Leaf::Power: { auto c=vecu::PowerControllerConfig{}; c.period_ns=1000000; return Actor{std::in_place_type<vecu::PowerController>,c}; }
    case transport::Leaf::Count: break;
    }
    throw std::invalid_argument("Leaf role");
}
AsyncLeafOwner::AsyncLeafOwner(transport::Leaf leaf,transport::Clock& clock,transport::RunGate& gate,transport::LeafLink& link,
    runtime::LatestSnapshot<OwnerSensors>& sensors,runtime::LatestSnapshot<OwnerActuation>& output,BmsGateChannel& bms_gate)
    :leaf_(leaf),clock_(clock),gate_(gate),link_(link),sensors_(sensors),output_(output),bms_gate_(bms_gate),actor_(make_actor(leaf)) { input_events_.reserve(12000); }
session::Preparation AsyncLeafOwner::prepare(const session::Plan& plan) noexcept {
    if(plan.epoch!=quiesced_) {
        quiesced_=plan.epoch; if(epoch_!=0) protect();
        for(std::size_t i=0;i<transport::kBudget;++i) if(!link_.work.pop()) break;
    }
    if(link_.failed()) return session::Preparation::Rejected;
    const auto sensors=sensors_.read();
    const bool ready=sensors && session_reset_safe(reset_evidence(*sensors),7,now_ns());
    if(ready) prepared_epoch_=plan.epoch;
    return ready?session::Preparation::Ready:session::Preparation::Pending;
}
bool AsyncLeafOwner::initialize(const session::Plan& plan) noexcept {
    const auto sensors=sensors_.read();
    if(!sensors || link_.failed() || !session_reset_safe(reset_evidence(*sensors),7,now_ns())) return false;
    const ActuatorSession mapping{plan.epoch,7,plan.enable_ns}; bool ok=false;
    switch(leaf_) {
    case transport::Leaf::Steering: ok=std::get<vecu::SteeringActuator>(actor_).start_session(mapping,ActuatorCommandStartup::NonDriving); break;
    case transport::Leaf::Brake: ok=std::get<vecu::BrakeActuator>(actor_).start_session(mapping,ActuatorCommandStartup::NonDriving); break;
    case transport::Leaf::Drive: ok=std::get<vecu::DriveController>(actor_).start_session(mapping,ActuatorCommandStartup::NonDriving); break;
    case transport::Leaf::Bms: ok=std::get<vecu::BmsController>(actor_).start_session(plan.epoch,7,plan.enable_ns); break;
    case transport::Leaf::Power: ok=std::get<vecu::PowerController>(actor_).start_session(plan.epoch,7,plan.enable_ns); break;
    case transport::Leaf::Count: break;
    }
    if(ok) {
        epoch_=plan.epoch; enable_=last_body_=plan.enable_ns; started_=false;
        command_expiry_ns_=command_source_ns_=0; expiry_reported_=false; prepared_epoch_=0;
        next_body_=enable_+(leaf_==transport::Leaf::Bms?20000000ULL:10000000ULL);
        e2e::p05_protect_init(bms_tx_.protection); e2e::p05_protect_init(power_tx_.protection);
    }
    return ok;
}
bool AsyncLeafOwner::faulted() const {
    switch(leaf_) {
    case transport::Leaf::Steering: return std::get<vecu::SteeringActuator>(actor_).fault()!=vecu::SteeringFault::None;
    case transport::Leaf::Brake: return std::get<vecu::BrakeActuator>(actor_).fault()!=vecu::BrakeFault::None;
    case transport::Leaf::Drive: return std::get<vecu::DriveController>(actor_).decision().fault!=vecu::DriveGateFault::None;
    case transport::Leaf::Bms: return std::get<vecu::BmsController>(actor_).decision().fault!=vecu::BmsControlFault::None;
    case transport::Leaf::Power: return std::get<vecu::PowerController>(actor_).output().fault!=vecu::PowerControlFault::None;
    case transport::Leaf::Count: return true;
    }
    return true;
}
int AsyncLeafOwner::fault_code() const {
    switch(leaf_) {
    case transport::Leaf::Steering: return static_cast<int>(std::get<vecu::SteeringActuator>(actor_).fault());
    case transport::Leaf::Brake: return static_cast<int>(std::get<vecu::BrakeActuator>(actor_).fault());
    case transport::Leaf::Drive: return static_cast<int>(std::get<vecu::DriveController>(actor_).decision().fault);
    case transport::Leaf::Bms: return static_cast<int>(std::get<vecu::BmsController>(actor_).decision().fault);
    case transport::Leaf::Power: return static_cast<int>(std::get<vecu::PowerController>(actor_).output().fault);
    case transport::Leaf::Count: return -1;
    }
    return -1;
}
void AsyncLeafOwner::protect() noexcept {
    if(epoch_==0) return;
    gate_.close();
    const auto now=now_ns();
    switch(leaf_) {
    case transport::Leaf::Steering: std::get<vecu::SteeringActuator>(actor_).request_local_protection(now); break;
    case transport::Leaf::Brake: std::get<vecu::BrakeActuator>(actor_).request_local_protection(now); break;
    case transport::Leaf::Drive: std::get<vecu::DriveController>(actor_).request_local_protection(now); break;
    case transport::Leaf::Bms: {
        auto& actor=std::get<vecu::BmsController>(actor_); actor.request_local_protection(now);
        bms_gate_.publish(actor.power_gate()); break;
    }
    case transport::Leaf::Power: std::get<vecu::PowerController>(actor_).request_local_protection(now); break;
    case transport::Leaf::Count: break;
    }
    output(now);
    if(faulted()) link_.protection.selected.store(epoch_,std::memory_order_release);
}
void AsyncLeafOwner::publish(const transport::Feedback& f) { if(!drop_actual && !link_.reports.push(transport::LeafReport{f})) protect(); }
bool AsyncLeafOwner::receive(const transport::LeafRequest& r) {
    const auto now=now_ns();
    receive_begin_=now;
    if(r.command && (r.command->parent.epoch!=epoch_ || r.command->oldest_input_time_ns>now || now-r.command->oldest_input_time_ns>70000000 ||
        now>=r.command->expires_at_ns || r.deadline_ns>r.command->expires_at_ns || r.command->expires_at_ns>r.command->parent.expires_at_ns)) return false;
    if(leaf_==transport::Leaf::Steering) {
        const auto* f=std::get_if<can::SteeringFrame>(&r.frame); return r.command && f && std::get<vecu::SteeringActuator>(actor_).receive(*f,now).decision==can::ActuatorReceiveDecision::Accepted;
    }
    if(leaf_==transport::Leaf::Brake) {
        const auto* f=std::get_if<can::BrakeFrame>(&r.frame); return r.command && f && std::get<vecu::BrakeActuator>(actor_).receive(*f,now).decision==can::ActuatorReceiveDecision::Accepted;
    }
    const auto* b=std::get_if<can::BmsFrame>(&r.frame);
    if(leaf_==transport::Leaf::Power) return b && std::get<vecu::PowerController>(actor_).receive(*b,now,r.parent?&*r.parent:nullptr).decision==can::ActuatorReceiveDecision::Accepted;
    if(leaf_==transport::Leaf::Drive) {
        auto& drive=std::get<vecu::DriveController>(actor_);
        if(const auto* f=std::get_if<can::DriveFrame>(&r.frame)) return r.command && drive.receive_command(*f,now).decision==can::ActuatorReceiveDecision::Accepted;
        if(!b) return false;
        const auto m=can::decode_bms_frame(*b); if(!m) return false;
        return (m->kind==can::BmsFrameKind::DriveBatteryLimits?drive.receive_limits(*b,now):
            drive.receive_permission(*b,now,r.parent?&*r.parent:nullptr)).decision==can::ActuatorReceiveDecision::Accepted;
    }
    return false;
}
void AsyncLeafOwner::handle(const transport::LeafRequest& r) {
    if(r.epoch!=epoch_) {
        if(input_events_.size()<input_events_.capacity()) input_events_.push_back({now_ns(),"old-epoch-rejected",static_cast<std::size_t>(leaf_)+2,r.epoch,r.sent_ns,r.deadline_ns,0,0});
        return;
    }
    const auto now=now_ns(); bool ok=gate_.allows(epoch_) && !faulted() && r.sent_ns<=now && now<r.deadline_ns;
    if(ok && r.operation==transport::LeafOperation::Frame) { ok=receive(r); if(ok && r.command) ++commands_; }
    if(ok && r.command) { command_expiry_ns_=r.command->expires_at_ns; command_source_ns_=fault_message(r).source; expiry_reported_=false; }
    if(r.operation==transport::LeafOperation::Frame && input_events_.size()<input_events_.capacity()) {
        const auto m=fault_message(r);
        // Accepted command authority outlives the bounded delivery envelope.
        // Keep this event correlated with command-expired; transport events
        // separately retain the original envelope deadline.
        input_events_.push_back({now_ns(),ok?"valid-input":"input-rejected",static_cast<std::size_t>(leaf_)+2,epoch_,m.source,r.command?r.command->expires_at_ns:m.deadline,ok?receive_begin_:now,r.command?1:0});
    }
    if(ok && r.operation==transport::LeafOperation::Arm) {
        ok=!reject_arm;
        if(ok) {
            if(leaf_==transport::Leaf::Steering) ok=std::get<vecu::SteeringActuator>(actor_).arm_normal_commands(now);
            else if(leaf_==transport::Leaf::Brake) ok=std::get<vecu::BrakeActuator>(actor_).arm_normal_commands(now);
            else if(leaf_==transport::Leaf::Drive) ok=std::get<vecu::DriveController>(actor_).arm_normal_commands(now);
            else ok=false;
        }
    }
    if(ok && r.operation==transport::LeafOperation::Stop) {
        ok=r.lease.has_value();
        if(ok && leaf_==transport::Leaf::Steering) ok=std::get<vecu::SteeringActuator>(actor_).select_normal_stop(*r.lease,now);
        else if(ok && leaf_==transport::Leaf::Brake) ok=std::get<vecu::BrakeActuator>(actor_).select_normal_stop(*r.lease,now);
        else if(ok && leaf_==transport::Leaf::Drive) ok=std::get<vecu::DriveController>(actor_).select_normal_stop(*r.lease,now);
        else ok=false;
        if(ok) { command_expiry_ns_=0; output(now); } // terminal lease now owns authority
    }
    if(!link_.reports.push(transport::LeafResult{epoch_,r.token,now_ns(),r.operation,ok})) protect();
}
void AsyncLeafOwner::output(std::uint64_t now) {
    OwnerActuation out; out.epoch=epoch_; out.source_ns=now;
    if(leaf_==transport::Leaf::Steering) out.steering=std::get<vecu::SteeringActuator>(actor_).output();
    if(leaf_==transport::Leaf::Brake) out.brake=std::get<vecu::BrakeActuator>(actor_).output();
    if(leaf_==transport::Leaf::Drive) out.drive=std::get<vecu::DriveController>(actor_).output();
    if(leaf_==transport::Leaf::Power) out.coils=std::get<vecu::PowerController>(actor_).output().coils;
    output_.publish(out);
}
void AsyncLeafOwner::runnable(const OwnerSensors& s,std::uint64_t now) {
    if(leaf_==transport::Leaf::Steering) {
        auto& actor=std::get<vecu::SteeringActuator>(actor_); if(actor.prepare(now)) { if(const auto f=actor.complete(s.angle,now)) publish(*f); }
    } else if(leaf_==transport::Leaf::Brake) {
        auto& actor=std::get<vecu::BrakeActuator>(actor_); if(actor.prepare(now)) { if(const auto f=actor.complete(s.pressure,now)) publish(*f); }
    } else if(leaf_==transport::Leaf::Drive) {
        auto& actor=std::get<vecu::DriveController>(actor_); actor.observe_local(s.drive,now);
        if(actor.prepare(now)) { if(const auto f=actor.complete(s.torque,now)) publish(*f); }
    } else if(leaf_==transport::Leaf::Bms) {
        auto& actor=std::get<vecu::BmsController>(actor_);
        if(const auto m=actor.tick(s.battery,now)) { if(const auto f=can::encode_bms_frame(*m,bms_tx_)) publish(*f); }
        bms_gate_.publish(actor.power_gate());
    } else if(leaf_==transport::Leaf::Power) {
        auto& actor=std::get<vecu::PowerController>(actor_); const auto gate=bms_gate_.read();
        if(const auto m=actor.tick(s.power,gate?*gate:std::nullopt,now)) { if(const auto f=can::encode_bms_frame(*m,power_tx_)) publish(*f); }
    }
    const auto completed=now_ns(); const bool late=execution_deadline_ && completed>body_deadline_;
    if(execution_deadline_ && input_events_.size()<input_events_.capacity()) input_events_.push_back({completed,"control-completed",static_cast<std::size_t>(leaf_)+2,epoch_,body_release_,body_deadline_,now,late?1:0});
    if(faulted() || late) protect(); else output(now); // no late normal actuation publication
}
void AsyncLeafOwner::service() noexcept {
    try { service_impl(); } catch(...) { protect(); }
}
void AsyncLeafOwner::service_impl() {
    if(epoch_==0) return;
    // Ready ACK guarantees old work is quiescent. Keep the session observer
    // running, but never advance an old actor across the agreed INIT boundary.
    if(prepared_epoch_>epoch_) return;
    const auto ingress_now=now_ns();
    if(command_expiry_ns_ && ingress_now>=command_expiry_ns_ && !expiry_reported_) {
        expiry_reported_=true;
        if(input_events_.size()<input_events_.capacity()) input_events_.push_back({ingress_now,"command-expired",static_cast<std::size_t>(leaf_)+2,epoch_,command_source_ns_,command_expiry_ns_,command_expiry_ns_,0});
        protect(); // A fresh packet arriving after expiry cannot heal this epoch.
    }
    if(link_.failed() || link_.protection.pending(epoch_)) protect();
    for(std::size_t i=0;i<transport::kBudget;++i) { const auto r=link_.work.pop(); if(!r) break; handle(*r); }
    const auto s=sensors_.read(); const auto now=now_ns(); const auto period=leaf_==transport::Leaf::Bms?20000000ULL:10000000ULL;
    if(now<last_body_) { protect(); return; }
    if(now<next_body_) return;
    // During fresh INIT, wait for acquisitions/dependencies after enable. Once
    // running, missing/stale sensors reach the actual controller's own monitor.
    if(!started_ && (!s || s->source_ns<enable_ || !s->power || s->power->input_time_ns<enable_ ||
        !s->battery.electrical || s->battery.electrical->input_time_ns<enable_)) {
        if(now-enable_>30000000) protect();
        return;
    }
    started_=true; last_body_=now; next_body_=enable_+((now-enable_)/period+1)*period;
    body_release_=next_body_-period; body_deadline_=body_release_+(leaf_==transport::Leaf::Bms?8000000ULL:5000000ULL);
    if(execution_deadline_ && now>=body_deadline_) {
        if(input_events_.size()<input_events_.capacity()) input_events_.push_back({now,"control-late-start",static_cast<std::size_t>(leaf_)+2,epoch_,body_release_,body_deadline_,now,1});
        protect(); return;
    }
    runnable(s.value_or(OwnerSensors{}),now);
}
}  // namespace stratadrive::simulation
