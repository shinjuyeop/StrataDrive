#include "speed_supervisor.hpp"
#include "control_allocation.hpp"
#include "available_force_estimator.hpp"
#include "allocation_fixture.hpp"
#include <gtest/gtest.h>
#include <limits>
#include <algorithm>

using namespace stratadrive;
using namespace stratadrive::central;
namespace {
constexpr std::uint64_t ms=1000000, start=1000*ms, now=1100*ms;
AvailableForce force(std::uint64_t t=now) {return {1,t,t,t+30*ms+1,1000,3000,100,200};}
SpeedSample speed(std::uint64_t t=now,double value=2) {return {1,t,t,value};}
ClassicalSpeedProposal fallback(std::uint64_t t=now) {return {1,7,t,t+30*ms+1,2,true};}
PlannerProposal proposal(std::uint64_t t=now) {
    PlannerProposal p;p.epoch=1;p.clock_instance=7;p.sequence=t;p.model_revision=3;p.source_ns=t;p.expires_ns=t+30*ms+1;
    p.history_ns={t-60*ms,t-40*ms,t-20*ms,t};p.speed_mps.fill(2.5);p.speed_limit_mps=4;p.risk=.1;p.valid=true;return p;
}
can::DriveMessage actual(std::uint64_t t=now) {
    can::DriveMessage a;a.kind=can::DriveFrameKind::Actual;a.epoch=1;a.wheel_speed=can::DriveWheelSpeed{2/.3,t};return a;
}
TEST(AvailableForceReference, RobustIntersectionContainsEveryPossibleRoadLoad) {
    for(int sign:{-1,1}) {
        AvailableForceReference c;ASSERT_TRUE(c.start_session(1,start));
        const auto r=c.step(now,sign>0?8:0,speed(),force());ASSERT_TRUE(r);
        EXPECT_NEAR(r->minimum_acceleration_mps2,-2.8,1e-12);
        EXPECT_NEAR(r->maximum_acceleration_mps2,.7,1e-12);
        EXPECT_TRUE(r->limited);
        for(int load=100;load<=200;++load) {
            const double actuator=1000*r->acceleration_mps2+load;
            EXPECT_GE(actuator,-2700-1e-9);EXPECT_LE(actuator,900+1e-9);
        }
        EXPECT_NEAR(r->target_mps,2+(sign>0?.7:-2.8)*.02,1e-12);
    }
}
TEST(AvailableForceReference, DownhillReducesBrakingAndDeratingReducesAcceleration) {
    AvailableForceReference c;ASSERT_TRUE(c.start_session(1,start));auto f=force();f.road_load_min_n=-600;f.road_load_max_n=-500;
    auto r=c.step(now,0,speed(),f);ASSERT_TRUE(r);EXPECT_NEAR(r->minimum_acceleration_mps2,-2.1,1e-12);
    AvailableForceReference d;ASSERT_TRUE(d.start_session(1,start));f=force();f.propulsion_n=300;
    r=d.step(now,8,speed(),f);ASSERT_TRUE(r);EXPECT_NEAR(r->maximum_acceleration_mps2,.07,1e-12);
}
TEST(AvailableForceReference, CannotHoldSpeedWithAvailableForceRequiresProtection) {
    for(bool downhill:{false,true}) {
        AvailableForceReference c;ASSERT_TRUE(c.start_session(1,start));auto f=force();
        if(downhill){f.road_load_min_n=-4000;f.road_load_max_n=-3900;}else f.road_load_max_n=2000;
        EXPECT_FALSE(c.step(now,2,speed(),f));EXPECT_EQ(c.fault(),ReferenceFault::Capacity);
        EXPECT_FALSE(c.step(now+20*ms,2,speed(now+20*ms),force(now+20*ms)));
    }
}
TEST(AvailableForceReference, RejectsMalformedExpiredFutureAndWrongEpochInputs) {
    for(int mutation=0;mutation<10;++mutation) {
        AvailableForceReference c;ASSERT_TRUE(c.start_session(1,start));auto f=force();auto s=speed();
        switch(mutation) {
        case 0:f.propulsion_n=-1;break;case 1:f.braking_n=std::numeric_limits<double>::quiet_NaN();break;
        case 2:f.road_load_min_n=300;break;case 3:f.expires_ns=now;break;case 4:f.source_ns=now+1;break;
        case 5:f.source_ns=now-31*ms;break;case 6:f.epoch=2;break;case 7:s.source_ns=now+1;break;
        case 8:s.speed_mps=std::numeric_limits<double>::infinity();break;case 9:f.expires_ns=now+31*ms;break;
        }
        EXPECT_FALSE(c.step(now,3,s,f))<<mutation;
    }
}
TEST(AvailableForceReference, DuplicateMutationClockAndTrackingCannotResetGovernor) {
    for(int mutation=0;mutation<4;++mutation) {
        AvailableForceReference c;ASSERT_TRUE(c.start_session(1,start));ASSERT_TRUE(c.step(now,3,speed(),force()));
        auto f=force(now+20*ms);auto s=speed(now+20*ms);auto t=now+20*ms;
        if(mutation==0){f=force();f.propulsion_n=900;}
        if(mutation==1)s=speed();
        if(mutation==2)t+=1;
        if(mutation==3)s.speed_mps=0;
        EXPECT_FALSE(c.step(t,3,s,f));EXPECT_FALSE(c.start_session(1,t));
    }
}
TEST(AvailableForceReference, LongReferenceRampRespectsCapacityAndConverges) {
    AvailableForceReference c;ASSERT_TRUE(c.start_session(1,start));double v=2;
    for(std::uint64_t i=0;i<5000;++i) {
        const auto t=now+i*20*ms;auto f=force(t);f.propulsion_n=i<2500?500:1000;
        const auto r=c.step(t,i<2500?5:1,speed(t,v),f);ASSERT_TRUE(r)<<i;
        v+=r->acceleration_mps2*.02;EXPECT_NEAR(v,r->target_mps,1e-12);
    }
    EXPECT_NEAR(v,1,1e-10);
}
TEST(SupervisedSpeedRequest, SyntheticPlantTracksDeratingAndGradeWithFreshAllocationFeedback) {
    SupervisedSpeedRequest c;ASSERT_TRUE(c.start_session(1,7,start));
    double v=2;std::optional<PropulsionSelection> selection;
    for(std::uint64_t i=0;i<5000;++i) {
        const auto t=now+i*20*ms;auto a=actual(t);a.wheel_speed->value_rad_s=v/.3;
        auto f=force(t);f.propulsion_n=i<2000?500:1000;
        auto target=fallback(t);target.speed_mps=i<3000?4:1;
        const auto r=c.step(t,std::nullopt,target,a,f,true,selection);ASSERT_TRUE(r)<<i;
        const double command=r->request.acceleration_mps2;
        const double requested=1000*command;
        const double applied=std::clamp(requested,-f.braking_n,f.propulsion_n);
        v=std::max(0.0,v+(applied-150)/1000*.02);
        const double drive=std::max(0.0,requested)*.3,brake=std::max(0.0,-requested)*.3;
        selection=PropulsionSelection{1,r->request.sequence,t+10*ms,command,drive,std::min(drive,f.propulsion_n*.3),drive>f.propulsion_n*.3,
            brake,std::min(brake,f.braking_n*.3),brake>f.braking_n*.3};
        EXPECT_LE(std::abs(c.reference()->target_mps-a.wheel_speed->value_rad_s*.3),.5+1e-10);
    }
    EXPECT_NEAR(v,1,.02);
}
TEST(SpeedSupervisor, ValidProposalAndMissingModelUseExplicitSources) {
    SpeedSupervisor s;ASSERT_TRUE(s.start_session(1,7,start));
    auto r=s.select(now,proposal(),fallback(),true);ASSERT_TRUE(r.target_mps);EXPECT_EQ(r.source,ProposalSource::Learned);
    EXPECT_EQ(r.oldest_source_ns,now);EXPECT_EQ(*r.target_mps,2.5);
    r=s.select(now+20*ms,std::nullopt,fallback(now+20*ms),true);EXPECT_EQ(r.source,ProposalSource::Classical);EXPECT_EQ(r.reason,ProposalReason::Missing);
}
TEST(SpeedSupervisor, ModelAdapterOwnsAcquisitionIdentityAndChecksStateTensor) {
    PlannerInput input;input.valid=true;input.epoch=1;input.clock_instance=7;
    input.source_ns={now-60*ms,now-40*ms,now-20*ms,now};
    for(auto& state:input.history)state={2,3,1000,3000,100,200};
    ModelSpeedOutput output;output.speed_mps.fill(3);output.valid=true;output.risk=.1;
    const auto p=bind_speed_proposal(input,output,9,3);ASSERT_TRUE(p);EXPECT_EQ(p->source_ns,now);EXPECT_EQ(p->expires_ns,now+30*ms+1);
    EXPECT_EQ(p->history_ns,input.source_ns);EXPECT_EQ(p->sequence,9U);
    SpeedSupervisor supervisor;ASSERT_TRUE(supervisor.start_session(1,7,start));
    EXPECT_EQ(supervisor.select(now,p,fallback(),true).source,ProposalSource::Learned);
    input.history[1].road_load_min_n=300;EXPECT_FALSE(bind_speed_proposal(input,output,10,3));
    input.history[1].road_load_min_n=100;input.history[2].speed_mps=std::numeric_limits<double>::quiet_NaN();
    EXPECT_FALSE(bind_speed_proposal(input,output,10,3));
}
TEST(SpeedSupervisor, EveryMalformedModelOutputFallsBackWithoutRepairingItsTimestamp) {
    for(int mutation=0;mutation<13;++mutation) {
        SpeedSupervisor s;ASSERT_TRUE(s.start_session(1,7,start));auto p=proposal();
        switch(mutation) {
        case 0:p.valid=false;break;case 1:p.schema=2;break;case 2:p.clock_instance=9;break;case 3:p.epoch=2;break;
        case 4:p.expires_ns=now;break;case 5:p.history_ns[1]+=1;break;case 6:p.speed_mps[15]=30;break;
        case 7:p.speed_mps[15]=std::numeric_limits<double>::quiet_NaN();break;case 8:p.risk=std::numeric_limits<double>::infinity();break;
        case 9:p.speed_mps[15]=3;break;case 10:p.model_revision=0;break;case 11:p=proposal(now-31*ms);break;case 12:p.speed_limit_mps=2;break;
        }
        auto f=fallback(now-2*ms);const auto r=s.select(now,p,f,true);
        EXPECT_EQ(r.source,ProposalSource::Classical)<<mutation;EXPECT_EQ(r.oldest_source_ns,f.source_ns);EXPECT_EQ(r.expires_ns,f.expires_ns);
    }
}
TEST(SpeedSupervisor, HazardAndMissingFallbackOrPermissionRequestProtection) {
    for(int failure=0;failure<3;++failure) {
        SpeedSupervisor s;ASSERT_TRUE(s.start_session(1,7,start));auto p=proposal();auto f=fallback();
        if(failure==0)p.risk=.3;
        if(failure==1){p.valid=false;f.valid=false;}
        const auto r=s.select(now,p,f,failure!=2);EXPECT_EQ(r.source,ProposalSource::Protection);EXPECT_FALSE(r.target_mps);
    }
}
TEST(SpeedSupervisor, IdentityMutationRollbackAndModelSwapCannotBeLearnedOutput) {
    for(int mutation=0;mutation<3;++mutation) {
        SpeedSupervisor s;ASSERT_TRUE(s.start_session(1,7,start));ASSERT_EQ(s.select(now,proposal(),fallback(),true).source,ProposalSource::Learned);
        auto p=proposal();if(mutation==0)p.speed_mps.fill(2);if(mutation==1)--p.sequence;if(mutation==2)++p.model_revision;
        const auto r=s.select(now+20*ms,p,fallback(now+20*ms),true);EXPECT_EQ(r.source,ProposalSource::Classical);EXPECT_EQ(r.reason,ProposalReason::Identity);
    }
}
TEST(SupervisedSpeedRequest, ProposalGovernorPiAndAllocatorPreserveOriginalDependencies) {
    SupervisedSpeedRequest c;ASSERT_TRUE(c.start_session(3,7,start));
    ControlAllocation allocator;ASSERT_TRUE(allocator.start_session(3,start));
    std::optional<PropulsionSelection> selection;
    for(std::uint32_t offset=20;offset<=200;offset+=20) {
        const auto t=start+offset*ms;auto f=force(t-4*ms);f.epoch=3;
        auto a=actual(t-1*ms);a.epoch=3;auto classic=fallback(t-2*ms);classic.epoch=3;classic.speed_mps=2.5;
        std::optional<PlannerProposal> learned;
        if(offset>=80 && offset<160){learned=proposal(t-2*ms);learned->epoch=3;}
        const auto r=c.step(t,learned,classic,a,f,true,selection);ASSERT_TRUE(r)<<offset;
        EXPECT_EQ(r->input.source_time_ns,f.source_ns);EXPECT_EQ(r->input.expires_at_ns,f.expires_ns);
        EXPECT_EQ(r->request.expires_at_ns,f.expires_ns);
        EXPECT_EQ(c.decision().source,learned?ProposalSource::Learned:ProposalSource::Classical);
        ASSERT_EQ(allocator.receive_request(r->request,t,r->input),AllocationReceiveDecision::Accepted);
        auto feedback=allocation_fixture::inputs(offset);feedback.feedback.rear.drive_actual->wheel_speed=a.wheel_speed;
        const auto output=allocator.tick(feedback,t);ASSERT_TRUE(output)<<offset;
        EXPECT_EQ(output->oldest_input_time_ns,f.source_ns);EXPECT_LE(output->expires_at_ns,f.expires_ns);
        selection=allocator.decision().propulsion_selection;ASSERT_TRUE(selection);
    }
}
TEST(SupervisedSpeedRequest, FailedStepLatchesAndInvalidInitCannotPartiallyReset) {
    SupervisedSpeedRequest c;ASSERT_TRUE(c.start_session(1,7,start));
    EXPECT_FALSE(c.step(now,proposal(),fallback(),actual(),force(),false));EXPECT_TRUE(c.protection_required());
    EXPECT_FALSE(c.start_session(2,0,now));
    EXPECT_FALSE(c.step(now+20*ms,proposal(),fallback(),actual(),force(),true));
    ASSERT_TRUE(c.start_session(2,7,now));EXPECT_FALSE(c.protection_required());
}
TEST(AvailableForceEstimator, ElectricalDeratingAndFrictionReserveUseActualCapacity) {
    AllocationConfig config;AvailableForceEstimator estimator(config,{-100,200});
    for(double omega:{0.,20.,80.})for(double discharge:{0.,200.,500.,1000.,80000.}) {
        auto in=allocation_fixture::inputs(20).feedback;
        in.rear.drive_actual->wheel_speed->value_rad_s=omega;
        auto& limits=std::get<can::BmsPowerLimits>(in.rear.power_limits->message.content);
        limits.discharge_power_w=discharge;
        const auto f=estimator.estimate(in,start+20*ms);ASSERT_TRUE(f);
        const double torque=f->propulsion_n*config.wheel_radius_m;
        EXPECT_LE(torque,config.max_propulsion_nm+1e-9);
        EXPECT_LE(torque*omega,config.propulsion_mechanical_power_w+1e-9);
        EXPECT_LE(torque*omega/config.motoring_efficiency_lower_bound+config.copper_loss_w_per_nm2*torque*torque,
            std::max(0.0,discharge-config.reserve_power_w)+1e-9);
        EXPECT_DOUBLE_EQ(f->braking_n,5000); // no optional regen credit
        EXPECT_DOUBLE_EQ(f->road_load_min_n,-100);EXPECT_DOUBLE_EQ(f->road_load_max_n,200);
        EXPECT_EQ(f->source_ns,start+20*ms);
    }
}
TEST(AvailableForceEstimator, OldestOriginalDependencyBoundsAgeAndExpiry) {
    AvailableForceEstimator estimator({}, {0,200});auto in=allocation_fixture::inputs(40).feedback;
    std::get<can::BmsPowerLimits>(in.rear.power_limits->message.content).input_time_ns=start+20*ms;
    const auto f=estimator.estimate(in,start+40*ms);ASSERT_TRUE(f);
    EXPECT_EQ(f->source_ns,start+20*ms);EXPECT_EQ(f->expires_ns,start+90*ms+1);
    EXPECT_FALSE(estimator.estimate(in,start+71*ms));
}
TEST(AvailableForceEstimator, MissingInvalidFutureAndForeignInputsHaveNoCapacity) {
    for(unsigned fault=0;fault<8;++fault) {
        AvailableForceEstimator estimator({}, {0,200});auto in=allocation_fixture::inputs(20).feedback;
        switch(fault) {
        case 0:in.rear.power_limits.reset();break;
        case 1:in.rear.drive_actual->wheel_speed.reset();break;
        case 2:in.rear.drive_actual->wheel_speed->source_time_ns=start+21*ms;break;
        case 3:in.rear.power_limits->message.epoch=4;break;
        case 4:in.front.brake_actual.reset();break;
        case 5:in.rear.power_limits->quality[1]=can::BmsFieldQuality::NotApplicable;break;
        case 6:std::get<can::BmsPowerLimits>(in.rear.power_limits->message.content).discharge_power_w=std::numeric_limits<double>::quiet_NaN();break;
        case 7:in.rear.drive_actual->wheel_speed->value_rad_s=-1;break;
        }
        EXPECT_FALSE(estimator.estimate(in,start+20*ms))<<fault;
    }
    EXPECT_THROW((AvailableForceEstimator({}, {200,100})),std::invalid_argument);
    AllocationConfig bad;bad.wheel_radius_m=0;EXPECT_THROW((AvailableForceEstimator(bad,{})),std::invalid_argument);
}
TEST(SupervisedSpeedRequest, MissingCapacityFreezesFirstObservationUntilNewInit) {
    SupervisedSpeedRequest c;ASSERT_TRUE(c.start_session(1,7,start));
    ASSERT_TRUE(c.step(now,std::nullopt,fallback(),actual(),force(),true));
    EXPECT_FALSE(c.step(now+20*ms,std::nullopt,fallback(now+20*ms),actual(now+20*ms),std::nullopt,true));
    ASSERT_TRUE(c.fault_observation());EXPECT_EQ(c.fault_observation()->detected_ns,now+20*ms);
    EXPECT_EQ(c.fault_observation()->reason,ProposalReason::CapacityInput);
    EXPECT_FALSE(c.step(now+40*ms,std::nullopt,fallback(now+40*ms),actual(now+40*ms),force(now+40*ms),true));
    EXPECT_EQ(c.fault_observation()->detected_ns,now+20*ms);EXPECT_FALSE(c.start_session(1,7,now+40*ms));
    ASSERT_TRUE(c.start_session(2,7,now+40*ms));EXPECT_FALSE(c.fault_observation());
    auto f=force(now+60*ms);f.epoch=2;auto a=actual(now+60*ms);a.epoch=2;
    auto target=fallback(now+60*ms);target.epoch=2;
    EXPECT_TRUE(c.step(now+60*ms,std::nullopt,target,a,f,true));
}
TEST(SupervisedSpeedRequest, ReceiverPowerAgeIsSeparateFromCurrentWheelAge) {
    SupervisedSpeedRequest c;ControlAllocation allocator;AvailableForceEstimator estimator({}, {0,200});
    ASSERT_TRUE(c.start_session(3,7,start));ASSERT_TRUE(allocator.start_session(3,start));
    std::optional<PropulsionSelection> selection;
    for(std::uint32_t offset=20;offset<=200;offset+=20) {
        const auto t=start+offset*ms;auto in=allocation_fixture::inputs(offset);
        std::get<can::BmsPowerLimits>(in.feedback.rear.power_limits->message.content).input_time_ns=offset>=40?t-32*ms:start;
        auto target=fallback(t);target.epoch=3;target.speed_mps=6;
        const auto f=estimator.estimate(in.feedback,t);ASSERT_TRUE(f);
        const auto request=c.step(t,std::nullopt,target,in.feedback.rear.drive_actual,f,true,selection);ASSERT_TRUE(request);
        ASSERT_TRUE(request->input.power);EXPECT_EQ(request->input.power->source_time_ns,f->source_ns);
        EXPECT_EQ(request->input.source_time_ns,t); // wheel age gate is unchanged
        ASSERT_EQ(allocator.receive_request(request->request,t,request->input),AllocationReceiveDecision::Accepted);
        const auto commands=allocator.tick(in,t);ASSERT_TRUE(commands);
        EXPECT_EQ(commands->oldest_input_time_ns,f->source_ns);EXPECT_LE(commands->expires_at_ns,f->expires_ns);
        selection=allocator.decision().propulsion_selection;
    }
}
TEST(SupervisedPowerProvenance, SpeedGateExpiryAndDuplicateIdentityRemainStrict) {
    ControlAllocation warmed;ASSERT_TRUE(warmed.start_session(3,start));
    for(std::uint32_t offset=20;offset<100;offset+=20) {
        const auto t=start+offset*ms;
        ASSERT_EQ(warmed.receive_request({3,offset/20,t,t+30*ms,0,0,0,false},t),AllocationReceiveDecision::Accepted);
        ASSERT_TRUE(warmed.tick(allocation_fixture::inputs(offset),t));
    }
    const auto t=start+100*ms;
    const VehicleRequest request{3,5,t,t+20*ms,0,0,0,false};
    const VehicleInputDependency original{t-2*ms,t+20*ms,PowerInputDependency{t-32*ms,t+38*ms+1}};
    for(unsigned mutation=0;mutation<6;++mutation) {
        auto c=warmed;auto input=original;
        switch(mutation) {
        case 0:input.source_time_ns=t-31*ms;break;
        case 1:input.power->source_time_ns=t-71*ms;break;
        case 2:input.power->source_time_ns=t+1;break;
        case 3:input.power->expires_at_ns=t;break;
        case 4:input.power->expires_at_ns=t+38*ms+2;break;
        case 5:input.power->expires_at_ns=t+19*ms;break;
        }
        EXPECT_EQ(c.receive_request(request,t,input),AllocationReceiveDecision::Invalid)<<mutation;
    }
    auto c=warmed;ASSERT_EQ(c.receive_request(request,t,original),AllocationReceiveDecision::Accepted);
    EXPECT_EQ(c.receive_request(request,t,original),AllocationReceiveDecision::Unchanged);
    auto changed=original;--changed.power->expires_at_ns;
    EXPECT_EQ(c.receive_request(request,t,changed),AllocationReceiveDecision::MutationRejected);
    changed=original;changed.power.reset();EXPECT_EQ(c.receive_request(request,t,changed),AllocationReceiveDecision::MutationRejected);
    auto newer=request;++newer.sequence;++newer.source_time_ns;
    EXPECT_EQ(c.receive_request(newer,t+1,changed),AllocationReceiveDecision::Invalid);
}
} // namespace
