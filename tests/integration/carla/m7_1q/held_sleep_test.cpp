#include "held_steer_sleep.hpp"
#include "solver_observer.inc"
#include <gtest/gtest.h>
#include <array>
#include <limits>
namespace {
using Wheels=std::array<double,4>;
const Wheels angle{-.06,-.05,0,0},drive{},brake{250,250,250,250};
bool hold(bool previous,bool current,const Wheels& a,const Wheels& d,const Wheels& b) {
    return stratadrive::m7_native::held_protection(previous,current,angle.data(),a.data(),drive.data(),d.data(),brake.data(),b.data());
}
TEST(M7HeldSleep, OnlyIdenticalCompletedProtectedHoldQualifies) {
    EXPECT_TRUE(hold(true,true,angle,drive,brake));
    EXPECT_FALSE(hold(false,true,angle,drive,brake));
    EXPECT_FALSE(hold(true,false,angle,drive,brake));
    EXPECT_FALSE(hold(false,false,angle,drive,brake));
    for(unsigned wheel=0;wheel<4;++wheel) {
        auto a=angle;auto d=drive;auto b=brake;
        a[wheel]+=1e-12;EXPECT_FALSE(hold(true,true,a,d,b));a=angle;
        d[wheel]=1e-12;EXPECT_FALSE(hold(true,true,a,d,b));
        d[wheel]=-1e-12;EXPECT_FALSE(hold(true,true,a,d,b));d=drive;
        b[wheel]-=1e-12;EXPECT_FALSE(hold(true,true,a,d,b));
        b[wheel]=0;EXPECT_FALSE(hold(true,true,a,d,b));
    }
}
TEST(M7HeldSleep, InvalidInputsCannotSuppressWake) {
    for(double bad:{std::numeric_limits<double>::infinity(),std::numeric_limits<double>::quiet_NaN()}) {
        auto a=angle;auto d=drive;auto b=brake;
        a[0]=bad;EXPECT_FALSE(hold(true,true,a,d,b));a=angle;
        d[2]=bad;EXPECT_FALSE(hold(true,true,a,d,b));d=drive;
        b[3]=bad;EXPECT_FALSE(hold(true,true,a,d,b));
    }
}
TEST(M7HeldSleep, SolverHookIsBoundSingleFrameAndDefaultsToOriginalWake) {
    int vehicle=0,other=0;
    EXPECT_FALSE(M7SolverKeepProtectedSteerSleep(&vehicle));
    M7SolverStart(&vehicle);
    EXPECT_TRUE(m7_steer_wakes(&vehicle));
    EXPECT_FALSE(M7SolverKeepProtectedSteerSleep(&other));
    EXPECT_TRUE(M7SolverKeepProtectedSteerSleep(&vehicle));
    EXPECT_FALSE(m7_steer_wakes(&vehicle));EXPECT_TRUE(m7_steer_wakes(&other));
    const float zeros[4]={};
    m7_step(&other,0,320,0,.00003125f,zeros,zeros,zeros,zeros,zeros,zeros);
    m7_begin(&vehicle,4,.01f);
    EXPECT_FALSE(M7SolverKeepProtectedSteerSleep(&vehicle));
    m7_end(&vehicle,true);
    const auto* trace=M7SolverFinish(&vehicle);ASSERT_TRUE(trace);
    EXPECT_EQ(trace->abi,2U);EXPECT_EQ(trace->protected_steer_hold,1U);EXPECT_EQ(trace->sleeping,1U);EXPECT_EQ(trace->count,0U);
    EXPECT_TRUE(m7_steer_wakes(&vehicle));
    M7SolverStart(&vehicle);EXPECT_TRUE(m7_steer_wakes(&vehicle));M7SolverFinish(&vehicle);
}
}
