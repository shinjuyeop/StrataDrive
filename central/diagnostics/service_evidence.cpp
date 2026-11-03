#include "service_evidence.hpp"

namespace stratadrive::diagnostics {
ServiceEvidence capture_service_evidence(ControlContext actor,Session session,Stamp enable,
    const central::NormalDriveReadinessInputs& input,Stamp now,bool inhibited) noexcept {
    ServiceEvidence e;e.now=now;e.enable=enable;e.normal_dispatch_inhibited=inhibited;
    if(!actor.run || !actor.producer || !actor.profile || actor.domain!=Domain::Monotonic || !actor.clock_instance || session.run!=actor.run || !session.epoch ||
       now.domain!=actor.domain || now.instance!=actor.clock_instance || !comparable(now,enable) || input.epoch!=session.epoch || input.session_enable_ns!=enable.ns ||
       !input.rear.drive_actual || !input.front.brake_actual)return e;
    const auto& drive=*input.rear.drive_actual;const auto& brake=*input.front.brake_actual;
    if(drive.kind!=can::DriveFrameKind::Actual || brake.kind!=can::BrakeFrameKind::Actual || drive.epoch!=session.epoch || brake.epoch!=session.epoch ||
       !drive.torque_nm || !drive.wheel_speed || !brake.pressure_pa)return e;
    e.wheel={actor.domain,actor.clock_instance,drive.wheel_speed->source_time_ns,true,true};
    e.drive={actor.domain,actor.clock_instance,drive.source_time_ns,true,true};e.brake={actor.domain,actor.clock_instance,brake.source_time_ns,true,true};
    e.wheel_rad_s=drive.wheel_speed->value_rad_s;e.torque_nm=*drive.torque_nm;e.pressure_pa=*brake.pressure_pa;
    e.current_streams_valid=true;if(!stationary_evidence(e))e.current_streams_valid=false;return e;
}
} // namespace stratadrive::diagnostics
