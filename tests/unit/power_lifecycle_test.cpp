#include "power_model.hpp"
#include "power_controller.hpp"
#include "bms_controller.hpp"

#include <gtest/gtest.h>
#include <cmath>
#include <functional>
#include <limits>
#include <stdexcept>

namespace {
using namespace stratadrive;
constexpr std::uint64_t kStart = 1000000000, kMs = 1000000;
simulation::PowerModelConfig plant_config() { return {0.002, 50, 0.02, 100, 1000, 500}; }
simulation::PowerEnvironment environment(double load = 0) { return {400, load, true, true, true, false, false}; }
simulation::PowerInterval interval(std::uint32_t index, power::CoilCommand coils = {}, double load = 0) {
    const auto begin = kStart+static_cast<std::uint64_t>(index)*10*kMs;
    return {begin, begin+10*kMs, {environment(load), {7, index, begin}, begin}, coils};
}
power::SensorSnapshot sensor(std::uint32_t ms) {
    const auto ns = kStart+static_cast<std::uint64_t>(ms)*kMs;
    return {{7, ms/10, ns}, ns, 400, 0, 0, power::ContactorPositions{}, {true, true, true, false, false}};
}
power::BmsSafetyGate gate(std::uint32_t ms, std::optional<bool> inhibit = false) {
    const auto ns = kStart+static_cast<std::uint64_t>(ms)*kMs;
    return {1, ms/10, ns, ns, inhibit};
}
TEST(PowerConfiguration, RejectsInvalidPlantAndControllerCalibration) {
    auto p = plant_config(); p.capacitance_f = 0;
    EXPECT_THROW(simulation::PowerModel{p}, std::invalid_argument);
    p = plant_config(); p.main_resistance_ohm = 50;
    EXPECT_THROW(simulation::PowerModel{p}, std::invalid_argument);
    p = plant_config(); p.contactor_delay_ns = 0;
    EXPECT_THROW(simulation::PowerModel{p}, std::invalid_argument);
    vecu::PowerControllerConfig c; c.precharge_ratio = 1;
    EXPECT_THROW(vecu::PowerController{c}, std::invalid_argument);
    c = {}; c.opening_current_max_a = std::numeric_limits<double>::quiet_NaN();
    EXPECT_THROW(vecu::PowerController{c}, std::invalid_argument);
    c = {}; c.off_bus_max_v = 400;
    EXPECT_THROW(vecu::PowerController{c}, std::invalid_argument);
    c = {}; c.current_dwell_ns = 0;
    EXPECT_THROW(vecu::PowerController{c}, std::invalid_argument);
}
TEST(PowerPlant, RequiresExplicitScenarioAndDoesNotInventInitialSensors) {
    simulation::PowerModel p(plant_config());
    EXPECT_EQ(p.step(interval(0)), simulation::PowerModelFault::NotInitialized);
    EXPECT_FALSE(p.initialize({0, 0, kStart}, 0));
    EXPECT_TRUE(p.initialize({7, 0, kStart}, 0)); EXPECT_FALSE(p.observation());
    EXPECT_FALSE(p.initialize({7, 0, kStart}, 0));
}
TEST(PowerPlant, ContactorDelayAndPrechargeFollowAnalyticalRcResponse) {
    simulation::PowerModel p(plant_config()); ASSERT_TRUE(p.initialize({7, 0, kStart}, 0));
    for (std::uint32_t i = 0; i < 12; ++i) ASSERT_EQ(p.step(interval(i, {{false, true, true}, false})), simulation::PowerModelFault::None);
    // First 20 ms: actual contacts remain open. Then tau=50 ohm * 2 mF=100 ms.
    EXPECT_NEAR(p.diagnostic_state().bus_voltage_v, 400*(1-std::exp(-1.0)), 1e-9);
    EXPECT_NEAR(p.diagnostic_state().pack_current_a, (400-p.diagnostic_state().bus_voltage_v)/50, 1e-12);
    ASSERT_TRUE(p.observation()); EXPECT_EQ(p.observation()->identity.sequence, 12U);
}
TEST(PowerPlant, CapacitorHoldsWhenIsolatedAndDischargesOnlyThroughExplicitPath) {
    simulation::PowerModel p(plant_config()); ASSERT_TRUE(p.initialize({7, 0, kStart}, 400));
    ASSERT_EQ(p.step(interval(0)), simulation::PowerModelFault::None);
    EXPECT_DOUBLE_EQ(p.diagnostic_state().bus_voltage_v, 400);
    for (std::uint32_t i = 1; i <= 20; ++i) ASSERT_EQ(p.step(interval(i, {{}, true})), simulation::PowerModelFault::None);
    EXPECT_NEAR(p.diagnostic_state().bus_voltage_v, 400*std::exp(-1.0), 1e-9);
    EXPECT_DOUBLE_EQ(p.diagnostic_state().pack_current_a, 0);
}
TEST(PowerPlant, ActualLoadAndReturnCurrentAffectBusInBothDirections) {
    simulation::PowerModel p(plant_config()); ASSERT_TRUE(p.initialize({7, 0, kStart}, 400, {true, true, false}));
    ASSERT_EQ(p.step(interval(0, {{true, true, false}, false}, 20)), simulation::PowerModelFault::None);
    EXPECT_NEAR(p.diagnostic_state().bus_voltage_v, 399.6, 1e-7);
    EXPECT_NEAR(p.diagnostic_state().pack_current_a, 20, 1e-6);
    ASSERT_EQ(p.step(interval(1, {{true, true, false}, false}, -20)), simulation::PowerModelFault::None);
    EXPECT_NEAR(p.diagnostic_state().bus_voltage_v, 400.4, 1e-7);
    EXPECT_NEAR(p.diagnostic_state().pack_current_a, -20, 1e-6);
}
TEST(PowerPlant, WeldedAndStuckOpenContactsOverrideCommands) {
    simulation::PowerModel p(plant_config()); ASSERT_TRUE(p.initialize({7, 0, kStart}, 0));
    simulation::PowerFaultInjection f; f.contactors[0] = simulation::ContactorFailure::StuckClosed;
    f.contactors[1] = simulation::ContactorFailure::StuckOpen;
    ASSERT_EQ(p.step(interval(0, {{false, true, false}, false}), f), simulation::PowerModelFault::None);
    EXPECT_TRUE(p.observation()->contactors->positive); EXPECT_FALSE(p.observation()->contactors->negative);
    EXPECT_DOUBLE_EQ(*p.observation()->bus_voltage_v, 0);
}
TEST(PowerPlant, LvLossDropsCoilsButDoesNotOpenWeldedContacts) {
    simulation::PowerModel p(plant_config()); ASSERT_TRUE(p.initialize({7, 0, kStart}, 400, {true, true, false}));
    simulation::PowerFaultInjection f; f.contactors[0] = simulation::ContactorFailure::StuckClosed;
    for (std::uint32_t i = 0; i < 3; ++i) {
        auto in = interval(i, {{true, true, false}, false}); in.environment.value.lv_available = false;
        ASSERT_EQ(p.step(in, f), simulation::PowerModelFault::None);
    }
    EXPECT_TRUE(p.observation()->contactors->positive); EXPECT_FALSE(p.observation()->contactors->negative);
}
TEST(PowerPlant, HoldPreservesAcquisitionAndInvalidGroupDoesNotEraseOtherActuals) {
    simulation::PowerModel p(plant_config()); ASSERT_TRUE(p.initialize({7, 0, kStart}, 0));
    ASSERT_EQ(p.step(interval(0)), simulation::PowerModelFault::None);
    const auto old = *p.observation(); simulation::PowerFaultInjection f; f.hold_sensors = true;
    ASSERT_EQ(p.step(interval(1), f), simulation::PowerModelFault::None);
    EXPECT_EQ(p.observation()->identity.source_time_ns, old.identity.source_time_ns);
    f = {}; f.invalidate_bus = true;
    ASSERT_EQ(p.step(interval(2), f), simulation::PowerModelFault::None);
    EXPECT_FALSE(p.observation()->bus_voltage_v); EXPECT_TRUE(p.observation()->contactors);
}
TEST(PowerPlant, BadPowerTimingAndCachedMutationLatchWithoutBackfill) {
    simulation::PowerModel p(plant_config()); ASSERT_TRUE(p.initialize({7, 0, kStart}, 0));
    ASSERT_EQ(p.step(interval(0)), simulation::PowerModelFault::None);
    auto changed = interval(1); changed.environment = interval(0).environment; changed.environment.value.pack_voltage_v = 401;
    EXPECT_EQ(p.step(changed), simulation::PowerModelFault::Identity); EXPECT_FALSE(p.observation());
    EXPECT_EQ(p.step(interval(2)), simulation::PowerModelFault::Identity);
    simulation::PowerModel q(plant_config()); ASSERT_TRUE(q.initialize({7, 0, kStart}, 0));
    EXPECT_EQ(q.step(interval(1)), simulation::PowerModelFault::Timing);
}
TEST(PowerPlant, RejectsUnknownPhysicalIntervalEvolutionRatherThanClippingVoltage) {
    simulation::PowerModel p(plant_config()); ASSERT_TRUE(p.initialize({7, 0, kStart}, 0));
    EXPECT_EQ(p.step(interval(0, {}, 20)), simulation::PowerModelFault::Electrical);
    EXPECT_DOUBLE_EQ(p.diagnostic_state().bus_voltage_v, 0); EXPECT_FALSE(p.observation());
}
TEST(PowerPlant, OldDependenciesAndWrongScenarioAreRejected) {
    simulation::PowerModel p(plant_config()); ASSERT_TRUE(p.initialize({7, 0, kStart}, 0));
    auto in = interval(0); in.environment.identity.epoch = 8;
    EXPECT_EQ(p.step(in), simulation::PowerModelFault::Identity);
    simulation::PowerModel q(plant_config()); ASSERT_TRUE(q.initialize({7, 0, kStart}, 0));
    for (std::uint32_t i = 0; i < 5; ++i) { in = interval(i); in.environment = interval(0).environment; ASSERT_EQ(q.step(in), simulation::PowerModelFault::None); }
    in = interval(5); in.environment = interval(0).environment;
    EXPECT_EQ(q.step(in), simulation::PowerModelFault::Stale);
}

class PowerLifecycleTest : public ::testing::Test {
protected:
    simulation::PowerModel plant{plant_config()};
    vecu::PowerController controller{vecu::PowerControllerConfig{}};
    can::BmsTxState requests{can::BmsFrameKind::PowerRequest}, status_tx{can::BmsFrameKind::PowerStatus};
    can::BmsReceiver status_rx{can::BmsReceiverConfig{can::BmsFrameKind::PowerStatus, {{0, 1000}, {-3000, 3000}, {-50, 100}, 100000}}};
    std::uint32_t step_index{0}, request_sequence{0};
    can::BmsPowerAction action{can::BmsPowerAction::Enable};
    bool send_request{true};
    bool expect_request_timeout{false};
    std::optional<bool> bms_inhibit{false};
    std::optional<power::BmsSafetyGate> fixed_gate;
    double load_a{0};
    simulation::PowerFaultInjection injection{};
    can::BmsMessage latest{};
    std::function<void(power::SensorSnapshot&)> change_sensor;
    void SetUp() override {
        ASSERT_TRUE(plant.initialize({7, 0, kStart}, 0));
        ASSERT_TRUE(controller.start_session(1, 7, kStart)); ASSERT_TRUE(status_rx.start_session(1, kStart));
    }
    void publish_request(std::uint64_t now) {
        can::BmsMessage m; m.kind = can::BmsFrameKind::PowerRequest; m.epoch = 1; m.sequence = request_sequence++;
        m.source_time_ns = now; m.causal_sequence = 1000+m.sequence; m.local_state = can::ActuatorLocalState::Init; m.origin = can::ActuatorOrigin::NormalPath;
        m.content = can::BmsPowerRequest{action, now+60*kMs, now};
        const can::BmsParentContext parent{1, m.causal_sequence, now, now+60*kMs};
        const auto frame = can::encode_bms_frame(m, requests); ASSERT_TRUE(frame);
        EXPECT_EQ(controller.receive(*frame, now, &parent).decision, expect_request_timeout ?
            can::ActuatorReceiveDecision::Timeout : can::ActuatorReceiveDecision::Accepted);
    }
    void step() {
        const auto coils = controller.output().coils.value_or(power::CoilCommand{});
        const auto in = interval(step_index, coils, load_a);
        ASSERT_EQ(plant.step(in, injection), simulation::PowerModelFault::None);
        const auto now = in.end_ns;
        if (send_request && step_index%2 == 0) publish_request(now);
        auto observation = plant.observation();
        if (observation && change_sensor) change_sensor(*observation);
        const auto msg = controller.tick(observation, fixed_gate ? fixed_gate :
            std::optional<power::BmsSafetyGate>{gate((step_index+1)*10, bms_inhibit)}, now); ASSERT_TRUE(msg);
        latest = *msg; auto frame = can::encode_bms_frame(latest, status_tx); ASSERT_TRUE(frame);
        const auto received = status_rx.receive(*frame, now);
        EXPECT_EQ(received.decision, can::ActuatorReceiveDecision::Accepted);
        ++step_index;
    }
    void until(vecu::PowerPhase phase, std::uint32_t limit = 300) {
        while (controller.output().phase != phase && step_index < limit) step();
        ASSERT_EQ(controller.output().phase, phase);
    }
    const can::BmsPowerStatus& status() const { return std::get<can::BmsPowerStatus>(latest.content); }
};
TEST_F(PowerLifecycleTest, UsesActualRcFeedbackBeforeReadyAndNeverProducesDrivePermission) {
    until(vecu::PowerPhase::Precharging);
    EXPECT_FALSE(controller.output().coils->close.positive);
    EXPECT_LT(*status().hv_bus_voltage_v, 396);
    EXPECT_EQ(status().state, can::BmsPowerState::Precharge);
    EXPECT_EQ(latest.local_state, can::ActuatorLocalState::Normal); // controller health is independent of HV readiness
    until(vecu::PowerPhase::Ready);
    EXPECT_GE(*status().hv_bus_voltage_v, 396); EXPECT_TRUE(status().positive_contactor_closed.value());
    EXPECT_TRUE(status().negative_contactor_closed.value()); EXPECT_FALSE(status().precharge_contactor_closed.value());
    EXPECT_EQ(controller.output().fault, vecu::PowerControlFault::None);
    EXPECT_FALSE(controller.output().inhibit_drive);
    const auto current = status_rx.current_sample(latest.source_time_ns); ASSERT_TRUE(current);
    EXPECT_TRUE(can::bms_power_is_ready(*current)); EXPECT_FALSE(can::bms_permission_allows_normal(*current));
    EXPECT_EQ(status().input_sequence, plant.observation()->identity.sequence);
    EXPECT_EQ(status().input_time_ns, plant.observation()->input_time_ns);
    EXPECT_EQ(latest.causal_sequence, request_sequence-1); // command identity, not its upstream parent sequence
}
TEST_F(PowerLifecycleTest, ShutdownWaitsForActualCurrentThenContactsAndResidualVoltage) {
    until(vecu::PowerPhase::Ready); load_a = 20; step(); action = can::BmsPowerAction::Shutdown;
    until(vecu::PowerPhase::WaitCurrent);
    for (int i = 0; i < 10; ++i) step();
    EXPECT_TRUE(controller.output().coils->close.positive); EXPECT_TRUE(controller.output().inhibit_drive);
    load_a = 0; until(vecu::PowerPhase::OpenContactors);
    EXPECT_FALSE(controller.output().coils->close.positive);
    EXPECT_EQ(status().state, can::BmsPowerState::Shutdown);
    until(vecu::PowerPhase::Discharging); EXPECT_GT(*status().hv_bus_voltage_v, 30);
    EXPECT_EQ(status().state, can::BmsPowerState::Shutdown);
    until(vecu::PowerPhase::Off); EXPECT_LE(*status().hv_bus_voltage_v, 30);
    EXPECT_FALSE(status().positive_contactor_closed.value()); EXPECT_EQ(controller.output().fault, vecu::PowerControlFault::None);
    EXPECT_EQ(latest.local_state, can::ActuatorLocalState::Normal);
    injection.invalidate_current = true; step();
    EXPECT_EQ(controller.output().fault, vecu::PowerControlFault::InputsUnavailable);
    EXPECT_EQ(latest.local_state, can::ActuatorLocalState::FailSafe);
    EXPECT_EQ(status().state, can::BmsPowerState::Off); // known physical OFF and unhealthy sensing coexist
}
TEST_F(PowerLifecycleTest, ChargeReturnCurrentAlsoBlocksOpeningUntilMagnitudeFalls) {
    until(vecu::PowerPhase::Ready); load_a = -20; step(); action = can::BmsPowerAction::Shutdown;
    until(vecu::PowerPhase::WaitCurrent); for (int i = 0; i < 5; ++i) step();
    EXPECT_TRUE(controller.output().coils->close.positive);
    load_a = 0; until(vecu::PowerPhase::Off);
}
TEST_F(PowerLifecycleTest, CurrentTimeoutReportsBlockedWithoutOpeningUnderLoad) {
    until(vecu::PowerPhase::Ready); load_a = 20; step(); action = can::BmsPowerAction::Shutdown;
    until(vecu::PowerPhase::WaitCurrent); for (int i = 0; i < 35; ++i) step();
    EXPECT_TRUE(controller.output().shutdown_blocked); EXPECT_TRUE(controller.output().coils->close.positive);
    EXPECT_EQ(controller.output().phase, vecu::PowerPhase::WaitCurrent);
    EXPECT_EQ(controller.output().fault, vecu::PowerControlFault::ShutdownCurrentBlocked);
    EXPECT_NE(status().state, can::BmsPowerState::Off);
    load_a = 0; until(vecu::PowerPhase::Off); action = can::BmsPowerAction::Enable;
    for (int i = 0; i < 10; ++i) { step(); }
    EXPECT_EQ(controller.output().phase, vecu::PowerPhase::Off);
}
TEST_F(PowerLifecycleTest, BmsStartupInhibitWaitsAndLaterAllowsChecks) {
    bms_inhibit = true; for (int i = 0; i < 15; ++i) step();
    EXPECT_EQ(controller.output().phase, vecu::PowerPhase::Checks);
    EXPECT_FALSE(controller.output().coils->close.negative);
    bms_inhibit = false; until(vecu::PowerPhase::Ready);
}
TEST_F(PowerLifecycleTest, BmsProtectionRequestsControlledShutdownAndLatches) {
    until(vecu::PowerPhase::Ready); bms_inhibit = true; step();
    EXPECT_EQ(controller.output().phase, vecu::PowerPhase::WaitCurrent);
    EXPECT_EQ(controller.output().fault, vecu::PowerControlFault::BmsInhibit);
    bms_inhibit = false; until(vecu::PowerPhase::Off);
    for (int i = 0; i < 10; ++i) { step(); }
    EXPECT_NE(controller.output().phase, vecu::PowerPhase::Ready);
    EXPECT_EQ(latest.local_state, can::ActuatorLocalState::FailSafe);
}
TEST_F(PowerLifecycleTest, MissingBusCannotDeclareReadyAndPreservesKnownContactorsOnWire) {
    until(vecu::PowerPhase::Precharging); injection.invalidate_bus = true; step();
    EXPECT_FALSE(status().hv_bus_voltage_v); EXPECT_TRUE(status().negative_contactor_closed.has_value());
    EXPECT_NE(status().state, can::BmsPowerState::HvReady);
    EXPECT_EQ(controller.output().fault, vecu::PowerControlFault::InputsUnavailable);
}
TEST_F(PowerLifecycleTest, MissingCurrentNeverBecomesZeroOrPermitsOpening) {
    until(vecu::PowerPhase::Ready); injection.invalidate_current = true;
    for (int i = 0; i < 35; ++i) step();
    EXPECT_EQ(controller.output().phase, vecu::PowerPhase::WaitCurrent);
    EXPECT_TRUE(controller.output().coils->close.positive); EXPECT_TRUE(controller.output().shutdown_blocked);
}
TEST_F(PowerLifecycleTest, UnknownInterlockDoesNotBecomeSafeFalseOrReady) {
    until(vecu::PowerPhase::Ready);
    change_sensor = [](power::SensorSnapshot& s) { s.conditions.interlock_closed.reset(); }; step();
    EXPECT_EQ(status().condition_validity & 2U, 0U);
    EXPECT_NE(status().state, can::BmsPowerState::HvReady); EXPECT_TRUE(controller.output().inhibit_drive);
}
TEST_F(PowerLifecycleTest, ChargerConnectionTriggersInhibitAndShutdown) {
    until(vecu::PowerPhase::Ready);
    change_sensor = [](power::SensorSnapshot& s) { s.conditions.charger_connected = true; }; step();
    EXPECT_EQ(controller.output().fault, vecu::PowerControlFault::ConditionsUnsafe);
    EXPECT_NE(status().condition_bits & 8U, 0U);
    EXPECT_FALSE(can::bms_power_is_ready(*status_rx.current_sample(latest.source_time_ns)));
}
TEST_F(PowerLifecycleTest, StuckNegativeAndOpenPrechargePathCannotTimeIntoReady) {
    injection.contactors[1] = simulation::ContactorFailure::StuckOpen;
    for (int i = 0; i < 30; ++i) step();
    EXPECT_EQ(controller.output().fault, vecu::PowerControlFault::ContactorResponse);
    EXPECT_NE(status().state, can::BmsPowerState::HvReady);
}
TEST_F(PowerLifecycleTest, StuckPrechargePathTimesOutRatherThanClosingMainPositive) {
    injection.contactors[2] = simulation::ContactorFailure::StuckOpen;
    for (int i = 0; i < 220; ++i) step();
    EXPECT_EQ(controller.output().fault, vecu::PowerControlFault::PrechargeTimeout);
    EXPECT_FALSE(controller.output().coils->close.positive);
}
TEST_F(PowerLifecycleTest, WeldedContactCannotBeReportedOffAfterOpenCommand) {
    until(vecu::PowerPhase::Ready); injection.contactors[0] = simulation::ContactorFailure::StuckClosed;
    action = can::BmsPowerAction::Shutdown; until(vecu::PowerPhase::OpenContactors);
    for (int i = 0; i < 20; ++i) step();
    EXPECT_TRUE(status().positive_contactor_closed.value()); EXPECT_TRUE(controller.output().shutdown_blocked);
    EXPECT_NE(status().state, can::BmsPowerState::Off);
    EXPECT_FALSE(controller.output().coils->discharge_bus);
}
TEST_F(PowerLifecycleTest, RequestExpiryRevokesReadinessWithoutLateEnableRecovery) {
    until(vecu::PowerPhase::Ready); send_request = false;
    for (int i = 0; i < 7; ++i) step();
    EXPECT_EQ(controller.output().fault, vecu::PowerControlFault::RequestLost);
    send_request = true; expect_request_timeout = true; until(vecu::PowerPhase::Off);
    for (int i = 0; i < 10; ++i) { step(); }
    EXPECT_EQ(controller.output().phase, vecu::PowerPhase::Off);
}
TEST_F(PowerLifecycleTest, ApplicationRestartKeepsChargedPlantAndRechecksThroughShutdown) {
    until(vecu::PowerPhase::Ready); const auto bus_before = plant.diagnostic_state().bus_voltage_v;
    const auto now = latest.source_time_ns;
    ASSERT_TRUE(controller.start_session(2, 7, now)); EXPECT_FALSE(controller.output().coils);
    EXPECT_DOUBLE_EQ(plant.diagnostic_state().bus_voltage_v, bus_before);
    auto s = *plant.observation(); s.identity.source_time_ns = now+10*kMs; s.identity.sequence++; s.input_time_ns = now;
    auto m = controller.tick(s, std::nullopt, now+10*kMs); ASSERT_TRUE(m);
    EXPECT_EQ(controller.output().fault, vecu::PowerControlFault::StartupEnergized);
    EXPECT_TRUE(controller.output().coils->close.positive); EXPECT_TRUE(controller.output().inhibit_drive);
}
TEST(PowerControllerTiming, CachedSafeMeasurementCannotAdvanceCurrentOpeningDwell) {
    vecu::PowerController c({}); ASSERT_TRUE(c.start_session(1, 7, kStart));
    auto s = sensor(0); s.contactors = power::ContactorPositions{true, true, false}; s.bus_voltage_v = 400;
    ASSERT_TRUE(c.tick(s, gate(0), kStart));
    for (std::uint32_t ms = 10; ms <= 40; ms += 10) ASSERT_TRUE(c.tick(s, gate(ms), kStart+ms*kMs));
    EXPECT_EQ(c.output().phase, vecu::PowerPhase::WaitCurrent); EXPECT_TRUE(c.output().coils->close.positive);
}
TEST(PowerControllerTiming, InvalidIdentityMutationAndAgeCannotRefreshActual) {
    vecu::PowerController c({}); ASSERT_TRUE(c.start_session(1, 7, kStart));
    ASSERT_TRUE(c.tick(sensor(0), gate(0), kStart));
    auto s = sensor(0); s.bus_voltage_v = 400;
    auto m = c.tick(s, gate(10), kStart+10*kMs); ASSERT_TRUE(m);
    EXPECT_FALSE(std::get<can::BmsPowerStatus>(m->content).hv_bus_voltage_v);
    s = sensor(20); s.identity.epoch = 8; m = c.tick(s, gate(20), kStart+20*kMs); ASSERT_TRUE(m);
    EXPECT_FALSE(std::get<can::BmsPowerStatus>(m->content).state);
}
TEST(PowerControllerTiming, EmptyPartialObservationStillProducesCanonicalUnknownFrame) {
    vecu::PowerController c({}); ASSERT_TRUE(c.start_session(1, 7, kStart));
    auto s = sensor(0); s.bus_voltage_v.reset(); s.contactors.reset(); s.conditions = {};
    auto m = c.tick(s, std::nullopt, kStart); ASSERT_TRUE(m);
    can::BmsTxState tx{can::BmsFrameKind::PowerStatus}; EXPECT_TRUE(can::encode_bms_frame(*m, tx));
    EXPECT_EQ(std::get<can::BmsPowerStatus>(m->content).input_sequence, 0U);
}
TEST(PowerControllerTiming, ClockRollbackStopsPublicationAndNewEpochMustBeMonotonic) {
    vecu::PowerController c({}); ASSERT_TRUE(c.start_session(1, 7, kStart));
    ASSERT_TRUE(c.tick(sensor(0), gate(0), kStart));
    EXPECT_FALSE(c.tick(sensor(0), gate(0), kStart-1)); EXPECT_FALSE(c.output().coils);
    EXPECT_EQ(c.output().fault, vecu::PowerControlFault::ClockError);
    EXPECT_FALSE(c.start_session(1, 7, kStart)); EXPECT_FALSE(c.start_session(2, 6, kStart));
    EXPECT_TRUE(c.start_session(2, 7, kStart));
}
TEST(PowerControllerTiming, DeadlineAndContinuityLossInhibitWithoutInventingOpenActuals) {
    vecu::PowerController c({}); ASSERT_TRUE(c.start_session(1, 7, kStart));
    auto s = sensor(0); s.contactors = power::ContactorPositions{true, true, false}; s.bus_voltage_v = 400;
    ASSERT_TRUE(c.tick(s, gate(0), kStart));
    s = sensor(40); s.contactors = power::ContactorPositions{true, true, false}; s.bus_voltage_v = 400; s.pack_current_a = 20;
    ASSERT_TRUE(c.tick(s, gate(40), kStart+40*kMs));
    EXPECT_EQ(c.output().fault, vecu::PowerControlFault::ControlDeadline); EXPECT_TRUE(c.output().coils->close.positive);
    c.mark_continuity_lost(kStart+40*kMs); EXPECT_TRUE(c.output().inhibit_drive);
}
TEST_F(PowerLifecycleTest, PrechargeContactWeldCannotCompleteReadyHandoff) {
    until(vecu::PowerPhase::OpenPrecharge);
    injection.contactors[2] = simulation::ContactorFailure::StuckClosed;
    for (int i = 0; i < 15; ++i) { step(); }
    EXPECT_EQ(controller.output().fault, vecu::PowerControlFault::ContactorResponse);
    EXPECT_TRUE(controller.output().inhibit_drive);
    EXPECT_NE(status().state, can::BmsPowerState::HvReady);
}
TEST_F(PowerLifecycleTest, BusVoltageLossAfterReadyRevokesReadinessBeforeOpening) {
    until(vecu::PowerPhase::Ready);
    change_sensor = [](power::SensorSnapshot& s) { s.bus_voltage_v = 300; }; step();
    EXPECT_EQ(controller.output().fault, vecu::PowerControlFault::BusNotReady);
    EXPECT_EQ(controller.output().phase, vecu::PowerPhase::WaitCurrent);
    EXPECT_TRUE(controller.output().coils->close.positive);
}
TEST_F(PowerLifecycleTest, UnknownBmsGateNeverActsLikeAllow) {
    until(vecu::PowerPhase::Ready); bms_inhibit.reset(); step();
    EXPECT_EQ(controller.output().fault, vecu::PowerControlFault::BmsInhibit);
    EXPECT_TRUE(controller.output().inhibit_drive);
}
TEST_F(PowerLifecycleTest, RepeatedCachedBmsAllowCannotKeepReadyPastItsSourceAge) {
    until(vecu::PowerPhase::Ready); fixed_gate = gate(step_index*10);
    for (int i = 0; i < 5; ++i) { step(); }
    EXPECT_EQ(controller.output().phase, vecu::PowerPhase::Ready); // exactly 50 ms remains fresh
    step();
    EXPECT_EQ(controller.output().fault, vecu::PowerControlFault::BmsInhibit);
    EXPECT_NE(status().state, can::BmsPowerState::HvReady);
}
TEST(PowerControllerTiming, DischargeTimeoutDoesNotCallAChargedIsolatedBusOff) {
    vecu::PowerController c({}); ASSERT_TRUE(c.start_session(1, 7, kStart));
    for (std::uint32_t ms = 0; ms <= 1100; ms += 10) {
        auto s = sensor(ms); s.bus_voltage_v = 400;
        ASSERT_TRUE(c.tick(s, gate(ms), kStart+ms*kMs));
    }
    EXPECT_EQ(c.output().phase, vecu::PowerPhase::Discharging);
    EXPECT_EQ(c.output().fault, vecu::PowerControlFault::DischargeTimeout);
    EXPECT_TRUE(c.output().shutdown_blocked);
}
TEST(PowerControllerTiming, EnableRequiresSeparatelyTrustedParentContext) {
    vecu::PowerController c({}); ASSERT_TRUE(c.start_session(1, 7, kStart));
    can::BmsMessage m; m.kind = can::BmsFrameKind::PowerRequest; m.epoch = 1; m.source_time_ns = kStart;
    m.origin = can::ActuatorOrigin::NormalPath; m.content = can::BmsPowerRequest{can::BmsPowerAction::Enable, kStart+60*kMs, kStart};
    can::BmsTxState tx{can::BmsFrameKind::PowerRequest}; const auto f = can::encode_bms_frame(m, tx); ASSERT_TRUE(f);
    EXPECT_EQ(c.receive(*f, kStart, nullptr).issue, can::BmsReceiveIssue::ParentMissing);
    ASSERT_TRUE(c.tick(sensor(0), gate(0), kStart)); EXPECT_EQ(c.output().phase, vecu::PowerPhase::Off);
}
}  // namespace
