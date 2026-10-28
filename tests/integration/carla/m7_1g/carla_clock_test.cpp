#include "wall_rig.hpp"
#include <gtest/gtest.h>
using namespace stratadrive;
using namespace m7_functional;
namespace {
constexpr Time wall=1000000000000ULL,model=1000000000ULL;
m7_external::CarlaWork frame(unsigned i,Time source) {
    m7_external::CarlaWork c;
    auto& w=c.work;w.frame=100+i;w.begin=model+(i-1)*10*ms;w.end=model+i*10*ms;w.oldest=w.begin;
    w.dt=double(.01f*(1.f/320.f));w.wheel={0,{7,99+i,w.begin},w.begin};
    c.applied=source-9*ms;c.acquired_begin=source;c.acquired_end=source+1000;c.oldest=c.applied;
    return c;
}
TEST(M7CarlaClock, ModelDtAndWallAcquisitionRemainDistinctAndCached) {
    m7_external::ActuatorElectrical m(wall,42,m7_external::PlantExecution::CarlaObservedWork,model);
    std::array<std::optional<simulation::OwnerActuation>,5> outputs{};
    for(unsigned i=1;i<=55;++i) {
        ASSERT_TRUE(m.advance_actuators(wall+i*ms,{},outputs,0));
        if(i==13 || i==34) {
            auto c=frame(i==13?1:2,wall+(i-1)*ms);
            ASSERT_TRUE(m.settle_carla_frame(c))<<m.error();
        }
        if(i>=13) {
            ASSERT_TRUE(m.sensors()->power);
            const auto acquired=wall+(i<34?12:33)*ms;
            EXPECT_EQ(m.sensors()->power->identity.source_time_ns,acquired);
            EXPECT_EQ(m.sensors()->drive.hv->identity.source_time_ns,acquired);
            EXPECT_EQ(m.sensors()->battery.soc->identity.source_time_ns,acquired);
            EXPECT_EQ(m.electrical_time(),model+(i<34?10:20)*ms);
        }
    }
}
TEST(M7CarlaClock, RejectsFutureReplayedAndMixedClockReceipts) {
    for(unsigned fault=0;fault<5;++fault) {
        m7_external::ActuatorElectrical m(wall,42,m7_external::PlantExecution::CarlaObservedWork,model);
        std::array<std::optional<simulation::OwnerActuation>,5> outputs{};
        for(unsigned i=1;i<=12;++i)ASSERT_TRUE(m.advance_actuators(wall+i*ms,{},outputs,0));
        auto c=frame(1,wall+10*ms);
        if(fault==0)c.acquired_end=wall+13*ms;
        if(fault==1)c.work.begin=wall;
        if(fault==2)c.oldest=c.applied+1;
        if(fault==3)c.work.oldest=c.work.begin-1;
        if(fault==4){ASSERT_TRUE(m.settle_carla_frame(c));}
        EXPECT_FALSE(m.settle_carla_frame(c));EXPECT_FALSE(m.electrical_ok());
        EXPECT_TRUE(m.advance_actuators(wall+13*ms,{},outputs,0,true));
    }
}
TEST(M7CarlaClock, NoElectricalAcquisitionWithoutCompletedPhysics) {
    m7_external::ActuatorElectrical m(wall,42,m7_external::PlantExecution::CarlaObservedWork,model);
    std::array<std::optional<simulation::OwnerActuation>,5> outputs{};
    for(unsigned i=1;i<=300;++i) {
        ASSERT_TRUE(m.advance_actuators(wall+i*ms,{},outputs,0,true));
        EXPECT_FALSE(m.sensors()->power);EXPECT_FALSE(m.sensors()->drive.hv);
        EXPECT_EQ(m.electrical_time(),model);EXPECT_EQ(m.electrical_acquisition(),0U);
    }
}
TEST(M7CarlaClock, NativeUsesOriginalAcquisitionInsteadOfModelTimestamp) {
    WallRig rig({1,42,7},99,wall,model);WallReport r;
    for(unsigned i=1;i<=100;++i) {
        std::optional<WallReceipt> receipt;
        if(i%10==1 && i>10) {
            auto c=frame(i/10,wall+(i-1)*ms);
            receipt=WallReceipt{{99,c.work.frame,c.acquired_begin,{0,0,0,0}},c.work,wall_domain,c};
        }
        r=rig.service(wall+i*ms,receipt);
        if(receipt){EXPECT_EQ(r.native.sensor_wheel->source,receipt->carla->acquired_begin);}
        ASSERT_FALSE(r.failed)<<i<<' '<<r.reason;
    }
    EXPECT_EQ(r.native.release_mask,255U);
    EXPECT_LT(r.native.electrical->end,wall);EXPECT_GE(r.native.electrical_acquired,wall);
}
TEST(M7CarlaClock, SensorIngressHandlesDriftingPhysicsPhaseWithoutExtraControlJobs) {
    WallRig rig({1,42,7},99,wall,model);
    std::array<Report,3> history{};WallReport r;unsigned frames=0;
    for(unsigned i=1;i<=1500;++i) {
        std::optional<WallReceipt> receipt;
        if(i>11 && i%11==1) {
            auto c=frame(++frames,wall+(i-1)*ms);
            c.applied=wall+(i-2)*ms;
            const auto& applied=history[(i-2)%3];
            c.coils=applied.coils;c.coil_source=applied.coil_source;c.oldest=c.applied;
            for(auto source:applied.actual_sources)if(source)c.oldest=std::min(c.oldest,source);
            if(applied.sensor_wheel)c.oldest=std::min(c.oldest,applied.sensor_wheel->source);
            receipt=WallReceipt{{99,c.work.frame,c.acquired_begin,{0,0,0,0}},c.work,wall_domain,c};
        }
        r=rig.service(wall+i*ms,receipt);history[i%3]=r.native;
        ASSERT_FALSE(r.failed)<<i<<' '<<r.reason;
    }
    EXPECT_TRUE(r.native.armed);EXPECT_LE(r.native.controller_releases,75U);
    EXPECT_EQ(r.native.electrical->end,model+frames*10*ms);
}

}
