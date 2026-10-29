#include "sdk_scene.hpp"
#include "nodrive_port.hpp"
#include "wheel_contract.hpp"
#include <gtest/gtest.h>
#include <cstdlib>
#include <fstream>
#include <iomanip>

namespace {
using namespace stratadrive;
using namespace m7_nodrive;
constexpr Time start=1000000000;
Time at(unsigned frame) {return start+frame*10*ms;}
struct ActualFixture {
    can::SteeringTxState st{can::SteeringFrameKind::Actual};
    can::BrakeTxState bt{can::BrakeFrameKind::Actual};
    can::DriveTxState dt{can::DriveFrameKind::Actual};
    Frames frames(unsigned frame,double torque,double pressure=0,double angle=0) {
        can::SteeringMessage s;s.kind=can::SteeringFrameKind::Actual;s.epoch=1;s.sequence=frame;s.source_time_ns=at(frame);
        s.causal_sequence=frame;s.local_state=can::ActuatorLocalState::Normal;s.origin=can::ActuatorOrigin::NormalPath;s.angle_rad=angle;
        can::BrakeMessage b;b.kind=can::BrakeFrameKind::Actual;b.epoch=1;b.sequence=frame;b.source_time_ns=at(frame);
        b.causal_sequence=frame;b.local_state=can::ActuatorLocalState::Normal;b.origin=can::ActuatorOrigin::NormalPath;b.pressure_pa=pressure;
        can::DriveMessage d;d.kind=can::DriveFrameKind::Actual;d.epoch=1;d.sequence=frame;d.source_time_ns=at(frame);
        d.causal_sequence=frame;d.local_state=can::ActuatorLocalState::Normal;d.origin=can::ActuatorOrigin::NormalPath;d.torque_nm=torque;
        return {can::encode_steering_frame(s,st),can::encode_brake_frame(b,bt),can::encode_drive_frame(d,dt)};
    }
    Provenance support(unsigned frame) {
        const auto t=at(frame);return {1,10,7,{{{Role::Steering,t,t+60*ms},{Role::Brake,t,t+60*ms},{Role::Drive,t,t+60*ms}}}};
    }
};
class NoDrive : public testing::Test {
protected:
    Scene scene;
    Port port{scene.vehicle(),scene.definition(),Scene::order,[this]{return scene.step();}};
    Boundary boundary{port};std::unique_ptr<Boundary::Writer> writer=boundary.claim();ActualFixture actual;
    std::uint64_t ticket=0;
    void SetUp() override {ASSERT_TRUE(scene.errors.messages.empty());ASSERT_TRUE(writer);ASSERT_EQ(boundary.start(*writer,1,7,1,10,start),Code::Ok);}
    void TearDown() override {EXPECT_TRUE(scene.errors.messages.empty());}
    void stage(unsigned frame,double torque,double pressure=0,double angle=0) {
        ASSERT_EQ(boundary.receive(*writer,actual.frames(frame,torque,pressure,angle),actual.support(frame),at(frame)),Code::Ok);
        ASSERT_EQ(boundary.prepare(*writer,Mode::FakeProbe,{frame,at(frame),at(frame+1)},at(frame),ticket),Code::Ok);
        ASSERT_EQ(boundary.commit(*writer,ticket,at(frame)),Code::Ok);
    }
    void advance(unsigned frame) {
        ASSERT_EQ(boundary.advance(*writer,ticket,frame,at(frame)),Code::Ok)<<port.error();
    }
    void expect_cleared() {
        for(unsigned w=0;w<4;++w) {EXPECT_EQ(scene.vehicle().getDriveTorque(w),0);EXPECT_EQ(scene.vehicle().getBrakeTorque(w),0);EXPECT_EQ(scene.vehicle().getSteerAngle(w),0);}
    }
};
TEST_F(NoDrive, StageIsNotPhysicsAndOneTickConsumesAndClearsAllPersistentInputs) {
    stage(1,100,100000,.1);expect_cleared();EXPECT_EQ(scene.ticks,0U);EXPECT_FALSE(port.observation());
    advance(1);ASSERT_TRUE(port.observation());const auto& r=*port.observation();
    EXPECT_EQ(r.applied.motor_nm,m7_effort::Four({0,0,50,50}));
    EXPECT_EQ(r.applied.friction_nm,m7_effort::Four({1000,1000,1000,1000}));
    EXPECT_LT(r.applied.steer_right_rad[0],0);EXPECT_FALSE(r.interval_work_valid);
    EXPECT_EQ(r.actual.drive.source_time_ns,at(1));EXPECT_EQ(r.actual.provenance.support[2].oldest,at(1));
    EXPECT_EQ(scene.ticks,1U);expect_cleared();
    EXPECT_EQ(boundary.advance(*writer,ticket,1,at(1)),Code::Ticket);EXPECT_EQ(scene.ticks,1U);
}
TEST_F(NoDrive, SameVehicleCannotHaveASecondPortOrBoundaryWriter) {
    EXPECT_THROW((Port{scene.vehicle(),scene.definition(),Scene::order,[]{return true;}}),std::invalid_argument);
    Boundary second(port);EXPECT_FALSE(second.claim());EXPECT_FALSE(boundary.claim());
}
TEST_F(NoDrive, MissingStageDoesNotAdvancePhysics) {
    EXPECT_EQ(boundary.advance(*writer,123,1,at(1)),Code::Ticket);EXPECT_EQ(scene.ticks,0U);expect_cleared();
}
TEST_F(NoDrive, DelayedTickDoesNotApplyStagedEffortOrRestampItsSource) {
    stage(1,100);EXPECT_EQ(boundary.advance(*writer,ticket,1,at(2)),Code::Time);
    EXPECT_EQ(scene.ticks,0U);EXPECT_FALSE(port.observation());expect_cleared();
}
TEST_F(NoDrive, PauseClearsPendingAndNeedsNewInit) {
    stage(1,100);port.pause();expect_cleared();
    EXPECT_EQ(boundary.advance(*writer,ticket,1,at(1)),Code::TickAmbiguous);EXPECT_EQ(scene.ticks,0U);
    EXPECT_FALSE(port.observation());
}
TEST_F(NoDrive, UnownedSdkWriteIsDetectedBeforePhysics) {
    stage(1,100);scene.vehicle().setDriveTorque(0,1); // explicit negative injection
    EXPECT_EQ(boundary.advance(*writer,ticket,1,at(1)),Code::TickAmbiguous);
    EXPECT_EQ(scene.ticks,0U);EXPECT_FALSE(port.observation());expect_cleared();
}
TEST_F(NoDrive, CommandFrameIsNotAnActuatorActual) {
    auto frames=actual.frames(1,100);can::DriveMessage command;command.kind=can::DriveFrameKind::Command;
    command.epoch=1;command.source_time_ns=at(1);command.torque_nm=100;
    can::DriveTxState tx{can::DriveFrameKind::Command};frames.drive=can::encode_drive_frame(command,tx);
    EXPECT_EQ(boundary.receive(*writer,frames,actual.support(1),at(1)),Code::Receiver);EXPECT_EQ(scene.ticks,0U);expect_cleared();
}
TEST_F(NoDrive, WrongWheelBindingIsRejected) {
    // Rejected before attempting the duplicate owner claim.
    EXPECT_THROW((Port{scene.vehicle(),scene.definition(),{0,1,1,3},[]{return true;}}),std::invalid_argument);
    EXPECT_GT(scene.definition().wheelbase_m,0);EXPECT_GT(scene.definition().front_track_m,0);
}
TEST_F(NoDrive, SignedReverseOmegaIsPreservedAndNeverClamped) {
    stage(1,-100);advance(1);ASSERT_TRUE(port.observation());
    EXPECT_LT(port.observation()->omega[2],0);EXPECT_LT(port.observation()->omega[3],0);
    // This deliberately out-of-ODD SDK vector does NOT enter native LocalSensors.
}
TEST_F(NoDrive, CoarseSolverNegativeWheelStopsBeforeNextPhysicsTick) {
    scene.vehicle().mWheelsSimData.setSubStepCount(5,3,3);
    unsigned fault_frame=0;
    for(unsigned f=1;f<=200;++f) {
        stage(f,f<=100?0:300,f<=100?100000:0);ASSERT_FALSE(HasFatalFailure());
        advance(f);ASSERT_FALSE(HasFatalFailure());ASSERT_TRUE(port.observation());
        const auto assessment=m7_external::assess(port.observation()->omega);
        if(!assessment.forward_rad_s) {
            EXPECT_EQ(assessment.validity,m7_external::WheelValidity::ReverseOrMixed);
            fault_frame=f;port.pause();break; // invalidate, do not manufacture zero
        }
    }
    ASSERT_GT(fault_frame,0U);EXPECT_EQ(scene.ticks,fault_frame);expect_cleared();
    const unsigned next=fault_frame+1;
    ASSERT_EQ(boundary.receive(*writer,actual.frames(next,300),actual.support(next),at(next)),Code::Ok);
    ASSERT_EQ(boundary.prepare(*writer,Mode::FakeProbe,{next,at(next),at(next+1)},at(next),ticket),Code::Ok);
    EXPECT_EQ(boundary.commit(*writer,ticket,at(next)),Code::ApplyRejected);
    EXPECT_EQ(scene.ticks,fault_frame);
}
TEST_F(NoDrive, LeftActualSteersTheFrontAxleToLeftTrajectory) {
    for(unsigned f=1;f<=500;++f) {
        stage(f,f<=100?0:300,f<=100?100000:0,f<=100?0:.1);ASSERT_FALSE(HasFatalFailure());
        advance(f);ASSERT_FALSE(HasFatalFailure());
    }
    EXPECT_LT(scene.vehicle().getRigidDynamicActor()->getGlobalPose().p.x,-.01);
    EXPECT_GT(scene.vehicle().getRigidDynamicActor()->getGlobalPose().p.z,1);
}
TEST_F(NoDrive, RightActualSteersTheFrontAxleToRightTrajectory) {
    for(unsigned f=1;f<=500;++f) {
        stage(f,f<=100?0:300,f<=100?100000:0,f<=100?0:-.1);ASSERT_FALSE(HasFatalFailure());
        advance(f);ASSERT_FALSE(HasFatalFailure());
    }
    EXPECT_GT(scene.vehicle().getRigidDynamicActor()->getGlobalPose().p.x,.01);
    EXPECT_GT(scene.vehicle().getRigidDynamicActor()->getGlobalPose().p.z,1);
}
TEST_F(NoDrive, ActualFixtureHoldAccelerateRegenerateAndStopOnRealSdkPlane) {
    std::ofstream trace;
    if(const char* path=std::getenv("M7_NODRIVE_TRACE")) {
        trace.open(path);ASSERT_TRUE(trace.is_open());trace<<std::setprecision(17);
        trace<<"frame,begin_ns,end_ns,source_ns,oldest_ns,torque_nm,pressure_pa,motor_rl_nm,motor_rr_nm,friction_fl_nm,friction_fr_nm,friction_rl_nm,friction_rr_nm,omega_fl,omega_fr,omega_rl,omega_rr,forward_m_s,z_m,sleeping,air_fl,air_fr,air_rl,air_rr,work_valid,low_substeps,high_substeps\n";
    }
    double acceleration_end=0,regen_end=0;unsigned negative_samples=0;
    for(unsigned f=1;f<=850;++f) {
        const double torque=f<=100?0:(f<=500?300:(f<=650?-150:0));
        const double pressure=(f<=100 || f>650)?100000:0;
        stage(f,torque,pressure);ASSERT_FALSE(HasFatalFailure());advance(f);ASSERT_FALSE(HasFatalFailure());
        ASSERT_TRUE(port.observation());const auto& r=*port.observation();
        const auto body=scene.vehicle().getRigidDynamicActor();const auto air=scene.in_air();
        const double speed=body->getLinearVelocity().z;
        ASSERT_TRUE(std::isfinite(speed));
        if(f==500)acceleration_end=speed;
        if(f==650)regen_end=speed;
        if(r.omega[2]<0 || r.omega[3]<0)++negative_samples;
        if(f<=100 || f>=750) {EXPECT_EQ(r.omega[2],0)<<f;EXPECT_EQ(r.omega[3],0)<<f;}
        EXPECT_FALSE(r.interval_work_valid);expect_cleared();
        if(trace.is_open()) {
            trace<<f<<','<<r.interval.begin<<','<<r.interval.end<<','<<r.actual.drive.source_time_ns<<','
                 <<r.actual.provenance.support[2].oldest<<','<<torque<<','<<pressure<<','
                 <<r.applied.motor_nm[2]<<','<<r.applied.motor_nm[3];
            for(double v:r.applied.friction_nm)trace<<','<<v;
            for(double v:r.omega)trace<<','<<v;
            trace<<','<<speed<<','<<body->getGlobalPose().p.z<<','<<r.sleeping;
            for(bool v:air)trace<<','<<v;
            trace<<','<<r.interval_work_valid<<','<<scene.vehicle().mWheelsSimData.getLowForwardSpeedSubStepCount()
                 <<','<<scene.vehicle().mWheelsSimData.getHighForwardSpeedSubStepCount()<<'\n';
        }
    }
    EXPECT_GT(acceleration_end,1);EXPECT_GT(regen_end,0);EXPECT_LT(regen_end,acceleration_end);
    EXPECT_LT(std::abs(scene.vehicle().getRigidDynamicActor()->getLinearVelocity().z),.01);
    EXPECT_EQ(negative_samples,0U);EXPECT_EQ(scene.ticks,850U);EXPECT_EQ(port.completed_ticks(),850U);
}
TEST(NoDriveFault, AmbiguousStepClearsInputsWithoutClaimingObservation) {
    Scene scene;Port port(scene.vehicle(),scene.definition(),Scene::order,[&]{scene.step();return false;});
    Boundary b(port);auto w=b.claim();ActualFixture actual;std::uint64_t ticket=0;
    ASSERT_EQ(b.start(*w,1,7,1,10,start),Code::Ok);
    ASSERT_EQ(b.receive(*w,actual.frames(1,100),actual.support(1),at(1)),Code::Ok);
    ASSERT_EQ(b.prepare(*w,Mode::FakeProbe,{1,at(1),at(2)},at(1),ticket),Code::Ok);
    ASSERT_EQ(b.commit(*w,ticket,at(1)),Code::Ok);
    EXPECT_EQ(b.advance(*w,ticket,1,at(1)),Code::TickAmbiguous);EXPECT_EQ(scene.ticks,1U);
    EXPECT_FALSE(port.observation());EXPECT_EQ(port.completed_ticks(),0U);
    for(unsigned i=0;i<4;++i)EXPECT_EQ(scene.vehicle().getDriveTorque(i),0);
    EXPECT_EQ(b.advance(*w,ticket,1,at(1)),Code::TickAmbiguous);EXPECT_EQ(scene.ticks,1U);
}
TEST(NoDriveFault, StepExceptionClearsInputsAndCannotBeRetried) {
    Scene scene;Port port(scene.vehicle(),scene.definition(),Scene::order,[]()->bool {throw std::runtime_error("injected tick failure");});
    Boundary b(port);auto w=b.claim();ActualFixture actual;std::uint64_t ticket=0;
    ASSERT_EQ(b.start(*w,1,7,1,10,start),Code::Ok);
    ASSERT_EQ(b.receive(*w,actual.frames(1,100),actual.support(1),at(1)),Code::Ok);
    ASSERT_EQ(b.prepare(*w,Mode::FakeProbe,{1,at(1),at(2)},at(1),ticket),Code::Ok);
    ASSERT_EQ(b.commit(*w,ticket,at(1)),Code::Ok);
    EXPECT_EQ(b.advance(*w,ticket,1,at(1)),Code::TickAmbiguous);EXPECT_EQ(scene.ticks,0U);
    EXPECT_FALSE(port.observation());
    for(unsigned i=0;i<4;++i)EXPECT_EQ(scene.vehicle().getDriveTorque(i),0);
    EXPECT_EQ(b.advance(*w,ticket,1,at(1)),Code::TickAmbiguous);
}
} // namespace
