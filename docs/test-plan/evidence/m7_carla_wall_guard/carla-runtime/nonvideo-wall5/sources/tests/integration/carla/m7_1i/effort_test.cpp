#include "wheel_effort.hpp"
#include "actual_boundary.hpp"
#include <gtest/gtest.h>
#include <limits>

namespace {
using namespace stratadrive;
using namespace m7_effort;
// Synthetic mathematical vectors ONLY. No real CARLA calibration is supplied.
Definition fixture() {
    return {2.8,1.6,{1.2,1.2,0,0},{0,0,150,150},{800,800,800,800},
        {{0,{0,0,0,0}}, {100000,{10,10,5,5}}, {300000,{50,50,20,20}}}};
}
TEST(M7EffortMath, StraightZeroAndSignedMotorRemainDistinctFromFriction) {
    Mapping m(fixture());
    auto zero=m.map(0,0,0);ASSERT_TRUE(zero.effort);
    EXPECT_EQ(zero.effort->steer_right_rad,Four({0,0,0,0}));
    EXPECT_EQ(zero.effort->motor_nm,Four({0,0,0,0}));
    EXPECT_EQ(zero.effort->friction_nm,Four({0,0,0,0}));
    for (double torque:{-200.,300.}) {
        auto r=m.map(0,torque,100000);ASSERT_TRUE(r.effort);
        EXPECT_EQ(r.effort->motor_nm,Four({0,0,torque/2,torque/2}));
        EXPECT_EQ(r.effort->friction_nm,Four({10,10,5,5}));
    }
}
TEST(M7EffortMath, AckermannWheelAxesShareTheEquivalentInstantaneousCentre) {
    Mapping m(fixture());
    for (double angle:{-.3,-.1,-1e-9,1e-9,.1,.3}) {
        auto r=m.map(angle,0,0);ASSERT_TRUE(r.effort);
        // Independent geometric invariant: each wheel's normal intersects the
        // same rear-axle point as the equivalent bicycle wheel.
        const double radius=2.8/std::tan(angle);
        const double from_left=.8+2.8/std::tan(-r.effort->steer_right_rad[0]);
        const double from_right=-.8+2.8/std::tan(-r.effort->steer_right_rad[1]);
        EXPECT_NEAR(from_left/radius,1,1e-14);EXPECT_NEAR(from_right/radius,1,1e-14);
        EXPECT_EQ(r.effort->steer_right_rad[2],0);EXPECT_EQ(r.effort->steer_right_rad[3],0);
    }
}
TEST(M7EffortMath, LeftTurnIsNegativeCarlaSteerAndInnerWheelTurnsFurther) {
    Mapping m(fixture());auto left=m.map(.2,0,0),right=m.map(-.2,0,0);
    ASSERT_TRUE(left.effort);ASSERT_TRUE(right.effort);
    EXPECT_LT(left.effort->steer_right_rad[0],left.effort->steer_right_rad[1]);
    EXPECT_LT(left.effort->steer_right_rad[1],0);
    EXPECT_DOUBLE_EQ(left.effort->steer_right_rad[0],-right.effort->steer_right_rad[1]);
    EXPECT_DOUBLE_EQ(left.effort->steer_right_rad[1],-right.effort->steer_right_rad[0]);
}
TEST(M7EffortMath, BrakeUsesExplicitPerWheelPiecewiseTableWithoutExtrapolation) {
    Mapping m(fixture());
    auto mid=m.map(0,0,200000);ASSERT_TRUE(mid.effort);
    EXPECT_EQ(mid.effort->friction_nm,Four({30,30,12.5,12.5}));
    for (const auto& knot:fixture().friction) {
        auto r=m.map(0,0,knot.pressure_pa);ASSERT_TRUE(r.effort);
        EXPECT_EQ(r.effort->friction_nm,knot.torque_nm);
    }
    EXPECT_EQ(m.map(0,0,300001).error,Error::PressureRange);
    EXPECT_FALSE(m.map(0,0,300001).effort);
}
TEST(M7EffortMath, EqualRearTorqueIsPowerConjugateToArithmeticMeanWheelSpeed) {
    Mapping m(fixture());
    for (double torque:{-200.,0.,25.,300.}) {
        auto r=m.map(0,torque,0);ASSERT_TRUE(r.effort);
        const Four omega{11,13,7,19};
        const double per_wheel=r.effort->motor_nm[2]*omega[2]+r.effort->motor_nm[3]*omega[3];
        EXPECT_DOUBLE_EQ(per_wheel,torque*((omega[2]+omega[3])/2));
    }
    // A torque-vectoring allocation cannot reuse the mean for electrical work.
    EXPECT_NE(100*.25*7+100*.75*19,100*((7.+19)/2));
}
TEST(M7EffortMath, RejectsLimitsWithoutSilentSaturation) {
    Mapping m(fixture());
    for (double torque:{-301.,301.}) {
        EXPECT_EQ(m.map(0,torque,0).error,Error::DriveLimit);EXPECT_FALSE(m.map(0,torque,0).effort);
    }
    EXPECT_EQ(m.map(1.1,0,0).error,Error::SteeringLimit);
    EXPECT_EQ(m.map(1.5,0,0).error,Error::Geometry);
}
TEST(M7EffortMath, RejectsNonfiniteAndInvalidPhysicalValues) {
    Mapping m(fixture());
    for (double x:{std::numeric_limits<double>::quiet_NaN(),std::numeric_limits<double>::infinity(),
                   -std::numeric_limits<double>::infinity()}) {
        EXPECT_FALSE(m.map(x,0,0).effort);EXPECT_FALSE(m.map(0,x,0).effort);EXPECT_FALSE(m.map(0,0,x).effort);
    }
    EXPECT_FALSE(m.map(0,0,-1e-12).effort);EXPECT_FALSE(m.map(2,0,0).effort);
}
TEST(M7EffortMath, MissingOrInvalidCalibrationHasNoDefaultGain) {
    for (unsigned fault=0;fault<12;++fault) {
        auto d=fixture();
        if(fault==0)d.friction.clear();
        if(fault==1)d.friction.resize(1);
        if(fault==2)d.wheelbase_m=0;
        if(fault==3)d.front_track_m=std::numeric_limits<double>::quiet_NaN();
        if(fault==4)d.friction[1].pressure_pa=0;
        if(fault==5)d.friction[0].torque_nm[0]=1;
        if(fault==6)d.friction[2].torque_nm[0]=9;
        if(fault==7)d.friction[1].torque_nm[0]=801;
        if(fault==8)d.friction[2].pressure_pa=std::numeric_limits<double>::infinity();
        if(fault==9)d.steer_limit_rad[0]=2;
        if(fault==10)d.drive_limit_nm[2]=0;
        if(fault==11)d.brake_limit_nm[1]=-1;
        EXPECT_THROW(Mapping{d},std::invalid_argument)<<fault;
    }
}
TEST(M7EffortMath, MappingOwnsItsImmutableDefinition) {
    auto d=fixture();Mapping m(d);d.friction[1].torque_nm[0]=700;
    auto r=m.map(0,0,100000);ASSERT_TRUE(r.effort);EXPECT_EQ(r.effort->friction_nm[0],10);
}
TEST(M7EffortMath, WheelMaximumBrakeTorqueCannotIdentifyPressureCalibration) {
    auto first=fixture(),second=fixture();
    for(auto& knot:second.friction)for(double& torque:knot.torque_nm)torque*=2;
    Mapping a(first),b(second);
    auto x=a.map(0,0,100000),y=b.map(0,0,100000);ASSERT_TRUE(x.effort);ASSERT_TRUE(y.effort);
    EXPECT_EQ(first.brake_limit_nm,second.brake_limit_nm);
    EXPECT_NE(x.effort->friction_nm,y.effort->friction_nm);
}
TEST(M7EffortMath, CentimetreTorqueConversionUsesLengthSquaredAndRejectsOverflow) {
    auto r=torque_to_kg_cm2_s2({0,1,-2,800});ASSERT_TRUE(r);EXPECT_EQ(*r,Four({0,10000,-20000,8000000}));
    EXPECT_FALSE(torque_to_kg_cm2_s2({0,0,0,std::numeric_limits<double>::max()}));
    EXPECT_FALSE(torque_to_kg_cm2_s2({0,0,0,std::numeric_limits<double>::quiet_NaN()}));
}

using namespace m7_test;
constexpr Time start=1000000000;
Time t(unsigned ms_value) {return start+ms_value*ms;}
Provenance provenance() {return {1,10,7,{{{Role::Steering,t(10),t(70)},
    {Role::Brake,t(10),t(70)},{Role::Drive,t(10),t(70)}}}};}
Frames actual(bool commands=false,double pressure_pa=100000) {
    can::SteeringMessage s;s.kind=commands?can::SteeringFrameKind::Command:can::SteeringFrameKind::Actual;
    s.epoch=1;s.source_time_ns=t(10);s.causal_sequence=42;s.local_state=can::ActuatorLocalState::Normal;
    s.origin=can::ActuatorOrigin::NormalPath;s.angle_rad=.1;
    can::SteeringTxState st{s.kind};
    can::BrakeMessage b;b.kind=commands?can::BrakeFrameKind::Command:can::BrakeFrameKind::Actual;
    b.epoch=1;b.source_time_ns=t(10);b.causal_sequence=43;b.local_state=can::ActuatorLocalState::Normal;
    b.origin=can::ActuatorOrigin::NormalPath;b.pressure_pa=pressure_pa;
    can::BrakeTxState bt{b.kind};
    can::DriveMessage d;d.kind=commands?can::DriveFrameKind::Command:can::DriveFrameKind::Actual;
    d.epoch=1;d.source_time_ns=t(10);d.causal_sequence=44;d.local_state=can::ActuatorLocalState::Normal;
    d.origin=can::ActuatorOrigin::NormalPath;d.torque_nm=-100;
    can::DriveTxState dt{d.kind};
    return {can::encode_steering_frame(s,st),can::encode_brake_frame(b,bt),can::encode_drive_frame(d,dt)};
}
// Fake backend connected to the unchanged 1c Actual boundary. It has no CARLA
// handle or apply/tick API. These are local contract tests, not ECU/live evidence.
class FakeEffort final : public Backend {
public:
    Mapping mapping{fixture()};unsigned applies=0,ticks=0;
    std::optional<ActualBundle> observed;
    std::optional<Effort> effort;
private:
    ApplyResult apply(const ActualBundle& a,const Interval&) override {
        if (!a.steering.angle_rad || !a.drive.torque_nm || !a.brake.pressure_pa) return ApplyResult::Rejected;
        const auto r=mapping.map(*a.steering.angle_rad,*a.drive.torque_nm,*a.brake.pressure_pa);
        if (!r.effort) return ApplyResult::Rejected;
        observed=a;effort=r.effort;++applies;return ApplyResult::Applied;
    }
    bool tick(const Interval&) override {++ticks;return true;}
};
TEST(M7EffortBoundary, ActualFramesMapOnceAndRetainOriginalProvenance) {
    FakeEffort fake;Boundary b(fake);auto w=b.claim();ASSERT_TRUE(w);
    ASSERT_EQ(b.start(*w,1,7,1,10,start),Code::Ok);
    const auto frames=actual();ASSERT_EQ(b.receive(*w,frames,provenance(),t(12)),Code::Ok);
    std::uint64_t ticket=0;
    ASSERT_EQ(b.prepare(*w,Mode::FakeProbe,{1,t(12),t(20)},t(12),ticket),Code::Ok);
    ASSERT_EQ(b.commit(*w,ticket,t(12)),Code::Ok);ASSERT_TRUE(fake.effort);ASSERT_TRUE(fake.observed);
    EXPECT_EQ(fake.effort->motor_nm,Four({0,0,-50,-50}));EXPECT_EQ(fake.effort->friction_nm,Four({10,10,5,5}));
    EXPECT_EQ(fake.observed->drive.source_time_ns,t(10));EXPECT_EQ(fake.observed->drive.causal_sequence,44U);
    EXPECT_EQ(fake.observed->provenance.support[2].oldest,t(10));
    EXPECT_EQ(fake.observed->provenance.support[2].exclusive_expiry,t(70));
    EXPECT_EQ(fake.observed->original_frames.drive->payload,frames.drive->payload);
    ASSERT_EQ(b.advance(*w,ticket,1,t(12)),Code::Ok);
    EXPECT_EQ(b.commit(*w,ticket,t(12)),Code::Ticket);EXPECT_EQ(fake.applies,1U);EXPECT_EQ(fake.ticks,1U);
}
TEST(M7EffortBoundary, CommandCannotReachEffortMappingForAnyRole) {
    for(unsigned role=0;role<3;++role) {
        FakeEffort fake;Boundary b(fake);auto w=b.claim();ASSERT_EQ(b.start(*w,1,7,1,10,start),Code::Ok);
        auto f=actual();auto command=actual(true);
        if(role==0)f.steering=command.steering;
        if(role==1)f.brake=command.brake;
        if(role==2)f.drive=command.drive;
        EXPECT_EQ(b.receive(*w,f,provenance(),t(10)),Code::Receiver);
        EXPECT_FALSE(fake.effort);EXPECT_EQ(fake.applies,0U);EXPECT_EQ(fake.ticks,0U);
    }
}
TEST(M7EffortBoundary, OriginalDependencyMustCoverWholeInterval) {
    FakeEffort fake;Boundary b(fake);auto w=b.claim();ASSERT_EQ(b.start(*w,1,7,1,10,start),Code::Ok);
    ASSERT_EQ(b.receive(*w,actual(),provenance(),t(10)),Code::Ok);std::uint64_t ticket=0;
    EXPECT_EQ(b.prepare(*w,Mode::FakeProbe,{1,t(10),t(41)},t(10),ticket),Code::Coverage);
    EXPECT_EQ(fake.applies,0U);EXPECT_EQ(fake.ticks,0U);
}
TEST(M7EffortBoundary, MathematicalMappingCannotEnableCarlaDriving) {
    FakeEffort fake;Boundary b(fake);auto w=b.claim();ASSERT_EQ(b.start(*w,1,7,1,10,start),Code::Ok);
    ASSERT_EQ(b.receive(*w,actual(),provenance(),t(10)),Code::Ok);std::uint64_t ticket=0;
    EXPECT_EQ(b.prepare(*w,Mode::CarlaDriving,{1,t(10),t(20)},t(10),ticket),Code::Disabled);
    EXPECT_EQ(fake.applies,0U);EXPECT_EQ(fake.ticks,0U);
}
TEST(M7EffortBoundary, ValidWireActualOutsideCalibratedPressureRangeStopsBeforeTick) {
    FakeEffort fake;Boundary b(fake);auto w=b.claim();ASSERT_EQ(b.start(*w,1,7,1,10,start),Code::Ok);
    ASSERT_EQ(b.receive(*w,actual(false,500000),provenance(),t(10)),Code::Ok);std::uint64_t ticket=0;
    ASSERT_EQ(b.prepare(*w,Mode::FakeProbe,{1,t(10),t(20)},t(10),ticket),Code::Ok);
    EXPECT_EQ(b.commit(*w,ticket,t(10)),Code::ApplyRejected);
    EXPECT_EQ(b.advance(*w,ticket,1,t(10)),Code::ApplyRejected);
    EXPECT_EQ(fake.applies,0U);EXPECT_EQ(fake.ticks,0U);EXPECT_FALSE(fake.effort);
}
} // namespace
