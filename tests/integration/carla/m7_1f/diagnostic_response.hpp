#pragma once
#include "control_diagnostics.hpp"
#include <algorithm>
#include <cmath>
#include <optional>

namespace stratadrive::m7_functional {
// Single-owner CARLA composition observer. The root is an original event from
// the real native diagnostic adapter, never a fault inferred from injection.
// Response records keep that foreign occurrence and independently acquired
// CAN values; they neither create a DTC nor grant recovery/clear/actuation.
class DiagnosticResponse {
public:
    void root(const diagnostics::Event& event) {
        if(root_ || event.kind!=diagnostics::Kind::Fault || event.key.code!=diagnostics::Code::CommandLoss ||
           event.cause_unknown || event.unmapped || !event.times[2].present || !event.times[2].trusted ||
           !event.session_enable.present || !event.session_enable.trusted ||
           event.session_enable.domain!=diagnostics::Domain::Simulation ||
           !diagnostics::comparable(event.times[2],event.session_enable) || event.times[2].ns<event.session_enable.ns)return;
        root_=event;
    }
    template<class Emit> void observe(const central::NormalDriveReadinessInputs& in,std::uint64_t now,Emit emit) {
        if(done_ || !root_ || in.epoch!=root_->session.epoch || in.session_enable_ns!=root_->session_enable.ns ||
           !in.rear.drive_actual || !in.front.brake_actual)return;
        const auto& d=*in.rear.drive_actual;const auto& b=*in.front.brake_actual;
        if(d.epoch!=in.epoch || b.epoch!=in.epoch || !d.torque_nm || !d.wheel_speed || !b.pressure_pa ||
           d.kind!=can::DriveFrameKind::Actual || b.kind!=can::BrakeFrameKind::Actual ||
           d.origin!=can::ActuatorOrigin::LocalProtection || b.origin!=can::ActuatorOrigin::LocalProtection ||
           d.local_state!=can::ActuatorLocalState::FailSafe || b.local_state!=can::ActuatorLocalState::FailSafe ||
           !std::isfinite(*d.torque_nm) || !std::isfinite(*b.pressure_pa) || !std::isfinite(d.wheel_speed->value_rad_s) ||
           std::abs(*d.torque_nm)>1 || *b.pressure_pa<1000000 || *b.pressure_pa>1500000 ||
           d.wheel_speed->value_rad_s<0 || d.wheel_speed->value_rad_s>100)return;
        const auto low=std::min({d.source_time_ns,b.source_time_ns,d.wheel_speed->source_time_ns});
        const auto high=std::max({d.source_time_ns,b.source_time_ns,d.wheel_speed->source_time_ns});
        if(low<root_->times[2].ns || high>now || now-low>30000000 || high-low>20000000)return;
        const auto stamp=[&](std::uint64_t ns){auto s=root_->session_enable;s.ns=ns;return s;};
        const auto actual=[&](diagnostics::Component actor,std::uint64_t sequence,std::uint64_t source,double measured) {
            auto e=*root_;e.id={root_->id.run,9,next_++};e.related=root_->id;
            e.kind=diagnostics::Kind::Actual;e.proof=diagnostics::Proof::Response;
            e.source={true,static_cast<std::uint64_t>(actor),sequence,in.epoch,stamp(source),{}};
            e.times[5]=stamp(source);e.times[6]=stamp(now);e.measured=measured;emit(e);
        };
        actual(diagnostics::Component::DriveWheel,d.wheel_speed->source_time_ns,d.wheel_speed->source_time_ns,d.wheel_speed->value_rad_s);
        actual(diagnostics::Component::Drive,d.sequence,d.source_time_ns,*d.torque_nm);
        actual(diagnostics::Component::Brake,b.sequence,b.source_time_ns,*b.pressure_pa);
        done_=true;
    }
private:
    std::optional<diagnostics::Event> root_;
    std::uint64_t next_=1;bool done_=false;
};
}
