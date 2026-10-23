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
    State(Time start,std::uint32_t application):initial(start),last(start),maximum_application(application) {
        motor.begin(7,start);
        if(!start || !application || !angle.begin(start) || !pressure.begin(start) ||
           !electrical.initialize({7,start,.63,25},0))throw std::invalid_argument("M7 fixture initialization");
    }
};
ActuatorElectrical::ActuatorElectrical(Time start,std::uint32_t app):state_(std::make_unique<State>(start,app)) {}
ActuatorElectrical::~ActuatorElectrical()=default;
Time ActuatorElectrical::last_success() const {return state_->last;}
bool ActuatorElectrical::fail(const char* why) {if(error_.empty())error_=why;sensors_.reset();return false;}
bool ActuatorElectrical::step(Time now,const std::optional<Wheel>& wheel,
    const std::array<std::optional<OwnerActuation>,5>& outputs,std::uint32_t released,bool protect) {
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
    const auto result=s.electrical.step({s.last,now,input,s.coils});
    if(result.fault!=EvPowerFault::None)return fail("M7 EV input/interval/energy rejection");
    if(!s.motor.advance(now,false) || !s.angle.advance(now) || !s.pressure.advance(now))return fail("M7 actuator advance");
    OwnerSensors measured;measured.source_ns=now;
    measured.angle=s.angle.capture();measured.pressure=s.pressure.capture();measured.torque=s.motor.capture(now);
    measured.power=s.electrical.power_observation();measured.battery=s.electrical.battery_observation();
    measured.drive.wheel_speed=wheel;
    const auto& power=s.electrical.power_state();
    if(!measured.angle || !measured.pressure || !measured.torque || !measured.power)return fail("M7 acquisition unavailable");
    measured.drive.hv=battery::ModelMeasurement<drive::HvFeedback>{{power.bus_voltage_v,
        power.contactors.positive && power.contactors.negative && power.bus_voltage_v>=300,false},
        {7,s.sequence,now},measured.power->input_time_ns};

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
        if(std::abs(s.motor.actual_nm())<.1 && std::abs(power.pack_current_a)<vecu::PowerControllerConfig{}.opening_current_max_a) {
            if(!s.current_safe_since)s.current_safe_since=now;
            if(now-s.current_safe_since>=vecu::PowerControllerConfig{}.current_dwell_ns)s.coils={{false,false,false},true};
        } else s.current_safe_since=0;
    }
    if(protect && (!s.angle.hold(now) || !s.pressure.request_protection(1000000,now) ||
                  !s.motor.apply({drive::ActuationMode::Zero,0,std::nullopt,now})))return fail("M7 protection");
    const auto& energy=s.electrical.diagnostic_state();
    const ElectricalAudit audit{s.last,now,wheel->identity.source_time_ns,wheel->input_time_ns,wheel->value,torque,
        energy.mechanical_j-state_->electrical.diagnostic_state().mechanical_j,energy.mechanical_j,
        s.electrical.battery_state().soc,energy.balance_error_j};
    s.last=now;++s.sequence;
    state_=std::move(next);sensors_=measured;audit_=audit;
    return true;
}
} // namespace stratadrive::m7_external
