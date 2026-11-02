#include "pure_pursuit.hpp"
#include <gtest/gtest.h>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace stratadrive::central {
namespace {
constexpr std::uint64_t dt=20000000;
std::vector<RoutePoint> straight() {
    std::vector<RoutePoint> r;for(int i=0;i<=400;++i)r.push_back({i*.5,0});return r;
}
TEST(PurePursuit, StraightAndCorrectionSigns) {
    for(double offset:{-.02,0.,.02}) {
        PurePursuit p(straight(),2.86);ASSERT_TRUE(p.start_session(1,0));
        auto o=p.step(0,{1,0,0,0,offset,0},0);ASSERT_TRUE(o);
        EXPECT_DOUBLE_EQ(o->cross_track_m,offset);
        EXPECT_NEAR(o->curvature_inv_m, -2*offset/(16+offset*offset),1e-15);
    }
}
TEST(PurePursuit, CircleHasAnalyticCurvatureAndMirrors) {
    for(double sign:{-1.,1.}) {
        std::vector<RoutePoint> route;
        for(int i=0;i<=700;++i) {double a=i*.5/200;route.push_back({200*std::sin(a),sign*200*(1-std::cos(a))});}
        PurePursuit p(route,2.86);ASSERT_TRUE(p.start_session(1,0));
        const auto o=p.step(0,{1,1,0,0,0,0},30/3.6);ASSERT_TRUE(o);
        EXPECT_NEAR(o->curvature_inv_m,sign/200,1e-8);
        EXPECT_DOUBLE_EQ(o->lookahead_m,10);
    }
}
TEST(PurePursuit, AgeBoundaryAndFrozenSourceLatchUntilNewSession) {
    PurePursuit p(straight(),2.86);ASSERT_TRUE(p.start_session(1,0));
    ASSERT_TRUE(p.step(30000000,{1,1,0,0,0,0},0));
    EXPECT_FALSE(p.step(50000000,{1,2,0,0,0,0},0));EXPECT_TRUE(p.faulted());
    EXPECT_FALSE(p.step(70000000,{1,3,70000000,0,0,0},0));
    EXPECT_FALSE(p.start_session(1,70000000));ASSERT_TRUE(p.start_session(2,70000000));
    EXPECT_TRUE(p.step(70000000,{2,1,70000000,0,0,0},0));
}
TEST(PurePursuit, InvalidTimeIdentityGeometryAndInputsFailClosed) {
    for(int kind=0;kind<10;++kind) {
        PurePursuit p(straight(),2.86);ASSERT_TRUE(p.start_session(1,10));
        RoutePose pose{1,1,10,0,0,0};std::uint64_t now=10;double speed=0;
        switch(kind) {
            case 0:pose.epoch=2;break;case 1:pose.source_ns=11;break;
            case 2:pose.source_ns=9;break;case 3:now+=30000001;break;
            case 4:pose.x_m=3;break;case 5:pose.y_m=.301;break;
            case 6:pose.yaw_rad=.06;break;case 7:speed=-.01;break;
            case 8:pose.x_m=std::numeric_limits<double>::quiet_NaN();break;
            case 9:speed=12;break;
        }
        EXPECT_FALSE(p.step(now,pose,speed))<<kind;EXPECT_TRUE(p.faulted());
    }
}
TEST(PurePursuit, MissedTickDuplicateSequenceAndOffRouteAreRejected) {
    for(int kind=0;kind<3;++kind) {
        PurePursuit p(straight(),2.86);ASSERT_TRUE(p.start_session(1,0));
        ASSERT_TRUE(p.step(0,{1,1,0,0,0,0},0));
        RoutePose pose{1,2,dt,0,0,0};auto now=dt;
        if(kind==0)now+=dt;
        if(kind==1)pose.sequence=1;
        if(kind==2)pose.y_m=1.51;
        EXPECT_FALSE(p.step(now,pose,0));
    }
}
TEST(PurePursuit, RouteValidation) {
    EXPECT_THROW(PurePursuit({},2.86),std::invalid_argument);
    EXPECT_THROW(PurePursuit({{0,0},{0,0}},2.86),std::invalid_argument);
    EXPECT_THROW(PurePursuit({{0,0},{6,0}},2.86),std::invalid_argument);
    EXPECT_THROW(PurePursuit(straight(),0),std::invalid_argument);
    EXPECT_THROW(PurePursuit({{0,0},{1,std::numeric_limits<double>::infinity()}},2.86),std::invalid_argument);
}
TEST(PurePursuit, AngleSaturationAndSlewAreActiveInBothDirections) {
    for(double sign:{-1.,1.}) {
        PurePursuit p(straight(),2.86);ASSERT_TRUE(p.start_session(1,0));
        ASSERT_TRUE(p.step(0,{1,0,0,0,0,0},0));
        for(unsigned i=1;i<=20;++i) {
            const auto o=p.step(i*dt,{1,i,i*dt,0,sign,0},0);ASSERT_TRUE(o);
            EXPECT_NEAR(std::atan(2.86*o->curvature_inv_m),-sign*std::min(.02*i,.3),1e-14);
            EXPECT_TRUE(o->limited);
        }
    }
}
TEST(PurePursuit, HeadingWrapAndBackwardProgress) {
    auto route=straight();for(auto& point:route)point.x_m=-point.x_m;
    PurePursuit p(route,2.86);ASSERT_TRUE(p.start_session(1,0));
    constexpr double pi=3.14159265358979323846;
    ASSERT_TRUE(p.step(0,{1,0,0,0,0,pi},1));
    const auto o=p.step(dt,{1,1,dt,-1,0,-pi},1);ASSERT_TRUE(o);
    EXPECT_NEAR(o->heading_error_rad,0,1e-14);
    EXPECT_FALSE(p.step(2*dt,{1,2,2*dt,0,0,pi},1));
}
TEST(PurePursuit, KinematicCurveTrackingPreservesTwentyMillisecondContract) {
    std::vector<RoutePoint> route;
    for(int i=0;i<=1000;++i) {double a=i*.5/200;route.push_back({200*std::sin(a),200*(1-std::cos(a))});}
    PurePursuit p(route,2.86);ASSERT_TRUE(p.start_session(1,0));
    double x=0,y=.1,yaw=0,angle=0;
    for(unsigned i=0;i<1800;++i) {
        auto o=p.step(i*dt,{1,i,i*dt,x,y,yaw},30/3.6);ASSERT_TRUE(o)<<i;
        EXPECT_LT(std::abs(o->cross_track_m),.3);EXPECT_LT(std::abs(o->heading_error_rad),.053);
        const double next=std::atan(2.86*o->curvature_inv_m);
        EXPECT_LE(std::abs(next-angle),.02000000001);angle=next;
        x+=30/3.6*.02*std::cos(yaw);y+=30/3.6*.02*std::sin(yaw);yaw+=30/3.6*.02*o->curvature_inv_m;
    }
}
} // namespace
} // namespace stratadrive::central
