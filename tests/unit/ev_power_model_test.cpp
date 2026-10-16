#include "ev_power_model.hpp"

#include <gtest/gtest.h>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace {
using namespace stratadrive;
using namespace stratadrive::simulation;
constexpr std::uint64_t kStart = 1000000000, kMs = 1000000;
BatteryConfig battery_config() { return {180000000, 400, 0.05, 200000, 20, 25, 100, 0.01, 1, 100000}; }
PowerModelConfig circuit_config() { return {0.002, 50, 0.02, 100, 1000, 500}; }
struct Point { double torque{0}, speed{20}, aux_a{0}; bool enabled{false}; };
EvPowerInterval interval(std::uint32_t i, power::CoilCommand coils = {}, Point p = {}) {
    const auto begin = kStart+static_cast<std::uint64_t>(i)*10*kMs;
    const ModelIdentity id{7, i, begin};
    return {begin, begin+10*kMs, {ModelMeasurement<double>{p.torque, id, begin},
        ModelMeasurement<double>{p.speed, id, begin}, ModelMeasurement<EvElectricalEnvironment>{{p.aux_a, p.enabled}, id, begin}}, coils};
}
class EvCircuitTest : public ::testing::Test {
protected:
    EvPowerModel model{{}, battery_config(), circuit_config()};
    void SetUp() override { ASSERT_TRUE(model.initialize({7, kStart, 0.5, 25}, 0)); }
    void step(std::uint32_t i, power::CoilCommand coils = {}, Point point = {}) {
        const auto result = model.step(interval(i, coils, point));
        ASSERT_EQ(result.fault, EvPowerFault::None) << "circuit=" << static_cast<int>(result.circuit_fault) << " battery=" << static_cast<int>(result.battery_fault);
    }
};
TEST(EvCircuitConfiguration, ValidatesPhysicalTimingAndMotorCalibration) {
    auto drive = DriveEnergyConfig{}; drive.motoring_efficiency = 0;
    EXPECT_THROW((EvPowerModel{drive, battery_config(), circuit_config()}), std::invalid_argument);
    drive = {}; drive.max_step_ns = 30*kMs;
    EXPECT_THROW((EvPowerModel{drive, battery_config(), circuit_config()}), std::invalid_argument);
    drive = {}; drive.max_input_age_ns = 100*kMs;
    EXPECT_THROW((EvPowerModel{drive, battery_config(), circuit_config()}), std::invalid_argument);
    auto circuit = circuit_config(); circuit.integration_step_ns = 0;
    EXPECT_THROW((EvPowerModel{{}, battery_config(), circuit}), std::invalid_argument);
}
TEST(EvCircuitConfiguration, InitializationOfBatteryAndCapacitorIsAtomicAndExplicit) {
    EvPowerModel model({}, battery_config(), circuit_config());
    EXPECT_EQ(model.step(interval(0)).fault, EvPowerFault::NotInitialized);
    EXPECT_FALSE(model.initialize({7, kStart, 0.5, 25}, -1)); EXPECT_EQ(model.battery_state().identity.epoch, 0U);
    ASSERT_TRUE(model.initialize({7, kStart, 0.5, 25}, 400));
    EXPECT_EQ(model.diagnostic_state().initial_capacitor_j, 160); EXPECT_FALSE(model.power_observation());
    EXPECT_FALSE(model.initialize({7, kStart, 0.6, 25}, 0)); EXPECT_EQ(model.battery_state().soc, 0.5);
}
TEST_F(EvCircuitTest, PrechargeCountsChemicalEnergyCapacitorAndBothSeriesResistors) {
    for (std::uint32_t i = 0; i < 200; ++i) step(i, {{false, true, true}, false});
    const auto& s = model.diagnostic_state(); const auto& b = model.battery_state();
    EXPECT_NEAR(s.capacitor_j, 160, 1e-5); EXPECT_NEAR(b.initial_energy_j-b.energy_j, 320, 1e-5);
    EXPECT_NEAR(s.precharge_loss_j+b.ohmic_loss_j, 160, 1e-5);
    EXPECT_NEAR(s.precharge_loss_j/b.ohmic_loss_j, 50/0.05, 1e-6);
    EXPECT_EQ(s.motor_loss_j, 0); EXPECT_NEAR(s.balance_error_j, 0, 0.00072);
}
TEST_F(EvCircuitTest, ContactFeedbackAtEndDoesNotBackdateClosingIntoThePreviousInterval) {
    step(0, {{false, true, true}, false}); EXPECT_EQ(model.diagnostic_state().capacitor_j, 0);
    step(1, {{false, true, true}, false});
    EXPECT_TRUE(model.power_state().contactors.precharge); EXPECT_EQ(model.diagnostic_state().capacitor_j, 0);
    EXPECT_EQ(model.last_flow()->battery.charge_c, 0); EXPECT_GT(model.power_state().pack_current_a, 0);
    step(2, {{false, true, true}, false}); EXPECT_GT(model.diagnostic_state().capacitor_j, 0);
}
TEST(EvCircuitPhysics, EventInsideIntervalMatchesAnalyticalPrechargeDuration) {
    auto config = circuit_config(); config.contactor_delay_ns = 15*kMs;
    EvPowerModel model({}, battery_config(), config); ASSERT_TRUE(model.initialize({7, kStart, 0.5, 25}, 0));
    auto in = interval(0, {{false, true, true}, false}); in.end_ns += 10*kMs;
    ASSERT_EQ(model.step(in).fault, EvPowerFault::None);
    EXPECT_NEAR(model.power_state().bus_voltage_v, 400*(1-std::exp(-0.005/(50.05*0.002))), 1e-5);
}
TEST(EvCircuitPhysics, IsolatedCapacitorDischargeDoesNotChargeOrDischargeTheBattery) {
    EvPowerModel model({}, battery_config(), circuit_config()); ASSERT_TRUE(model.initialize({7, kStart, 0.5, 25}, 400));
    for (std::uint32_t i = 0; i < 200; ++i) ASSERT_EQ(model.step(interval(i, {{}, true})).fault, EvPowerFault::None);
    EXPECT_EQ(model.battery_state().energy_j, 90000000); EXPECT_EQ(model.battery_state().ohmic_loss_j, 0);
    EXPECT_NEAR(model.diagnostic_state().discharge_loss_j, 160, 1e-5);
    EXPECT_NEAR(model.diagnostic_state().balance_error_j, 0, 1e-8);
}
TEST(EvCircuitPhysics, IsolatedRegenerationStoresEnergyInCapacitorRatherThanInventingBatteryCharge) {
    EvPowerModel model({}, battery_config(), circuit_config()); ASSERT_TRUE(model.initialize({7, kStart, 0.5, 25}, 400));
    ASSERT_EQ(model.step(interval(0, {}, {-100, 20, 0, true})).fault, EvPowerFault::None);
    EXPECT_NEAR(model.diagnostic_state().capacitor_j, 175.5, 1e-8);
    EXPECT_EQ(model.battery_state().received_dc_j, 0); EXPECT_EQ(model.battery_state().energy_j, 90000000);
    EXPECT_NEAR(model.last_flow()->load_j, -15.5, 1e-10);
}
TEST(EvCircuitPhysics, InfeasibleIsolatedLoadLatchesWithoutCommittingEitherPhysicalState) {
    EvPowerModel model({}, battery_config(), circuit_config()); ASSERT_TRUE(model.initialize({7, kStart, 0.5, 25}, 400));
    std::uint32_t i = 0;
    for (; i < 20; ++i) {
        const auto voltage = model.power_state().bus_voltage_v; const auto energy = model.battery_state().energy_j;
        const auto previous = model.diagnostic_state().identity.sequence;
        const auto result = model.step(interval(i, {}, {100, 20, 0, true}));
        if (result.fault != EvPowerFault::None) {
            EXPECT_EQ(result.fault, EvPowerFault::Circuit); EXPECT_EQ(result.circuit_fault, PowerModelFault::Electrical);
            EXPECT_EQ(model.power_state().bus_voltage_v, voltage); EXPECT_EQ(model.battery_state().energy_j, energy);
            EXPECT_EQ(model.diagnostic_state().identity.sequence, previous); EXPECT_FALSE(model.power_observation()); break;
        }
    }
    EXPECT_LT(i, 20U); EXPECT_GT(i, 0U);
}
TEST(EvCircuitPhysics, MotoringUsesRealTerminalAndBusVoltagesAndSeparatesPathLoss) {
    EvPowerModel model({}, battery_config(), circuit_config()); ASSERT_TRUE(model.initialize({7, kStart, 0.5, 25}, 400, {true, true, false}));
    for (std::uint32_t i = 0; i < 100; ++i) ASSERT_EQ(model.step(interval(i, {{true, true, false}, false}, {100, 20, 0.375, true})).fault, EvPowerFault::None);
    const auto& b = model.battery_observation().electrical->value; const auto& p = *model.power_observation();
    EXPECT_LT(model.battery_state().soc, 0.5); EXPECT_LT(*p.bus_voltage_v, b.voltage_v); EXPECT_LT(b.voltage_v, 400);
    EXPECT_EQ(*p.pack_voltage_v, b.voltage_v); EXPECT_EQ(*p.pack_current_a, b.current_a);
    EXPECT_GT(model.diagnostic_state().main_loss_j, 0); EXPECT_GT(model.battery_state().ohmic_loss_j, 0);
    EXPECT_NEAR(model.last_flow()->capacitor_delta_j, 0, 1e-8);
}
TEST(EvCircuitPhysics, ConnectedRegenerationRaisesBatterySocAfterMotorPathAndBatteryLosses) {
    EvPowerModel model({}, battery_config(), circuit_config()); ASSERT_TRUE(model.initialize({7, kStart, 0.5, 25}, 400, {true, true, false}));
    for (std::uint32_t i = 0; i < 100; ++i) ASSERT_EQ(model.step(interval(i, {{true, true, false}, false}, {-100, 20, 0.375, true})).fault, EvPowerFault::None);
    EXPECT_GT(model.battery_state().soc, 0.5); EXPECT_LT(model.battery_state().electrical->current_a, 0);
    EXPECT_GT(model.power_state().bus_voltage_v, model.battery_state().electrical->voltage_v);
    EXPECT_GT(model.battery_state().electrical->voltage_v, 400); EXPECT_NEAR(model.diagnostic_state().balance_error_j, 0, 0.00072);
}
TEST_F(EvCircuitTest, InverterOffRequiresActualZeroRatherThanErasingResidualTorque) {
    EXPECT_EQ(model.step(interval(0, {}, {10, 20, 0, false})).fault, EvPowerFault::InverterOff);
    EXPECT_EQ(model.battery_state().energy_j, 90000000); EXPECT_EQ(model.power_state().bus_voltage_v, 0);
}
TEST_F(EvCircuitTest, InverterPowerCannotBeAppliedToAnUnchargedBus) {
    EXPECT_EQ(model.step(interval(0, {}, {0, 20, 0, true})).fault, EvPowerFault::Circuit);
    EXPECT_EQ(model.power_state().bus_voltage_v, 0);
}
TEST_F(EvCircuitTest, AuxiliaryKeepsConsumingAtOffAndIsAnExplicitIndependentBranch) {
    step(0, {}, {0, 20, 0.375, false});
    EXPECT_EQ(model.diagnostic_state().capacitor_j, 0); EXPECT_EQ(model.diagnostic_state().motor_loss_j, 0);
    EXPECT_NEAR(model.battery_state().auxiliary_j, (400-0.05*0.375)*0.375*0.01, 1e-10);
    EXPECT_LT(model.battery_state().soc, 0.5); EXPECT_NEAR(model.battery_state().ohmic_loss_j, 0.05*0.375*0.375*0.01, 1e-12);
}
TEST_F(EvCircuitTest, PartialOrHeldPowerSensorsDoNotEraseThePhysicalEnergyFlow) {
    step(0, {}, {0, 20, 0.375, false}); const auto first = *model.power_observation();
    PowerFaultInjection fault; fault.hold_sensors = true;
    ASSERT_EQ(model.step(interval(1, {}, {0, 20, 0.375, false}), fault).fault, EvPowerFault::None);
    EXPECT_EQ(model.power_observation()->identity.source_time_ns, first.identity.source_time_ns);
    EXPECT_GT(model.battery_observation().batch.source_time_ns, first.identity.source_time_ns);
    fault = {}; fault.invalidate_current = true;
    ASSERT_EQ(model.step(interval(2, {}, {0, 20, 0.375, false}), fault).fault, EvPowerFault::None);
    EXPECT_FALSE(model.power_observation()->pack_current_a); EXPECT_TRUE(model.battery_observation().electrical);
    EXPECT_GT(model.battery_state().auxiliary_j, 4);
}
TEST_F(EvCircuitTest, MissingPhysicalGroupsNeverBecomeZeroLoad) {
    auto in = interval(0); in.inputs.actual_torque_nm.reset();
    EXPECT_EQ(model.step(in).fault, EvPowerFault::Inputs); EXPECT_FALSE(model.battery_observation().available);
    EXPECT_EQ(model.step(interval(0)).fault, EvPowerFault::Inputs);
}
TEST_F(EvCircuitTest, WrongScenarioAndCachedValueMutationAreRejected) {
    auto in = interval(0); in.inputs.electrical->identity.epoch = 8;
    EXPECT_EQ(model.step(in).fault, EvPowerFault::Identity);
    ASSERT_TRUE(model.initialize({8, kStart+10*kMs, 0.5, 25}, 0));
    in = interval(1); in.inputs.actual_torque_nm->identity.epoch = in.inputs.wheel_speed_rad_s->identity.epoch = in.inputs.electrical->identity.epoch = 8;
    ASSERT_EQ(model.step(in).fault, EvPowerFault::None);
    in.begin_ns += 10*kMs; in.end_ns += 10*kMs; in.inputs.electrical->value.auxiliary_current_a = 1;
    EXPECT_EQ(model.step(in).fault, EvPowerFault::Identity);
}
TEST_F(EvCircuitTest, EndSampleCannotBeAppliedBackwardsAndPhysicalGapsAreNotFilled) {
    auto in = interval(0); in.inputs.wheel_speed_rad_s->identity.source_time_ns = in.end_ns;
    EXPECT_EQ(model.step(in).fault, EvPowerFault::Inputs);
    ASSERT_TRUE(model.initialize({8, kStart+10*kMs, 0.5, 25}, 0));
    EXPECT_EQ(model.step(interval(2)).fault, EvPowerFault::Timing);
}
TEST_F(EvCircuitTest, HeldInputsExpireAtIntervalEnd) {
    auto in = interval(0);
    for (int i = 0; i < 3; ++i) {
        ASSERT_EQ(model.step(in).fault, EvPowerFault::None); in.begin_ns += 10*kMs; in.end_ns += 10*kMs;
    }
    EXPECT_EQ(model.step(in).fault, EvPowerFault::Stale);
}
TEST_F(EvCircuitTest, IndependentSourcesCannotExceedTheSkewBudget) {
    step(0); auto in = interval(1); in.inputs.wheel_speed_rad_s = interval(0).inputs.wheel_speed_rad_s;
    ASSERT_EQ(model.step(in).fault, EvPowerFault::None);
    in = interval(2); in.inputs.wheel_speed_rad_s = interval(0).inputs.wheel_speed_rad_s;
    EXPECT_EQ(model.step(in).fault, EvPowerFault::Skew);
}
TEST_F(EvCircuitTest, ClockRegressionDoesNotRewindEitherStateAndResetNeedsNewPhysicalScenario) {
    step(0); auto in = interval(0); in.end_ns = kStart;
    EXPECT_EQ(model.step(in).fault, EvPowerFault::Clock); EXPECT_EQ(model.power_state().identity.sequence, 1U);
    EXPECT_FALSE(model.initialize({7, kStart+10*kMs, 0.5, 25}, 0));
    EXPECT_FALSE(model.initialize({8, kStart, 0.5, 25}, 0));
    EXPECT_TRUE(model.initialize({8, kStart+10*kMs, 0.5, 25}, 0));
}
TEST(EvCircuitPhysics, FullBatteryRejectionDoesNotPartiallyAdvanceCapacitorOrContacts) {
    EvPowerModel model({}, battery_config(), circuit_config()); ASSERT_TRUE(model.initialize({7, kStart, 1, 25}, 400, {true, true, false}));
    const auto result = model.step(interval(0, {{true, true, false}, false}, {-200, 20, 0, true}));
    EXPECT_EQ(result.fault, EvPowerFault::Battery); EXPECT_EQ(result.battery_fault, BatteryFault::CapacityViolation);
    EXPECT_GT(result.boundary_excess_j, 0); EXPECT_EQ(model.power_state().bus_voltage_v, 400);
    EXPECT_EQ(model.power_state().identity.sequence, 0U); EXPECT_EQ(model.battery_state().soc, 1);
}
TEST(EvCircuitPhysics, ElectricalSubstepRefinementConvergesToAnalyticalRcTransient) {
    const auto sample = [](std::uint64_t integration_ns) {
        auto config = circuit_config(); config.integration_step_ns = integration_ns;
        PowerModel model(config); if (!model.initialize({7, 0, kStart}, 390, {true, true, false})) throw std::runtime_error("init");
        PowerEnvironment env{400, 0, true, true, true, false, false, 0.05, 0, 0};
        if (model.step({kStart, kStart+100000, {env, {7, 0, kStart}, kStart}, {{true, true, false}, false}}) != PowerModelFault::None) throw std::runtime_error("step");
        return model.diagnostic_state().bus_voltage_v;
    };
    const auto exact = 400-10*std::exp(-0.0001/(0.07*0.002));
    EXPECT_LT(std::abs(sample(25000)-exact), std::abs(sample(50000)-exact));
    EXPECT_NEAR(sample(25000), exact, 0.02);
}
TEST(EvCircuitPhysics, LongAlternatingTractionBalancesAllEnergyOwnersWithoutDrift) {
    EvPowerModel model({}, battery_config(), circuit_config()); ASSERT_TRUE(model.initialize({7, kStart, 0.5, 25}, 400, {true, true, false}));
    for (std::uint32_t i = 0; i < 10000; ++i) {
        const auto result = model.step(interval(i, {{true, true, false}, false}, {i%2 == 0 ? 100.0 : -100.0, 20, 0.375, true}));
        ASSERT_EQ(result.fault, EvPowerFault::None) << i;
    }
    EXPECT_NEAR(model.diagnostic_state().mechanical_j, 0, 1e-9);
    EXPECT_GT(model.diagnostic_state().main_loss_j, 0); EXPECT_LT(model.battery_state().soc, 0.5);
    EXPECT_NEAR(model.diagnostic_state().balance_error_j, 0, 0.00072);
}
TEST(EvCircuitPhysics, DemoReserveCoversSteadyIdleAuxiliaryAndWorstMainPathLoss) {
    const DriveEnergyConfig motor;
    const auto maximum_dc = calculate_motor_power(motor, motor.maximum_abs_torque_nm, motor.maximum_speed_rad_s);
    ASSERT_TRUE(maximum_dc);
    const auto path_loss = circuit_config().main_resistance_ohm*std::pow(maximum_dc->dc_w/300, 2);
    EXPECT_LT(motor.inverter_idle_w+0.375*450+path_loss, 500);
    // This is the steady target budget; capacitor recharge and finite torque residuals remain actual flow.
}
}  // namespace
