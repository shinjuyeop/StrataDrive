#include "actuator_electrical.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace stratadrive::m7_external {
using namespace simulation;
namespace {constexpr Time ms=1000000;}
struct ActuatorElectrical::State {
    // Models are separate owners of physical response and electrical energy.
    // Exactly the M6 functional fixture parameters; no SimpleVehicle member.
    SteeringResponse angle{{-.3,.3,.1,1,50*ms,7}};
    BrakePressureResponse pressure{{1500000,200000,5000000,10000000,50*ms,7}};
    DriveSilPlant motor{vecu::DriveControllerConfig{}.response};
    EvPowerModel electrical{{},{180000000,400,.05,200000,20,25,100,.01,1,100000},{.002,50,.02,100,1000,500}};
    Time initial=0,last=0,current_safe_since=0;
    std::uint32_t sequence=0,maximum_application=0,brake_release=0,power_application=0;
    std::array<Time,5> applied{};
    std::array<std::uint32_t,5> applied_epoch{};
    power::CoilCommand coils{};
    bool power_watchdog=false;
    bool solver_work=false;
    Time last_work_frame=0;
    std::optional<SolverWork> work;
    State(Time start,std::uint32_t application):initial(start),last(start),maximum_application(application) {
        motor.begin(7,start);
        if(!start || !application || !angle.begin(start) || !pressure.begin(start) ||
           !electrical.initialize({7,start,.63,25},0))throw std::invalid_argument("M7 fixture initialization");
    }
};
ActuatorElectrical::ActuatorElectrical(Time start,std::uint32_t app,bool work)
    :ActuatorElectrical(start,app,work?PlantExecution::CoupledObservedWork:PlantExecution::Zoh) {}
ActuatorElectrical::ActuatorElectrical(Time start,std::uint32_t app,PlantExecution execution)
    :state_(std::make_unique<State>(start,app)),deferred_(execution==PlantExecution::DeferredObservedWork) {
    state_->solver_work=execution!=PlantExecution::Zoh;
}
ActuatorElectrical::~ActuatorElectrical()=default;
bool ActuatorElectrical::fail_electrical(const char* why) {
    if(!deferred_)return fail(why);
    if(electrical_error_.empty())electrical_error_=why;
    protection_latched_=true;
    if(sensors_)capture_electrical(*state_,*sensors_);
    return false;
}
Time ActuatorElectrical::last_success() const {return state_->last;}
power::CoilCommand ActuatorElectrical::applied_coils() const {return state_->coils;}
bool ActuatorElectrical::fail(const char* why) {if(error_.empty())error_=why;sensors_.reset();return false;}
Time ActuatorElectrical::electrical_time() const {return state_->electrical.diagnostic_state().identity.source_time_ns;}
double ActuatorElectrical::settled_work() const {return state_->electrical.diagnostic_state().mechanical_j;}
void ActuatorElectrical::commit_work_frame() {
    if(deferred_){fail_electrical("M7 deferred mode has no coupled commit");return;}
    checkpoint_.reset();
}
bool ActuatorElectrical::begin_work_frame(const SolverWork& work) {
    if(deferred_)return fail_electrical("M7 deferred mode requires complete settlement");
    if(!ok())return false;
    if(!state_->solver_work || checkpoint_ || state_->work || !work.valid() || work.begin!=electrical_time() ||
       (state_->last_work_frame && work.frame!=state_->last_work_frame+1))return fail("M7 solver work frame binding/completeness");
    checkpoint_=std::make_unique<State>(*state_);
    checkpoint_audit_=audit_;
    state_->work=work;
    return true;
}
void ActuatorElectrical::abort_work_frame() {
    if(deferred_){fail_electrical("M7 deferred response cannot be rolled back");return;}
    if(checkpoint_) {state_=std::move(checkpoint_);audit_=checkpoint_audit_;}
    fail("M7 solver work frame aborted");
}
bool ActuatorElectrical::settle(State& s,Time end,const power::CoilCommand& coils) {
    const auto begin=s.electrical.diagnostic_state().identity.source_time_ns;
    if(!s.work || begin<s.work->begin || end>s.work->end || end<=begin || end-begin>ms)
        return fail_electrical("M7 solver work coverage");
    const auto& w=*s.work;
    const auto& previous=s.electrical.power_state();
    const bool enabled=(previous.contactors.positive && previous.contactors.negative && previous.bus_voltage_v>=300) || w.torque!=0;
    // This is the physical applied setter witness at the original frame begin,
    // with the original CAN/wheel dependency retained. It is not restamped CAN.
    const battery::ModelIdentity applied{7,static_cast<std::uint32_t>(w.frame),w.begin};
    const auto sequence=s.electrical.diagnostic_state().identity.sequence;
    const battery::ModelIdentity environment{7,sequence,begin};
    const EvPowerInputs input{Wheel{w.torque,applied,w.oldest},w.wheel,
        battery::ModelMeasurement<EvElectricalEnvironment>{{.25,enabled},environment,begin}};
    const IntegratedMotorWork work{{7,sequence+1,end},begin,end,w.oldest,w.work(begin,end)};
    const auto result=s.electrical.step_integrated_motion({begin,end,input,coils},work);
    if(result.fault!=EvPowerFault::None)return fail_electrical("M7 integrated EV input/interval/energy rejection");
    return true;
}
void ActuatorElectrical::capture_electrical(State& s,OwnerSensors& measured) {
    if(deferred_ && !electrical_ok()) {
        measured.power.reset();measured.battery={};measured.drive.hv.reset();return;
    }
    measured.power=s.electrical.power_observation();measured.battery=s.electrical.battery_observation();
    const auto& power=s.electrical.power_state();
    const auto& id=s.electrical.diagnostic_state().identity;
    if(measured.power)measured.drive.hv=battery::ModelMeasurement<drive::HvFeedback>{{power.bus_voltage_v,
        power.contactors.positive && power.contactors.negative && power.bus_voltage_v>=300,false},
        id,measured.power->input_time_ns};
}
bool ActuatorElectrical::finish_work_frame(Time end) {
    if(deferred_)return fail_electrical("M7 deferred mode requires complete settlement");
    if(!ok() || !checkpoint_ || !state_->work || state_->work->end!=end) {abort_work_frame();return false;}
    auto next=std::make_unique<State>(*state_);
    const auto begin=next->electrical.diagnostic_state().identity.source_time_ns;
    const double before=next->electrical.diagnostic_state().mechanical_j;
    if(begin<end && !settle(*next,end,next->coils)) {abort_work_frame();return false;}
    if(begin>end) {abort_work_frame();return false;}
    const auto& energy=next->electrical.diagnostic_state();
    const auto& w=*next->work;
    audit_={begin,end,w.wheel.identity.source_time_ns,w.oldest,w.wheel.value,w.torque,
        energy.mechanical_j-before,energy.mechanical_j,next->electrical.battery_state().soc,energy.balance_error_j};
    const auto& battery=next->electrical.battery_state();
    audit_.motor_loss_j=energy.motor_loss_j;audit_.auxiliary_j=battery.auxiliary_j;audit_.ohmic_j=battery.ohmic_loss_j;
    audit_.capacitor_delta_j=energy.capacitor_j-energy.initial_capacitor_j;
    audit_.circuit_loss_j=energy.precharge_loss_j+energy.main_loss_j+energy.discharge_loss_j;
    audit_.chemical_j=battery.initial_energy_j-battery.energy_j;
    if(sensors_)capture_electrical(*next,*sensors_);
    next->last_work_frame=w.frame;next->work.reset();
    state_=std::move(next);
    return true;
}
bool ActuatorElectrical::advance_response(State& s,Time now,const std::optional<Wheel>& wheel,
    const std::array<std::optional<OwnerActuation>,5>& outputs,std::uint32_t released,bool protect,OwnerSensors& measured) {
    if(!s.motor.advance(now,false) || !s.angle.advance(now) || !s.pressure.advance(now))return fail("M7 actuator advance");
    measured.source_ns=now;
    measured.angle=s.angle.capture();measured.pressure=s.pressure.capture();measured.torque=s.motor.capture(now);
    measured.power=s.electrical.power_observation();measured.battery=s.electrical.battery_observation();
    measured.drive.wheel_speed=wheel;
    const auto& power=s.electrical.power_state();
    if(!measured.angle || !measured.pressure || !measured.torque || (!deferred_ && !measured.power))return fail("M7 acquisition unavailable");
    if(measured.power)measured.drive.hv=battery::ModelMeasurement<drive::HvFeedback>{{power.bus_voltage_v,
        power.contactors.positive && power.contactors.negative && power.bus_voltage_v>=300,false},
        {7,s.sequence,now},measured.power->input_time_ns};
    if(s.solver_work)capture_electrical(s,measured);

    for(unsigned i=0;i<5;++i) {
        const auto& out=outputs[i];
        if(!out)continue;
        const unsigned fields=unsigned(bool(out->steering))+unsigned(bool(out->brake))+unsigned(bool(out->drive))+unsigned(bool(out->coils));
        if(fields==0)continue; // BMS/no-actuation publication cannot renew an output watchdog
        if(fields!=1 || (i==0 && !out->steering) || (i==1 && !out->brake) ||
           (i==2 && !out->drive) || i==3 || (i==4 && !out->coils))return fail("M7 output role/type");
        if(out->source_ns<s.initial || out->source_ns>now || out->source_ns<s.applied[i])return fail("M7 output time");
        if(out->source_ns==s.applied[i]) {
            if(out->epoch!=s.applied_epoch[i])return fail("M7 cached output scope");
            continue;
        }
        if(out->epoch!=s.maximum_application)return fail("M7 output application binding");
        const bool stale=now-out->source_ns>30*ms;
        s.applied[i]=out->source_ns;
        s.applied_epoch[i]=out->epoch;
        if(protect && i<3)continue; // protection below has sole physical priority
        if(i==0 && !(stale || out->steering->mode==steering::ActuationMode::Hold?s.angle.hold(now):s.angle.set_target(out->steering->target_rad,now)))return fail("M7 steering output");
        if(i==1) {
            if(out->epoch>s.brake_release && released==out->epoch) {
                if(!s.pressure.begin(now))return fail("M7 pressure new release");
                s.brake_release=out->epoch;
            }
            if(out->brake->mode!=brake::ActuationMode::Protect && s.brake_release!=out->epoch)continue;
            const bool good=stale || out->brake->mode==brake::ActuationMode::Protect?
                s.pressure.request_protection(out->brake->target_pa,now):out->brake->mode==brake::ActuationMode::Hold?
                s.pressure.hold(now):s.pressure.set_target(out->brake->target_pa,now);
            if(!good)return fail("M7 brake output");
        }
        if(i==2) {
            auto application=*out->drive;application.issued_time_ns=now;
            if(stale){application.mode=drive::ActuationMode::Zero;application.target_nm=0;}
            if(!s.motor.apply(application))return fail("M7 Drive output");
        }
        if(i==4) {
            if(out->epoch>s.power_application && released==out->epoch){s.power_watchdog=false;s.current_safe_since=0;s.power_application=out->epoch;}
            s.coils=*out->coils;
        }
    }
    const auto expired=[&](unsigned i){return s.applied[i] && now-s.applied[i]>30*ms;};
    if(expired(0) && !s.angle.hold(now))return fail("M7 steering watchdog");
    if(expired(1) && !s.pressure.request_protection(1000000,now))return fail("M7 brake watchdog");
    if(expired(2) && !s.motor.apply({drive::ActuationMode::Zero,0,std::nullopt,now}))return fail("M7 Drive watchdog");
    if(expired(4))s.power_watchdog=true;
    if(s.power_watchdog) {
        if(!s.motor.apply({drive::ActuationMode::Zero,0,std::nullopt,now}))return fail("M7 power watchdog torque");
        const vecu::PowerControllerConfig config{};
        const bool current_fresh=measured.power && measured.power->pack_current_a &&
            std::isfinite(*measured.power->pack_current_a) && measured.power->identity.source_time_ns<=now &&
            measured.power->input_time_ns<=measured.power->identity.source_time_ns &&
            now-measured.power->identity.source_time_ns<=config.max_source_age_ns &&
            now-measured.power->input_time_ns<=config.max_dependency_age_ns;
        // Reuse the original Power sensor 50/70ms bounds, not the Drive 30ms
        // bound. A held electrical sample cannot satisfy dwell after expiry.
        if((!deferred_ || current_fresh) && std::abs(s.motor.actual_nm())<.1 &&
           std::abs(deferred_?*measured.power->pack_current_a:power.pack_current_a)<config.opening_current_max_a) {
            if(!s.current_safe_since)s.current_safe_since=now;
            if(now-s.current_safe_since>=vecu::PowerControllerConfig{}.current_dwell_ns)s.coils={{false,false,false},true};
        } else s.current_safe_since=0;
    }
    if(protect && (!s.angle.hold(now) || !s.pressure.request_protection(1000000,now) ||
                  !s.motor.apply({drive::ActuationMode::Zero,0,std::nullopt,now})))return fail("M7 protection");
    s.last=now;++s.sequence;
    return true;
}
bool ActuatorElectrical::step(Time now,const std::optional<Wheel>& wheel,
    const std::array<std::optional<OwnerActuation>,5>& outputs,std::uint32_t released,bool protect) {
    if(deferred_)return fail_electrical("M7 deferred mode cannot use coupled step");
    if(!ok())return false;
    if(now<=state_->last || now-state_->last>ms)return fail("M7 physical interval must be (0,1ms]");
    if(!wheel || !std::isfinite(wheel->value) || wheel->value<0 || wheel->value>100)return fail("M7 wheel unavailable/value");
    // Candidate actuator, circuit, battery, output cursors and observations all
    // commit once. A rejected energy or output step leaves physical state intact.
    auto next=std::make_unique<State>(*state_);
    auto& s=*next;
    if(s.sequence==UINT32_MAX)return fail("M7 physical sequence exhausted");
    s.maximum_application=std::max(s.maximum_application,released);
    const battery::ModelIdentity id{7,s.sequence,s.last};
    const double torque=s.motor.actual_nm();
    const auto& previous=s.electrical.power_state();
    const bool enabled=(previous.contactors.positive && previous.contactors.negative && previous.bus_voltage_v>=300) || std::abs(torque)>1e-9;
    const EvPowerInputs input{Wheel{torque,id,s.last},wheel,
        battery::ModelMeasurement<EvElectricalEnvironment>{{.25,enabled},id,s.last}};
    const auto energy_begin=s.electrical.diagnostic_state().identity.source_time_ns;
    if(s.solver_work) {
        if(!settle(s,now,s.coils))return false;
    } else {
        const auto result=s.electrical.step({s.last,now,input,s.coils});
        if(result.fault!=EvPowerFault::None)return fail("M7 EV input/interval/energy rejection");
    }
    OwnerSensors measured;
    if(!advance_response(s,now,wheel,outputs,released,protect,measured))return false;
    const auto& energy=s.electrical.diagnostic_state();
    const auto& energy_wheel=s.solver_work?s.work->wheel:*wheel;
    const ElectricalAudit audit{energy_begin,now,energy_wheel.identity.source_time_ns,
        s.solver_work?s.work->oldest:wheel->input_time_ns,energy_wheel.value,s.solver_work?s.work->torque:torque,
        energy.mechanical_j-state_->electrical.diagnostic_state().mechanical_j,energy.mechanical_j,
        s.electrical.battery_state().soc,energy.balance_error_j};
    state_=std::move(next);sensors_=measured;audit_=audit;
    return true;
}
bool ActuatorElectrical::advance_actuators(Time now,const std::optional<Wheel>& wheel,
    const std::array<std::optional<OwnerActuation>,5>& outputs,std::uint32_t released,bool protect) {
    if(!deferred_)return fail("M7 independent response requires deferred work mode");
    if(!actuators_ok())return false;
    if(now<=state_->last || now-state_->last>ms)return fail("M7 response interval must be (0,1ms]");
    if(state_->sequence==UINT32_MAX)return fail("M7 physical sequence exhausted");
    // A missing sensor does not stop the physical response. Present invalid
    // values are rejected; no abs/clamp, invented wheel, or acquisition restamp.
    if(wheel && (!std::isfinite(wheel->value) || wheel->value<0 || wheel->value>100 ||
       wheel->identity.epoch!=7 || wheel->identity.source_time_ns>now ||
       wheel->input_time_ns<state_->initial || wheel->input_time_ns>wheel->identity.source_time_ns))
        return fail("M7 deferred wheel identity/value");
    if(wheel && last_wheel_) {
        const auto& old=*last_wheel_;
        const bool same=wheel->identity.sequence==old.identity.sequence &&
                        wheel->identity.source_time_ns==old.identity.source_time_ns;
        if(same ? (wheel->value!=old.value || wheel->input_time_ns!=old.input_time_ns) :
           (wheel->identity.sequence<=old.identity.sequence || wheel->identity.source_time_ns<=old.identity.source_time_ns))
            return fail("M7 deferred wheel mutation/regression");
    }
    if(history_count_==history_.size())fail_electrical("M7 applied coil history overflow");
    protection_latched_=protection_latched_ || protect;
    auto next=std::make_unique<State>(*state_);
    next->maximum_application=std::max(next->maximum_application,released);
    OwnerSensors measured;
    const std::array<std::optional<OwnerActuation>,5> withheld{};
    // An electrical fault cannot authorize fresh normal output or contactor
    // changes. Existing output watchdogs remain, without stale-current dwell.
    if(!advance_response(*next,now,wheel,electrical_ok()?outputs:withheld,released,
                         protection_latched_,measured))return false;
    if(electrical_ok()) {
        const auto index=(history_head_+history_count_)%history_.size();
        history_[index]={state_->last,now,state_->coils};++history_count_;
    }
    state_=std::move(next);sensors_=measured;if(wheel)last_wheel_=wheel;
    return true;
}
bool ActuatorElectrical::settle_observed_frame(const SolverWork& work) {
    if(!deferred_)return fail("M7 deferred settlement requires independent mode");
    if(!ok())return false;
    if(!work.valid() || Time(work.wheel.identity.sequence)+1!=work.frame ||
       work.begin!=electrical_time() || work.end>state_->last ||
       (state_->last_work_frame && work.frame!=state_->last_work_frame+1))
        return fail_electrical("M7 deferred work identity/coverage");
    auto candidate=std::make_unique<State>(*state_);
    candidate->work=work;
    const auto before=candidate->electrical.diagnostic_state().mechanical_j;
    auto cursor=work.begin;
    for(std::size_t i=0;i<history_count_ && cursor<work.end;++i) {
        const auto& interval=history_[(history_head_+i)%history_.size()];
        if(interval.end<=cursor)continue;
        if(interval.begin!=cursor)return fail_electrical("M7 deferred coil history gap");
        const auto end=std::min(interval.end,work.end);
        if(!settle(*candidate,end,interval.coils))return false;
        cursor=end;
    }
    if(cursor!=work.end)return fail_electrical("M7 deferred coil history incomplete");
    const auto& energy=candidate->electrical.diagnostic_state();
    const auto& battery=candidate->electrical.battery_state();
    ElectricalAudit audit{work.begin,work.end,work.wheel.identity.source_time_ns,work.oldest,
        work.wheel.value,work.torque,energy.mechanical_j-before,energy.mechanical_j,
        battery.soc,energy.balance_error_j};
    audit.motor_loss_j=energy.motor_loss_j;audit.auxiliary_j=battery.auxiliary_j;audit.ohmic_j=battery.ohmic_loss_j;
    audit.capacitor_delta_j=energy.capacitor_j-energy.initial_capacitor_j;
    audit.circuit_loss_j=energy.precharge_loss_j+energy.main_loss_j+energy.discharge_loss_j;
    audit.chemical_j=battery.initial_energy_j-battery.energy_j;
    candidate->last_work_frame=work.frame;candidate->work.reset();
    state_=std::move(candidate);audit_=audit;
    while(history_count_) {
        auto& interval=history_[history_head_];
        if(interval.end>work.end) {if(interval.begin<work.end)interval.begin=work.end;break;}
        history_head_=(history_head_+1)%history_.size();--history_count_;
    }
    if(sensors_)capture_electrical(*state_,*sensors_);
    return true;
}
} // namespace stratadrive::m7_external
