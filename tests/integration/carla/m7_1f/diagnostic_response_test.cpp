#include "diagnostic_response.hpp"
#include <gtest/gtest.h>
#include <limits>
namespace {
using namespace stratadrive;
constexpr std::uint64_t ms=1000000;
diagnostics::Event original() {
    diagnostics::Event e;e.kind=diagnostics::Kind::Fault;e.key={diagnostics::Code::CommandLoss,7,6,2};
    e.id={1,30,4};e.occurrence={1,30,42,6,4};e.session={1,42};
    e.session_enable={diagnostics::Domain::Simulation,99,1000*ms,true,true};
    e.times[2]={diagnostics::Domain::Simulation,99,1100*ms,true,true};return e;
}
central::NormalDriveReadinessInputs response() {
    central::NormalDriveReadinessInputs in;in.epoch=42;in.session_enable_ns=1000*ms;
    can::DriveMessage d{};d.kind=can::DriveFrameKind::Actual;d.epoch=42;d.sequence=17;d.source_time_ns=1120*ms;
    d.origin=can::ActuatorOrigin::LocalProtection;d.local_state=can::ActuatorLocalState::FailSafe;
    d.torque_nm=0;d.wheel_speed=can::DriveWheelSpeed{2,1110*ms};in.rear.drive_actual=d;
    can::BrakeMessage b{};b.kind=can::BrakeFrameKind::Actual;b.epoch=42;b.sequence=18;b.source_time_ns=1120*ms;
    b.origin=can::ActuatorOrigin::LocalProtection;b.local_state=can::ActuatorLocalState::FailSafe;b.pressure_pa=1200000;
    in.front.brake_actual=b;return in;
}
TEST(M9CarlaResponse, OriginalForeignOccurrenceAndOriginalAcquisitionsArePreservedOnce) {
    m7_functional::DiagnosticResponse capture;const auto root=original();capture.root(root);
    std::vector<diagnostics::Event> events;const auto emit=[&](const auto& e){events.push_back(e);};
    capture.observe(response(),1120*ms,emit);capture.observe(response(),1121*ms,emit);
    ASSERT_EQ(events.size(),3U);
    for(unsigned i=0;i<3;++i) {
        EXPECT_TRUE(events[i].related==root.id);EXPECT_TRUE(events[i].occurrence==root.occurrence);
        EXPECT_EQ(events[i].id.producer,9U);EXPECT_EQ(events[i].id.sequence,i+1);
        EXPECT_EQ(events[i].kind,diagnostics::Kind::Actual);EXPECT_EQ(events[i].times[2].ns,1100*ms);
        EXPECT_EQ(events[i].source.source.ns,events[i].times[5].ns);EXPECT_EQ(events[i].times[6].ns,1120*ms);
    }
    EXPECT_EQ(events[0].source.producer,11U);EXPECT_EQ(events[0].times[5].ns,1110*ms);EXPECT_EQ(events[0].measured,2);
    EXPECT_EQ(events[1].source.sequence,17U);EXPECT_EQ(events[2].measured,1200000);
}
TEST(M9CarlaResponse, MissingStaleFuturePreFaultWrongModeOrInvalidValueCannotBecomeResponse) {
    for(unsigned fault=0;fault<12;++fault) {
        m7_functional::DiagnosticResponse capture;capture.root(original());auto in=response();
        if(fault==0)in.rear.drive_actual.reset();
        if(fault==1)in.front.brake_actual.reset();
        if(fault==2)in.rear.drive_actual->wheel_speed.reset();
        if(fault==3)in.rear.drive_actual->wheel_speed->source_time_ns=1099*ms;
        if(fault==4)in.rear.drive_actual->source_time_ns=1121*ms;
        if(fault==5)in.rear.drive_actual->origin=can::ActuatorOrigin::NormalPath;
        if(fault==6)in.front.brake_actual->local_state=can::ActuatorLocalState::Normal;
        if(fault==7)in.front.brake_actual->pressure_pa=999999;
        if(fault==8)in.rear.drive_actual->torque_nm=std::numeric_limits<double>::quiet_NaN();
        if(fault==9)in.rear.drive_actual->wheel_speed->value_rad_s=-.1;
        if(fault==10)in.epoch=43;
        unsigned emitted=0;capture.observe(in,(fault==11?1151:1120)*ms,[&](const auto&){++emitted;});
        EXPECT_EQ(emitted,0U)<<fault;
        capture.observe(response(),1120*ms,[&](const auto&){++emitted;});EXPECT_EQ(emitted,3U)<<fault;
    }
}
TEST(M9CarlaResponse, NoFaultIsInventedFromObservationUnknownCauseOrUntrustedClock) {
    for(unsigned fault=0;fault<5;++fault) {
        auto root=original();
        if(fault==0)root.kind=diagnostics::Kind::Observation;
        if(fault==1)root.cause_unknown=true;
        if(fault==2)root.unmapped=true;
        if(fault==3)root.times[2].trusted=false;
        if(fault==4)root.times[2].instance=100;
        m7_functional::DiagnosticResponse capture;capture.root(root);unsigned emitted=0;
        capture.observe(response(),1120*ms,[&](const auto&){++emitted;});EXPECT_EQ(emitted,0U);
    }
}
}
