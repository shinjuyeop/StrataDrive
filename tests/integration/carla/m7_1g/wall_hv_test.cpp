#include "wall_drive_controller.hpp"
#include "wall_rig.hpp"
#include <gtest/gtest.h>
using namespace stratadrive;
namespace {
constexpr std::uint64_t ms=1000000,start=1000000000;
drive::LocalSensors sensors(std::uint64_t source,std::uint64_t dependency) {
    const battery::ModelIdentity id{7,static_cast<std::uint32_t>(source-start),source};
    return {battery::ModelMeasurement<double>{0,id,source},
        battery::ModelMeasurement<drive::HvFeedback>{{400,true,false},id,dependency}};
}
vecu::WallDriveControllerConfig config(std::uint64_t limit) {
    vecu::WallDriveControllerConfig c;c.hv_dependency_age_ns=limit;return c;
}
void inhibit(vecu::WallDriveController& c,std::uint64_t now) {
    can::BmsTxState limits{can::BmsFrameKind::DriveBatteryLimits},grant{can::BmsFrameKind::DrivePermission};
    can::BmsMessage m;m.kind=can::BmsFrameKind::PowerLimits;m.epoch=42;m.sequence=1;m.source_time_ns=now;
    m.local_state=can::ActuatorLocalState::Normal;m.origin=can::ActuatorOrigin::NormalPath;
    m.content=can::BmsPowerLimits{30000,80000,can::BmsLimitReason::Nominal,can::BmsLimitReason::Nominal,now};
    auto f=can::forward_bms_limits(m,limits);ASSERT_TRUE(f);
    ASSERT_EQ(c.receive_limits(*f,now).decision,can::ActuatorReceiveDecision::Accepted);
    m.kind=can::BmsFrameKind::DrivePermission;
    m.content=can::BmsDriveGrant{can::BmsDrivePermission::Inhibit,0,0,0,now+60*ms};
    f=can::encode_bms_frame(m,grant);ASSERT_TRUE(f);
    ASSERT_EQ(c.receive_permission(*f,now,nullptr).decision,can::ActuatorReceiveDecision::Accepted);
}
TEST(M7WallHv, DependencyBudgetIsExplicitAndBoundaryInclusive) {
    for(const auto limit:{30*ms,50*ms})for(const auto delta:{0ULL,1ULL}) {
        vecu::WallDriveController c(config(limit));ASSERT_TRUE(c.start_session({42,7,start}));
        const auto now=start+60*ms;
        EXPECT_EQ(c.observe_local(sensors(now,now-limit-delta),now).hv,
                  delta?drive::SensorDecision::Time:drive::SensorDecision::Accepted);
    }
    vecu::DriveController original({});ASSERT_TRUE(original.start_session({42,7,start}));
    EXPECT_EQ(original.observe_local(sensors(start+60*ms,start+30*ms-1),start+60*ms).hv,drive::SensorDecision::Time);
}
TEST(M7WallHv, SourceAndWheelStayAtThirtyMs) {
    for(unsigned kind=0;kind<3;++kind)for(const auto delta:{0ULL,1ULL}) {
        vecu::WallDriveController c(config(50*ms));ASSERT_TRUE(c.start_session({42,7,start}));
        const auto now=start+60*ms;auto s=sensors(now,now);
        if(kind==0)s.hv->identity.source_time_ns=s.hv->input_time_ns=now-30*ms-delta;
        if(kind==1)s.wheel_speed->identity.source_time_ns=s.wheel_speed->input_time_ns=now-30*ms-delta;
        if(kind==2)s.wheel_speed->input_time_ns=now-30*ms-delta;
        auto r=c.observe_local(s,now);
        EXPECT_EQ(kind==0?r.hv:r.wheel_speed,delta?drive::SensorDecision::Time:drive::SensorDecision::Accepted);
    }
}
TEST(M7WallHv, CachedIdentityCannotAcquireNewTimes) {
    for(unsigned field=0;field<2;++field) {
        vecu::WallDriveController c(config(50*ms));ASSERT_TRUE(c.start_session({42,7,start}));
        auto s=sensors(start+20*ms,start+10*ms);
        ASSERT_EQ(c.observe_local(s,start+20*ms).hv,drive::SensorDecision::Accepted);
        ASSERT_EQ(c.observe_local(s,start+21*ms).hv,drive::SensorDecision::Accepted);
        if(field==0)++s.hv->identity.source_time_ns;else ++s.hv->input_time_ns;
        EXPECT_EQ(c.observe_local(s,start+22*ms).hv,drive::SensorDecision::Identity);
    }
}
TEST(M7WallHv, FreshReplacementCannotHidePreviousExpiry) {
    for(const auto limit:{30*ms,50*ms})for(const auto delta:{0ULL,1ULL}) {
        vecu::WallDriveController c(config(limit));ASSERT_TRUE(c.start_session({42,7,start},vecu::DriveCommandStartup::NonDriving));
        const std::uint64_t before=start+40*ms,now=before+20*ms+delta;
        inhibit(c,before);
        ASSERT_EQ(c.observe_local(sensors(before,now-limit-delta),before).hv,drive::SensorDecision::Accepted);
        ASSERT_EQ(c.decision().fault,vecu::DriveGateFault::None);
        EXPECT_EQ(c.observe_local(sensors(now,now),now).hv,drive::SensorDecision::Accepted);
        EXPECT_EQ(c.decision().fault,delta?vecu::DriveGateFault::LocalInputsUnavailable:vecu::DriveGateFault::None);
        if(delta) {
            c.observe_local(sensors(now+ms,now+ms),now+ms);
            EXPECT_EQ(c.decision().fault,vecu::DriveGateFault::LocalInputsUnavailable);
        }
    }
}
TEST(M7WallHv, InvalidOrUnscopedBudgetIsRejected) {
    for(const auto limit:{0ULL,40000000ULL,50000001ULL,100000000ULL})
        EXPECT_THROW(vecu::WallDriveController{config(limit)},std::invalid_argument);
    EXPECT_THROW((m7_functional::WallRig{{1,42,7},99,start,0,10*ms,50*ms}),std::runtime_error);
    EXPECT_THROW((m7_functional::WallRig{{1,42,7},99,start,start,10*ms,50*ms}),std::runtime_error);
    EXPECT_NO_THROW((m7_functional::WallRig{{1,42,7},99,start,start,5*ms,50*ms}));
}
}
