#include "functional_rig.hpp"
#include "wheel_contract.hpp"
#include <gtest/gtest.h>
#include <limits>

namespace {
using namespace stratadrive;
using namespace m7_functional;
constexpr Scope scope{1,42,7};
constexpr Time start=1000000000;
Observation observation(unsigned i) {return {scope,domain,100+i,1+i*.01,.01};}
WheelSample packet(unsigned i,double speed=0) {return {99,100+i,start+i*tick_ns,{speed,speed,speed,speed}};}
std::array<std::optional<simulation::OwnerActuation>,5> none{};
m7_external::Wheel wheel(Time source=start,double v=0,unsigned seq=100) {return {v,{7,seq,source},source};}
TEST(M7ExternalWheel, ZeroBinDoesNotAuthorizeNegativeToZeroConversion) {
    for(double negative:{-1e-12,-4.784922111866763e-7,-.004999999}) {
        const auto a=m7_external::assess({0,0,negative,0});
        EXPECT_EQ(a.validity,m7_external::WheelValidity::SubResolutionNegative);EXPECT_FALSE(a.forward_rad_s);
    }
    for(double reverse:{-.005,-.01,-1.}) {
        const auto a=m7_external::assess({0,0,reverse,0});
        EXPECT_EQ(a.validity,m7_external::WheelValidity::ReverseOrMixed);EXPECT_FALSE(a.forward_rad_s);
    }
    EXPECT_DOUBLE_EQ(*m7_external::assess({0,0,.001234,.002468}).forward_rad_s,.001851);
}
TEST(M7ExternalPlant, HeldWheelAcquisitionIsNotRestampedAtOneMsModelSteps) {
    m7_external::ActuatorElectrical plant(start,42);
    for(unsigned i=1;i<=10;++i) {
        ASSERT_TRUE(plant.step(start+i*ms,wheel(start,2),none,0))<<plant.error();
        EXPECT_EQ(plant.audit().wheel_source,start);EXPECT_EQ(plant.audit().wheel_oldest,start);
        ASSERT_TRUE(plant.sensors());ASSERT_TRUE(plant.sensors()->drive.wheel_speed);
        EXPECT_EQ(plant.sensors()->drive.wheel_speed->identity.source_time_ns,start);
    }
}
TEST(M7ExternalPlant, MissingFutureWrongEpochReverseAndNonfiniteInputsLatchWithoutCommit) {
    for(unsigned fault=0;fault<5;++fault) {
        m7_external::ActuatorElectrical plant(start,42);std::optional<m7_external::Wheel> w=wheel();
        if(fault==0)w.reset();
        if(fault==1)w->identity.source_time_ns=w->input_time_ns=start+ms;
        if(fault==2)++w->identity.epoch;
        if(fault==3)w->value=-1e-12;
        if(fault==4)w->value=std::numeric_limits<double>::quiet_NaN();
        EXPECT_FALSE(plant.step(start+ms,w,none,0));EXPECT_EQ(plant.last_success(),start);EXPECT_FALSE(plant.sensors());
        EXPECT_FALSE(plant.step(start+ms,wheel(),none,0));
    }
}
TEST(M7ExternalPlant, StaleOldestDependencyStillExpiresAtThirtyMs) {
    m7_external::ActuatorElectrical plant(start,42);
    for(unsigned i=1;i<=30;++i) {
        auto w=wheel(start+(i-1)*ms,0,100+i);w.input_time_ns=start;
        ASSERT_TRUE(plant.step(start+i*ms,w,none,0))<<plant.error();
    }
    auto w=wheel(start+30*ms,0,131);w.input_time_ns=start;
    EXPECT_FALSE(plant.step(start+31*ms,w,none,0));EXPECT_EQ(plant.last_success(),start+30*ms);
}
TEST(M7ExternalPlant, MutatedCachedSampleDoesNotBecomeNewEnergyInput) {
    m7_external::ActuatorElectrical plant(start,42);
    ASSERT_TRUE(plant.step(start+ms,wheel(start,1),none,0));
    EXPECT_FALSE(plant.step(start+2*ms,wheel(start,2),none,0));
    EXPECT_EQ(plant.last_success(),start+ms);
}
TEST(M7ExternalPlant, BadOutputAfterCandidateEnergyStepRollsBackAllPhysicalState) {
    for(unsigned fault=0;fault<6;++fault) {
        m7_external::ActuatorElectrical plant(start,42);ASSERT_TRUE(plant.step(start+ms,wheel(),none,0));
        const auto old=plant.audit();auto out=none;
        simulation::OwnerActuation o;o.epoch=42;o.source_ns=start+ms;
        o.drive=drive::Actuation{drive::ActuationMode::Target,1,std::nullopt,start+ms};
        if(fault==0)o.source_ns=start+3*ms;
        if(fault==1)o.epoch=43;
        if(fault==3)o.epoch=41;
        if(fault==4)o.source_ns=start-1;
        if(fault==5)o.drive->target_nm=std::numeric_limits<double>::quiet_NaN();
        out[fault==2?0:2]=o;
        EXPECT_FALSE(plant.step(start+2*ms,wheel(),out,0));
        EXPECT_EQ(plant.last_success(),start+ms);EXPECT_DOUBLE_EQ(plant.audit().soc,old.soc);
        EXPECT_FALSE(plant.sensors());
    }
}
TEST(M7ExternalNative, EightRolesUseRealWheelForElectricalZohWithoutVehicleIntegration) {
    FunctionalRig rig(scope,99,PlantMode::ExternalWheelZoh);Report r;double sum=0;
    for(unsigned i=0;i<=240;++i) {
        r=rig.observe(observation(i),packet(i,i<100?0:5));
        for(unsigned j=0;j<r.electrical_count;++j) {
            const auto& e=r.electrical_steps[j];
            EXPECT_LE(e.wheel_source,e.begin);EXPECT_EQ(e.wheel_oldest,e.wheel_source);
            EXPECT_LE(e.end-e.wheel_oldest,30*ms);
            const double work=e.torque_nm*e.wheel_rad_s*static_cast<double>(e.end-e.begin)*1e-9;
            EXPECT_NEAR(e.mechanical_j,work,1e-10);sum+=work;
            EXPECT_NEAR(e.total_mechanical_j,sum,1e-8);
        }
    }
    ASSERT_TRUE(r.armed);EXPECT_EQ(r.credit_mask,255U);ASSERT_TRUE(r.electrical);
    EXPECT_EQ(r.electrical->wheel_rad_s,5);EXPECT_GT(r.electrical->total_mechanical_j,0);
    ASSERT_TRUE(r.returned_wheel);EXPECT_EQ(r.returned_wheel->rad_s,5);
}
TEST(M7ExternalPlant, LostActuatorOutputSelectsZeroAndPressureFloorWithRealResponse) {
    m7_external::ActuatorElectrical plant(start,42);auto out=none;double peak=0;
    for(unsigned i=1;i<=1800;++i) {
        const auto now=start+i*ms;
        if(i==1 || i%10==0) {
            simulation::OwnerActuation power;power.epoch=42;power.source_ns=now;
            power.coils=power::CoilCommand{{i>=1000,true,i<1000},false};out[4]=power;
            if(i<=1500) {
                simulation::OwnerActuation drive_out;drive_out.epoch=42;drive_out.source_ns=now;
                drive_out.drive=drive::Actuation{drive::ActuationMode::Target,i>=1100?100.:0.,std::nullopt,now};out[2]=drive_out;
                simulation::OwnerActuation brake_out;brake_out.epoch=42;brake_out.source_ns=now;
                brake_out.brake=brake::Actuation{brake::ActuationMode::Target,0,now};out[1]=brake_out;
            }
        }
        ASSERT_TRUE(plant.step(now,wheel(now-ms,5,100+i),out,42))<<i<<' '<<plant.error();
        peak=std::max(peak,plant.sensors()->torque->torque_nm);
    }
    EXPECT_GE(peak,99.9);EXPECT_LE(std::abs(plant.sensors()->torque->torque_nm),1);
    EXPECT_GE(plant.sensors()->pressure->pressure_pa,1000000);
    EXPECT_GT(plant.audit().total_mechanical_j,0);
}
TEST(M7ExternalNative, FutureEndpointCannotChangePreviousIntervalWork) {
    FunctionalRig rig(scope,99,PlantMode::ExternalWheelZoh);Report r;
    for(unsigned i=0;i<150;++i)r=rig.observe(observation(i),packet(i,0));
    r=rig.observe(observation(150),packet(150,10));
    for(unsigned j=0;j<r.electrical_count;++j)EXPECT_EQ(r.electrical_steps[j].wheel_rad_s,0);
    r=rig.observe(observation(151),packet(151,10));
    ASSERT_TRUE(r.electrical);EXPECT_EQ(r.electrical->wheel_rad_s,10);
}
TEST(M7ExternalNative, FractionalTimestampAndOldestRemainOriginal) {
    FunctionalRig rig(scope,99,PlantMode::ExternalWheelZoh);Report r;
    for(unsigned i=0;i<=180;++i) {
        auto o=observation(i);o.elapsed_s=3.997146773152053+i*.009999999776482582;
        auto w=packet(i,i<100?0:2.34567);w.source=static_cast<Time>(std::llround(o.elapsed_s*1e9));
        r=rig.observe(o,w);
        for(unsigned j=0;j<r.electrical_count;++j)EXPECT_LE(r.electrical_steps[j].wheel_source,r.electrical_steps[j].begin);
    }
    EXPECT_TRUE(r.armed);ASSERT_TRUE(r.electrical);EXPECT_EQ(r.electrical->wheel_rad_s,2.34567);
}
} // namespace
