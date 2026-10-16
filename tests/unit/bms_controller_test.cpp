#include "bms_controller.hpp"
#include "battery_model.hpp"
#include "bms_receiver.hpp"

#include <gtest/gtest.h>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace {
using namespace stratadrive;
using namespace stratadrive::vecu;
constexpr std::uint64_t kStart = 1000000000, kMs = 1000000;
BmsControllerConfig fixture_config() {
    BmsControllerConfig c;
    c.charge_current_a = 80; c.discharge_current_a = 200;
    c.max_charge_power_w = 30000; c.max_discharge_power_w = 80000;
    c.charge_soc = {0.95, 0.8}; c.discharge_soc = {0.05, 0.1};
    c.charge_cell_v = {4.2, 4.1}; c.discharge_cell_v = {3, 3.3};
    c.charge_temperature = {0, 10, 40, 45}; c.discharge_temperature = {-20, 0, 45, 55};
    c.cell_v = {2.8, 2.95, 4.15, 4.25}; c.pack_v = {280, 295, 415, 425};
    c.temperature_c = {-30, -15, 50, 60}; c.current_a = {-100, -80, 200, 250};
    c.series_cells = 100; c.pack_extrema_tolerance_v = 2;
    return c;
}
battery::SensorSnapshot sample(std::uint32_t ms, std::uint32_t model_epoch = 7) {
    const auto ns = kStart + ms*kMs;
    const battery::ModelIdentity id{model_epoch, ms/20, ns};
    return {id, true, battery::ModelMeasurement<double>{0.5, id, ns},
        battery::ModelMeasurement<battery::ElectricalPair>{{400, 0}, id, ns},
        battery::ModelMeasurement<double>{25, id, ns},
        battery::ModelMeasurement<battery::CellExtrema>{{3.99, 4.01}, id, ns},
        battery::ModelMeasurement<battery::CellExtrema>{{24, 26}, id, ns}};
}
class BmsControllerTest : public ::testing::Test {
protected:
    BmsController controller{fixture_config()};
    void SetUp() override { ASSERT_TRUE(controller.start_session(1, 7, kStart)); }
    can::BmsMessage tick(battery::SensorSnapshot s, std::uint32_t now_ms) {
        auto m = controller.tick(s, kStart+now_ms*kMs);
        EXPECT_TRUE(m); return m.value_or(can::BmsMessage{});
    }
    void ready() {
        for (std::uint32_t ms = 0; ms <= 100; ms += 20) tick(sample(ms), ms);
        ASSERT_EQ(controller.decision().state, BmsControlState::Active);
    }
};
TEST(BmsControllerConfiguration, RejectsInvalidCalibrationAndTiming) {
    auto c = fixture_config(); c.charge_current_a = 0;
    EXPECT_THROW(BmsController{c}, std::invalid_argument);
    c = fixture_config(); c.charge_soc = {0.7, 0.8};
    EXPECT_THROW(BmsController{c}, std::invalid_argument);
    c = fixture_config(); c.discharge_cell_v.full = c.charge_cell_v.full+1;
    EXPECT_THROW(BmsController{c}, std::invalid_argument);
    c = fixture_config(); c.temperature_c.release_high = 61;
    EXPECT_THROW(BmsController{c}, std::invalid_argument);
    c = fixture_config(); c.charge_temperature.cold_full = c.charge_temperature.cold_stop;
    EXPECT_THROW(BmsController{c}, std::invalid_argument);
    c = fixture_config(); c.max_charge_power_w = std::numeric_limits<double>::infinity();
    EXPECT_THROW(BmsController{c}, std::invalid_argument);
    c = fixture_config(); c.max_source_age_ns = 51000000;
    EXPECT_THROW(BmsController{c}, std::invalid_argument);
    c = fixture_config(); c.trip_dwell_ns = 0;
    EXPECT_THROW(BmsController{c}, std::invalid_argument);
    c = fixture_config(); c.series_cells = 0;
    EXPECT_THROW(BmsController{c}, std::invalid_argument);
}
TEST(BmsControllerConfiguration, NeedsTrustedApplicationAndModelEpochs) {
    BmsController c(fixture_config());
    EXPECT_FALSE(c.tick(sample(0), kStart));
    EXPECT_FALSE(c.start_session(0, 7, kStart)); EXPECT_FALSE(c.start_session(1, 0, kStart));
    EXPECT_TRUE(c.start_session(1, 7, kStart)); EXPECT_FALSE(c.start_session(1, 7, kStart));
    EXPECT_FALSE(c.start_session(2, 6, kStart));
}
TEST_F(BmsControllerTest, StartupRequiresFreshReleaseBandDwellThenPublishesNominalLimits) {
    auto m = tick(sample(0), 0);
    EXPECT_EQ(m.local_state, can::ActuatorLocalState::Init);
    EXPECT_EQ(m.origin, can::ActuatorOrigin::NormalPath); // sensor accepted; checks still inhibit output
    EXPECT_EQ(controller.decision().limits.charge_power_w, 0);
    for (std::uint32_t ms = 20; ms < 100; ms += 20) {
        tick(sample(ms), ms); EXPECT_EQ(controller.decision().state, BmsControlState::InitialChecks);
    }
    m = tick(sample(100), 100);
    EXPECT_EQ(m.local_state, can::ActuatorLocalState::Normal);
    EXPECT_EQ(controller.decision().limits.charge_power_w, 30000);
    EXPECT_EQ(controller.decision().limits.discharge_power_w, 80000);
    EXPECT_DOUBLE_EQ(*controller.decision().charge_current_a, 75); // power cap / 400 V
    EXPECT_DOUBLE_EQ(*controller.decision().discharge_current_a, 200);
    EXPECT_FALSE(controller.decision().inhibit_requested);
}
TEST_F(BmsControllerTest, MissingStartupSensorsAreUnknownAndCannotCompleteChecks) {
    for (std::uint32_t ms = 0; ms <= 200; ms += 20) {
        auto s = sample(ms); s.electrical.reset(); const auto m = tick(s, ms);
        EXPECT_EQ(m.origin, can::ActuatorOrigin::NoAcceptedInput);
        EXPECT_FALSE(controller.decision().limits.charge_power_w);
        EXPECT_FALSE(controller.decision().recovery_ready);
    }
    EXPECT_EQ(controller.decision().state, BmsControlState::InitialChecks);
}
TEST_F(BmsControllerTest, CachedSafeInputsDoNotCompleteStartupDwell) {
    auto s = sample(0);
    tick(s, 0); tick(s, 20); tick(s, 40);
    EXPECT_EQ(controller.decision().state, BmsControlState::InitialChecks);
    tick(s, 60); EXPECT_EQ(controller.decision().input_issue, BmsInputIssue::Stale);
    EXPECT_FALSE(controller.decision().recovery_ready);
}
TEST_F(BmsControllerTest, FullSocDisablesOnlyChargeAndEmptySocDisablesOnlyDischarge) {
    ready(); auto s = sample(120); s.soc->value = 1; tick(s, 120);
    EXPECT_EQ(controller.decision().limits.charge_power_w, 0);
    EXPECT_FALSE(std::signbit(*controller.decision().limits.charge_power_w));
    EXPECT_EQ(controller.decision().limits.discharge_power_w, 80000);
    EXPECT_EQ(controller.decision().limits.charge_reason, can::BmsLimitReason::SocLimited);
    s = sample(140); s.soc->value = 0; tick(s, 140);
    EXPECT_EQ(controller.decision().limits.discharge_power_w, 0);
    EXPECT_EQ(controller.decision().limits.charge_power_w, 30000);
    EXPECT_FALSE(controller.decision().inhibit_requested);
}
TEST_F(BmsControllerTest, SocDeratingIsLinearWithIndependentDirections) {
    ready(); auto s = sample(120); s.soc->value = 0.875; tick(s, 120);
    EXPECT_NEAR(*controller.decision().limits.charge_power_w, 16000, 10);
    EXPECT_EQ(controller.decision().limits.discharge_power_w, 80000);
    s = sample(140); s.soc->value = 0.075; tick(s, 140);
    EXPECT_NEAR(*controller.decision().limits.discharge_power_w, 40000, 10);
}
TEST_F(BmsControllerTest, ChargeColdCutKeepsDischargeAvailable) {
    ready(); auto s = sample(120); s.cell_temperature->value.minimum = 0; tick(s, 120);
    EXPECT_EQ(controller.decision().limits.charge_power_w, 0);
    EXPECT_EQ(controller.decision().limits.discharge_power_w, 80000);
    EXPECT_EQ(controller.decision().limits.charge_reason, can::BmsLimitReason::TemperatureLimited);
}
TEST_F(BmsControllerTest, SingleHotCellDeratesDespiteNormalPackMean) {
    ready(); auto s = sample(120); s.cell_temperature->value.maximum = 42.5; tick(s, 120);
    EXPECT_EQ(controller.decision().limits.charge_power_w, 16000);
    EXPECT_EQ(controller.decision().limits.discharge_power_w, 80000);
    EXPECT_EQ(controller.decision().limits.charge_reason, can::BmsLimitReason::TemperatureLimited);
}
TEST_F(BmsControllerTest, PackTemperatureAlsoLimitsWhenCellSensorsLookCool) {
    ready(); auto s = sample(120); s.temperature->value = 50; tick(s, 120);
    EXPECT_EQ(controller.decision().limits.charge_power_w, 0);
    EXPECT_EQ(controller.decision().limits.discharge_power_w, 40000);
}
TEST_F(BmsControllerTest, CellVoltageExtremaApplyIndependentDirectionalLimits) {
    ready(); auto s = sample(120); s.cell_voltage->value.maximum = 4.2; tick(s, 120);
    EXPECT_EQ(controller.decision().limits.charge_power_w, 0);
    EXPECT_EQ(controller.decision().limits.discharge_power_w, 80000);
    s = sample(140); s.cell_voltage->value.minimum = 3; tick(s, 140);
    EXPECT_EQ(controller.decision().limits.charge_power_w, 30000);
    EXPECT_EQ(controller.decision().limits.discharge_power_w, 0);
    EXPECT_EQ(controller.decision().limits.discharge_reason, can::BmsLimitReason::ElectricalLimited);
}
TEST_F(BmsControllerTest, TightestFactorWinsRatherThanMultiplyingIndependentMargins) {
    ready(); auto s = sample(120); s.soc->value = 0.875;
    s.cell_temperature->value.maximum = 43.75; s.cell_voltage->value.maximum = 4.11;
    tick(s, 120);
    EXPECT_EQ(controller.decision().limits.charge_power_w, 8000);
    EXPECT_EQ(controller.decision().limits.charge_reason, can::BmsLimitReason::TemperatureLimited);
}
TEST_F(BmsControllerTest, FloorQuantizationNeverOverstatesCalculatedPower) {
    ready(); auto s = sample(120); s.electrical->value.voltage_v = 399.99; tick(s, 120);
    EXPECT_EQ(controller.decision().limits.discharge_power_w, 79990);
    EXPECT_LE(*controller.decision().discharge_current_a, 200);
    EXPECT_LE(*controller.decision().limits.discharge_power_w, 399.99*200);
}
TEST_F(BmsControllerTest, HardCellFaultInhibitsImmediatelyAndLatchesAfterFreshDwell) {
    ready();
    for (std::uint32_t ms = 120; ms <= 160; ms += 20) {
        auto s = sample(ms); s.cell_voltage->value.maximum = 4.25; tick(s, ms);
        EXPECT_TRUE(controller.decision().inhibit_requested);
        EXPECT_EQ(controller.decision().limits.discharge_power_w, 0);
        EXPECT_NE(controller.decision().pending_trips & CellOverVoltage, 0);
        EXPECT_EQ(controller.decision().state, ms == 160 ? BmsControlState::Latched : BmsControlState::Active);
    }
    EXPECT_EQ(controller.decision().fault, BmsControlFault::Protection);
    EXPECT_NE(controller.decision().latched_trips & CellOverVoltage, 0);
}
TEST_F(BmsControllerTest, OneTransientDoesNotLatchAndIndependentFaultsDoNotShareDwell) {
    ready(); auto s = sample(120); s.cell_voltage->value.maximum = 4.3; tick(s, 120);
    s = sample(140); s.cell_temperature->value.maximum = 60; tick(s, 140);
    s = sample(160); s.electrical->value.current_a = 250; tick(s, 160);
    tick(sample(180), 180);
    EXPECT_EQ(controller.decision().state, BmsControlState::Active);
    EXPECT_EQ(controller.decision().latched_trips, 0);
}
TEST_F(BmsControllerTest, CachedViolationCannotAdvanceProtectionConfirmation) {
    ready(); auto s = sample(120); s.cell_temperature->value.maximum = 60;
    tick(s, 120); tick(s, 140); tick(s, 160);
    EXPECT_EQ(controller.decision().state, BmsControlState::Active);
    EXPECT_EQ(controller.decision().latched_trips, 0);
    tick(s, 180); EXPECT_EQ(controller.decision().fault, BmsControlFault::InputsInvalid);
}
TEST_F(BmsControllerTest, HardCurrentInBothDirectionsAndPackVoltageAreMonitored) {
    ready(); auto s = sample(120); s.electrical->value.current_a = -100; tick(s, 120);
    EXPECT_NE(controller.decision().pending_trips & ChargeOverCurrent, 0);
    s = sample(140); s.electrical->value.current_a = 250; tick(s, 140);
    EXPECT_NE(controller.decision().pending_trips & DischargeOverCurrent, 0);
    s = sample(160); s.electrical->value.voltage_v = 425; s.cell_voltage->value = {3.9, 4.3}; tick(s, 160);
    EXPECT_NE(controller.decision().pending_trips & PackOverVoltage, 0);
    s = sample(180); s.electrical->value.voltage_v = 280; s.cell_voltage->value = {2.7, 4}; tick(s, 180);
    EXPECT_NE(controller.decision().pending_trips & PackUnderVoltage, 0);
    EXPECT_NE(controller.decision().pending_trips & CellUnderVoltage, 0);
    s = sample(200); s.cell_temperature->value.minimum = -30; tick(s, 200);
    EXPECT_NE(controller.decision().pending_trips & UnderTemperature, 0);
}
TEST_F(BmsControllerTest, LatchDoesNotAutoClearAndRecoveryHysteresisNeedsNewSession) {
    ready();
    for (std::uint32_t ms = 120; ms <= 160; ms += 20) {
        auto s = sample(ms); s.cell_temperature->value.maximum = 60; tick(s, ms);
    }
    for (std::uint32_t ms = 180; ms <= 300; ms += 20) {
        auto s = sample(ms); s.cell_temperature->value.maximum = 55; tick(s, ms);
        EXPECT_FALSE(controller.decision().recovery_ready); // below trip, above release 50
    }
    for (std::uint32_t ms = 320; ms <= 420; ms += 20) tick(sample(ms), ms);
    EXPECT_TRUE(controller.decision().recovery_ready);
    EXPECT_EQ(controller.decision().state, BmsControlState::Latched);
    EXPECT_EQ(controller.decision().limits.charge_power_w, 0);
    ASSERT_TRUE(controller.start_session(2, 7, kStart+440*kMs));
    for (std::uint32_t ms = 440; ms <= 540; ms += 20) tick(sample(ms), ms);
    EXPECT_EQ(controller.decision().state, BmsControlState::Active);
}
TEST_F(BmsControllerTest, MissingCriticalGroupIsUnknownThenValidZeroWhileLatched) {
    ready(); auto s = sample(120); s.cell_temperature.reset(); auto m = tick(s, 120);
    EXPECT_EQ(controller.decision().fault, BmsControlFault::InputsInvalid);
    EXPECT_FALSE(controller.decision().limits.charge_power_w);
    EXPECT_EQ(controller.decision().limits.input_time_ns, 0);
    EXPECT_EQ(m.local_state, can::ActuatorLocalState::FailSafe);
    tick(sample(140), 140);
    EXPECT_EQ(controller.decision().limits.charge_power_w, 0);
    EXPECT_EQ(controller.decision().limits.charge_reason, can::BmsLimitReason::Disabled);
}
TEST_F(BmsControllerTest, BroadRepresentationChecksRejectNanInvalidPairsAndSoc) {
    ready(); auto s = sample(120); s.soc->value = std::numeric_limits<double>::quiet_NaN(); tick(s, 120);
    EXPECT_EQ(controller.decision().input_issue, BmsInputIssue::Value);
    s = sample(140); s.cell_voltage->value = {4.1, 4}; tick(s, 140);
    EXPECT_EQ(controller.decision().input_issue, BmsInputIssue::Value);
    s = sample(160); s.soc->value = 1.01; tick(s, 160);
    EXPECT_EQ(controller.decision().input_issue, BmsInputIssue::Value);
    s = sample(180); s.temperature->value = -274; tick(s, 180);
    EXPECT_EQ(controller.decision().input_issue, BmsInputIssue::Value);
}
TEST_F(BmsControllerTest, PackVoltageMustFitCellExtremaBounds) {
    ready(); auto s = sample(120); s.cell_voltage->value = {4.1, 4.2}; tick(s, 120);
    EXPECT_EQ(controller.decision().input_issue, BmsInputIssue::Value);
    EXPECT_FALSE(controller.decision().limits.discharge_power_w);
}
TEST_F(BmsControllerTest, WrongModelEpochAndAcquisitionEpochAreRejected) {
    ready(); auto s = sample(120, 8); tick(s, 120);
    EXPECT_EQ(controller.decision().input_issue, BmsInputIssue::Identity);
    s = sample(140); s.soc->identity.epoch = 1; tick(s, 140);
    EXPECT_EQ(controller.decision().input_issue, BmsInputIssue::Identity);
}
TEST_F(BmsControllerTest, RejectsFuturePreSessionAndBackwardsDependencyTimes) {
    ready(); auto s = sample(140); tick(s, 120);
    EXPECT_EQ(controller.decision().input_issue, BmsInputIssue::Timestamp);
    s = sample(140); s.soc->input_time_ns = kStart-1; tick(s, 140);
    EXPECT_EQ(controller.decision().input_issue, BmsInputIssue::Timestamp);
    s = sample(160); s.soc->input_time_ns = s.soc->identity.source_time_ns+1; tick(s, 160);
    EXPECT_EQ(controller.decision().input_issue, BmsInputIssue::Timestamp);
}
TEST_F(BmsControllerTest, HeldGroupAgeAndSensorSkewAreCheckedIndependentlyOfEnvelope) {
    ready(); auto held = sample(100).cell_voltage;
    auto s = sample(120); s.cell_voltage = held; tick(s, 120);
    EXPECT_EQ(controller.decision().input_issue, BmsInputIssue::None); // skew boundary 20 ms
    s = sample(140); s.cell_voltage = held; tick(s, 140);
    EXPECT_EQ(controller.decision().input_issue, BmsInputIssue::Skew);
    s = sample(160); s.cell_voltage = held; tick(s, 160);
    EXPECT_EQ(controller.decision().input_issue, BmsInputIssue::Stale);
}
TEST_F(BmsControllerTest, SourceAndOldestDependencyAgesHaveSeparateInclusiveBounds) {
    auto c = fixture_config(); c.max_sensor_skew_ns = 50000000;
    BmsController b(c); ASSERT_TRUE(b.start_session(1, 7, kStart));
    auto s = sample(80); s.batch.source_time_ns = kStart+100*kMs;
    for (auto* g : {&s.soc.value(), &s.temperature.value()}) g->input_time_ns = kStart+60*kMs;
    auto m = b.tick(s, kStart+130*kMs); // first tick late => deadline, but validation remains observable
    ASSERT_TRUE(m); EXPECT_EQ(b.decision().input_issue, BmsInputIssue::None); // source50 dep70
    s.batch.source_time_ns = kStart+140*kMs; s.batch.sequence++;
    b.tick(s, kStart+150*kMs); EXPECT_EQ(b.decision().input_issue, BmsInputIssue::Stale);
}
TEST_F(BmsControllerTest, CachedMeasurementsAreImmutableAndSequencesCannotRollBack) {
    ready(); auto s = sample(100); s.soc->value = 0.6; tick(s, 120);
    EXPECT_EQ(controller.decision().input_issue, BmsInputIssue::Identity);
    s = sample(80); tick(s, 140); EXPECT_EQ(controller.decision().input_issue, BmsInputIssue::Identity);
    s = sample(160); s.soc = sample(100).soc; s.soc->input_time_ns += 1; tick(s, 160);
    EXPECT_NE(controller.decision().input_issue, BmsInputIssue::None);
}
TEST_F(BmsControllerTest, EarlyTicksDoNotReissueSamplesAndDeadlineInhibitsUntilRestart) {
    ready(); EXPECT_FALSE(controller.tick(sample(100), kStart+110*kMs));
    EXPECT_FALSE(controller.tick(sample(100), kStart+110*kMs));
    auto s = sample(120); s.cell_temperature->value.maximum = 60; tick(s, 120);
    EXPECT_NE(controller.decision().pending_trips, 0);
    tick(sample(180), 180);
    EXPECT_EQ(controller.decision().fault, BmsControlFault::ControlDeadline);
    EXPECT_EQ(controller.decision().pending_trips, 0);
    EXPECT_FALSE(controller.decision().limits.charge_power_w);
    tick(sample(200), 200); EXPECT_FALSE(controller.decision().limits.charge_power_w);
}
TEST_F(BmsControllerTest, ClockRollbackStopsPublicationAndRestartMustBeMonotonic) {
    ready(); EXPECT_FALSE(controller.tick(sample(80), kStart+99*kMs));
    EXPECT_EQ(controller.decision().fault, BmsControlFault::ClockError);
    EXPECT_FALSE(controller.tick(sample(120), kStart+120*kMs));
    EXPECT_FALSE(controller.start_session(2, 7, kStart+99*kMs));
    EXPECT_TRUE(controller.start_session(2, 7, kStart+120*kMs));
}
TEST_F(BmsControllerTest, DeadlineAfterSensorFaultStillMakesLimitsUnknownUntilRestart) {
    ready(); auto s = sample(120); s.soc.reset(); tick(s, 120);
    EXPECT_EQ(controller.decision().fault, BmsControlFault::InputsInvalid);
    tick(sample(180), 180);
    EXPECT_EQ(controller.decision().fault, BmsControlFault::ControlDeadline);
    EXPECT_FALSE(controller.decision().limits.charge_power_w);
    tick(sample(200), 200); EXPECT_FALSE(controller.decision().limits.charge_power_w);
}
TEST_F(BmsControllerTest, CachedBatchCannotAcquireNewMeasurementsOrRefreshDependency) {
    ready(); auto s = sample(120); s.cell_voltage = sample(100).cell_voltage; tick(s, 120);
    s.cell_voltage = sample(120).cell_voltage; tick(s, 140);
    EXPECT_EQ(controller.decision().input_issue, BmsInputIssue::Identity);
    s = sample(160); s.cell_voltage = sample(100).cell_voltage;
    s.cell_voltage->input_time_ns = kStart+120*kMs; tick(s, 160);
    EXPECT_NE(controller.decision().input_issue, BmsInputIssue::None);
}
TEST_F(BmsControllerTest, CanCodecAndReceiverPreserveCausalBatchDependencyAndValidZero) {
    can::BmsReceiver receiver({can::BmsFrameKind::PowerLimits, {{0, 1000}, {-300, 300}, {-50, 100}, 100000}});
    ASSERT_TRUE(receiver.start_session(1, kStart));
    can::BmsTxState tx{can::BmsFrameKind::PowerLimits};
    for (std::uint32_t ms = 0; ms <= 160; ms += 20) {
        auto s = sample(ms);
        if (ms >= 120) s.soc->value = 1;
        // Every dependency remains 20 ms older than this acquisition after startup.
        if (ms > 0) s.soc->input_time_ns -= 20*kMs;
        auto m = tick(s, ms);
        auto frame = can::encode_bms_frame(m, tx); ASSERT_TRUE(frame);
        auto decoded = can::decode_bms_frame(*frame); ASSERT_TRUE(decoded);
        EXPECT_EQ(decoded->causal_sequence, s.batch.sequence);
        EXPECT_EQ(std::get<can::BmsPowerLimits>(decoded->content).input_time_ns, s.soc->input_time_ns);
        const auto rx = receiver.receive(*frame, kStart+ms*kMs);
        EXPECT_EQ(rx.decision, can::ActuatorReceiveDecision::Accepted);
    }
    auto current = receiver.current_sample(kStart+160*kMs); ASSERT_TRUE(current);
    EXPECT_EQ(current->quality[0], can::BmsFieldQuality::Usable);
    EXPECT_EQ(std::get<can::BmsPowerLimits>(current->message.content).charge_power_w, 0);
    EXPECT_FALSE(can::bms_power_is_ready(*current));
}
TEST_F(BmsControllerTest, UnknownPublishedLimitsCannotRefreshUsableReceiverClock) {
    can::BmsReceiver receiver({can::BmsFrameKind::PowerLimits, {{0, 1000}, {-300, 300}, {-50, 100}, 100000}});
    ASSERT_TRUE(receiver.start_session(1, kStart)); can::BmsTxState tx{can::BmsFrameKind::PowerLimits};
    auto m = tick(sample(0), 0); auto f = can::encode_bms_frame(m, tx); ASSERT_TRUE(f);
    receiver.receive(*f, kStart);
    ASSERT_TRUE(receiver.last_usable_rx_time_ns(0));
    for (std::uint32_t ms = 20; ms < 80; ms += 20) {
        auto s = sample(ms); s.cell_voltage.reset(); m = tick(s, ms);
        f = can::encode_bms_frame(m, tx); ASSERT_TRUE(f); receiver.receive(*f, kStart+ms*kMs);
        EXPECT_EQ(*receiver.last_usable_rx_time_ns(0), kStart);
    }
    EXPECT_EQ(receiver.poll(kStart+80*kMs), can::ActuatorReceiverHealth::Timeout);
}
TEST_F(BmsControllerTest, BatteryPlantSurvivesApplicationRestartWithSameModelEpoch) {
    simulation::BatteryModel plant({180000000, 400, 0.05, 200000, 20, 25, 100, 0.01, 1, 100000});
    ASSERT_TRUE(plant.initialize({7, kStart, 0.5, 25}));
    for (std::uint32_t i = 0; i < 20; ++i) {
        const auto begin = kStart+static_cast<std::uint64_t>(i)*20*kMs;
        ASSERT_EQ(plant.step({begin, begin+20*kMs, {{7, i, begin}, begin, 1000, 200}}).fault, simulation::BatteryFault::None);
        if (i == 10) { ASSERT_TRUE(controller.start_session(2, 7, begin)); }
        ASSERT_TRUE(controller.tick(plant.observation(), begin+20*kMs));
    }
    EXPECT_EQ(plant.diagnostic_state().identity.epoch, 7U);
    EXPECT_LT(plant.diagnostic_state().soc, 0.5);
    EXPECT_GT(plant.diagnostic_state().drawn_dc_j, 0);
    EXPECT_EQ(controller.decision().state, BmsControlState::Active);
}
TEST_F(BmsControllerTest, LocalPowerGateCarriesOriginalDecisionIdentityAndUnknownRemainsUnknown) {
    ready(); ASSERT_TRUE(controller.power_gate()); EXPECT_EQ(controller.power_gate()->inhibit, false);
    EXPECT_EQ(controller.power_gate()->application_epoch, 1U);
    auto s = sample(120); s.soc->value = 1; const auto m = tick(s, 120);
    EXPECT_EQ(controller.power_gate()->inhibit, false); // charge-only cut permits discharge
    EXPECT_EQ(controller.power_gate()->sequence, m.sequence);
    EXPECT_EQ(controller.power_gate()->source_time_ns, m.source_time_ns);
    EXPECT_EQ(controller.power_gate()->input_time_ns, controller.decision().limits.input_time_ns);
    s = sample(140); s.cell_temperature.reset(); tick(s, 140);
    EXPECT_FALSE(controller.power_gate()->inhibit.has_value());
    EXPECT_FALSE(controller.tick(s, kStart+139*kMs)); EXPECT_FALSE(controller.power_gate());
}
}  // namespace
