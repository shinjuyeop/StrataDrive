#include "actuator_electrical.hpp"
#include <gtest/gtest.h>
#include <limits>
#include <vector>
namespace {
using namespace stratadrive;
using namespace m7_external;
constexpr Time start=1000000000,ms=1000000;
std::array<std::optional<simulation::OwnerActuation>,5> none{};
SolverWork frame_work(unsigned frame,double torque=0) {
    SolverWork w;w.frame=101+frame;w.begin=start+frame*10*ms;w.end=w.begin+10*ms;
    w.oldest=w.begin;w.dt=double(.01f*(1.f/320.f));
    w.wheel={5,{7,100+frame,w.begin},w.begin};w.torque=torque;
    for(unsigned i=0;i<320;++i)w.rear_mean[i]=5.+double(i%7)*.001;
    return w;
}
auto outputs_at(unsigned step) {
    auto outputs=none;const auto now=start+step*ms;
    simulation::OwnerActuation drive_out;drive_out.epoch=42;drive_out.source_ns=now;
    drive_out.drive=drive::Actuation{drive::ActuationMode::Target,100,std::nullopt,now};outputs[2]=drive_out;
    simulation::OwnerActuation brake_out;brake_out.epoch=42;brake_out.source_ns=now;
    brake_out.brake=brake::Actuation{brake::ActuationMode::Target,0,now};outputs[1]=brake_out;
    simulation::OwnerActuation power_out;power_out.epoch=42;power_out.source_ns=now;
    power_out.coils=power::CoilCommand{{step>=1001,true,step<1001},false};outputs[4]=power_out;
    return outputs;
}
TEST(M7DeferredWork, MissingWorkDoesNotFreezeProtectionOrRestampElectricalSensors) {
    ActuatorElectrical p(start,42,PlantExecution::DeferredObservedWork);
    for(unsigned i=1;i<=200;++i) {
        const auto w=frame_work((i-1)/10);
        ASSERT_TRUE(p.advance_actuators(start+i*ms,w.wheel,outputs_at(i),42))<<p.error();
        if(i%10==0) {ASSERT_TRUE(p.settle_observed_frame(w))<<p.error();}
    }
    ASSERT_GT(p.sensors()->torque->torque_nm,99);
    const auto source=p.sensors()->power->identity.source_time_ns;
    const auto oldest=p.sensors()->power->input_time_ns;
    const auto hv=p.sensors()->drive.hv->identity.source_time_ns;
    Time pressure_reached=0,zero_reached=0;
    for(unsigned i=201;i<=450;++i) {
        ASSERT_TRUE(p.advance_actuators(start+i*ms,std::nullopt,none,42,i==201))<<p.error();
        ASSERT_TRUE(p.sensors());EXPECT_FALSE(p.sensors()->drive.wheel_speed);
        EXPECT_EQ(p.sensors()->pressure->source_time_ns,start+i*ms);
        EXPECT_EQ(p.sensors()->torque->source_time_ns,start+i*ms);
        if(!pressure_reached && p.sensors()->pressure->pressure_pa>=1000000)pressure_reached=start+i*ms;
        if(!zero_reached && p.sensors()->torque->torque_nm==0)zero_reached=start+i*ms;
        EXPECT_EQ(p.electrical_time(),start+200*ms);EXPECT_EQ(p.audit().end,start+200*ms);
        if(i<=328) {
            ASSERT_TRUE(p.sensors()->power);ASSERT_TRUE(p.sensors()->drive.hv);
            EXPECT_EQ(p.sensors()->power->identity.source_time_ns,source);
            EXPECT_EQ(p.sensors()->power->input_time_ns,oldest);
            EXPECT_EQ(p.sensors()->drive.hv->identity.source_time_ns,hv);
        }
    }
    EXPECT_TRUE(p.actuators_ok());EXPECT_FALSE(p.electrical_ok());
    EXPECT_FALSE(p.sensors()->power);EXPECT_FALSE(p.sensors()->drive.hv);
    EXPECT_GE(p.sensors()->pressure->pressure_pa,1000000);
    EXPECT_EQ(p.sensors()->torque->torque_nm,0);EXPECT_EQ(p.pending_intervals(),128U);
    ASSERT_NE(pressure_reached,0U);ASSERT_NE(zero_reached,0U);
    EXPECT_LE(pressure_reached-(start+201*ms),230*ms);
    EXPECT_LE(zero_reached-(start+201*ms),230*ms);
    EXPECT_FALSE(p.settle_observed_frame(frame_work(20)));
    ASSERT_TRUE(p.advance_actuators(start+451*ms,std::nullopt,outputs_at(451),42));
    EXPECT_GE(p.sensors()->pressure->pressure_pa,1000000);EXPECT_EQ(p.sensors()->torque->torque_nm,0);
}
TEST(M7DeferredWork, DelayedWorkUsesHistoricalCoilsAndPreservesSingleEvSignedLedger) {
    ActuatorElectrical immediate(start,42,true),delayed(start,42,PlantExecution::DeferredObservedWork);
    std::vector<SolverWork> pending;
    for(unsigned frame=0;frame<180;++frame) {
        const auto w=frame_work(frame,frame<110?0:frame<140?50:-20);
        ASSERT_TRUE(immediate.begin_work_frame(w));
        for(unsigned k=1;k<=10;++k) {
            const auto step=frame*10+k;const auto now=start+step*ms;
            const auto output=outputs_at(step);
            ASSERT_TRUE(immediate.step(now,w.wheel,output,42))<<immediate.error();
            ASSERT_TRUE(delayed.advance_actuators(now,w.wheel,output,42))<<delayed.error();
            EXPECT_EQ(delayed.sensors()->pressure->pressure_pa,immediate.sensors()->pressure->pressure_pa);
            EXPECT_EQ(delayed.sensors()->torque->torque_nm,immediate.sensors()->torque->torque_nm);
        }
        ASSERT_TRUE(immediate.finish_work_frame(w.end));immediate.commit_work_frame();
        pending.push_back(w);
        if(frame%3==2) {
            for(const auto& past:pending)ASSERT_TRUE(delayed.settle_observed_frame(past))<<frame<<' '<<delayed.error();
            pending.clear();
            const auto& a=immediate.audit();const auto& b=delayed.audit();
            EXPECT_EQ(a.total_mechanical_j,b.total_mechanical_j);EXPECT_EQ(a.soc,b.soc);
            EXPECT_EQ(a.motor_loss_j,b.motor_loss_j);EXPECT_EQ(a.circuit_loss_j,b.circuit_loss_j);
            EXPECT_EQ(a.chemical_j,b.chemical_j);EXPECT_EQ(a.balance_j,b.balance_j);
            EXPECT_EQ(immediate.sensors()->power->bus_voltage_v,delayed.sensors()->power->bus_voltage_v);
            EXPECT_EQ(immediate.sensors()->power->pack_current_a,delayed.sensors()->power->pack_current_a);
            EXPECT_EQ(delayed.pending_intervals(),0U);
        }
    }
}
TEST(M7DeferredWork, FractionalFrameTailDoesNotRestampNewerActuatorAcquisitions) {
    ActuatorElectrical p(start,42,PlantExecution::DeferredObservedWork);
    auto w=frame_work(0);--w.end;
    for(unsigned i=1;i<=10;++i)ASSERT_TRUE(p.advance_actuators(start+i*ms,w.wheel,none,42));
    ASSERT_TRUE(p.settle_observed_frame(w));EXPECT_EQ(p.pending_intervals(),1U);
    EXPECT_EQ(p.sensors()->pressure->source_time_ns,start+10*ms);
    EXPECT_EQ(p.sensors()->power->identity.source_time_ns,w.end);
    auto next=w;next.begin=w.end;next.end=w.end+10*ms;++next.frame;next.oldest=next.begin;
    next.wheel={0,{7,101,next.begin},next.begin};
    for(unsigned i=11;i<=20;++i)ASSERT_TRUE(p.advance_actuators(start+i*ms,next.wheel,none,42));
    ASSERT_TRUE(p.settle_observed_frame(next));EXPECT_EQ(p.pending_intervals(),1U);
    EXPECT_EQ(p.sensors()->torque->source_time_ns,start+20*ms);
    EXPECT_EQ(p.sensors()->drive.hv->identity.source_time_ns,next.end);
    EXPECT_EQ(p.audit().wheel_source,next.begin);EXPECT_EQ(p.electrical_time(),next.end);
}
TEST(M7DeferredWork, InvalidOrReplayedEnergyCannotRollBackResponseOrHeal) {
    for(unsigned fault=0;fault<5;++fault) {
        ActuatorElectrical p(start,42,PlantExecution::DeferredObservedWork);auto w=frame_work(0);
        for(unsigned i=1;i<=20;++i)ASSERT_TRUE(p.advance_actuators(start+i*ms,w.wheel,outputs_at(i),42));
        ASSERT_TRUE(p.settle_observed_frame(w));
        auto next=frame_work(1);
        if(fault==0)next=w;
        if(fault==1)++next.frame;
        if(fault==2)next.rear_mean[0]=std::numeric_limits<double>::quiet_NaN();
        if(fault==3)next.end+=10*ms;
        if(fault==4)next.torque=100; // uncharged/open HV circuit: energy rejection
        const auto energy=p.settled_work(),pressure=p.sensors()->pressure->pressure_pa;
        EXPECT_FALSE(p.settle_observed_frame(next))<<fault;
        EXPECT_EQ(p.last_success(),start+20*ms);EXPECT_EQ(p.electrical_time(),start+10*ms);
        EXPECT_EQ(p.settled_work(),energy);ASSERT_TRUE(p.sensors());
        EXPECT_EQ(p.sensors()->pressure->pressure_pa,pressure);EXPECT_FALSE(p.sensors()->power);
        EXPECT_TRUE(p.actuators_ok());EXPECT_FALSE(p.electrical_ok());
        EXPECT_FALSE(p.settle_observed_frame(frame_work(1)));
        for(unsigned i=21;i<=250;++i)ASSERT_TRUE(p.advance_actuators(start+i*ms,std::nullopt,none,42));
        EXPECT_GE(p.sensors()->pressure->pressure_pa,1000000);EXPECT_EQ(p.sensors()->torque->torque_nm,0);
    }
}
TEST(M7DeferredWork, StaleCurrentCannotAuthorizePowerWatchdogOpeningDwell) {
    ActuatorElectrical p(start,42,PlantExecution::DeferredObservedWork);
    for(unsigned i=1;i<=1100;++i) {
        const auto w=frame_work((i-1)/10);
        auto output=outputs_at(i);if(i>=900)output[2]->drive->target_nm=0;
        ASSERT_TRUE(p.advance_actuators(start+i*ms,w.wheel,output,42));
        if(i%10==0) {ASSERT_TRUE(p.settle_observed_frame(w));}
    }
    ASSERT_TRUE(p.applied_coils().close.positive);
    ASSERT_EQ(p.sensors()->torque->torque_nm,0);
    for(unsigned i=1101;i<=1200;++i)ASSERT_TRUE(p.advance_actuators(start+i*ms,std::nullopt,none,42,true));
    EXPECT_TRUE(p.applied_coils().close.positive);EXPECT_FALSE(p.applied_coils().discharge_bus);
    EXPECT_EQ(p.sensors()->power->identity.source_time_ns,start+1100*ms);
    EXPECT_EQ(p.sensors()->torque->torque_nm,0);
}
TEST(M7DeferredWork, WheelIdentityCannotBeMutatedRegressedOrRestamped) {
    for(unsigned fault=0;fault<5;++fault) {
        ActuatorElectrical p(start,42,PlantExecution::DeferredObservedWork);
        auto wheel=frame_work(0).wheel;
        ASSERT_TRUE(p.advance_actuators(start+ms,wheel,none,42));
        if(fault==0)wheel.value+=1;
        if(fault==1)++wheel.input_time_ns;
        if(fault==2)++wheel.identity.source_time_ns;
        if(fault==3)--wheel.identity.sequence;
        if(fault==4)wheel.identity.source_time_ns=start+3*ms;
        EXPECT_FALSE(p.advance_actuators(start+2*ms,wheel,none,42));
        EXPECT_EQ(p.last_success(),start+ms);EXPECT_EQ(p.electrical_time(),start);
    }
}
TEST(M7DeferredWork, CoupledRollbackAndIndependentAdvanceCannotBeMixed) {
    for(unsigned operation=0;operation<4;++operation) {
        ActuatorElectrical p(start,42,PlantExecution::DeferredObservedWork);auto w=frame_work(0);
        for(unsigned i=1;i<=10;++i)ASSERT_TRUE(p.advance_actuators(start+i*ms,w.wheel,none,42));
        if(operation==0) {EXPECT_FALSE(p.begin_work_frame(w));}
        if(operation==1) {EXPECT_FALSE(p.step(start+11*ms,w.wheel,none,42));}
        if(operation==2)p.abort_work_frame();
        if(operation==3)p.commit_work_frame();
        EXPECT_FALSE(p.electrical_ok());EXPECT_TRUE(p.actuators_ok());
        EXPECT_EQ(p.last_success(),start+10*ms);EXPECT_EQ(p.electrical_time(),start);
        ASSERT_TRUE(p.advance_actuators(start+11*ms,std::nullopt,none,42));
    }
}
}
