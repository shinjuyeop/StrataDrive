#include "functional_rig.hpp"
#include "native_admission.hpp"
#include <gtest/gtest.h>

namespace stratadrive::m7_functional {
namespace {
TEST(M8CarlaRoute, CombinedMarkersLatchOnceAndUseContinuousFixedRamps) {
    RouteSpeedProfile profile(RouteProfile::Combined);
    constexpr Time sec=1000000000;
    EXPECT_DOUBLE_EQ(profile.step(0,0),0);
    EXPECT_DOUBLE_EQ(profile.step(5*sec,20),15/3.6);
    EXPECT_DOUBLE_EQ(profile.step(25*sec,179.999),30/3.6);
    EXPECT_FALSE(profile.slow_ns());
    EXPECT_DOUBLE_EQ(profile.step(27*sec,180),30/3.6);
    EXPECT_EQ(profile.slow_ns(),27*sec);
    EXPECT_NEAR(profile.step(30*sec,179.9),25/3.6,1e-14);
    EXPECT_NEAR(profile.step(33*sec,220),20/3.6,1e-14);
    EXPECT_NEAR(profile.step(50*sec,329.999),20/3.6,1e-14);
    EXPECT_FALSE(profile.stop_ns());
    EXPECT_DOUBLE_EQ(profile.step(53*sec,330),20/3.6);
    EXPECT_EQ(profile.slow_ns(),27*sec);
    EXPECT_EQ(profile.stop_ns(),53*sec);
    EXPECT_DOUBLE_EQ(profile.step(57*sec,329.9),10/3.6);
    EXPECT_DOUBLE_EQ(profile.step(61*sec,352),0);
    EXPECT_DOUBLE_EQ(profile.step(75*sec,352),0);
}
TEST(M8CarlaRoute, StraightProfileMatchesCurveAndIgnoresPositionMarkers) {
    RouteSpeedProfile straight(RouteProfile::Straight30),curve(RouteProfile::Curve30);
    for(Time t=0;t<60000;t+=20)EXPECT_DOUBLE_EQ(straight.step(t*ms,400),curve.step(t*ms,0));
    EXPECT_FALSE(straight.slow_ns());EXPECT_FALSE(straight.stop_ns());
}
TEST(M8CarlaRoute, Stop30IsSeparateAndRejectsUnsupportedScopeBeforeMutation) {
    RouteSpeedProfile profile(RouteProfile::Straight30Stop);
    EXPECT_DOUBLE_EQ(profile.step(10'000'000'000ULL,0),15/3.6);
    EXPECT_DOUBLE_EQ(profile.step(35'000'000'000ULL,200),30/3.6);
    EXPECT_DOUBLE_EQ(profile.step(55'000'000'000ULL,240),30/3.6);
    FunctionalRig rig({1,42,7},99,PlantMode::ExternalSolverWork,true,60000);
    EXPECT_THROW(rig.speed_profile(SpeedTerminal::NormalStop30),std::runtime_error);
    EXPECT_THROW(rig.route_profile({{0,0},{5,0}},RouteProfile::Straight30Stop,true),std::runtime_error);
    EXPECT_THROW(rig.route_profile({{0,0},{5,0}},static_cast<RouteProfile>(99)),std::runtime_error);
    EXPECT_NO_THROW(rig.route_profile({{0,0},{5,0}},RouteProfile::Straight30Stop));
}
TEST(M8CarlaRoute, CombinedV2UsesFeasibleStartupAndShiftedFixedMarkers) {
    RouteSpeedProfile profile(RouteProfile::CombinedV2);
    constexpr Time sec=1000000000;
    EXPECT_DOUBLE_EQ(profile.step(10*sec,20),15/3.6);
    EXPECT_DOUBLE_EQ(profile.step(20*sec,80),30/3.6);
    EXPECT_DOUBLE_EQ(profile.step(35*sec,229.999),30/3.6);
    EXPECT_FALSE(profile.slow_ns());
    EXPECT_DOUBLE_EQ(profile.step(38*sec,230),30/3.6);
    EXPECT_EQ(profile.slow_ns(),38*sec);
    EXPECT_DOUBLE_EQ(profile.requested_mps(30/3.6),20/3.6);
    EXPECT_NEAR(profile.step(41*sec,250),25/3.6,1e-14);
    EXPECT_NEAR(profile.step(44*sec,272),20/3.6,1e-14);
    EXPECT_NEAR(profile.step(63*sec,379.999),20/3.6,1e-14);
    EXPECT_FALSE(profile.stop_ns());
    EXPECT_DOUBLE_EQ(profile.step(64*sec,380),20/3.6);
    EXPECT_EQ(profile.stop_ns(),64*sec);
    EXPECT_DOUBLE_EQ(profile.requested_mps(20/3.6),0);
    EXPECT_DOUBLE_EQ(profile.step(68*sec,395),10/3.6);
    EXPECT_DOUBLE_EQ(profile.step(72*sec,402),0);
    FunctionalRig combined({1,42,7},99,PlantMode::ExternalSolverWork,true,80000);
    EXPECT_NO_THROW(combined.route_profile({{0,0},{5,0}},RouteProfile::CombinedV2));
}
TEST(M8CarlaRoute, ExtendedHorizonRequiresCombinedRouteBeforeObservation) {
    FunctionalRig wrong({1,42,7},99,PlantMode::ExternalSolverWork,true,80000);
    EXPECT_THROW(wrong.speed_profile(),std::runtime_error);
    EXPECT_THROW(wrong.route_profile({{0,0},{5,0}},RouteProfile::Straight30),std::runtime_error);
    EXPECT_THROW(wrong.observe({{1,42,7},domain,100,1,.01},{99,100,1000000000,{0,0,0,0}}),std::runtime_error);
    FunctionalRig short_rig({1,42,7},99,PlantMode::ExternalSolverWork,true,60000);
    EXPECT_THROW(short_rig.route_profile({{0,0},{5,0}},RouteProfile::Combined),std::runtime_error);
    FunctionalRig combined({1,42,7},99,PlantMode::ExternalSolverWork,true,80000);
    EXPECT_NO_THROW(combined.route_profile({{0,0},{5,0}},RouteProfile::Combined));
}
TEST(M8CarlaRoute, OriginalPoseAndWheelSupportAdmissionUntilStalePoseBlocksAdvance) {
    for(bool aware:{false,true}) {
    FunctionalRig rig({1,42,7},99,PlantMode::ExternalSolverWork,true,60000);
    std::vector<central::RoutePoint> route;
    for(int i=0;i<=720;++i)route.push_back({i*.5,0});
    rig.route_profile(route,RouteProfile::Curve30,aware);
    std::unique_ptr<m7_native::Admission> admission;
    m7_native::Output prior;Time previous=0;unsigned controls=0;
    for(unsigned i=0;i<=200;++i) {
        const double seconds=3.997146773152053+i*.009999999776482582;
        const auto now=static_cast<Time>(std::llround(seconds*1e9));
        const Observation o{{1,42,7},domain,100+i,seconds,.01};
        const WheelSample wheel{99,100+i,now,{0,0,0,0}};
        rig.pose({42,100+i,now-(i==200?10*ms:0),0,0,0},99);
        m7_external::SolverWork w;
        if(i) {
            w.frame=100+i;w.begin=previous;w.end=now;w.oldest=prior.empty?previous:prior.oldest_actuator;
            w.torque=prior.torque;w.dt=double(.01f*(1.f/320.f));w.wheel={0,{7,99+i,previous},previous};
        }
        if(i==200) {EXPECT_THROW(rig.observe(o,wheel,w),std::runtime_error);break;}
        const auto r=i?rig.observe(o,wheel,w):rig.observe(o,wheel);
        if(!admission)admission=std::make_unique<m7_native::Admission>(42,now);
        const auto& e=*r.native_export;m7_native::Input in;
        in.observed=e.observed;in.enable=e.enable;in.normal=e.normal;in.actual=e.actual;in.commands=e.commands;
        in.release=e.release;in.credit=e.credit;in.permission=e.permission;
        in.service_mask=r.service_mask;in.credit_mask=r.credit_mask;in.release_mask=r.release_mask;
        ASSERT_TRUE(admission->accept(in,now,prior))<<admission->error();
        if(r.speed_control) {
            ASSERT_TRUE(r.lateral_control);++controls;
            EXPECT_DOUBLE_EQ(r.lateral_control->curvature_inv_m,0);
            EXPECT_LE(r.lateral_control->source_ns,r.speed_control->release_ns);
        }
        previous=now;
    }
    EXPECT_GT(controls,50U);
    }
}
TEST(M8CarlaRoute, MissingPoseAndUnboundActorRejected) {
    FunctionalRig rig({1,42,7},99,PlantMode::ExternalSolverWork,true,60000);
    rig.route_profile({{0,0},{5,0}});
    EXPECT_THROW(rig.pose({42,100,1000000000,0,0,0},98),std::runtime_error);
    EXPECT_THROW(rig.observe({{1,42,7},domain,100,1,.01},{99,100,1000000000,{0,0,0,0}}),std::runtime_error);
}
} // namespace
} // namespace stratadrive::m7_functional
