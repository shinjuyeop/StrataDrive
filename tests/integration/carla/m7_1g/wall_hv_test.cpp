#include "drive_controller.hpp"
#include "wall_rig.hpp"
#include "wall_service_options.hpp"
#include <gtest/gtest.h>
using namespace stratadrive;
namespace {
TEST(M7WallService, ExplicitHalfMsRequiresProfiledEnduranceAndRejectsDuplicateOptions) {
    const auto parse=[](std::initializer_list<const char*> tail,unsigned endurance) {
        std::vector<std::string> values(10,"base");for(const auto* v:tail)values.emplace_back(v);
        std::vector<char*> args;for(auto& v:values)args.push_back(v.data());
        return m7_functional::wall_service_options(static_cast<int>(args.size()),args.data(),endurance);
    };
    EXPECT_EQ(parse({},0).period_ns,1000000U);
    EXPECT_EQ(parse({"--profile-state-path"},300).period_ns,1000000U);
    EXPECT_EQ(parse({"--profile-state-path","--service-us","500"},300).period_ns,500000U);
    EXPECT_EQ(parse({"--service-us","500","--profile-state-path"},30).period_ns,500000U);
    EXPECT_THROW(parse({"--service-us","500"},300),std::runtime_error);
    EXPECT_THROW(parse({"--profile-state-path","--service-us","500"},0),std::runtime_error);
    EXPECT_THROW(parse({"--profile-state-path","--profile-state-path"},300),std::runtime_error);
    EXPECT_THROW(parse({"--profile-state-path","--service-us","500","--service-us","500"},300),std::runtime_error);
    EXPECT_THROW(parse({"--profile-state-path","--service-us","250"},300),std::runtime_error);
    EXPECT_THROW(parse({"--profile-state-path","--service-us"},300),std::runtime_error);
}
TEST(M7WallService, AbsoluteCadenceSkipsMissedSlotsInsteadOfReplayingOldJobs) {
    constexpr std::uint64_t begin=1000000000;
    for(const std::uint64_t period:{500000,1000000}) {
        EXPECT_EQ(m7_functional::next_wall_service(begin,begin,period),begin+period);
        EXPECT_EQ(m7_functional::next_wall_service(begin,begin+period-1,period),begin+period);
        EXPECT_EQ(m7_functional::next_wall_service(begin,begin+period,period),begin+2*period);
        EXPECT_EQ(m7_functional::next_wall_service(begin,begin+5*period+1,period),begin+6*period);
    }
    EXPECT_THROW(m7_functional::next_wall_service(begin,begin-1,500000),std::runtime_error);
}
constexpr std::uint64_t ms=1000000,start=1000000000;
drive::LocalSensors sensors(std::uint64_t source,std::uint64_t dependency) {
    const battery::ModelIdentity id{7,static_cast<std::uint32_t>(source-start),source};
    return {battery::ModelMeasurement<double>{0,id,source},
        battery::ModelMeasurement<drive::HvFeedback>{{400,true,false},id,dependency}};
}
vecu::DriveControllerConfig config(std::uint64_t limit) {
    vecu::DriveControllerConfig c;c.hv_dependency_age_ns=limit;return c;
}
void inhibit(vecu::DriveController& c,std::uint64_t now) {
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
        vecu::DriveController c(config(limit));ASSERT_TRUE(c.start_session({42,7,start}));
        const auto now=start+60*ms;
        EXPECT_EQ(c.observe_local(sensors(now,now-limit-delta),now).hv,
                  delta?drive::SensorDecision::Time:drive::SensorDecision::Accepted);
    }
    vecu::DriveController original({});ASSERT_TRUE(original.start_session({42,7,start}));
    EXPECT_EQ(original.observe_local(sensors(start+60*ms,start+30*ms-1),start+60*ms).hv,drive::SensorDecision::Time);
}
TEST(M7WallHv, SourceAndWheelStayAtThirtyMs) {
    for(unsigned kind=0;kind<3;++kind)for(const auto delta:{0ULL,1ULL}) {
        vecu::DriveController c(config(50*ms));ASSERT_TRUE(c.start_session({42,7,start}));
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
        vecu::DriveController c(config(50*ms));ASSERT_TRUE(c.start_session({42,7,start}));
        auto s=sensors(start+20*ms,start+10*ms);
        ASSERT_EQ(c.observe_local(s,start+20*ms).hv,drive::SensorDecision::Accepted);
        ASSERT_EQ(c.observe_local(s,start+21*ms).hv,drive::SensorDecision::Accepted);
        if(field==0)++s.hv->identity.source_time_ns;else ++s.hv->input_time_ns;
        EXPECT_EQ(c.observe_local(s,start+22*ms).hv,drive::SensorDecision::Identity);
    }
}
TEST(M7WallHv, FreshReplacementCannotHidePreviousExpiry) {
    for(const auto limit:{30*ms,50*ms})for(const auto delta:{0ULL,1ULL}) {
        vecu::DriveController c(config(limit));ASSERT_TRUE(c.start_session({42,7,start},vecu::DriveCommandStartup::NonDriving));
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
        EXPECT_THROW(vecu::DriveController{config(limit)},std::invalid_argument);
    EXPECT_THROW((m7_functional::WallRig{{1,42,7},99,start,0,10*ms,50*ms}),std::runtime_error);
    EXPECT_THROW((m7_functional::WallRig{{1,42,7},99,start,start,10*ms,50*ms}),std::runtime_error);
    EXPECT_NO_THROW((m7_functional::WallRig{{1,42,7},99,start,start,5*ms,50*ms}));
    for(unsigned horizon:{30U,300U}) {
        EXPECT_NO_THROW((m7_functional::WallRig{{1,42,7},99,start,start,5*ms,50*ms,horizon}));
        EXPECT_THROW((m7_functional::WallRig{{1,42,7},99,start,start,10*ms,50*ms,horizon}),std::runtime_error);
    }
}
TEST(M7WallHv, OwnerOptionsCannotChangeAnotherLeafOrUseUnknownIngress) {
    struct Clock : transport::Clock { std::uint64_t now_ns() noexcept override {return start;} } clock;
    transport::RunGate gate;transport::LeafLink link;
    runtime::LatestSnapshot<simulation::OwnerSensors> sensors;
    runtime::LatestSnapshot<simulation::OwnerActuation> output;
    simulation::BmsGateChannel bms;
    const simulation::LeafOwnerConfig config{simulation::DriveSensorIngress::BeforeIo,50*ms};
    EXPECT_THROW((simulation::AsyncLeafOwner{transport::Leaf::Brake,clock,gate,link,sensors,output,bms,config}),std::invalid_argument);
    const simulation::LeafOwnerConfig invalid{static_cast<simulation::DriveSensorIngress>(99),{}};
    EXPECT_THROW((simulation::AsyncLeafOwner{transport::Leaf::Drive,clock,gate,link,sensors,output,bms,invalid}),std::invalid_argument);
    EXPECT_NO_THROW((simulation::AsyncLeafOwner{transport::Leaf::Drive,clock,gate,link,sensors,output,bms,config}));
}
}
