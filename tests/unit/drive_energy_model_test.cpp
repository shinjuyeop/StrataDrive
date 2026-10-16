#include "drive_energy_model.hpp"
#include "drive_sil.hpp"
#include "bms_controller.hpp"

#include <gtest/gtest.h>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace {
using namespace stratadrive;
using namespace stratadrive::simulation;
constexpr std::uint64_t kStart = 1000000000, kMs = 1000000;
BatteryConfig battery_config() { return {180000000, 400, 0.05, 200000, 20, 25, 100, 0.01, 1, 100000}; }
BatteryConfig ideal_battery() { auto c = battery_config(); c.resistance_ohm = 0; return c; }
DriveEnergyConfig ideal_drive() { auto c = DriveEnergyConfig{}; c.motoring_efficiency = c.generating_efficiency = 1; c.copper_loss_w_per_nm2 = c.inverter_idle_w = 0; return c; }
struct OperatingPoint { double torque{100}, speed{20}, auxiliary{150}; };
DriveEnergyInterval interval(std::uint32_t sequence, OperatingPoint point = {}) {
    const auto begin = kStart+static_cast<std::uint64_t>(sequence)*10*kMs;
    const battery::ModelIdentity id{7, sequence, begin};
    return {begin, begin+10*kMs, {battery::ModelMeasurement<double>{point.torque, id, begin},
        battery::ModelMeasurement<double>{point.speed, id, begin}, battery::ModelMeasurement<double>{point.auxiliary, id, begin}}};
}
class DriveEnergyTest : public ::testing::Test {
protected:
    DriveEnergyModel model{{}, ideal_battery()};
    void SetUp() override { ASSERT_TRUE(model.initialize({7, kStart, 0.5, 25})); }
    void step(std::uint32_t sequence, OperatingPoint point = {}) {
        ASSERT_EQ(model.step(interval(sequence, point)).fault, DriveEnergyFault::None);
    }
};
TEST(DriveEnergyConfiguration, RejectsInvalidEfficienciesLossesBoundsAndIncompatibleTiming) {
    auto c = DriveEnergyConfig{}; c.motoring_efficiency = 0;
    EXPECT_THROW((DriveEnergyModel{c, battery_config()}), std::invalid_argument);
    c = {}; c.generating_efficiency = 1.01; EXPECT_THROW((DriveEnergyModel{c, battery_config()}), std::invalid_argument);
    c = {}; c.copper_loss_w_per_nm2 = -1; EXPECT_THROW((DriveEnergyModel{c, battery_config()}), std::invalid_argument);
    c = {}; c.inverter_idle_w = std::numeric_limits<double>::infinity(); EXPECT_THROW((DriveEnergyModel{c, battery_config()}), std::invalid_argument);
    c = {}; c.maximum_speed_rad_s = 0; EXPECT_THROW((DriveEnergyModel{c, battery_config()}), std::invalid_argument);
    c = {}; c.max_step_ns = 50*kMs; EXPECT_THROW((DriveEnergyModel{c, battery_config()}), std::invalid_argument);
    c = {}; c.max_input_age_ns = 10*kMs; EXPECT_THROW((DriveEnergyModel{c, battery_config()}), std::invalid_argument);
}
TEST(DriveEnergyConfiguration, RequiresExplicitPhysicalInitializationAndNeverUsesAnApplicationEpochToReset) {
    DriveEnergyModel model({}, battery_config());
    EXPECT_EQ(model.step(interval(0)).fault, DriveEnergyFault::NotInitialized);
    EXPECT_FALSE(model.initialize({0, kStart, 0.5, 25})); ASSERT_TRUE(model.initialize({7, kStart, 0.5, 25}));
    ASSERT_EQ(model.step(interval(0)).fault, DriveEnergyFault::None);
    const auto energy = model.battery_state().energy_j;
    EXPECT_FALSE(model.initialize({7, kStart+10*kMs, 0.5, 25})); EXPECT_DOUBLE_EQ(model.battery_state().energy_j, energy);
    EXPECT_FALSE(model.initialize({8, kStart, 0.5, 25})); ASSERT_TRUE(model.initialize({8, kStart+10*kMs, 0.4, 25}));
    EXPECT_DOUBLE_EQ(model.battery_state().soc, 0.4); EXPECT_EQ(model.diagnostic_state().mechanical_j, 0);
}
TEST_F(DriveEnergyTest, MotoringDrawIncludesConversionCopperIdleAndSeparateAuxiliaryExactlyOnce) {
    step(0);
    const auto loss = 2000*(1/0.92-1)+100+50;
    EXPECT_NEAR(model.diagnostic_state().motor_loss_w, loss, 1e-10);
    EXPECT_DOUBLE_EQ(model.diagnostic_state().mechanical_w, 2000);
    EXPECT_NEAR(model.diagnostic_state().traction_dc_w, 2000+loss, 1e-10);
    EXPECT_NEAR(90000000-model.battery_state().energy_j, (2000+loss+150)*0.01, 2e-8);
    EXPECT_DOUBLE_EQ(model.battery_state().auxiliary_j, 1.5); EXPECT_LT(model.battery_state().soc, 0.5);
}
TEST_F(DriveEnergyTest, RegenerationStoresLessEnergyThanMechanicalBrakingBecauseOfAllLosses) {
    step(0, {-100, 20, 150});
    EXPECT_DOUBLE_EQ(model.diagnostic_state().mechanical_w, -2000);
    EXPECT_NEAR(model.diagnostic_state().motor_loss_w, 450, 1e-10);
    EXPECT_NEAR(model.diagnostic_state().traction_dc_w, -1550, 1e-10);
    EXPECT_NEAR(model.battery_state().energy_j-90000000, 14, 2e-8);
    EXPECT_GT(model.battery_state().soc, 0.5);
}
TEST_F(DriveEnergyTest, NegativeTorqueCanStillConsumeDcWhenMechanicalInputCannotCoverMotorLosses) {
    step(0, {-5, 1, 150});
    EXPECT_LT(model.diagnostic_state().mechanical_w, 0); EXPECT_GT(model.diagnostic_state().traction_dc_w, 0);
    EXPECT_EQ(model.battery_state().received_dc_j, 0); EXPECT_LT(model.battery_state().soc, 0.5);
}
TEST(DriveEnergyPhysics, AuxiliaryCanConsumeAllElectricalReturnWithoutBatteryCharging) {
    DriveEnergyModel model(ideal_drive(), ideal_battery()); ASSERT_TRUE(model.initialize({7, kStart, 0.5, 25}));
    ASSERT_EQ(model.step(interval(0, {-10, 10, 200})).fault, DriveEnergyFault::None);
    EXPECT_EQ(model.battery_state().received_dc_j, 1); EXPECT_EQ(model.battery_state().auxiliary_j, 2);
    EXPECT_NEAR(model.battery_state().energy_j, 89999999, 1e-8);
}
TEST_F(DriveEnergyTest, StandstillTorqueHasCopperAndIdleDrawWithoutDividingBySpeed) {
    step(0, {100, 0, 150}); EXPECT_EQ(model.diagnostic_state().mechanical_w, 0);
    EXPECT_EQ(model.diagnostic_state().traction_dc_w, 150); EXPECT_NEAR(model.battery_state().energy_j, 89999997, 1e-8);
}
TEST(DriveEnergyPhysics, ExplicitIdealZeroPreservesEnergyAndHasUsableZeroElectricalFeedback) {
    DriveEnergyModel model(ideal_drive(), ideal_battery()); ASSERT_TRUE(model.initialize({7, kStart, 0.5, 25}));
    ASSERT_EQ(model.step(interval(0, {0, 0, 0})).fault, DriveEnergyFault::None);
    EXPECT_EQ(model.battery_state().energy_j, 90000000); ASSERT_TRUE(model.observation().electrical);
    EXPECT_EQ(model.observation().electrical->value.current_a, 0);
}
TEST(DriveEnergyPhysics, BatteryResistanceHeatIsAddedOnceAndMotorHeatDoesNotBecomeBatteryHeat) {
    DriveEnergyModel model({}, battery_config()); ASSERT_TRUE(model.initialize({7, kStart, 0.5, 25}));
    ASSERT_EQ(model.step(interval(0)).fault, DriveEnergyFault::None);
    const auto& b = model.battery_state(); const auto& d = model.diagnostic_state();
    EXPECT_GT(b.ohmic_loss_j, 0); EXPECT_GT(b.temperature_c, 25);
    EXPECT_NEAR(b.initial_energy_j-b.energy_j, d.mechanical_j+d.motor_loss_j+b.auxiliary_j+b.ohmic_loss_j, 2e-8);
    EXPECT_LT(b.ohmic_loss_j, d.motor_loss_j);
}
TEST_F(DriveEnergyTest, PreservesOldestDependencyInsteadOfRefreshingCachedInputs) {
    step(0); auto in = interval(1); in.inputs.wheel_speed_rad_s = interval(0).inputs.wheel_speed_rad_s;
    ASSERT_EQ(model.step(in).fault, DriveEnergyFault::None);
    ASSERT_TRUE(model.observation().soc); EXPECT_EQ(model.observation().soc->input_time_ns, kStart);
    EXPECT_EQ(model.observation().soc->identity.source_time_ns, kStart+20*kMs);
    EXPECT_EQ(model.battery_state().power->identity.source_time_ns, kStart+10*kMs);
}
TEST_F(DriveEnergyTest, EndOfIntervalAcquisitionCannotBeAppliedRetroactively) {
    auto in = interval(0); in.inputs.actual_torque_nm->identity.source_time_ns = in.end_ns;
    EXPECT_EQ(model.step(in).fault, DriveEnergyFault::Timestamp); EXPECT_EQ(model.battery_state().energy_j, 90000000);
}
TEST_F(DriveEnergyTest, MissingActualTorqueSpeedOrAuxiliaryLatchesUnknownRatherThanBecomingZero) {
    for (int field = 0; field < 3; ++field) {
        DriveEnergyModel other({}, battery_config()); ASSERT_TRUE(other.initialize({7, kStart, 0.5, 25}));
        auto in = interval(0);
        if (field == 0) in.inputs.actual_torque_nm.reset();
        if (field == 1) in.inputs.wheel_speed_rad_s.reset();
        if (field == 2) in.inputs.auxiliary_w.reset();
        EXPECT_EQ(other.step(in).fault, DriveEnergyFault::Unavailable); EXPECT_FALSE(other.observation().available);
        EXPECT_EQ(other.step(interval(0)).fault, DriveEnergyFault::Unavailable);
        EXPECT_EQ(other.battery_state().energy_j, 90000000);
    }
}
TEST_F(DriveEnergyTest, NonfiniteOutOfRangeReverseSpeedAndNegativeAuxiliaryAreRejected) {
    for (const auto p : {OperatingPoint{301, 20, 150}, {100, -1, 150}, {100, 101, 150}, {100, 20, -1},
        {std::numeric_limits<double>::quiet_NaN(), 20, 150}, {100, 20, std::numeric_limits<double>::infinity()}}) {
        DriveEnergyModel other({}, battery_config()); ASSERT_TRUE(other.initialize({7, kStart, 0.5, 25}));
        EXPECT_EQ(other.step(interval(0, p)).fault, DriveEnergyFault::Value); EXPECT_FALSE(other.observation().available);
    }
}
TEST_F(DriveEnergyTest, HeldAcquisitionsExpireAtIntervalEndEvenWhenCalculationTimeAdvances) {
    auto in = interval(0); ASSERT_EQ(model.step(in).fault, DriveEnergyFault::None);
    in.begin_ns += 10*kMs; in.end_ns += 10*kMs; ASSERT_EQ(model.step(in).fault, DriveEnergyFault::None);
    in.begin_ns += 10*kMs; in.end_ns += 10*kMs; ASSERT_EQ(model.step(in).fault, DriveEnergyFault::None);
    const auto energy = model.battery_state().energy_j;
    in.begin_ns += 10*kMs; in.end_ns += 10*kMs; EXPECT_EQ(model.step(in).fault, DriveEnergyFault::Stale);
    EXPECT_EQ(model.battery_state().energy_j, energy);
}
TEST_F(DriveEnergyTest, ReusingIdentityWithChangedActualValueIsNotANewAcquisition) {
    step(0); auto in = interval(1); in.inputs.actual_torque_nm = interval(0).inputs.actual_torque_nm;
    in.inputs.actual_torque_nm->value = 101;
    EXPECT_EQ(model.step(in).fault, DriveEnergyFault::Identity);
}
TEST_F(DriveEnergyTest, WrongPhysicalEpochAndSequenceWithoutSourceProgressAreRejected) {
    step(0); auto in = interval(1); in.inputs.wheel_speed_rad_s->identity.epoch = 8;
    EXPECT_EQ(model.step(in).fault, DriveEnergyFault::Identity);
    ASSERT_TRUE(model.initialize({8, kStart+20*kMs, 0.5, 25}));
    in = interval(2); in.inputs.actual_torque_nm->identity.epoch = 8;
    in.inputs.wheel_speed_rad_s->identity.epoch = in.inputs.auxiliary_w->identity.epoch = 8;
    ASSERT_EQ(model.step(in).fault, DriveEnergyFault::None);
    in.begin_ns += 10*kMs; in.end_ns += 10*kMs; ++in.inputs.actual_torque_nm->identity.sequence;
    EXPECT_EQ(model.step(in).fault, DriveEnergyFault::Identity);
}
TEST_F(DriveEnergyTest, IndependentAcquisitionsMustStayWithinSkewBudget) {
    step(0); auto held = interval(1); held.inputs.actual_torque_nm = interval(0).inputs.actual_torque_nm;
    ASSERT_EQ(model.step(held).fault, DriveEnergyFault::None);
    auto in = interval(2); in.inputs.actual_torque_nm = interval(0).inputs.actual_torque_nm;
    EXPECT_EQ(model.step(in).fault, DriveEnergyFault::Skew);
}
TEST_F(DriveEnergyTest, InvalidDependencyCannotComeFromBeforeScenarioOrAfterAcquisition) {
    auto in = interval(0); in.inputs.auxiliary_w->input_time_ns = kStart-1;
    EXPECT_EQ(model.step(in).fault, DriveEnergyFault::Timestamp);
}
TEST_F(DriveEnergyTest, GapsAreNotBackfilledAndClockRollbackDoesNotRewindEnergy) {
    step(0); const auto energy = model.battery_state().energy_j;
    EXPECT_EQ(model.step(interval(2)).fault, DriveEnergyFault::Timing); EXPECT_EQ(model.battery_state().energy_j, energy);
    DriveEnergyModel other({}, battery_config()); ASSERT_TRUE(other.initialize({7, kStart, 0.5, 25}));
    ASSERT_EQ(other.step(interval(0)).fault, DriveEnergyFault::None);
    auto in = interval(0); in.end_ns = kStart;
    EXPECT_EQ(other.step(in).fault, DriveEnergyFault::Clock);
}
TEST(DriveEnergyPhysics, FullBatteryRejectsResidualChargingWithoutClippingOrCommittingMotorLedger) {
    DriveEnergyModel model({}, battery_config()); ASSERT_TRUE(model.initialize({7, kStart, 1, 25}));
    const auto result = model.step(interval(0, {-200, 20, 150}));
    EXPECT_EQ(result.fault, DriveEnergyFault::Battery); EXPECT_EQ(result.battery_fault, BatteryFault::CapacityViolation);
    EXPECT_GT(result.boundary_excess_j, 0); EXPECT_EQ(model.battery_state().soc, 1);
    EXPECT_EQ(model.diagnostic_state().motor_loss_j, 0); EXPECT_FALSE(model.observation().available);
}
TEST(DriveEnergyPhysics, EmptyBatteryRejectsActualDischargeAndPropagatesBatteryFault) {
    DriveEnergyModel model({}, battery_config()); ASSERT_TRUE(model.initialize({7, kStart, 0, 25}));
    const auto result = model.step(interval(0)); EXPECT_EQ(result.battery_fault, BatteryFault::CapacityViolation);
    EXPECT_GT(result.boundary_excess_j, 0); EXPECT_EQ(model.battery_state().soc, 0);
}
TEST(DriveEnergyPhysics, BatteryPowerBoundsRemainEffectiveAfterMechanicalConversion) {
    auto b = battery_config(); b.max_abs_power_w = 1000;
    DriveEnergyModel model({}, b); ASSERT_TRUE(model.initialize({7, kStart, 0.5, 25}));
    EXPECT_EQ(model.step(interval(0)).battery_fault, BatteryFault::InvalidInput);
}
TEST(DriveEnergyPhysics, LongAlternatingOperationBalancesMechanicalMotorAuxiliaryAndBatteryLosses) {
    DriveEnergyModel model({}, battery_config()); ASSERT_TRUE(model.initialize({7, kStart, 0.5, 25}));
    for (std::uint32_t i = 0; i < 20000; ++i) {
        ASSERT_EQ(model.step(interval(i, {i%2 == 0 ? 100.0 : -100.0, 20, 150})).fault, DriveEnergyFault::None);
    }
    EXPECT_NEAR(model.diagnostic_state().mechanical_j, 0, 1e-9);
    EXPECT_GT(model.diagnostic_state().motor_loss_j, 0); EXPECT_LT(model.battery_state().soc, 0.5);
    EXPECT_NEAR(model.diagnostic_state().balance_error_j, 0, 0.00036);
}
TEST(DriveEnergyPhysics, SmallerZeroOrderHoldStepConvergesTowardKnownMechanicalWork) {
    const auto work = [](std::uint32_t step_ms) {
        DriveEnergyModel model(ideal_drive(), ideal_battery());
        if (!model.initialize({7, kStart, 0.5, 25})) throw std::runtime_error("initialization");
        for (std::uint32_t ms = 0; ms < 1000; ms += step_ms) {
            auto in = interval(ms/10, {ms/10.0, 20, 0}); in.end_ns = in.begin_ns+step_ms*kMs;
            if (model.step(in).fault != DriveEnergyFault::None) throw std::runtime_error("integration");
        }
        return model.diagnostic_state().mechanical_j;
    };
    EXPECT_NEAR(work(20), 980, 1e-9); EXPECT_NEAR(work(10), 990, 1e-9);
    EXPECT_LT(std::abs(work(10)-1000), std::abs(work(20)-1000));
}

vecu::BmsControllerConfig bms_config() {
    vecu::BmsControllerConfig c;
    c.charge_current_a = 80; c.discharge_current_a = 200; c.max_charge_power_w = 30000; c.max_discharge_power_w = 80000;
    c.charge_soc = {0.95, 0.8}; c.discharge_soc = {0.05, 0.1}; c.charge_cell_v = {4.2, 4.1}; c.discharge_cell_v = {3, 3.3};
    c.charge_temperature = {0, 10, 40, 45}; c.discharge_temperature = {-20, 0, 45, 55};
    c.cell_v = {2.8, 2.95, 4.15, 4.25}; c.pack_v = {280, 295, 415, 425};
    c.temperature_c = {-30, -15, 50, 60}; c.current_a = {-100, -80, 200, 250}; c.series_cells = 100; c.pack_extrema_tolerance_v = 2;
    return c;
}
class DriveEnergyLoop : public ::testing::Test {
protected:
    DriveEnergyModel energy{{}, battery_config()};
    simulation::DriveSil drive{{}};
    vecu::BmsController bms{bms_config()};
    can::DriveTxState command_tx{can::DriveFrameKind::Command};
    can::BmsTxState relay{can::BmsFrameKind::DriveBatteryLimits}, grants{can::BmsFrameKind::DrivePermission};
    can::DriveReceiver feedback{{can::DriveFrameKind::Actual, {-300, 500}, 100, 300, 30000000, 80000000, 30000000, 70000000}};
    std::uint32_t index{0}, app_epoch{1};
    void SetUp() override {
        ASSERT_TRUE(energy.initialize({7, kStart, 0.5, 25})); ASSERT_TRUE(bms.start_session(app_epoch, 7, kStart));
        ASSERT_TRUE(drive.start_session(app_epoch, 7, kStart)); ASSERT_TRUE(feedback.start_session(app_epoch, kStart));
    }
    void advance(double demand, bool hot_cell = false) {
        auto in = interval(index, {drive.actual_torque_nm(), 20, 150});
        BatterySensorCapture capture; if (hot_cell) capture.temperature_override = battery::CellExtrema{44, 45};
        ASSERT_EQ(energy.step(in, capture).fault, DriveEnergyFault::None);
        const auto now = in.end_ns; const auto& sensors = energy.observation();
        const auto limits = bms.tick(sensors, now);
        can::DriveMessage cmd; cmd.epoch = app_epoch; cmd.sequence = index; cmd.source_time_ns = now;
        cmd.torque_nm = demand; cmd.local_state = can::ActuatorLocalState::Normal; cmd.origin = can::ActuatorOrigin::NormalPath;
        const auto frame = can::encode_drive_frame(cmd, command_tx); ASSERT_TRUE(frame);
        ASSERT_EQ(drive.receive_command(*frame, now).decision, can::ActuatorReceiveDecision::Accepted);
        if (limits) {
            const auto routed = can::forward_bms_limits(*limits, relay); ASSERT_TRUE(routed);
            ASSERT_EQ(drive.receive_limits(*routed, now).decision, can::ActuatorReceiveDecision::Accepted);
        }
        const bool allow = bms.decision().state == vecu::BmsControlState::Active && index >= 12;
        const can::BmsParentContext parent{app_epoch, 1000+index, now, now+60*kMs};
        can::BmsMessage grant; grant.kind = can::BmsFrameKind::DrivePermission; grant.epoch = app_epoch; grant.sequence = index;
        grant.causal_sequence = parent.sequence; grant.source_time_ns = now;
        grant.local_state = can::ActuatorLocalState::Normal; grant.origin = can::ActuatorOrigin::NormalPath;
        grant.content = can::BmsDriveGrant{allow ? can::BmsDrivePermission::AllowNormal : can::BmsDrivePermission::Inhibit,
            allow ? index+1 : 0, allow ? now : 0, allow ? in.begin_ns : 0, now+60*kMs};
        const auto g = can::encode_bms_frame(grant, grants); ASSERT_TRUE(g);
        ASSERT_EQ(drive.receive_permission(*g, now, allow ? &parent : nullptr).decision, can::ActuatorReceiveDecision::Accepted);
        drive.observe_local({battery::ModelMeasurement<double>{20, sensors.batch, now},
            battery::ModelMeasurement<drive::HvFeedback>{{sensors.electrical->value.voltage_v, true, false}, sensors.batch,
                sensors.electrical->input_time_ns}}, now);
        const auto actual = drive.tick(now); ASSERT_TRUE(actual);
        ASSERT_EQ(feedback.receive(*actual, now).decision, can::ActuatorReceiveDecision::Accepted);
        ++index;
    }
};
TEST_F(DriveEnergyLoop, ActualTorqueDelayConsumesIdleOnlyBeforeResponseAndThenDischargesBattery) {
    for (int i = 0; i < 15; ++i) advance(100);
    EXPECT_EQ(drive.actual_torque_nm(), 0); EXPECT_EQ(energy.diagnostic_state().mechanical_j, 0);
    EXPECT_NEAR(energy.battery_state().drawn_dc_j, 7.5, 1e-9);
    for (int i = 0; i < 85; ++i) advance(100);
    EXPECT_EQ(drive.actual_torque_nm(), 100); EXPECT_GT(energy.diagnostic_state().mechanical_j, 0);
    EXPECT_LT(energy.battery_state().soc, 0.5); EXPECT_EQ(drive.decision().fault, vecu::DriveGateFault::None);
}
TEST_F(DriveEnergyLoop, RealBatteryObservationsFeedBmsAndRegenerationActuallyIncreasesSoc) {
    for (int i = 0; i < 100; ++i) advance(100);
    for (int i = 0; i < 100; ++i) advance(-100);
    const auto soc = energy.battery_state().soc;
    for (int i = 0; i < 100; ++i) advance(-100);
    EXPECT_GT(energy.battery_state().soc, soc); EXPECT_GT(energy.battery_state().received_dc_j, 0);
    EXPECT_LT(energy.battery_state().electrical->current_a, 0); EXPECT_EQ(bms.decision().fault, vecu::BmsControlFault::None);
    EXPECT_EQ(drive.decision().fault, vecu::DriveGateFault::None);
    EXPECT_LE(bms.decision().limits.input_time_ns, energy.observation().soc->input_time_ns);
    EXPECT_LT(energy.observation().soc->input_time_ns-bms.decision().limits.input_time_ns, 20*kMs);
}
TEST_F(DriveEnergyLoop, ChargeZeroKeepsCountingResidualActualReturnUntilTorqueHasRampedDown) {
    for (int i = 0; i < 100; ++i) advance(-200);
    const auto before = energy.battery_state().received_dc_j;
    advance(-200, true);
    EXPECT_EQ(drive.decision().regen_limit_nm, 0); EXPECT_EQ(drive.decision().selected_target_nm, 0);
    EXPECT_EQ(drive.actual_torque_nm(), -200); EXPECT_TRUE(drive.decision().actual_outside_envelope);
    const auto at_zero_target = energy.battery_state().received_dc_j;
    EXPECT_GT(at_zero_target, before); advance(-200, true);
    EXPECT_GT(energy.battery_state().received_dc_j, at_zero_target); EXPECT_LT(energy.diagnostic_state().traction_dc_w, 0);
    for (int i = 0; i < 20; ++i) advance(-200, true);
    EXPECT_EQ(drive.actual_torque_nm(), 0); EXPECT_GT(energy.diagnostic_state().traction_dc_w, 0);
    EXPECT_EQ(drive.decision().fault, vecu::DriveGateFault::None);
}
TEST(DriveEnergyPhysics, FixtureSocGuardBandsExceedConservativeFiniteReactionEnergyBudget) {
    const auto b = battery_config(); const auto c = bms_config();
    const DriveEnergyConfig motor; const vecu::DriveControllerConfig gate;
    EXPECT_GE(motor.motoring_efficiency, gate.motoring_efficiency_lower_bound);
    EXPECT_LE(motor.copper_loss_w_per_nm2, gate.copper_loss_w_per_nm2);
    EXPECT_LE(motor.inverter_idle_w+150, gate.fixed_power_reserve_w);
    EXPECT_GE(motor.maximum_abs_torque_nm, std::max(-gate.response.minimum_nm, gate.response.maximum_nm));
    // 100 ms detection + 20 ms ZOH + 300 Nm / 2000 Nm/s protection response.
    const double reaction_seconds = 0.1+0.02+300.0/2000;
    const auto maximum_i = 2*b.max_abs_power_w/(b.open_circuit_voltage_v+
        std::sqrt(b.open_circuit_voltage_v*b.open_circuit_voltage_v-4*b.resistance_ohm*b.max_abs_power_w));
    const auto budget_j = b.open_circuit_voltage_v*maximum_i*reaction_seconds;
    EXPECT_GT((1-c.charge_soc.zero)*b.capacity_j, budget_j);
    EXPECT_GT(c.discharge_soc.zero*b.capacity_j, budget_j);
    EXPECT_GT(budget_j, 27000); EXPECT_LT(budget_j, 30000);
}
}  // namespace
