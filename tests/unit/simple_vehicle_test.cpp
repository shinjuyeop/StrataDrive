#include "simple_vehicle.hpp"
#include "torque_response.hpp"
#include "brake_pressure_response.hpp"
#include <gtest/gtest.h>
#include <cmath>
#include <limits>
using namespace stratadrive;
using namespace stratadrive::simulation;
namespace {
constexpr std::uint64_t ms=1000000;
VehicleActual actual(std::uint64_t ns,double torque=300,double pressure=0,double angle=0){
    battery::ModelIdentity id{7,static_cast<std::uint32_t>(ns/ms),ns};return {{torque,id,ns},{pressure,id,ns},{angle,id,ns}};
}
SimpleVehicleConfig ideal(){SimpleVehicleConfig c;c.rolling_n=0;c.drag_n_per_mps2=0;return c;}
TEST(SimpleVehicle,AnalyticConstantTorqueWorkAndGeometry){
    SimpleVehicle v(ideal());ASSERT_TRUE(v.initialize(7,0));
    for(unsigned i=0;i<1000;++i)ASSERT_EQ(v.step(i*ms,(i+1)*ms,actual(i*ms)),VehicleFault::None);
    EXPECT_NEAR(v.state().speed_mps,1,1e-12);EXPECT_NEAR(v.state().x_m,.5,1e-12);
    EXPECT_DOUBLE_EQ(v.state().y_m,0);EXPECT_NEAR(v.state().motor_work_j,500,1e-8);
    EXPECT_NEAR(v.state().balance_error_j,0,1e-8);EXPECT_NEAR(v.wheel_speed_rad_s(),1/.3,1e-10);
}
TEST(SimpleVehicle,BrakeStopsWithinStepWithoutReverseOrExtraWork){
    SimpleVehicle v(ideal());ASSERT_TRUE(v.initialize(7,0,.01));
    ASSERT_EQ(v.step(0,20*ms,actual(0,0,1500000)),VehicleFault::None);
    EXPECT_DOUBLE_EQ(v.state().speed_mps,0);EXPECT_NEAR(v.state().distance_m,.00001,1e-12);
    EXPECT_NEAR(v.state().friction_work_j,.05,1e-12);EXPECT_NEAR(v.state().balance_error_j,0,1e-12);
    ASSERT_EQ(v.step(20*ms,40*ms,actual(20*ms,-200,1500000)),VehicleFault::None);
    EXPECT_NEAR(v.state().distance_m,.00001,1e-12);
}
TEST(SimpleVehicle,CoastAndRegenerationRemoveKineticEnergy){
    SimpleVehicle v;ASSERT_TRUE(v.initialize(7,0,5));
    ASSERT_EQ(v.step(0,10*ms,actual(0,0)),VehicleFault::None);EXPECT_LT(v.state().speed_mps,5);
    ASSERT_EQ(v.step(10*ms,20*ms,actual(10*ms,-100)),VehicleFault::None);
    EXPECT_LT(v.state().motor_work_j,0);EXPECT_GT(v.state().road_work_j,0);EXPECT_NEAR(v.state().balance_error_j,0,1e-8);
}
TEST(SimpleVehicle,ExactCircleUsesActualSteeringRearAxleReference){
    SimpleVehicle v(ideal());ASSERT_TRUE(v.initialize(7,0,3));
    for(unsigned i=0;i<1000;++i)ASSERT_EQ(v.step(i*ms,(i+1)*ms,actual(i*ms,0,0,.2)),VehicleFault::None);
    const double k=std::tan(.2)/2.7;EXPECT_NEAR(v.state().yaw_rad,3*k,1e-11);
    EXPECT_NEAR(v.state().x_m,std::sin(3*k)/k,1e-10);EXPECT_NEAR(v.state().y_m,(1-std::cos(3*k))/k,1e-10);
}
TEST(SimpleVehicle,RejectsBadTimeIdentityAndValueWithoutStateCommit){
    SimpleVehicle v;ASSERT_TRUE(v.initialize(7,100*ms,1));
    auto check=[&](VehicleActual a,VehicleFault f){EXPECT_EQ(v.step(100*ms,102*ms,a),f);EXPECT_EQ(v.state().identity.sequence,0U);EXPECT_DOUBLE_EQ(v.state().speed_mps,1);};
    auto a=actual(100*ms);a.torque.identity.epoch=8;check(a,VehicleFault::Identity);
    a=actual(103*ms);check(a,VehicleFault::Timestamp);
    a=actual(70*ms);check(a,VehicleFault::Stale);
    a=actual(100*ms);a.pressure.input_time_ns=89*ms;check(a,VehicleFault::Skew);
    a=actual(100*ms);a.steering.value=std::numeric_limits<double>::quiet_NaN();check(a,VehicleFault::Value);
    a=actual(100*ms);a.pressure.value=-1;check(a,VehicleFault::Value);
    EXPECT_EQ(v.step(100*ms,121*ms,actual(100*ms)),VehicleFault::Timing);
    EXPECT_EQ(v.step(99*ms,100*ms,actual(99*ms)),VehicleFault::Timing);
}
TEST(SimpleVehicle,CachedAcquisitionCannotMutateOrRefreshSource){
    SimpleVehicle v;ASSERT_TRUE(v.initialize(7,0));const auto a=actual(0);
    ASSERT_EQ(v.step(0,ms,a),VehicleFault::None);ASSERT_EQ(v.step(ms,2*ms,a),VehicleFault::None);
    auto bad=a;bad.torque.value=299;EXPECT_EQ(v.step(2*ms,3*ms,bad),VehicleFault::Identity);
    bad=a;bad.torque.identity.source_time_ns=ms;EXPECT_EQ(v.step(2*ms,3*ms,bad),VehicleFault::Identity);
    EXPECT_EQ(v.state().identity.source_time_ns,2*ms);
}
TEST(SimpleVehicle,ScenarioStateCannotBeResetByNewEcuEpoch){
    SimpleVehicle v;ASSERT_TRUE(v.initialize(7,0));ASSERT_EQ(v.step(0,10*ms,actual(0)),VehicleFault::None);
    const auto before=v.state();EXPECT_FALSE(v.initialize(8,11*ms));
    EXPECT_EQ(v.state().identity.epoch,7U);EXPECT_EQ(v.state().distance_m,before.distance_m);
}
TEST(SimpleVehicle,ActualActuatorDelayAndProtectionRampReachVehicle){
    TorqueResponse motor({-200,300,0,1000,3000,50*ms});motor.begin(0);ASSERT_TRUE(motor.set_target(300,0));
    BrakePressureResponse brake({1500000,0,5000000,10000000,50*ms,7});ASSERT_TRUE(brake.begin(0));
    SimpleVehicle v(ideal());ASSERT_TRUE(v.initialize(7,0));
    for(unsigned i=0;i<1000;++i){
        const auto t=i*ms;
        ASSERT_EQ(v.step(t,t+ms,actual(t,motor.actual_nm(),brake.actual_pressure_pa())),VehicleFault::None);
        ASSERT_TRUE(motor.advance(t+ms));ASSERT_TRUE(brake.advance(t+ms));
        if(i==40){EXPECT_DOUBLE_EQ(v.state().speed_mps,0);} // command is not actual
        if(i==400){EXPECT_GT(v.state().speed_mps,.1);motor.request_zero(t+ms);ASSERT_TRUE(brake.request_protection(1000000,t+ms));}
    }
    EXPECT_DOUBLE_EQ(v.state().speed_mps,0);EXPECT_GT(v.state().friction_work_j,0);EXPECT_NEAR(v.state().balance_error_j,0,1e-8);
}
TEST(SimpleVehicle,StepHalvingBoundsTheDeclaredFrozenRoadForceApproximation){
    SimpleVehicle coarse,fine;ASSERT_TRUE(coarse.initialize(7,0,10));ASSERT_TRUE(fine.initialize(7,0,10));
    for(unsigned i=0;i<500;++i)ASSERT_EQ(coarse.step(i*2*ms,(i+1)*2*ms,actual(i*2*ms)),VehicleFault::None);
    for(unsigned i=0;i<1000;++i)ASSERT_EQ(fine.step(i*ms,(i+1)*ms,actual(i*ms)),VehicleFault::None);
    EXPECT_NEAR(coarse.state().speed_mps,fine.state().speed_mps,1e-5);
    EXPECT_NEAR(coarse.state().distance_m,fine.state().distance_m,1e-5);
}
TEST(SimpleVehicle,InvalidConfigurationAndUninitializedAreRejected){
    auto c=ideal();c.mass_kg=0;EXPECT_THROW(SimpleVehicle{c},std::invalid_argument);
    SimpleVehicle v;EXPECT_EQ(v.step(0,ms,actual(0)),VehicleFault::Uninitialized);
    EXPECT_FALSE(v.initialize(0,0));EXPECT_FALSE(v.initialize(7,0,-1));
}
}
