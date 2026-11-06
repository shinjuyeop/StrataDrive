#include "control_diagnostics.hpp"
#include <algorithm>
#include <cmath>
#include <limits>

namespace stratadrive::diagnostics {
namespace {
std::uint32_t value(Component v) { return static_cast<std::uint32_t>(v); }
Key key(Code c,Component component,Monitor monitor,Subject subject) {
    return {c,value(component),static_cast<std::uint32_t>(monitor),static_cast<std::uint32_t>(subject)};
}
Code speed_code(central::SpeedRequestFault f) {
    using F=central::SpeedRequestFault;
    switch(f) {
    case F::Feedback: case F::Source: return Code::SpeedInput;
    case F::Session: case F::Controller: case F::Sequence: case F::PropulsionSelection: return Code::CentralControl;
    default: return Code::None;
    }
}
std::uint32_t speed_reason(central::SpeedRequestFault f,central::SpeedPIReason p) {
    using F=central::SpeedRequestFault; using P=central::SpeedPIReason;
    std::uint32_t primary=0,detail=0;
    switch(f) {
    case F::None: break; case F::Session: primary=1; break; case F::Permission: primary=2; break;
    case F::Feedback: primary=3; break; case F::Source: primary=4; break; case F::Controller: primary=5; break;
    case F::Sequence: primary=6; break; case F::PropulsionSelection: primary=7; break;
    }
    switch(p) {
    case P::Normal: break; case P::Uninitialized: detail=1; break; case P::Latched: detail=2; break;
    case P::SampleTime: detail=3; break; case P::Permission: detail=4; break; case P::Target: detail=5; break;
    case P::InvalidSpeed: detail=6; break; case P::Epoch: detail=7; break; case P::SourceAge: detail=8; break; case P::Identity: detail=9; break;
    }
    return (primary<<8)|detail;
}
Code stop_code(central::NormalStopFault f) {
    using F=central::NormalStopFault;
    switch(f) {
    case F::None: case F::UpstreamProtection: return Code::None;
    case F::ClockError: return Code::Clock; case F::ControlDeadline: return Code::Deadline;
    case F::RequestLost: return Code::StopRequest;
    case F::FeedbackUnavailable: case F::StopEvidenceLost: return Code::StopEvidence;
    case F::HandoffExpired: return Code::Handoff; case F::ShutdownTimeout: return Code::ShutdownTimeout;
    case F::BrakingTimeout: return Code::BrakingTimeout;
    case F::SequenceExhausted: return Code::CentralControl;
    }
    return Code::None;
}
std::uint32_t stop_reason(central::NormalStopFault f) {
    using F=central::NormalStopFault;
    switch(f) {
    case F::None: return 0; case F::ClockError: return 1; case F::ControlDeadline: return 2; case F::RequestLost: return 3;
    case F::FeedbackUnavailable: return 4; case F::StopEvidenceLost: return 5; case F::HandoffExpired: return 6;
    case F::ShutdownTimeout: return 7; case F::BrakingTimeout: return 8; case F::SequenceExhausted: return 9;
    case F::UpstreamProtection: return 10;
    }
    return 0;
}
std::uint32_t coordinator_reason(central::CoordinatorFault f) {
    using F=central::CoordinatorFault;
    switch(f) {
    case F::None: return 0; case F::ClockError: return 1; case F::ControlDeadline: return 2; case F::SessionMismatch: return 3;
    case F::Management: return 4; case F::Allocation: return 5; case F::Stop: return 6; case F::RequestDelivery: return 7;
    case F::Arm: return 8; case F::PowerDelivery: return 9; case F::CommandDelivery: return 10;
    case F::Handoff: return 11; case F::LocalProtection: return 12;
    }
    return 0;
}
bool has_root(const Event& e) { return e.id.sequence!=0; }
bool same_input(const can::DriveMessage& a,const can::DriveMessage& b) {
    return a.kind==b.kind && a.epoch==b.epoch && a.sequence==b.sequence && a.source_time_ns==b.source_time_ns &&
        a.origin==b.origin && a.local_state==b.local_state && a.torque_nm==b.torque_nm && a.wheel_speed && b.wheel_speed &&
        a.wheel_speed->source_time_ns==b.wheel_speed->source_time_ns && a.wheel_speed->value_rad_s==b.wheel_speed->value_rad_s;
}
bool same_request(const central::VehicleRequest& a,const central::VehicleRequest& b) {
    return a.epoch==b.epoch && a.sequence==b.sequence && a.source_time_ns==b.source_time_ns && a.expires_at_ns==b.expires_at_ns &&
        a.acceleration_mps2==b.acceleration_mps2 && a.curvature_inv_m==b.curvature_inv_m && a.braking_demand==b.braking_demand && a.standstill_hold==b.standstill_hold;
}
} // namespace
ControlDiagnostics::ControlDiagnostics(EventQueue& queue,ControlContext context,std::uint64_t first)
    :publisher_(queue,context,first,"control diagnostics context",1) {}
Event ControlDiagnostics::base(std::uint64_t now) const noexcept {
    Event e; e.id={capture_context().run,capture_context().producer,0}; e.session=session_; e.session_enable=stamp(enable_);
    e.profile=capture_context().profile; e.requirements=1; // bit0 = SYS-DIAG-001, interfaces bit0 = IF-FAULT-EVENT
    e.interfaces=1; e.times[static_cast<std::size_t>(Time::Observed)]=stamp(now,now>=enable_ && now!=std::numeric_limits<std::uint64_t>::max()); return e;
}
bool ControlDiagnostics::start_session(std::uint32_t epoch,std::uint64_t enable,bool publish_context) noexcept {
    if(!epoch || epoch<=session_.epoch || (session_.epoch && enable<enable_)) return false;
    session_={capture_context().run,epoch}; enable_=enable; speed_seen_=supervised_seen_=coordinator_seen_=response_seen_=false;
    stop_seen_={}; phase_seen_={}; protection_seen_={}; root_={};
    if(!publish_context) return healthy();
    auto e=base(enable); e.kind=Kind::Session; return publish(e).sequence!=0 && healthy();
}
void ControlDiagnostics::speed(const central::SpeedRequest& c,const std::optional<central::VehicleRequest>& command,std::uint64_t now) noexcept {
    const auto& observation=c.fault_observation();
    if(speed_seen_ || !observation || observation->epoch!=session_.epoch || observation->enable_ns!=enable_) return;
    speed_seen_=true; const auto& o=*observation; auto e=base(now);
    const auto code=speed_code(o.fault); e.key=key(code,Component::Speed,Monitor::Speed,Subject::Wheel);
    e.native_reason=speed_reason(o.fault,o.controller_reason); e.kind=code==Code::None?Kind::Observation:Kind::Fault;
    e.cause_unknown=code==Code::None; e.latch=Latch::Set; e.state_after=1;
    e.times[static_cast<std::size_t>(Time::Detected)]=stamp(o.detected_ns,o.detected_ns>=enable_ && o.detected_ns!=std::numeric_limits<std::uint64_t>::max());
    if(o.input && o.input->wheel_speed) {
        const auto source=o.input->wheel_speed->source_time_ns;
        e.source={o.input->epoch!=0,value(Component::DriveWheel),source,o.input->epoch,
            stamp(source,source>=enable_ && source<=o.detected_ns && o.input->epoch==session_.epoch),{}};
        if(std::isfinite(o.input->wheel_speed->value_rad_s)) e.measured=o.input->wheel_speed->value_rad_s;
    }
    if(command) e.command={true,value(Component::Speed),command->sequence,command->epoch,stamp(command->source_time_ns),stamp(command->expires_at_ns)};
    const auto id=publish(e); e.id=id;
    if(e.kind==Kind::Fault) e.occurrence={session_.run,capture_context().producer,session_.epoch,e.key.monitor,id.sequence};
    if(code==Code::SpeedInput || code==Code::CentralControl) { speed_recovery_target_=e; speed_recovered_=false; }
    if(!has_root(root_)) root_=e;
}
void ControlDiagnostics::stop(const central::NormalStop& c,std::uint64_t now) noexcept {
    const auto& phases=c.phase_observations();
    for(std::size_t i=0;i<phases.size();++i) if(!phase_seen_[i] && phases[i] && phases[i]->epoch==session_.epoch && phases[i]->enable_ns==enable_) {
        phase_seen_[i]=true; const auto& o=*phases[i]; auto e=base(now);
        e.key=key(Code::None,Component::Stop,Monitor::Stop,Subject::StopCycle);
        e.state_before=static_cast<std::uint32_t>(o.before); e.state_after=static_cast<std::uint32_t>(o.after);
        e.times[static_cast<std::size_t>(Time::Observed)]=stamp(o.observed_ns);
        if(o.request) { const auto& p=o.request->identity; e.command={true,value(Component::Stop),p.sequence,p.epoch,stamp(p.source_time_ns),stamp(p.expires_at_ns)}; }
        if(o.lease) e.stop_lease={true,value(Component::Stop),o.lease->sequence,o.lease->epoch,stamp(o.lease->source_time_ns),stamp(o.lease->expires_at_ns)};
        if(o.after==central::NormalStopState::PowerDown) e.times[static_cast<std::size_t>(Time::Acknowledged)]=stamp(o.observed_ns);
        const auto id=publish(e);
        if(o.after==central::NormalStopState::HandoffPending || o.after==central::NormalStopState::Complete) actuals(o,e,id,now);
    }
    const auto& faults=c.fault_observations();
    for(std::size_t i=0;i<faults.size();++i) if(!stop_seen_[i] && faults[i] && faults[i]->epoch==session_.epoch && faults[i]->enable_ns==enable_) {
        stop_seen_[i]=true; const auto& o=*faults[i]; auto e=base(now); const auto code=stop_code(o.fault);
        e.key=key(code,Component::Stop,Monitor::Stop,code==Code::Handoff?Subject::Handoff:Subject::StopCycle);
        e.kind=code==Code::None?Kind::Observation:Kind::Fault; e.native_reason=stop_reason(o.fault);
        e.cause_unknown=code==Code::None; e.latch=Latch::Set;
        e.state_before=static_cast<std::uint32_t>(o.before); e.state_after=static_cast<std::uint32_t>(o.after);
        e.times[static_cast<std::size_t>(Time::Detected)]=stamp(o.observed_ns,o.fault!=central::NormalStopFault::ClockError);
        if(o.fault==central::NormalStopFault::BrakingTimeout || o.fault==central::NormalStopFault::ShutdownTimeout) {
            const auto budget=o.fault==central::NormalStopFault::BrakingTimeout?o.config.braking_timeout_ns:o.config.shutdown_timeout_ns;
            e.times[static_cast<std::size_t>(Time::Violation)]=stamp(o.phase_start_ns+budget);
        }
        if(o.request) { const auto& p=o.request->identity; e.command={true,value(Component::Stop),p.sequence,p.epoch,stamp(p.source_time_ns),stamp(p.expires_at_ns)}; }
        if(o.lease) e.stop_lease={true,value(Component::Stop),o.lease->sequence,o.lease->epoch,stamp(o.lease->source_time_ns),stamp(o.lease->expires_at_ns)};
        if(has_root(root_)) e.related=root_.id;
        const auto id=publish(e); e.id=id;
        if(e.kind==Kind::Fault) e.occurrence={session_.run,capture_context().producer,session_.epoch,e.key.monitor,id.sequence};
        if(e.kind==Kind::Fault) remember_stop_recovery(e,o.config);
        if(!has_root(root_)) root_=e;
    }
}
void ControlDiagnostics::remember_stop_recovery(const Event& event,const central::NormalStopConfig& config) noexcept {
    switch(event.key.code) {
    case Code::BrakingTimeout: case Code::Handoff: case Code::StopEvidence:
    case Code::ShutdownTimeout: case Code::StopRequest: case Code::CentralControl: case Code::Deadline: break;
    default: return; // Clock recovery requires separate trusted clock qualification.
    }
    for(auto& target:stop_recovery_targets_) if(target && target->fault.key==event.key) {
        target=StopRecovery{event,config,false}; return;
    }
    for(auto& target:stop_recovery_targets_) if(!target) {target=StopRecovery{event,config,false}; return;}
    publisher_.incomplete(); // Bounded history cannot silently evict an unresolved occurrence.
}
void ControlDiagnostics::stop_recovery(const central::VehicleCoordinator& c,std::uint64_t now) noexcept {
    const auto decision=c.decision();const auto& phases=c.normal_stop().phase_observations();
    if(!healthy() || decision.fault!=central::CoordinatorFault::None || decision.normal_armed ||
       !decision.stopping || decision.stop.fault!=central::NormalStopFault::None ||
       decision.stop.state!=central::NormalStopState::Complete || decision.management.normal_allowed ||
       decision.management.state!=central::VehicleManagementState::Stopped || !decision.management.power_off_confirmed) return;
    std::uint64_t previous=enable_;
    for(const auto& phase:phases) {
        if(!phase || phase->epoch!=session_.epoch || phase->enable_ns!=enable_ ||
           phase->observed_ns<previous || phase->observed_ns>now) return;
        previous=phase->observed_ns;
    }
    const auto& complete=*phases[3];const auto& handoff=*phases[1];const auto& ack=*phases[2];
    if(now-previous>30000000 || now==std::numeric_limits<std::uint64_t>::max() ||
       !handoff.lease || !ack.lease || !same_stop_lease(*handoff.lease,*ack.lease) ||
       ack.observed_ns>=ack.lease->expires_at_ns || ack.lease->epoch!=session_.epoch ||
       handoff.observed_ns-phases[0]->observed_ns>=complete.config.braking_timeout_ns ||
       complete.observed_ns-ack.observed_ns>=complete.config.shutdown_timeout_ns ||
       !complete.evidence.drive || !complete.evidence.drive->wheel_speed ||
       !complete.evidence.brake || !complete.evidence.power) return;
    const auto& cfg=complete.config;
    for(auto& target:stop_recovery_targets_) {
        if(!target || target->passed || target->fault.session.epoch>=session_.epoch || target->fault.profile!=capture_context().profile) continue;
        const auto& old=target->config;
        if(old.deceleration_mps2!=cfg.deceleration_mps2 || old.confirmation_ns!=cfg.confirmation_ns ||
           old.braking_timeout_ns!=cfg.braking_timeout_ns || old.shutdown_timeout_ns!=cfg.shutdown_timeout_ns ||
           old.minimum_tick_interval_ns!=cfg.minimum_tick_interval_ns) continue;
        auto e=base(now);e.kind=Kind::Observation;e.key=target->fault.key;e.occurrence=target->fault.occurrence;
        e.related=target->fault.id;e.latch=Latch::Clear;
        switch(e.key.code) {
        case Code::BrakingTimeout:e.proof=Proof::Stop;break;
        case Code::Handoff:e.proof=Proof::Handoff;break;
        case Code::StopEvidence:e.proof=Proof::Hold;break;
        case Code::ShutdownTimeout:e.proof=Proof::Shutdown;break;
        case Code::StopRequest:e.proof=Proof::Input;break;
        default:e.proof=Proof::Control;break;
        }
        e.state_after=static_cast<std::uint32_t>(complete.after);
        e.stop_lease={true,value(Component::Stop),ack.lease->sequence,ack.lease->epoch,stamp(ack.lease->source_time_ns),stamp(ack.lease->expires_at_ns)};
        e.times[static_cast<std::size_t>(Time::Acknowledged)]=stamp(ack.observed_ns);
        e.times[static_cast<std::size_t>(Time::Actual)]=stamp(complete.evidence.drive->wheel_speed->source_time_ns);
        e.measured=complete.evidence.drive->wheel_speed->value_rad_s;
        const auto proof=publish(e);actuals(complete,e,proof,now);
        if(!healthy()) return;
        e.kind=Kind::Passed;e.proof_event=proof;publish(e);target->passed=true;
    }
}
void ControlDiagnostics::actuals(const central::NormalStopObservation& o,const Event& phase,EventId parent,std::uint64_t now) noexcept {
    const auto emit=[&](Component component,Subject subject,const can::ActuatorMetadata& metadata,std::uint64_t source,double measured) {
        if(!std::isfinite(measured)) { publisher_.incomplete(); return; }
        auto e=phase; e.kind=Kind::Actual; e.related=parent;
        if(e.key.code==Code::None) e.key.subject=static_cast<std::uint32_t>(subject);
        e.source={true,value(component),subject==Subject::Wheel?source:metadata.sequence,metadata.epoch,stamp(source),{}};
        e.measured=measured; e.times[static_cast<std::size_t>(Time::Actual)]=stamp(source);
        e.times[static_cast<std::size_t>(Time::Observed)]=stamp(o.evidence.observed_ns);
        // now is collector observation, not substituted for original acquisition.
        (void)now; publish(e);
    };
    if(o.evidence.drive) {
        const auto& d=*o.evidence.drive;
        if(d.wheel_speed) emit(Component::DriveWheel,Subject::Wheel,d,d.wheel_speed->source_time_ns,d.wheel_speed->value_rad_s);
        if(d.torque_nm) emit(Component::Drive,Subject::Torque,d,d.source_time_ns,*d.torque_nm);
    }
    if(o.evidence.brake && o.evidence.brake->pressure_pa) {
        const auto& b=*o.evidence.brake; emit(Component::Brake,Subject::Pressure,b,b.source_time_ns,*b.pressure_pa);
    }
    if(o.after==central::NormalStopState::Complete && o.evidence.power) {
        const auto& p=o.evidence.power->message; const auto* status=std::get_if<can::BmsPowerStatus>(&p.content);
        if(status && status->hv_bus_voltage_v) emit(Component::Power,Subject::Power,p,p.source_time_ns,*status->hv_bus_voltage_v);
    }
}
void ControlDiagnostics::coordinator(const central::VehicleCoordinator& c,std::uint64_t now) noexcept {
    const auto& fault=c.fault_observation();
    if(!coordinator_seen_ && fault && fault->epoch==session_.epoch && fault->enable_ns==enable_) {
        coordinator_seen_=true; const auto& o=*fault; auto e=base(now);
        e.native_reason=coordinator_reason(o.fault); bool handoff=o.fault==central::CoordinatorFault::Handoff;
        const bool transport=o.transport && o.transport->session.epoch==session_.epoch && o.transport->session.enable_ns==enable_ && o.transport->fault!=central::AsyncTransportFault::None;
        const bool allocation=o.fault==central::CoordinatorFault::Allocation && o.allocation_fault!=central::AllocationFault::None && o.allocation_fault!=central::AllocationFault::ContinuityLost;
        auto code=handoff?Code::Handoff:Code::None;
        if(allocation){
            code=o.allocation_fault==central::AllocationFault::ClockError?Code::Clock:
                 o.allocation_fault==central::AllocationFault::ControlDeadline?Code::Deadline:Code::CentralControl;
            // Explicit native reason namespace: bit16 marks the allocator; the
            // low16 bits retain AllocationFault from BEFORE protection changes.
            e.native_reason=0x10000U|static_cast<std::uint32_t>(o.allocation_fault);
            if(o.vehicle){const auto& r=*o.vehicle;e.command={true,value(Component::Coordinator),r.sequence,r.epoch,stamp(r.source_time_ns),stamp(r.expires_at_ns)};}
        }
        if(transport){
            const auto& t=*o.transport;handoff=t.stop_handoff;
            code=t.fault==central::AsyncTransportFault::Clock?Code::Clock:handoff?Code::Handoff:Code::CentralControl;
            e.native_reason=0x20000U|static_cast<std::uint32_t>(t.fault);
            if(t.token)e.command={true,value(Component::Coordinator),t.token,t.session.epoch,stamp(t.sent_ns,code!=Code::Clock),stamp(t.deadline_ns,code!=Code::Clock)};
            if(t.fault==central::AsyncTransportFault::ResultTimeout)e.times[static_cast<std::size_t>(Time::Violation)]=stamp(t.deadline_ns);
        }
        const bool confirmed=code!=Code::None;
        e.kind=confirmed?Kind::Fault:Kind::Observation;
        e.key=key(code,Component::Coordinator,Monitor::Coordinator,handoff?Subject::Handoff:allocation?Subject::Torque:Subject::Protection);
        e.latch=Latch::Set; e.times[static_cast<std::size_t>(Time::Detected)]=stamp(transport?o.transport->detected_ns:o.detected_ns,o.fault!=central::CoordinatorFault::ClockError && code!=Code::Clock);
        e.related=root_.id; e.cause_unknown=!confirmed && !has_root(root_);
        e.unmapped=!confirmed && !has_root(root_) && o.fault!=central::CoordinatorFault::LocalProtection;
        if(o.handoff) { const auto& l=o.handoff->lease; e.stop_lease={true,value(Component::Stop),l.sequence,l.epoch,stamp(l.source_time_ns),stamp(l.expires_at_ns)}; }
        const auto id=publish(e); e.id=id;
        if(confirmed) e.occurrence={session_.run,capture_context().producer,session_.epoch,e.key.monitor,id.sequence};
        if(e.kind==Kind::Fault) remember_stop_recovery(e,c.normal_stop().configuration());
        if(!has_root(root_)) root_=e;
    }
    const auto& selections=c.protection_observations();
    for(std::size_t i=0;i<selections.size();++i) if(!protection_seen_[i] && selections[i] && selections[i]->epoch==session_.epoch) {
        protection_seen_[i]=true; const auto& o=*selections[i]; auto e=has_root(root_)?root_:base(now);
        e.related=root_.id; e.kind=o.accepted?Kind::ProtectionAck:Kind::Observation; e.cause_unknown=!has_root(root_);
        e.source={true,value(Component::Coordinator),o.observed_ns,o.epoch,stamp(o.observed_ns,o.observed_ns>=o.requested_ns),{}};
        e.times[static_cast<std::size_t>(Time::Observed)]=stamp(o.observed_ns,o.observed_ns>=o.requested_ns);
        if(o.accepted) e.times[static_cast<std::size_t>(Time::Acknowledged)]=stamp(o.observed_ns,o.observed_ns>=o.requested_ns);
        if(i==0 && o.accepted) continue; // the accepted slot contains this same first attempt
        publish(e);
    }
}
void ControlDiagnostics::local_protection(Component actor,std::uint32_t roles,std::uint32_t epoch,std::uint64_t original,bool acknowledgement) noexcept {
    if(!session_.epoch || epoch!=session_.epoch || original<enable_) return;
    auto e=has_root(root_)?root_:base(original);
    e.kind=acknowledgement?Kind::ProtectionAck:Kind::ProtectionSelected;
    e.related=root_.id; e.cause_unknown=!has_root(root_);
    e.source={true,value(actor),original,epoch,stamp(original),{}}; e.received_roles=roles;
    e.times[static_cast<std::size_t>(acknowledgement?Time::Acknowledged:Time::Selected)]=stamp(original);
    e.times[static_cast<std::size_t>(Time::Observed)]=stamp(original);
    publish(e);
}
void ControlDiagnostics::observe_response(const central::NormalDriveReadinessInputs& in,std::uint64_t now) noexcept {
    if(response_seen_ || root_.kind!=Kind::Fault || !has_root(root_) || !root_.times[2].trusted ||
       in.epoch!=session_.epoch || in.session_enable_ns!=enable_ || !in.rear.drive_actual || !in.front.brake_actual) return;
    const auto& d=*in.rear.drive_actual; const auto& b=*in.front.brake_actual;
    if(d.epoch!=session_.epoch || b.epoch!=session_.epoch || !d.wheel_speed || !d.torque_nm || !b.pressure_pa ||
       d.kind!=can::DriveFrameKind::Actual || b.kind!=can::BrakeFrameKind::Actual ||
       d.origin!=can::ActuatorOrigin::LocalProtection || b.origin!=can::ActuatorOrigin::LocalProtection ||
       d.local_state!=can::ActuatorLocalState::FailSafe || b.local_state!=can::ActuatorLocalState::FailSafe ||
       !std::isfinite(*d.torque_nm) || !std::isfinite(*b.pressure_pa) || !std::isfinite(d.wheel_speed->value_rad_s) ||
       std::abs(*d.torque_nm)>1 || *b.pressure_pa<1000000 || *b.pressure_pa>1500000 ||
       d.wheel_speed->value_rad_s<0 || d.wheel_speed->value_rad_s>100) return;
    const auto low=std::min({d.source_time_ns,b.source_time_ns,d.wheel_speed->source_time_ns});
    const auto high=std::max({d.source_time_ns,b.source_time_ns,d.wheel_speed->source_time_ns});
    if(now<enable_ || low<enable_ || high>now || now-low>30000000 || high-low>20000000 || low<root_.times[2].ns) return;
    response_seen_=true;
    const auto emit=[&](Component actor,std::uint64_t sequence,std::uint64_t source,double measured) {
        auto e=root_; e.kind=Kind::Actual; e.related=root_.id;
        e.source={true,value(actor),sequence,session_.epoch,stamp(source),{}}; e.measured=measured;
        e.times[static_cast<std::size_t>(Time::Actual)]=stamp(source); e.times[static_cast<std::size_t>(Time::Observed)]=stamp(now);
        publish(e);
    };
    emit(Component::DriveWheel,d.wheel_speed->source_time_ns,d.wheel_speed->source_time_ns,d.wheel_speed->value_rad_s);
    emit(Component::Drive,d.sequence,d.source_time_ns,*d.torque_nm);
    emit(Component::Brake,b.sequence,b.source_time_ns,*b.pressure_pa);
}
void ControlDiagnostics::observe_speed_recovery(const central::SpeedRequest& speed_control,const central::VehicleCoordinator& c,
    const central::NormalDriveReadinessInputs& in,std::uint64_t now) noexcept {
    if(!healthy() || speed_recovered_ || !speed_recovery_target_ || session_.epoch<=speed_recovery_target_->session.epoch ||
       speed_recovery_target_->profile!=capture_context().profile || in.epoch!=session_.epoch || in.session_enable_ns!=enable_ ||
       speed_control.fault()!=central::SpeedRequestFault::None || speed_control.state().fault ||
       !speed_control.success_observation() || !c.last_vehicle_request() || !in.rear.drive_actual ||
       now<enable_ || now==std::numeric_limits<std::uint64_t>::max()) return;
    const auto& o=*speed_control.success_observation(); const auto d=c.decision();
    if(o.epoch!=session_.epoch || o.enable_ns!=enable_ || o.issued_ns>now || now-o.issued_ns>30000000 ||
       !speed_control.state().last_ns || *speed_control.state().last_ns!=o.issued_ns ||
       !same_request(o.request,*c.last_vehicle_request()) || o.request.expires_at_ns<=now ||
       !same_input(o.input,*in.rear.drive_actual) || !central::evaluate_normal_drive_readiness(in,now).ready() ||
       !d.normal_armed || d.stopping || d.fault!=central::CoordinatorFault::None ||
       !d.management.normal_allowed || d.management.fault!=central::VehicleManagementFault::None ||
       d.management.permission_support.expiry_ns<=now) return;
    auto e=base(now); e.kind=Kind::Actual; e.proof=speed_recovery_target_->key.code==Code::SpeedInput?Proof::Input:Proof::Control; e.key=speed_recovery_target_->key;
    e.occurrence=speed_recovery_target_->occurrence; e.related=speed_recovery_target_->id; e.latch=Latch::Clear;
    e.source={true,value(Component::DriveWheel),o.input.wheel_speed->source_time_ns,o.epoch,stamp(o.input.wheel_speed->source_time_ns),{}};
    e.command={true,value(Component::Speed),o.request.sequence,o.request.epoch,stamp(o.request.source_time_ns),stamp(o.request.expires_at_ns)};
    e.times[static_cast<std::size_t>(Time::Actual)]=stamp(o.input.wheel_speed->source_time_ns);
    e.measured=o.input.wheel_speed->value_rad_s;
    const auto evidence=publish(e); e.kind=Kind::Passed; e.proof_event=evidence; publish(e);
    speed_recovered_=true;
}
std::optional<ServiceEvidence> ControlDiagnostics::speed_clear_evidence(const central::SpeedRequest& speed_control,
    const central::VehicleCoordinator& c,const central::NormalDriveReadinessInputs& in,
    const std::optional<can::DriveMessage>& input,std::uint64_t now) const noexcept {
    if(!speed_recovered_ || !speed_recovery_target_ || speed_control.fault()!=central::SpeedRequestFault::None ||
       speed_control.state().epoch!=session_.epoch) return std::nullopt;
    return stationary_evidence(c,in,input,now);
}
std::optional<ServiceEvidence> ControlDiagnostics::stop_clear_evidence(const central::VehicleCoordinator& c,
    const central::NormalDriveReadinessInputs& in,std::uint64_t now) const noexcept {
    if(std::none_of(stop_recovery_targets_.begin(),stop_recovery_targets_.end(),[](const auto& t){return t && t->passed;})) return std::nullopt;
    return stationary_evidence(c,in,in.rear.drive_actual,now);
}
std::optional<ServiceEvidence> ControlDiagnostics::stationary_evidence(const central::VehicleCoordinator& c,
    const central::NormalDriveReadinessInputs& in,const std::optional<can::DriveMessage>& input,std::uint64_t now) const noexcept {
    if(!healthy() || in.epoch!=session_.epoch || in.session_enable_ns!=enable_ ||
       !input || !in.rear.drive_actual || !same_input(*input,*in.rear.drive_actual) || !input->wheel_speed ||
       !in.front.brake_actual || !input->torque_nm || !in.front.brake_actual->pressure_pa || !in.rear.power_status ||
       now<enable_ || now==std::numeric_limits<std::uint64_t>::max() || !central::evaluate_vehicle_input_health(in,now).ready()) return std::nullopt;
    const auto d=c.decision(); const auto* power=std::get_if<can::BmsPowerStatus>(&in.rear.power_status->message.content);
    if(d.fault!=central::CoordinatorFault::None || d.normal_armed || !d.stopping || d.management.normal_allowed ||
       d.stop.fault!=central::NormalStopFault::None || d.stop.state!=central::NormalStopState::Complete ||
       d.management.state!=central::VehicleManagementState::Stopped || !d.management.power_off_confirmed ||
       !power || power->state!=can::BmsPowerState::Off || !power->positive_contactor_closed || !power->negative_contactor_closed || !power->precharge_contactor_closed ||
       *power->positive_contactor_closed || *power->negative_contactor_closed || *power->precharge_contactor_closed ||
       !power->hv_bus_voltage_v || !std::isfinite(*power->hv_bus_voltage_v) || *power->hv_bus_voltage_v<0 || *power->hv_bus_voltage_v>30 ||
       !std::isfinite(input->wheel_speed->value_rad_s) || input->wheel_speed->value_rad_s<0 || input->wheel_speed->value_rad_s>.01 ||
       !std::isfinite(*input->torque_nm) || std::abs(*input->torque_nm)>.1 ||
       !std::isfinite(*in.front.brake_actual->pressure_pa) || *in.front.brake_actual->pressure_pa<100000 || *in.front.brake_actual->pressure_pa>1500000 ||
       input->wheel_speed->source_time_ns<enable_ || input->wheel_speed->source_time_ns>now || now-input->wheel_speed->source_time_ns>30000000) return std::nullopt;
    const auto low=std::min({input->wheel_speed->source_time_ns,input->source_time_ns,in.front.brake_actual->source_time_ns});
    const auto high=std::max({input->wheel_speed->source_time_ns,input->source_time_ns,in.front.brake_actual->source_time_ns});
    if(low<enable_ || high>now || now-low>30000000 || high-low>20000000) return std::nullopt;
    return ServiceEvidence{stamp(now),stamp(enable_),stamp(input->wheel_speed->source_time_ns),stamp(input->source_time_ns),
        stamp(in.front.brake_actual->source_time_ns),input->wheel_speed->value_rad_s,*input->torque_nm,*in.front.brake_actual->pressure_pa,true,true};
}
void ControlDiagnostics::observe(const central::SupervisedSpeedRequest& control,const central::VehicleCoordinator& c,std::uint64_t now) noexcept {
    const auto& fault=control.fault_observation();
    if(!supervised_seen_ && fault && fault->epoch==session_.epoch && fault->enable_ns==enable_ &&
       fault->clock_instance==capture_context().clock_instance) {
        supervised_seen_=true;
        auto e=base(now);e.kind=Kind::Fault;e.key=key(Code::CentralControl,Component::Speed,Monitor::SupervisedSpeed,Subject::Protection);
        // Dictionary v1: high byte ProposalReason, low byte ReferenceFault.
        e.native_reason=(static_cast<std::uint32_t>(fault->reason)<<8)|static_cast<std::uint32_t>(fault->reference_fault);
        e.latch=Latch::Set;e.state_after=1;
        e.times[static_cast<std::size_t>(Time::Detected)]=stamp(fault->detected_ns,
            fault->detected_ns>=enable_ && fault->detected_ns<=now && fault->detected_ns!=std::numeric_limits<std::uint64_t>::max());
        if(c.last_vehicle_request()) {
            const auto& q=*c.last_vehicle_request();
            e.command={true,value(Component::Speed),q.sequence,q.epoch,stamp(q.source_time_ns),stamp(q.expires_at_ns)};
        }
        e.id=publish(e);e.occurrence={session_.run,capture_context().producer,session_.epoch,e.key.monitor,e.id.sequence};
        if(!has_root(root_))root_=e;
    }
    // The original PI/allocator monitors still report their own failures.
    observe(control.controller(),c,now);
}
void ControlDiagnostics::observe(const central::SpeedRequest& speed_control,const central::VehicleCoordinator& c,std::uint64_t now) noexcept {
    if(!session_.epoch) return;
    speed(speed_control,c.last_vehicle_request(),now); stop(c.normal_stop(),now); coordinator(c,now); stop_recovery(c,now);
}
void ControlDiagnostics::observe(const central::VehicleCoordinator& c,std::uint64_t now) noexcept {
    if(session_.epoch) {stop(c.normal_stop(),now);coordinator(c,now);stop_recovery(c,now);}
}
void ControlDiagnostics::observe(const central::SpeedRequest& c,std::uint64_t now) noexcept {
    if(session_.epoch) speed(c,std::nullopt,now);
}
void ControlDiagnostics::observe(const central::NormalStop& c,std::uint64_t now) noexcept {
    if(session_.epoch) stop(c,now);
}
} // namespace stratadrive::diagnostics
