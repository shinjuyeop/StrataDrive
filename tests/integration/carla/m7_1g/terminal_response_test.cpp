#include "functional_rig.hpp"
#include <gtest/gtest.h>
namespace {
using namespace stratadrive;
using namespace m7_functional;
constexpr Scope scope{1,42,7};
constexpr Time wall=100000000000ULL;
struct Warm {
    FunctionalRig rig{scope,99,PlantMode::ExternalSolverWork,true};
    Report last;
    explicit Warm(bool fractional=false) {
        WheelSample old;
        for(unsigned i=0;i<=180;++i) {
            const double time=fractional?3.997146773152053+i*.009999999776482582:1+i*.01;
            const auto ns=static_cast<Time>(std::llround(time*1e9));
            WheelSample w{99,100+i,ns,{0,0,0,0}};
            Observation o{scope,domain,100+i,time,.01};
            if(!i)last=rig.observe(o,w);
            else {
                m7_external::SolverWork work;work.frame=w.frame;work.begin=old.source;work.end=ns;
                work.dt=double(.01f*(1.f/320.f));work.oldest=old.source;
                work.wheel={0,{7,static_cast<std::uint32_t>(old.frame),old.source},old.source};
                // Static zero-work component fixture, NOT a CARLA physics run.
                last=rig.observe(o,w,work);
            }
            old=w;
        }
    }
};
transport::Feedback actual(const NativeExport& e,unsigned role) {
    const auto& p=e.actual[role];
    if(!p)throw std::runtime_error("missing terminal Actual");
    const auto wire=remote::decode_owner_message(p->bytes.data(),p->size);
    if(!wire)throw std::runtime_error("invalid terminal wire");
    return std::get<transport::Feedback>(wire->payload);
}
TEST(M7TerminalResponse, SameEightOwnersKeepActualFeedbackWithoutWheelOrWork) {
    for(bool fractional:{false,true}) {
        Warm warm(fractional);ASSERT_TRUE(warm.last.armed);
        const auto before=warm.last;warm.rig.begin_terminal_response(wall);
        unsigned brake_changes=0;Time brake_source=0;
        for(unsigned i=1;i<=300;++i) {
            Report r;
            ASSERT_NO_THROW(r=warm.rig.service_terminal_response(wall+i*ms))<<"fractional="<<fractional<<" step="<<i;
            ASSERT_TRUE(r.native_export);EXPECT_FALSE(r.armed);EXPECT_EQ(r.credit_mask,0U);
            EXPECT_EQ(r.next_frame,0U);EXPECT_EQ(r.service_mask,255U);
            EXPECT_EQ(r.native_export->protection_selected_mask,255U);
            EXPECT_EQ(r.controller_releases,before.controller_releases);
            ASSERT_TRUE(r.electrical);EXPECT_EQ(r.electrical->end,before.electrical->end);
            EXPECT_DOUBLE_EQ(r.electrical->total_mechanical_j,before.electrical->total_mechanical_j);
            EXPECT_DOUBLE_EQ(r.electrical->soc,before.electrical->soc);
            ASSERT_TRUE(r.sensor_wheel);EXPECT_LE(r.sensor_wheel->source,before.now);
            if(i<25)continue; // original 10ms ECU/Zone delivery, no instant fake Ack
            const auto b=can::decode_brake_frame(std::get<can::BrakeFrame>(actual(*r.native_export,1)));
            const auto d=can::decode_drive_frame(std::get<can::DriveFrame>(actual(*r.native_export,2)));
            ASSERT_TRUE(b);ASSERT_TRUE(d);
            EXPECT_EQ(b->origin,can::ActuatorOrigin::LocalProtection);
            EXPECT_EQ(d->origin,can::ActuatorOrigin::LocalProtection);
            EXPECT_EQ(b->local_state,can::ActuatorLocalState::FailSafe);
            EXPECT_GT(b->source_time_ns,before.now);EXPECT_LE(r.now-b->source_time_ns,30*ms);
            if(b->source_time_ns!=brake_source){++brake_changes;brake_source=b->source_time_ns;}
            if(i>=250){EXPECT_GE(b->pressure_pa,1000000);EXPECT_EQ(d->torque_nm,0);}
        }
        EXPECT_GT(brake_changes,20U);
        EXPECT_THROW(warm.rig.begin_terminal_response(wall+400*ms),std::runtime_error);
        EXPECT_THROW(warm.rig.observe({scope,domain,281,2.81,.01},{99,281,2810000000ULL,{0,0,0,0}}),std::runtime_error);
    }
}
TEST(M7TerminalResponse, NoReplayPollsAfterLateServiceAndNoBackwardClock) {
    Warm warm;const auto before=warm.last;warm.rig.begin_terminal_response(wall);
    auto r=warm.rig.service_terminal_response(wall+ms);
    r=warm.rig.service_terminal_response(wall+40*ms);
    EXPECT_EQ(r.now,before.now+40*ms);EXPECT_EQ(r.credit_mask,0U);
    EXPECT_THROW(warm.rig.service_terminal_response(wall+39*ms),std::runtime_error);
    EXPECT_THROW(warm.rig.service_terminal_response(wall+40*ms),std::runtime_error);
    EXPECT_THROW(warm.rig.service_terminal_response(wall+1001*ms),std::runtime_error);
    bool rejected=false;
    std::thread other([&]{try{warm.rig.service_terminal_response(wall+41*ms);}catch(const std::runtime_error&){rejected=true;}});
    other.join();EXPECT_TRUE(rejected);
}
TEST(M7TerminalResponse, HandoffRequiresSettledNormalObservedWork) {
    FunctionalRig empty(scope,99,PlantMode::ExternalSolverWork,true);
    EXPECT_THROW(empty.begin_terminal_response(wall),std::runtime_error);
    FunctionalRig zoh(scope,99,PlantMode::ExternalWheelZoh,true);
    for(unsigned i=0;i<=180;++i)zoh.observe({scope,domain,100+i,1+i*.01,.01},{99,100+i,1000000000ULL+i*tick_ns,{0,0,0,0}});
    EXPECT_THROW(zoh.begin_terminal_response(wall),std::runtime_error);
    m7_external::ActuatorElectrical model(1000000000,42,true);
    EXPECT_FALSE(model.begin_terminal_response());
}
}
