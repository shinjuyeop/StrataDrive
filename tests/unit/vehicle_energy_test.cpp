#include "vehicle_ev_model.hpp"
#include "ev_power_model.hpp"
#include "../integration/someip/energy_scenario.hpp"
#include <gtest/gtest.h>
using namespace stratadrive;
using namespace stratadrive::simulation;
namespace {
constexpr std::uint64_t ms=1000000;
BatteryConfig battery_config(){return {180000000,400,.05,200000,20,25,100,.01,1,100000};}
PowerModelConfig circuit_config(){return {.002,50,.02,100,1000,500};}
TEST(VehicleEnergy,MotorWorkIsTheSameAtBothSidesOfPhysicalBoundary){
    VehicleEvModel m({},{},battery_config(),circuit_config());
    ASSERT_TRUE(m.initialize({7,0,.63,25},400,{true,true,false},3));
    for(unsigned i=0;i<10;++i){
        const std::uint64_t t=i*20*ms;const battery::ModelIdentity id{7,i,t};
        ASSERT_EQ(m.step(t,t+20*ms,{{300,id,t},{0,id,t},{0,id,t}},{{.25,true},id,t},{{true,true,false},false}).fault,VehicleEvFault::None);
    }
    EXPECT_NEAR(m.electrical().diagnostic_state().mechanical_j,m.vehicle().state().motor_work_j,1e-6);
    EXPECT_NEAR(m.ledger().combined_balance_j,0,.001);

}
VehicleEvStep advance(VehicleEvModel& m,std::uint64_t begin,std::uint64_t end,double torque,double pressure=0) {
    battery::ModelIdentity id{7,static_cast<std::uint32_t>(begin/ms),begin};
    return m.step(begin,end,{{torque,id,begin},{pressure,id,begin},{0,id,begin}},{{.25,true},id,begin},{{true,true,false},false});
}
TEST(VehicleEnergy,RegenerationAndFrictionAreDistinctActualEnergySinks){
    VehicleEvModel m({},{},battery_config(),circuit_config());ASSERT_TRUE(m.initialize({7,0,.63,25},400,{true,true,false},5));
    for(unsigned i=0;i<1000;++i)ASSERT_EQ(advance(m,i*ms,(i+1)*ms,-150,100000).fault,VehicleEvFault::None);
    EXPECT_LT(m.ledger().motor_work_j,-1);EXPECT_GT(m.ledger().received_dc_j,1);EXPECT_GT(m.ledger().friction_j,1);
    EXPECT_LT(m.vehicle().state().speed_mps,5);EXPECT_NEAR(m.ledger().combined_balance_j,0,.001);
}
TEST(VehicleEnergy,FrictionOnlyCannotInventMechanicalRegeneration){
    VehicleEvModel m({},{},battery_config(),circuit_config());ASSERT_TRUE(m.initialize({7,0,.96,25},400,{true,true,false},1));
    for(unsigned i=0;i<1000;++i)ASSERT_EQ(advance(m,i*ms,(i+1)*ms,0,1000000).fault,VehicleEvFault::None);
    EXPECT_DOUBLE_EQ(m.vehicle().state().speed_mps,0);EXPECT_DOUBLE_EQ(m.ledger().motor_work_j,0);
    EXPECT_GT(m.electrical().diagnostic_state().bus_load_w,0);EXPECT_NEAR(m.ledger().combined_balance_j,0,.001);EXPECT_GT(m.ledger().friction_j,0);EXPECT_GT(m.ledger().battery_draw_j,0);
}
TEST(VehicleEnergy,StopCrossingTransfersOnlyActualTravelWork){
    VehicleEvModel m({},{},battery_config(),circuit_config());ASSERT_TRUE(m.initialize({7,0,.63,25},400,{true,true,false},.001));
    ASSERT_EQ(advance(m,0,20*ms,-100,1000000).fault,VehicleEvFault::None);
    EXPECT_DOUBLE_EQ(m.vehicle().state().speed_mps,0);EXPECT_GT(m.ledger().motor_work_j,-.001);
    EXPECT_NEAR(m.ledger().coupling_balance_j,0,1e-6);EXPECT_NEAR(m.ledger().combined_balance_j,0,.001);
}
TEST(VehicleEnergy,RejectedElectricalInputDoesNotCommitCandidateMotion){
    VehicleEvModel m({},{},battery_config(),circuit_config());ASSERT_TRUE(m.initialize({7,0,.63,25},400,{true,true,false},3));
    const auto before=m.electrical().battery_state().energy_j;const battery::ModelIdentity id{7,0,0},future{7,0,ms};
    auto r=m.step(0,ms,{{300,id,0},{0,id,0},{0,id,0}},{{.25,true},future,0},{{true,true,false},false});
    EXPECT_EQ(r.fault,VehicleEvFault::Electrical);EXPECT_EQ(m.vehicle().state().identity.source_time_ns,0U);
    EXPECT_DOUBLE_EQ(m.vehicle().state().distance_m,0);EXPECT_DOUBLE_EQ(m.electrical().battery_state().energy_j,before);
    EXPECT_EQ(m.ledger().sequence,0U);EXPECT_EQ(advance(m,0,ms,300).fault,VehicleEvFault::Electrical);
}
TEST(VehicleEnergy,RejectedVehicleInputDoesNotCommitElectricalState){
    VehicleEvModel m({},{},battery_config(),circuit_config());ASSERT_TRUE(m.initialize({7,0,.63,25},400,{true,true,false},3));
    const auto before=m.electrical().battery_state().energy_j;
    EXPECT_EQ(advance(m,0,21*ms,300).fault,VehicleEvFault::Vehicle);
    EXPECT_DOUBLE_EQ(m.electrical().battery_state().energy_j,before);EXPECT_EQ(m.electrical().diagnostic_state().identity.sequence,0U);
    EXPECT_FALSE(m.initialize({8,22*ms,.5,25},400));
}
TEST(VehicleEnergy,IntegratedWorkCannotRestampOrReverseTheOriginalActual){
    for(unsigned bad=0;bad<5;++bad){
        EvPowerModel e({},battery_config(),circuit_config());ASSERT_TRUE(e.initialize({7,0,.63,25},400,{true,true,false}));
        const battery::ModelIdentity id{7,0,0};const EvPowerInputs in{{{100,id,0}},{{3,id,0}},{{{.25,true},id,0}}};
        IntegratedMotorWork w{{7,1,ms},0,ms,0,.3};
        if(bad==0)w.identity.source_time_ns=0;
        if(bad==1)w.identity.sequence=0;
        if(bad==2)w.input_time_ns=1;
        if(bad==3)w.mechanical_j=-.3;
        if(bad==4)w.mechanical_j=1000;
        EXPECT_NE(e.step_integrated_motion({0,ms,in,{{true,true,false},false}},w).fault,EvPowerFault::None);
        EXPECT_EQ(e.diagnostic_state().identity.source_time_ns,0U);
    }
}
TEST(VehicleEnergy,LedgerUsesTheActualVehicleMassNotAFixedAuditMass){
    SimpleVehicleConfig c;c.mass_kg=700;c.wheel_radius_m=.28;
    VehicleEvModel m(c,{},battery_config(),circuit_config());ASSERT_TRUE(m.initialize({7,0,.63,25},400,{true,true,false},3));
    ASSERT_EQ(advance(m,0,ms,200).fault,VehicleEvFault::None);
    EXPECT_DOUBLE_EQ(m.ledger().kinetic_j,.5*700*m.vehicle().state().speed_mps*m.vehicle().state().speed_mps);
    EXPECT_NEAR(m.ledger().combined_balance_j,0,.001);
}
TEST(VehicleEnergy,RefiningMotionStepPreservesBothLedgers){
    auto simulate=[](std::uint64_t dt){
        VehicleEvModel m({},{},battery_config(),circuit_config());EXPECT_TRUE(m.initialize({7,0,.63,25},400,{true,true,false},3));
        for(std::uint64_t t=0;t<2000*ms;t+=dt)EXPECT_EQ(advance(m,t,t+dt,t<1000*ms?200:-100,t<1000*ms?0:100000).fault,VehicleEvFault::None);
        EXPECT_NEAR(m.ledger().combined_balance_j,0,.001);EXPECT_NEAR(m.ledger().coupling_balance_j,0,1e-6);
        return m.vehicle().state();
    };
    const auto a=simulate(2*ms),b=simulate(ms);EXPECT_NEAR(a.speed_mps,b.speed_mps,1e-5);EXPECT_NEAR(a.distance_m,b.distance_m,1e-5);
}
TEST(EnergyScenario,PhasesAreMeasuredFromTheActualArmWithoutChangingRootExpiry){
    using stratadrive::someip::test::energy_demand;
    EXPECT_DOUBLE_EQ(energy_demand(0).acceleration,2);
    EXPECT_STREQ(energy_demand(1999999999).phase,"accelerate");
    EXPECT_STREQ(energy_demand(2000000000).phase,"coast");
    EXPECT_DOUBLE_EQ(energy_demand(2599999999).acceleration,0);
    EXPECT_DOUBLE_EQ(energy_demand(2600000000).acceleration,-1);
    EXPECT_TRUE(energy_demand(2600000000).hold);
    EXPECT_STREQ(energy_demand(4500000000).phase,"hold");
    EXPECT_DOUBLE_EQ(energy_demand(5000000000).acceleration,0);
}

TEST(VehicleEnergy,IntegratedWorkPreservesOldestMotionDependencyThroughBatteryFlow){
    VehicleEvModel m({},{},battery_config(),circuit_config());ASSERT_TRUE(m.initialize({7,0,.63,25},400,{true,true,false},3));
    ASSERT_EQ(advance(m,0,2*ms,200).fault,VehicleEvFault::None);
    const battery::ModelIdentity fresh{7,2,2*ms},held{7,0,0};
    ASSERT_EQ(m.step(2*ms,4*ms,{{200,fresh,2*ms},{0,held,0},{0,held,0}},{{.25,true},fresh,2*ms},{{true,true,false},false}).fault,VehicleEvFault::None);
    EXPECT_EQ(m.ledger().input_ns,0U);ASSERT_TRUE(m.electrical().last_flow());
    EXPECT_EQ(m.electrical().last_flow()->battery.input_time_ns,0U);
}

}
