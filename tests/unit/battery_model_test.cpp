#include "battery_model.hpp"

#include <gtest/gtest.h>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace {
using namespace stratadrive::simulation;
constexpr std::uint64_t kStart = 1000000000, kMs = 1000000;
BatteryConfig fixture_config() { return {180000000, 400, 0.05, 200000, 20, 25, 100, 0.01, 1, 100000}; }
BatteryConfig ideal_config() {
    auto config = fixture_config(); config.capacity_j = 1000; config.open_circuit_voltage_v = 100;
    config.resistance_ohm = config.cooling_w_k = 0; config.thermal_capacity_j_k = 1000;
    return config;
}
struct PowerInput { double traction_w; double auxiliary_w{0}; };
BatteryInterval interval(std::uint32_t step, PowerInput input) {
    const auto begin = kStart + static_cast<std::uint64_t>(step)*20*kMs;
    return {begin, begin + 20*kMs, {{1, step, begin}, begin, input.traction_w, input.auxiliary_w}};
}
void expect_no_current_observations(const BatteryModel& model) {
    const auto& sample = model.observation();
    EXPECT_FALSE(sample.available);
    EXPECT_FALSE(sample.soc); EXPECT_FALSE(sample.electrical); EXPECT_FALSE(sample.temperature);
    EXPECT_FALSE(sample.cell_voltage); EXPECT_FALSE(sample.cell_temperature);
}
class BatteryModelTest : public ::testing::Test {
protected:
    BatteryModel model{fixture_config()};
    void SetUp() override { ASSERT_TRUE(model.initialize({1, kStart, 0.5, 25})); }
    void step(std::uint32_t sequence, PowerInput input, BatterySensorCapture capture = {}) {
        ASSERT_EQ(model.step(interval(sequence, input), capture).fault, BatteryFault::None);
    }
};
BatteryElectricalInterval integrated_interval() {
    // Two 10 ms intervals at +10 A, +20 A: q=0.3 C, integral(I^2)=5 A^2s.
    return {kStart, kStart+20*kMs, {{1, 1, kStart+20*kMs}, kStart, 0.3, 5, 20, 119.75, 0, 0, 7980, 7980, 0}};
}
TEST_F(BatteryModelTest, IntegratedCurrentUsesMeanSquareRatherThanSquareOfMeanForHeat) {
    ASSERT_EQ(model.step_integrated(integrated_interval()).fault, BatteryFault::None);
    EXPECT_NEAR(model.diagnostic_state().ohmic_loss_j, 0.25, 1e-12);
    EXPECT_NEAR(model.diagnostic_state().energy_j, 90000000-120, 1e-8);
    EXPECT_EQ(model.observation().electrical->value.current_a, 20);
    EXPECT_EQ(model.observation().electrical->value.voltage_v, 399);
}
TEST_F(BatteryModelTest, BidirectionalIntegratedCurrentCanHeatBatteryWithZeroNetCharge) {
    auto in = integrated_interval(); in.flow.charge_c = 0; in.flow.current_squared_a2s = 2; in.flow.end_current_a = -10;
    in.flow.drawn_dc_j = 39.95; in.flow.received_dc_j = 40.05; in.flow.peak_abs_terminal_w = in.flow.peak_abs_branch_w = 4005;
    ASSERT_EQ(model.step_integrated(in).fault, BatteryFault::None);
    EXPECT_EQ(model.diagnostic_state().energy_j, 90000000); EXPECT_NEAR(model.diagnostic_state().ohmic_loss_j, 0.1, 1e-12);
    EXPECT_GT(model.observation().temperature->value, 25);
}
TEST_F(BatteryModelTest, ImpossibleCurrentMomentsAndNonconservingIntegratedFlowAreRejected) {
    auto in = integrated_interval(); in.flow.current_squared_a2s = 0;
    EXPECT_EQ(model.step_integrated(in).fault, BatteryFault::InvalidInput);
    ASSERT_TRUE(model.initialize({2, kStart+20*kMs, 0.5, 25}));
    in = integrated_interval(); in.begin_ns += 20*kMs; in.end_ns += 20*kMs;
    in.flow.identity = {2, 1, in.end_ns}; in.flow.input_time_ns = in.begin_ns; in.flow.drawn_dc_j += 1;
    EXPECT_EQ(model.step_integrated(in).fault, BatteryFault::InvalidInput);
}
TEST_F(BatteryModelTest, IntegratedFlowSourceIsEndButDependencyMustPrecedeTheWholeInterval) {
    auto in = integrated_interval(); in.flow.input_time_ns = in.end_ns;
    EXPECT_EQ(model.step_integrated(in).fault, BatteryFault::InvalidInput);
    EXPECT_EQ(model.diagnostic_state().energy_j, 90000000);
}
TEST_F(BatteryModelTest, IntegratedCurrentAndConstantPowerModesCannotBeMixedWithinAScenario) {
    ASSERT_EQ(model.step_integrated(integrated_interval()).fault, BatteryFault::None);
    EXPECT_EQ(model.step(interval(1, {1000})).fault, BatteryFault::InvalidInput);
    BatteryModel other(fixture_config()); ASSERT_TRUE(other.initialize({1, kStart, 0.5, 25}));
    ASSERT_EQ(other.step(interval(0, {1000})).fault, BatteryFault::None);
    auto in = integrated_interval(); in.begin_ns += 20*kMs; in.end_ns += 20*kMs;
    in.flow.identity.source_time_ns = in.end_ns; in.flow.input_time_ns = in.begin_ns;
    EXPECT_EQ(other.step_integrated(in).fault, BatteryFault::InvalidInput);
}
TEST(BatteryConfiguration, RejectsInvalidElectricalThermalCapacityAndTiming) {
    auto config = fixture_config(); config.capacity_j = 0;
    EXPECT_THROW(BatteryModel{config}, std::invalid_argument);
    config = fixture_config(); config.open_circuit_voltage_v = std::numeric_limits<double>::infinity();
    EXPECT_THROW(BatteryModel{config}, std::invalid_argument);
    config = fixture_config(); config.resistance_ohm = -1;
    EXPECT_THROW(BatteryModel{config}, std::invalid_argument);
    config = fixture_config(); config.thermal_capacity_j_k = 0;
    EXPECT_THROW(BatteryModel{config}, std::invalid_argument);
    config = fixture_config(); config.cooling_w_k = -1;
    EXPECT_THROW(BatteryModel{config}, std::invalid_argument);
    config = fixture_config(); config.series_cells = 0;
    EXPECT_THROW(BatteryModel{config}, std::invalid_argument);
    config = fixture_config(); config.cell_voltage_half_spread_v = 3;
    EXPECT_THROW(BatteryModel{config}, std::invalid_argument);
    config = fixture_config(); config.max_step_ns = 0;
    EXPECT_THROW(BatteryModel{config}, std::invalid_argument);
    config = fixture_config(); config.max_input_age_ns = config.max_step_ns-1;
    EXPECT_THROW(BatteryModel{config}, std::invalid_argument);
}
TEST(BatteryConfiguration, ExplicitInitializationIsRequiredAndValidatesKnownPhysicalState) {
    BatteryModel model(fixture_config());
    EXPECT_EQ(model.step(interval(0, {1000})).fault, BatteryFault::NotInitialized);
    EXPECT_FALSE(model.initialize({0, kStart, 0.5, 25}));
    EXPECT_FALSE(model.initialize({1, kStart, 1.01, 25}));
    EXPECT_FALSE(model.initialize({1, kStart, std::numeric_limits<double>::quiet_NaN(), 25}));
    EXPECT_FALSE(model.initialize({1, kStart, 0.5, -274}));
    ASSERT_TRUE(model.initialize({1, kStart, 0.5, 25}));
    EXPECT_DOUBLE_EQ(model.diagnostic_state().energy_j, 90000000);
    EXPECT_TRUE(model.observation().soc); EXPECT_TRUE(model.observation().temperature);
    EXPECT_TRUE(model.observation().cell_temperature);
    EXPECT_FALSE(model.observation().electrical); EXPECT_FALSE(model.observation().cell_voltage);
}
TEST_F(BatteryModelTest, DischargeAccountsForTerminalPowerAuxiliaryAndOhmicLossSeparately) {
    step(0, {20000, 200});
    const auto& state = model.diagnostic_state();
    const auto electrical = *state.electrical;
    EXPECT_GT(electrical.current_a, 0); EXPECT_LT(electrical.voltage_v, 400);
    EXPECT_NEAR(electrical.voltage_v*electrical.current_a, 20200, 1e-9);
    EXPECT_NEAR(state.drawn_dc_j, 400, 1e-12); EXPECT_NEAR(state.auxiliary_j, 4, 1e-12);
    EXPECT_GT(state.ohmic_loss_j, 0); EXPECT_DOUBLE_EQ(state.received_dc_j, 0);
    EXPECT_NEAR(state.initial_energy_j-state.energy_j, 404+state.ohmic_loss_j, 2e-8);
    EXPECT_LT(state.soc, 0.5); EXPECT_GT(state.temperature_c, 25);
}
TEST_F(BatteryModelTest, ChargingReturnsLessStoredEnergyThanDcInputBecauseOfLoadAndResistance) {
    step(0, {-10000, 200});
    const auto& state = model.diagnostic_state();
    EXPECT_LT(state.electrical->current_a, 0); EXPECT_GT(state.electrical->voltage_v, 400);
    EXPECT_NEAR(state.received_dc_j, 200, 1e-12); EXPECT_DOUBLE_EQ(state.drawn_dc_j, 0);
    EXPECT_NEAR(state.energy_j-state.initial_energy_j, 200-4-state.ohmic_loss_j, 2e-8);
    EXPECT_GT(state.soc, 0.5); EXPECT_LT(state.energy_j-state.initial_energy_j, state.received_dc_j);
}
TEST_F(BatteryModelTest, AuxiliaryLoadCanConsumeAllReturnedDcPowerWithoutChargingBattery) {
    step(0, {-100, 200});
    const auto& state = model.diagnostic_state();
    EXPECT_GT(state.received_dc_j, 0); EXPECT_LT(state.energy_j, state.initial_energy_j);
    EXPECT_GT(state.electrical->current_a, 0);
}
TEST_F(BatteryModelTest, ValidZeroPowerHasZeroCurrentAndPreservesEnergy) {
    step(0, {0, 0});
    const auto& sample = model.observation();
    ASSERT_TRUE(sample.electrical); ASSERT_TRUE(sample.soc);
    EXPECT_DOUBLE_EQ(sample.electrical->value.current_a, 0);
    EXPECT_DOUBLE_EQ(sample.electrical->value.voltage_v, 400);
    EXPECT_DOUBLE_EQ(model.diagnostic_state().energy_j, 90000000);
    EXPECT_DOUBLE_EQ(model.diagnostic_state().ohmic_loss_j, 0);
}
TEST_F(BatteryModelTest, UnknownPowerNeverBecomesZeroAndLatchesWithoutCommittingEnergy) {
    auto input = interval(0, {0, 0}); input.power.traction_dc_w.reset();
    EXPECT_EQ(model.step(input).fault, BatteryFault::PowerUnavailable);
    EXPECT_EQ(model.step(interval(0, {0, 0})).fault, BatteryFault::PowerUnavailable);
    EXPECT_EQ(model.diagnostic_state().identity.sequence, 0U);
    EXPECT_DOUBLE_EQ(model.diagnostic_state().energy_j, 90000000);
    expect_no_current_observations(model);
}
TEST_F(BatteryModelTest, UnknownAuxiliaryAndInvalidPowerAreRejectedAtomically) {
    auto input = interval(0, {0}); input.power.auxiliary_w.reset();
    EXPECT_EQ(model.step(input).fault, BatteryFault::PowerUnavailable);
    ASSERT_TRUE(model.initialize({2, kStart + 20*kMs, 0.5, 25}));
    input = interval(1, {std::numeric_limits<double>::quiet_NaN()}); input.power.identity.epoch = 2;
    EXPECT_EQ(model.step(input).fault, BatteryFault::InvalidInput);
    EXPECT_DOUBLE_EQ(model.diagnostic_state().drawn_dc_j, 0);
}
TEST_F(BatteryModelTest, NegativeAuxiliaryOrExcessiveDcPowerDoesNotCreateEnergy) {
    EXPECT_EQ(model.step(interval(0, {0, -1})).fault, BatteryFault::InvalidInput);
    ASSERT_TRUE(model.initialize({2, kStart + 20*kMs, 0.5, 25}));
    auto input = interval(1, {100001}); input.power.identity.epoch = 2;
    EXPECT_EQ(model.step(input).fault, BatteryFault::InvalidInput);
    EXPECT_DOUBLE_EQ(model.diagnostic_state().energy_j, 90000000);
}
TEST_F(BatteryModelTest, CachedActualPowerMayCoverOnlyContiguousFreshIntervals) {
    auto input = interval(0, {1000});
    ASSERT_EQ(model.step(input).fault, BatteryFault::None);
    input.begin_ns += 20*kMs; input.end_ns += 20*kMs;
    ASSERT_EQ(model.step(input).fault, BatteryFault::None);
    EXPECT_EQ(model.observation().batch.sequence, 2U);
    EXPECT_EQ(model.observation().electrical->input_time_ns, kStart);
    input.begin_ns += 20*kMs; input.end_ns += 20*kMs;
    EXPECT_EQ(model.step(input).fault, BatteryFault::InputStale);
    EXPECT_EQ(model.diagnostic_state().identity.sequence, 2U);
    expect_no_current_observations(model);
}
TEST_F(BatteryModelTest, NewProducerTimestampCannotRefreshOldPowerDependency) {
    step(0, {1000});
    auto input = interval(1, {1000}); input.power.input_time_ns = kStart;
    ASSERT_EQ(model.step(input).fault, BatteryFault::None);
    input = interval(2, {1000}); input.power.input_time_ns = kStart;
    EXPECT_EQ(model.step(input).fault, BatteryFault::InputStale);
}
TEST_F(BatteryModelTest, CachedIdentityCannotChangePhysicalPower) {
    step(0, {1000});
    auto input = interval(1, {2000});
    input.power.identity = {1, 0, kStart}; input.power.input_time_ns = kStart;
    EXPECT_EQ(model.step(input).fault, BatteryFault::IdentityError);
    EXPECT_EQ(model.diagnostic_state().identity.sequence, 1U);
}
TEST_F(BatteryModelTest, WrongEpochOrNonIncreasingSourceIsNotAccepted) {
    auto input = interval(0, {1000}); input.power.identity.epoch = 2;
    EXPECT_EQ(model.step(input).fault, BatteryFault::IdentityError);
    ASSERT_TRUE(model.initialize({2, kStart + 20*kMs, 0.5, 25}));
    input = interval(1, {1000}); input.power.identity.epoch = 2;
    ASSERT_EQ(model.step(input).fault, BatteryFault::None);
    input = interval(2, {1000}); input.power.identity = {2, 2, kStart + 20*kMs};
    input.power.input_time_ns = kStart + 20*kMs;
    EXPECT_EQ(model.step(input).fault, BatteryFault::IdentityError);
}
TEST_F(BatteryModelTest, FutureAndPreInitializationDependenciesAreInvalid) {
    auto input = interval(0, {1000}); input.power.input_time_ns = kStart + 1;
    EXPECT_EQ(model.step(input).fault, BatteryFault::InvalidInput);
    ASSERT_TRUE(model.initialize({2, kStart + 20*kMs, 0.5, 25}));
    input = interval(1, {1000}); input.power.identity.epoch = 2; input.power.input_time_ns = kStart;
    EXPECT_EQ(model.step(input).fault, BatteryFault::InvalidInput);
}
TEST_F(BatteryModelTest, DuplicateIntervalCannotDoubleIntegratePower) {
    const auto input = interval(0, {1000});
    ASSERT_EQ(model.step(input).fault, BatteryFault::None);
    const auto energy = model.diagnostic_state().energy_j;
    EXPECT_EQ(model.step(input).fault, BatteryFault::TimingError);
    EXPECT_DOUBLE_EQ(model.diagnostic_state().energy_j, energy);
}
TEST_F(BatteryModelTest, MissingIntervalAndOversizedStepAreNotBackfilled) {
    EXPECT_EQ(model.step(interval(1, {1000})).fault, BatteryFault::TimingError);
    ASSERT_TRUE(model.initialize({2, kStart + 40*kMs, 0.5, 25}));
    auto input = interval(2, {1000}); input.end_ns += 21*kMs; input.power.identity.epoch = 2;
    EXPECT_EQ(model.step(input).fault, BatteryFault::TimingError);
    EXPECT_DOUBLE_EQ(model.diagnostic_state().drawn_dc_j, 0);
}
TEST_F(BatteryModelTest, ClockRegressionDoesNotUpdateEnergyOrMakeFreshSensorData) {
    step(0, {1000});
    EXPECT_EQ(model.step(interval(0, {1000})).fault, BatteryFault::TimingError); // duplicate boundary
    ASSERT_TRUE(model.initialize({2, kStart + 20*kMs, 0.5, 25}));
    auto input = interval(0, {1000}); input.end_ns = kStart + 19*kMs;
    EXPECT_EQ(model.step(input).fault, BatteryFault::ClockError);
    expect_no_current_observations(model);
}
TEST(BatteryBoundaries, FullAndEmptyAreValidButImpossiblePowerIsReportedWithoutClipping) {
    BatteryModel model(ideal_config());
    ASSERT_TRUE(model.initialize({1, kStart, 1, 25}));
    const auto full = model.step(interval(0, {-100}));
    EXPECT_EQ(full.fault, BatteryFault::CapacityViolation); EXPECT_DOUBLE_EQ(full.boundary_excess_j, 2);
    EXPECT_DOUBLE_EQ(model.diagnostic_state().energy_j, 1000);
    EXPECT_DOUBLE_EQ(model.diagnostic_state().received_dc_j, 0);
    expect_no_current_observations(model);
    ASSERT_TRUE(model.initialize({2, kStart + 20*kMs, 0, 25}));
    auto input = interval(1, {100}); input.power.identity.epoch = 2;
    const auto empty = model.step(input);
    EXPECT_EQ(empty.fault, BatteryFault::CapacityViolation); EXPECT_DOUBLE_EQ(empty.boundary_excess_j, 2);
    EXPECT_DOUBLE_EQ(model.diagnostic_state().energy_j, 0);
    ASSERT_TRUE(model.initialize({3, kStart + 40*kMs, 1, 25}));
    input = interval(2, {-1e-100}); input.power.identity.epoch = 3;
    const auto tiny = model.step(input); // below one ULP of a full 1000 J reservoir
    EXPECT_EQ(tiny.fault, BatteryFault::CapacityViolation); EXPECT_GT(tiny.boundary_excess_j, 0);
}
TEST(BatteryBoundaries, ExactEmptyThenChargeAndExactFullThenDischargeConserveEnergy) {
    auto config = ideal_config(); config.capacity_j = 4;
    BatteryModel model(config); ASSERT_TRUE(model.initialize({1, kStart, 0.5, 25}));
    ASSERT_EQ(model.step(interval(0, {100})).fault, BatteryFault::None);
    EXPECT_DOUBLE_EQ(model.diagnostic_state().energy_j, 0);
    ASSERT_EQ(model.step(interval(1, {-100})).fault, BatteryFault::None);
    ASSERT_EQ(model.step(interval(2, {-100})).fault, BatteryFault::None);
    EXPECT_DOUBLE_EQ(model.diagnostic_state().soc, 1);
    ASSERT_EQ(model.step(interval(3, {100})).fault, BatteryFault::None);
    EXPECT_DOUBLE_EQ(model.diagnostic_state().energy_j, 2);
}
TEST(BatteryBoundaries, ElectricalMaximumPowerIsEnforcedByTheCircuitEquation) {
    auto config = fixture_config(); config.resistance_ohm = 1; config.max_abs_power_w = 100000;
    BatteryModel model(config); ASSERT_TRUE(model.initialize({1, kStart, 0.5, 25}));
    EXPECT_EQ(model.step(interval(0, {40001})).fault, BatteryFault::ElectricalInfeasible);
    EXPECT_DOUBLE_EQ(model.diagnostic_state().energy_j, 90000000);
    ASSERT_TRUE(model.initialize({2, kStart + 20*kMs, 0.5, 25}));
    auto input = interval(1, {40000}); input.power.identity.epoch = 2;
    ASSERT_EQ(model.step(input).fault, BatteryFault::None);
    EXPECT_DOUBLE_EQ(model.diagnostic_state().electrical->voltage_v, 200);
    EXPECT_DOUBLE_EQ(model.diagnostic_state().electrical->current_a, 200);
}
TEST(BatteryThermal, ConstantLoadFollowsLumpedAnalyticalThermalResponse) {
    auto config = fixture_config(); config.thermal_capacity_j_k = 1000; config.cooling_w_k = 10;
    BatteryModel model(config); ASSERT_TRUE(model.initialize({1, kStart, 0.5, 30}));
    // Choose I=100 A: Vt=395 V, Pdc=39500 W, heat=500 W.
    for (unsigned i = 0; i < 500; ++i) ASSERT_EQ(model.step(interval(i, {39500})).fault, BatteryFault::None);
    const auto expected = 25 + 500.0/10 + (30-25-500.0/10)*std::exp(-10.0*10/1000);
    EXPECT_NEAR(model.diagnostic_state().temperature_c, expected, 1e-10);
    EXPECT_NEAR(model.diagnostic_state().ohmic_loss_j, 5000, 1e-9);
}
TEST(BatteryThermal, ZeroResistanceAndAdiabaticHeatingAreSeparateCases) {
    auto config = fixture_config(); config.cooling_w_k = 0; config.thermal_capacity_j_k = 1000;
    BatteryModel model(config); ASSERT_TRUE(model.initialize({1, kStart, 0.5, 25}));
    ASSERT_EQ(model.step(interval(0, {39500})).fault, BatteryFault::None);
    EXPECT_NEAR(model.diagnostic_state().temperature_c, 25.01, 1e-12);
    config.resistance_ohm = 0;
    BatteryModel ideal(config); ASSERT_TRUE(ideal.initialize({1, kStart, 0.5, 25}));
    ASSERT_EQ(ideal.step(interval(0, {39500})).fault, BatteryFault::None);
    EXPECT_DOUBLE_EQ(ideal.diagnostic_state().temperature_c, 25);
    EXPECT_DOUBLE_EQ(ideal.diagnostic_state().ohmic_loss_j, 0);
}
TEST(BatteryThermal, HotPackCoolsAtZeroElectricalPowerWithoutChangingSoc) {
    BatteryModel model(fixture_config()); ASSERT_TRUE(model.initialize({1, kStart, 0.5, 40}));
    for (unsigned i = 0; i < 500; ++i) ASSERT_EQ(model.step(interval(i, {0, 0})).fault, BatteryFault::None);
    EXPECT_NEAR(model.diagnostic_state().temperature_c, 25 + 15*std::exp(-20.0*10/200000), 1e-10);
    EXPECT_DOUBLE_EQ(model.diagnostic_state().soc, 0.5);
}
TEST_F(BatteryModelTest, SensorGroupsAndCellPairsHaveIndependentValidityAndAcquisitionIdentity) {
    step(0, {1000});
    const auto old_voltage = model.observation().cell_voltage.value();
    BatterySensorCapture capture; capture.cell_voltage = SensorAction::Hold;
    capture.temperature = SensorAction::Invalidate;
    capture.temperature_override = CellExtrema{20, 80};
    step(1, {2000}, capture);
    const auto& sample = model.observation();
    ASSERT_TRUE(sample.cell_voltage); ASSERT_TRUE(sample.cell_temperature); ASSERT_TRUE(sample.electrical);
    EXPECT_EQ(sample.batch.sequence, 2U);
    EXPECT_EQ(sample.cell_voltage->identity.sequence, old_voltage.identity.sequence);
    EXPECT_EQ(sample.cell_voltage->identity.source_time_ns, old_voltage.identity.source_time_ns);
    EXPECT_EQ(sample.cell_voltage->input_time_ns, old_voltage.input_time_ns);
    EXPECT_EQ(sample.electrical->identity.source_time_ns, kStart + 40*kMs);
    EXPECT_FALSE(sample.temperature);
    EXPECT_DOUBLE_EQ(sample.cell_temperature->value.maximum, 80);
    EXPECT_LT(model.diagnostic_state().temperature_c, 26); // sensor fault does not heat the physical model
}
TEST_F(BatteryModelTest, InvalidCellPairCannotHideBehindFreshPackObservation) {
    BatterySensorCapture capture; capture.voltage_override = CellExtrema{4.2, 3.8};
    capture.temperature_override = CellExtrema{20, std::numeric_limits<double>::quiet_NaN()};
    step(0, {1000}, capture);
    EXPECT_TRUE(model.observation().electrical); EXPECT_TRUE(model.observation().soc);
    EXPECT_TRUE(model.observation().temperature);
    EXPECT_FALSE(model.observation().cell_voltage); EXPECT_FALSE(model.observation().cell_temperature);
    EXPECT_EQ(model.fault(), BatteryFault::None);
}
TEST_F(BatteryModelTest, GeneratedExtremaBracketPackMeanAndTemperature) {
    step(0, {1000});
    const auto& sample = model.observation();
    const auto mean = sample.electrical->value.voltage_v/100;
    EXPECT_NEAR(sample.cell_voltage->value.minimum, mean-0.01, 1e-14);
    EXPECT_NEAR(sample.cell_voltage->value.maximum, mean+0.01, 1e-14);
    EXPECT_NEAR(sample.cell_temperature->value.minimum, sample.temperature->value-1, 1e-14);
    EXPECT_NEAR(sample.cell_temperature->value.maximum, sample.temperature->value+1, 1e-14);
}
TEST_F(BatteryModelTest, HoldNeverInventsUnavailableSensorAndAcquisitionCanResume) {
    BatterySensorCapture capture; capture.electrical = capture.cell_voltage = SensorAction::Hold;
    step(0, {1000}, capture);
    EXPECT_FALSE(model.observation().electrical); EXPECT_FALSE(model.observation().cell_voltage);
    step(1, {1000});
    ASSERT_TRUE(model.observation().cell_voltage);
    EXPECT_EQ(model.observation().cell_voltage->identity.sequence, 2U);
    capture.cell_voltage = SensorAction::Invalidate;
    step(2, {1000}, capture); EXPECT_FALSE(model.observation().cell_voltage);
}
TEST_F(BatteryModelTest, ScenarioResetIsExplicitAndDoesNotMasqueradeAsAnEcuRestart) {
    step(0, {1000});
    const auto before = model.diagnostic_state().energy_j;
    EXPECT_FALSE(model.initialize({1, kStart + 20*kMs, 1, 25}));
    EXPECT_FALSE(model.initialize({2, kStart + 19*kMs, 1, 25}));
    EXPECT_DOUBLE_EQ(model.diagnostic_state().energy_j, before);
    ASSERT_TRUE(model.initialize({2, kStart + 20*kMs, 0.6, 30}));
    EXPECT_DOUBLE_EQ(model.diagnostic_state().energy_j, 108000000);
    EXPECT_DOUBLE_EQ(model.diagnostic_state().drawn_dc_j, 0);
    EXPECT_EQ(model.observation().batch.epoch, 2U); EXPECT_EQ(model.observation().batch.sequence, 0U);
    EXPECT_FALSE(model.observation().electrical); EXPECT_FALSE(model.observation().cell_voltage);
}
TEST(BatteryNumerics, LongAlternatingActualPowerKeepsDeclaredEnergyBalanceTolerance) {
    BatteryModel model(fixture_config()); ASSERT_TRUE(model.initialize({1, kStart, 0.5, 25}));
    for (unsigned i = 0; i < 100000; ++i) {
        ASSERT_EQ(model.step(interval(i, {i % 2 ? -10000.0 : 20000.0, 200})).fault, BatteryFault::None);
    }
    const auto& state = model.diagnostic_state();
    EXPECT_NEAR(state.drawn_dc_j, 20000000, 1e-7);
    EXPECT_NEAR(state.received_dc_j, 10000000, 1e-7);
    EXPECT_NEAR(state.auxiliary_j, 400000, 1e-7);
    EXPECT_NEAR((state.initial_energy_j-state.energy_j) -
        (state.drawn_dc_j-state.received_dc_j+state.auxiliary_j+state.ohmic_loss_j), 0, 0.00018);
    EXPECT_NEAR(state.soc, state.energy_j/180000000, 1e-15);
}
TEST(BatteryNumerics, NonfiniteElectricalArithmeticFailsWithoutPartialCommit) {
    auto config = fixture_config(); config.resistance_ohm = 1e308;
    BatteryModel model(config); ASSERT_TRUE(model.initialize({1, kStart, 0.5, 25}));
    EXPECT_EQ(model.step(interval(0, {-1000})).fault, BatteryFault::NumericalError);
    EXPECT_DOUBLE_EQ(model.diagnostic_state().received_dc_j, 0);
    EXPECT_EQ(model.diagnostic_state().identity.sequence, 0U);
    expect_no_current_observations(model);
    config = fixture_config(); config.resistance_ohm = 0;
    BatteryModel tiny(config); ASSERT_TRUE(tiny.initialize({1, kStart, 0.5, 25}));
    EXPECT_EQ(tiny.step(interval(0, {std::numeric_limits<double>::denorm_min()})).fault, BatteryFault::NumericalError);
    EXPECT_EQ(tiny.diagnostic_state().identity.sequence, 0U); expect_no_current_observations(tiny);
}
}  // namespace
