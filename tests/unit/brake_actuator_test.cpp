#include "brake_sil.hpp"

#include <gtest/gtest.h>
#include <algorithm>
#include <limits>
#include <stdexcept>

namespace {
using namespace stratadrive;
constexpr std::uint64_t kStart = 1000000000, kMs = 1000000;
vecu::BrakeActuatorConfig configuration() { return {2000000, 1500000, 0, 5000000, 10000000, 1000000, 50*kMs}; }
class BrakeActuatorTest : public ::testing::Test {
protected:
    simulation::BrakeSil model{configuration()};
    can::BrakeTxState tx{can::BrakeFrameKind::Command};
    std::uint32_t sequence{0};
    struct Input { int ms; double pressure; std::uint32_t epoch{1}; };
    void SetUp() override { ASSERT_TRUE(model.start_session(1, kStart)); }
    can::BrakeFrame command(Input input) {
        can::BrakeMessage message;
        message.pressure_pa = input.pressure; message.sequence = sequence++; message.epoch = input.epoch;
        message.source_time_ns = kStart + input.ms*kMs;
        message.local_state = can::BrakeLocalState::Normal; message.origin = can::BrakeOrigin::NormalPath;
        return can::encode_brake_frame(message, tx).value();
    }
    can::BrakeMessage tick(int ms) {
        return can::decode_brake_frame(model.tick(kStart + ms*kMs).value()).value();
    }
    can::BrakeMessage drive(int ms, double pressure) {
        EXPECT_EQ(model.receive(command({ms, pressure}), kStart + ms*kMs).decision, can::BrakeReceiveDecision::Accepted);
        return tick(ms);
    }
};
TEST(BrakeActuatorConfig, InvalidPressureRateFloorAndTimingAreRejected) {
    auto config = configuration(); config.rise_rate_pa_s = 0;
    EXPECT_THROW(simulation::BrakeSil{config}, std::invalid_argument);
    config = configuration(); config.fall_rate_pa_s = -1;
    EXPECT_THROW(simulation::BrakeSil{config}, std::invalid_argument);
    config = configuration(); config.fault_pressure_floor_pa = 1600000;
    EXPECT_THROW(simulation::BrakeSil{config}, std::invalid_argument);
    config = configuration(); config.initial_pressure_pa = std::numeric_limits<double>::quiet_NaN();
    EXPECT_THROW(simulation::BrakeSil{config}, std::invalid_argument);
    config = configuration(); config.delay_ns = 1001*kMs;
    EXPECT_THROW(simulation::BrakeSil{config}, std::invalid_argument);
}
TEST_F(BrakeActuatorTest, StartupSilenceIsInitThenDiagnosticUnavailableWithoutPressureJump) {
    for (int ms = 10; ms < 80; ms += 10) {
        const auto actual = tick(ms);
        EXPECT_EQ(actual.local_state, can::BrakeLocalState::Init);
        EXPECT_EQ(actual.origin, can::BrakeOrigin::NoAcceptedInput);
        EXPECT_DOUBLE_EQ(*actual.pressure_pa, 0);
    }
    const auto failed = tick(80);
    EXPECT_FALSE(failed.pressure_pa);
    EXPECT_EQ(failed.local_state, can::BrakeLocalState::FailSafe);
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(), 0);
    EXPECT_FALSE(tick(90).pressure_pa);
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(), 50000);
}
TEST_F(BrakeActuatorTest, RepeatedCommandKeepsDelayRateAndSaturationWithIndependentActual) {
    can::BrakeReceiver feedback({can::BrakeFrameKind::Actual, 0, 1500000});
    ASSERT_TRUE(feedback.start_session(1, kStart));
    for (int ms = 10; ms <= 400; ms += 10) {
        ASSERT_EQ(model.receive(command({ms, 2000000}), kStart + ms*kMs).decision, can::BrakeReceiveDecision::Accepted);
        const auto frame = model.tick(kStart + ms*kMs).value();
        ASSERT_EQ(feedback.receive(frame, kStart + ms*kMs).decision, can::BrakeReceiveDecision::Accepted);
        const auto actual = feedback.current_sample(kStart + ms*kMs).value();
        EXPECT_NEAR(*actual.pressure_pa, std::min(1500000.0, std::max(0.0, (ms-60)*5000.0)), 500.1);
        EXPECT_EQ(actual.causal_sequence, sequence-1);
        EXPECT_EQ(actual.source_time_ns, kStart + ms*kMs);
        EXPECT_EQ(actual.sequence, static_cast<std::uint32_t>(ms/10-1));
    }
    EXPECT_EQ(model.fault(), vecu::BrakeFault::None);
}
TEST_F(BrakeActuatorTest, ValidZeroReleasesWithDelayAndSeparateFasterFallRate) {
    for (int ms = 10; ms <= 300; ms += 10) drive(ms, 1000000);
    for (int ms = 310; ms <= 470; ms += 10) {
        const auto actual = drive(ms, 0);
        ASSERT_TRUE(actual.pressure_pa);
        EXPECT_NEAR(*actual.pressure_pa, std::max(0.0, 1000000.0 - std::max(0, ms-360)*10000.0), 500.1);
    }
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(), 0);
    EXPECT_EQ(model.fault(), vecu::BrakeFault::None);
}
TEST_F(BrakeActuatorTest, TargetChangesHaveSeparateDueTimesAndCanCancelBuildup) {
    for (int ms = 10; ms <= 110; ms += 10) {
        drive(ms, ms < 40 ? 1000000 : 0);
        if (ms == 90) { EXPECT_DOUBLE_EQ(model.actual_pressure_pa(), 150000); }
    }
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(), 0);
}
TEST_F(BrakeActuatorTest, JitteredTickSplitsAtDelayBoundary) {
    for (int ms = 10; ms <= 50; ms += 10) drive(ms, 1000000);
    drive(65, 1000000);
    EXPECT_NEAR(model.actual_pressure_pa(), 25000, 1e-6);
}
TEST_F(BrakeActuatorTest, ExpiryCancelsDelayedReleaseAndProtectiveFloorRampsWithoutRestarting) {
    drive(10, 0); tick(20); tick(30); tick(40);
    EXPECT_DOUBLE_EQ(*tick(50).pressure_pa, 0);
    for (int ms = 60; ms <= 280; ms += 10) {
        const auto actual = tick(ms);
        EXPECT_NEAR(*actual.pressure_pa, std::min(1000000.0, (ms-50)*5000.0), 500.1);
        EXPECT_EQ(actual.origin, can::BrakeOrigin::LocalProtection);
        EXPECT_EQ(actual.local_state, can::BrakeLocalState::FailSafe);
        EXPECT_EQ(actual.causal_sequence, 0U);
    }
}
TEST_F(BrakeActuatorTest, HigherPressureIsRetainedOnLossAndLateZeroCannotReleaseIt) {
    for (int ms = 10; ms <= 400; ms += 10) drive(ms, 2000000);
    drive(410, 0); // release due at 460 ms; expiry must cancel this pending target
    for (int ms = 420; ms <= 450; ms += 10) tick(ms);
    ASSERT_EQ(model.fault(), vecu::BrakeFault::CommandUnavailable);
    EXPECT_EQ(model.receive(command({460, 0}), kStart + 460*kMs).decision, can::BrakeReceiveDecision::ModeRejected);
    tick(460); tick(470);
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(), 1500000);
    EXPECT_EQ(model.receiver().last_accepted()->message.sequence, 40U);
}
TEST_F(BrakeActuatorTest, LossDuringBuildupRampsToFloorInsteadOfJumpingOrReleasing) {
    for (int ms = 10; ms <= 100; ms += 10) drive(ms, 2000000);
    tick(110); tick(120); tick(130);
    EXPECT_DOUBLE_EQ(*tick(140).pressure_pa, 350000);
    EXPECT_DOUBLE_EQ(*tick(150).pressure_pa, 400000);
    for (int ms = 160; ms <= 300; ms += 10) tick(ms);
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(), 1000000);
}
TEST_F(BrakeActuatorTest, ContinuityLossUsesOnlyElapsedTimeAfterDetection) {
    for (int ms = 10; ms <= 100; ms += 10) drive(ms, 1000000);
    model.mark_continuity_lost(kStart + 101*kMs);
    EXPECT_DOUBLE_EQ(*tick(110).pressure_pa, 245000);
    EXPECT_EQ(model.fault(), vecu::BrakeFault::ContinuityLost);
    EXPECT_EQ(model.receive(command({120, 0}), kStart + 120*kMs).decision, can::BrakeReceiveDecision::ModeRejected);
}
TEST_F(BrakeActuatorTest, MissedDeadlineDoesNotBackfillButLaterTicksCanRunProtection) {
    for (int ms = 10; ms <= 100; ms += 10) drive(ms, 1000000);
    ASSERT_EQ(model.receive(command({130, 1000000}), kStart + 130*kMs).decision, can::BrakeReceiveDecision::Accepted);
    EXPECT_DOUBLE_EQ(*tick(140).pressure_pa, 200000);
    EXPECT_EQ(model.fault(), vecu::BrakeFault::ControlDeadline);
    EXPECT_DOUBLE_EQ(*tick(150).pressure_pa, 250000);
}
TEST_F(BrakeActuatorTest, ClockRegressionSuppressesFeedbackAndMotion) {
    drive(10, 1000000);
    EXPECT_FALSE(model.tick(kStart + 10*kMs));
    EXPECT_EQ(drive(20, 1000000).sequence, 1U);
    EXPECT_FALSE(model.tick(kStart + 19*kMs));
    EXPECT_FALSE(model.tick(kStart + 30*kMs));
    EXPECT_EQ(model.fault(), vecu::BrakeFault::ClockError);
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(), 0);
}
TEST_F(BrakeActuatorTest, NewEpochPreservesPhysicalPressureAndResetsFeedbackStream) {
    for (int ms = 10; ms <= 100; ms += 10) drive(ms, 1000000);
    model.mark_continuity_lost(kStart + 101*kMs); tick(110);
    const auto held = model.actual_pressure_pa();
    EXPECT_FALSE(model.start_session(1, kStart + 110*kMs));
    EXPECT_FALSE(model.start_session(2, kStart + 109*kMs));
    ASSERT_TRUE(model.start_session(2, kStart + 110*kMs));
    const auto actual = tick(120);
    EXPECT_DOUBLE_EQ(*actual.pressure_pa, held);
    EXPECT_EQ(actual.epoch, 2U); EXPECT_EQ(actual.sequence, 0U);
    EXPECT_EQ(actual.local_state, can::BrakeLocalState::Init);
    EXPECT_EQ(model.fault(), vecu::BrakeFault::None);
}
TEST_F(BrakeActuatorTest, RangeUnavailableAndCorruptionDoNotRefreshAcceptedCommand) {
    drive(10, 1000000);
    EXPECT_EQ(model.receive(command({20, 2100000}), kStart + 20*kMs).decision, can::BrakeReceiveDecision::PressureOutOfRange);
    auto unavailable = can::decode_brake_frame(command({30, 0})).value(); unavailable.pressure_pa.reset();
    EXPECT_EQ(model.receive(can::encode_brake_frame(unavailable, tx).value(), kStart + 30*kMs).decision,
              can::BrakeReceiveDecision::Unavailable);
    auto corrupt = command({40, 1000000}); corrupt.payload[0] ^= 1;
    EXPECT_NE(model.receive(corrupt, kStart + 40*kMs).decision, can::BrakeReceiveDecision::Accepted);
    EXPECT_EQ(model.receiver().last_accepted()->message.sequence, 0U);
    EXPECT_EQ(model.receive(command({41, 0}), kStart + 41*kMs).decision, can::BrakeReceiveDecision::ModeRejected);
    EXPECT_EQ(model.fault(), vecu::BrakeFault::CommandUnavailable);
}
TEST_F(BrakeActuatorTest, InitialPressureZeroDelayAndDegradedInputRemainDistinct) {
    auto config = configuration(); config.initial_pressure_pa = 500000; config.delay_ns = 0;
    simulation::BrakeSil other(config); ASSERT_TRUE(other.start_session(1, kStart));
    can::BrakeMessage input;
    input.epoch = 1; input.pressure_pa = 1000000; input.source_time_ns = kStart + 10*kMs;
    input.local_state = can::BrakeLocalState::Degraded; input.origin = can::BrakeOrigin::NormalPath;
    ASSERT_EQ(other.receive(can::encode_brake_frame(input, tx).value(), input.source_time_ns).decision, can::BrakeReceiveDecision::Accepted);
    const auto first = can::decode_brake_frame(other.tick(input.source_time_ns).value()).value();
    EXPECT_DOUBLE_EQ(*first.pressure_pa, 500000);
    EXPECT_EQ(first.local_state, can::BrakeLocalState::Degraded);
    ASSERT_TRUE(other.tick(kStart + 20*kMs)); EXPECT_DOUBLE_EQ(other.actual_pressure_pa(), 550000);
}
TEST_F(BrakeActuatorTest, MaximumDelayAndManyTargetChangesStayWithinBoundedHistory) {
    auto config = configuration(); config.delay_ns = 1000*kMs;
    simulation::BrakeSil other(config); ASSERT_TRUE(other.start_session(1, kStart));
    for (int ms = 10; ms <= 3000; ms += 10) {
        ASSERT_EQ(other.receive(command({ms, ms % 20 ? 1000000.0 : 0.0}), kStart + ms*kMs).decision,
                  can::BrakeReceiveDecision::Accepted);
        ASSERT_TRUE(other.tick(kStart + ms*kMs));
        ASSERT_EQ(other.fault(), vecu::BrakeFault::None);
        ASSERT_GE(other.actual_pressure_pa(), 0); ASSERT_LE(other.actual_pressure_pa(), 1500000);
    }
}
TEST(BrakeActuatorConfig, InvalidMonitoringSettingsAreRejected) {
    auto c=configuration(); c.healthy_min_rate_fraction=1.1; EXPECT_THROW(simulation::BrakeSil{c},std::invalid_argument);
    c=configuration(); c.healthy_max_rate_fraction=.9; EXPECT_THROW(simulation::BrakeSil{c},std::invalid_argument);
    c=configuration(); c.response_confirmation_ns=kMs; EXPECT_THROW(simulation::BrakeSil{c},std::invalid_argument);
    c=configuration(); c.sensor_age_ns=40*kMs; EXPECT_THROW(simulation::BrakeSil{c},std::invalid_argument);
}
TEST_F(BrakeActuatorTest, StuckRiseWithFreshCommandAndSensorCannotFabricateProtectivePressure) {
    for(int ms=10;ms<=100;ms+=10) drive(ms,1000000);
    for(int ms=110;ms<=180;ms+=10) {
        ASSERT_EQ(model.receive(command({ms,1000000}),kStart+ms*kMs).decision,can::BrakeReceiveDecision::Accepted);
        const auto a=can::decode_brake_frame(*model.tick(kStart+ms*kMs,{true,1,1})).value();
        ASSERT_TRUE(a.pressure_pa); EXPECT_DOUBLE_EQ(*a.pressure_pa,200000);
        if(ms==120) { EXPECT_EQ(a.local_state,can::BrakeLocalState::Degraded); }
        if(ms<180) { EXPECT_EQ(model.fault(),vecu::BrakeFault::None); }
    }
    EXPECT_EQ(model.fault(),vecu::BrakeFault::ResponseError);
    EXPECT_EQ(model.receiver().health(),can::BrakeReceiverHealth::Receiving);
    EXPECT_EQ(model.monitor_decision().violation_since_ns,kStart+120*kMs);
    EXPECT_EQ(model.protection_floor_observed(),false);
    const auto failed=can::decode_brake_frame(*model.tick(kStart+190*kMs,{true,1,1})).value();
    EXPECT_DOUBLE_EQ(*failed.pressure_pa,200000); EXPECT_EQ(failed.origin,can::BrakeOrigin::LocalProtection);
    EXPECT_EQ(failed.local_state,can::BrakeLocalState::FailSafe);
    EXPECT_EQ(model.receive(command({190,0}),kStart+190*kMs).decision,can::BrakeReceiveDecision::ModeRejected);
}
TEST_F(BrakeActuatorTest, PhysicalRecoveryDoesNotClearLatchAndProtectionRampsFromDetection) {
    for(int ms=10;ms<=100;ms+=10) drive(ms,1000000);
    for(int ms=110;ms<=180;ms+=10) {
        model.receive(command({ms,1000000}),kStart+ms*kMs); ASSERT_TRUE(model.tick(kStart+ms*kMs,{true,1,1}));
    }
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(),200000);
    EXPECT_DOUBLE_EQ(*tick(190).pressure_pa,250000);
    for(int ms=200;ms<=340;ms+=10) tick(ms);
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(),1000000); EXPECT_EQ(model.protection_floor_observed(),true);
    EXPECT_EQ(model.fault(),vecu::BrakeFault::ResponseError);
}
TEST_F(BrakeActuatorTest, SlowRiseIsDetectedWhileIndependentAcquisitionsContinue) {
    for(int ms=10;ms<=100;ms+=10) drive(ms,1000000);
    for(int ms=110;ms<=190;ms+=10) {
        model.receive(command({ms,1000000}),kStart+ms*kMs); ASSERT_TRUE(model.tick(kStart+ms*kMs,{false,.25,1}));
    }
    EXPECT_EQ(model.fault(),vecu::BrakeFault::ResponseError);
    EXPECT_EQ(model.monitor_decision().violation_since_ns,kStart+130*kMs);
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(),312500); EXPECT_EQ(model.protection_floor_observed(),false);
}
TEST_F(BrakeActuatorTest, StuckReleaseRetainsHigherPressureEvenAfterProtectionRequest) {
    for(int ms=10;ms<=400;ms+=10) drive(ms,2000000);
    for(int ms=410;ms<=530;ms+=10) {
        model.receive(command({ms,0}),kStart+ms*kMs);
        ASSERT_TRUE(model.tick(kStart+ms*kMs,{ms>460,1,1}));
    }
    EXPECT_EQ(model.fault(),vecu::BrakeFault::ResponseError);
    EXPECT_EQ(model.monitor_decision().violation_since_ns,kStart+470*kMs);
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(),1500000);
    EXPECT_EQ(model.protection_floor_observed(),true); // floor observed is not successful release
    tick(540); EXPECT_DOUBLE_EQ(model.actual_pressure_pa(),1500000);
}
TEST_F(BrakeActuatorTest, SlowReleaseIsDetectedUsingFallBandThenCanBuildToProtectiveFloor) {
    for(int ms=10;ms<=300;ms+=10) drive(ms,1000000);
    for(int ms=310;ms<=430;ms+=10) {
        model.receive(command({ms,0}),kStart+ms*kMs);
        ASSERT_TRUE(model.tick(kStart+ms*kMs,{false,1,ms>360 ? .25:1}));
    }
    EXPECT_EQ(model.fault(),vecu::BrakeFault::ResponseError);
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(),825000); EXPECT_EQ(model.protection_floor_observed(),false);
    ASSERT_TRUE(model.tick(kStart+440*kMs,{false,1,.25})); EXPECT_DOUBLE_EQ(model.actual_pressure_pa(),875000);
}
TEST_F(BrakeActuatorTest, HealthyRateEdgesWithReversalAndSaturationDoNotLatch) {
    for(double fraction:{.8,1.,1.2}) {
        simulation::BrakeSil other(configuration()); ASSERT_TRUE(other.start_session(1,kStart));
        sequence=0; e2e::p05_protect_init(tx.protection);
        for(int ms=10;ms<=700;ms+=10) {
            ASSERT_EQ(other.receive(command({ms,ms<350 ? 2000000.:0}),kStart+ms*kMs).decision,can::BrakeReceiveDecision::Accepted);
            const auto f=other.tick(kStart+ms*kMs,{false,fraction,fraction}); ASSERT_TRUE(f);
            EXPECT_EQ(other.fault(),vecu::BrakeFault::None); EXPECT_FALSE(other.monitor_decision().violation_since_ns);
        }
    }
}
TEST_F(BrakeActuatorTest, HeldSensorDoesNotRenewDownstreamValidPressureOrConfirmSuccess) {
    can::BrakeReceiver downstream({can::BrakeFrameKind::Actual,0,1500000}); ASSERT_TRUE(downstream.start_session(1,kStart));
    for(int ms=10;ms<=100;ms+=10) {
        model.receive(command({ms,1000000}),kStart+ms*kMs); const auto f=model.tick(kStart+ms*kMs);
        ASSERT_EQ(downstream.receive(*f,kStart+ms*kMs).decision,can::BrakeReceiveDecision::Accepted);
    }
    for(int ms=110;ms<=300;ms+=10) {
        model.receive(command({ms,1000000}),kStart+ms*kMs);
        const auto f=model.tick(kStart+ms*kMs,{},simulation::BrakeSensorAction::Hold); ASSERT_TRUE(f);
        EXPECT_FALSE(can::decode_brake_frame(*f)->pressure_pa);
        EXPECT_NE(downstream.receive(*f,kStart+ms*kMs).decision,can::BrakeReceiveDecision::Accepted);
        EXPECT_FALSE(model.protection_floor_observed());
    }
    EXPECT_EQ(model.fault(),vecu::BrakeFault::SensorUnavailable);
    EXPECT_EQ(downstream.last_accepted()->received_time_ns,kStart+100*kMs);
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(),1000000); // diagnostic truth is not feedback
}
TEST_F(BrakeActuatorTest, InvalidPressureIsUnknownWithoutTruthFallback) {
    drive(10,1000000); model.receive(command({20,1000000}),kStart+20*kMs);
    const auto f=model.tick(kStart+20*kMs,{},simulation::BrakeSensorAction::Acquire,std::numeric_limits<double>::quiet_NaN());
    ASSERT_TRUE(f); EXPECT_FALSE(can::decode_brake_frame(*f)->pressure_pa);
    EXPECT_EQ(model.fault(),vecu::BrakeFault::SensorInvalid); EXPECT_FALSE(model.protection_floor_observed());
}
TEST_F(BrakeActuatorTest, ATransientOutlierDegradesThenClearsPendingWithoutLatch) {
    for(int ms=10;ms<=300;ms+=10) {
        model.receive(command({ms,1000000}),kStart+ms*kMs);
        const auto f=model.tick(kStart+ms*kMs,{},simulation::BrakeSensorAction::Acquire,
            ms==160 ? std::optional<double>{1500000}:std::nullopt);
        ASSERT_TRUE(f); const auto a=can::decode_brake_frame(*f).value();
        if(ms==160) { EXPECT_EQ(a.local_state,can::BrakeLocalState::Degraded); }
        if(ms==170) { EXPECT_EQ(a.local_state,can::BrakeLocalState::Normal); EXPECT_FALSE(model.monitor_decision().violation_since_ns); }
        EXPECT_EQ(model.fault(),vecu::BrakeFault::None);
    }
}
TEST_F(BrakeActuatorTest, NewEpochPreservesPhysicsAndRequiresANewAcquisition) {
    for(int ms=10;ms<=100;ms+=10) drive(ms,1000000);
    model.mark_continuity_lost(kStart+100*kMs); ASSERT_TRUE(model.start_session(2,kStart+110*kMs));
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(),200000);
    const auto f=model.tick(kStart+120*kMs,{},simulation::BrakeSensorAction::Hold); ASSERT_TRUE(f);
    EXPECT_EQ(model.fault(),vecu::BrakeFault::SensorInvalid); EXPECT_FALSE(can::decode_brake_frame(*f)->pressure_pa);
    ASSERT_TRUE(model.start_session(3,kStart+120*kMs)); const auto a=tick(130);
    EXPECT_DOUBLE_EQ(*a.pressure_pa,200000); EXPECT_EQ(a.epoch,3U); EXPECT_EQ(a.sequence,0U);
    EXPECT_EQ(model.fault(),vecu::BrakeFault::None);
}
TEST_F(BrakeActuatorTest, InvalidPhysicalIntervalIsUnavailableAndCannotBackfill) {
    for(int ms=10;ms<=100;ms+=10) drive(ms,1000000);
    model.receive(command({110,1000000}),kStart+110*kMs);
    const auto f=model.tick(kStart+110*kMs,{false,-1,1}); ASSERT_TRUE(f);
    EXPECT_FALSE(can::decode_brake_frame(*f)->pressure_pa); EXPECT_FALSE(model.protection_floor_observed());
    EXPECT_EQ(model.fault(),vecu::BrakeFault::PhysicalModelError); EXPECT_DOUBLE_EQ(model.actual_pressure_pa(),200000);
    EXPECT_DOUBLE_EQ(*tick(120).pressure_pa,250000);
}
TEST_F(BrakeActuatorTest, PlausibleSensorFreezeCanResembleStuckPhysicsWithoutProvingItsCause) {
    for(int ms=10;ms<=130;ms+=10) {
        model.receive(command({ms,1000000}),kStart+ms*kMs);
        ASSERT_TRUE(model.tick(kStart+ms*kMs,{},simulation::BrakeSensorAction::Acquire,0));
    }
    EXPECT_EQ(model.fault(),vecu::BrakeFault::ResponseError);
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(),350000); // plant moved; monitor cannot read this truth
    EXPECT_EQ(model.protection_floor_observed(),false);
}
TEST_F(BrakeActuatorTest, NewApplicationEpochCannotRepairPersistentPhysicalStuckFault) {
    for(int ms=10;ms<=100;ms+=10) drive(ms,1000000);
    for(int ms=110;ms<=180;ms+=10) {
        model.receive(command({ms,1000000}),kStart+ms*kMs); ASSERT_TRUE(model.tick(kStart+ms*kMs,{true,1,1}));
    }
    ASSERT_EQ(model.fault(),vecu::BrakeFault::ResponseError);
    ASSERT_TRUE(model.start_session(2,kStart+180*kMs)); sequence=0; e2e::p05_protect_init(tx.protection);
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(),200000);
    for(int ms=190;ms<=310;ms+=10) {
        ASSERT_EQ(model.receive(command({ms,1000000,2}),kStart+ms*kMs).decision,can::BrakeReceiveDecision::Accepted);
        const auto f=model.tick(kStart+ms*kMs,{true,1,1}); ASSERT_TRUE(f);
        if(ms==190) { EXPECT_EQ(can::decode_brake_frame(*f)->sequence,0U); EXPECT_EQ(model.fault(),vecu::BrakeFault::None); }
    }
    EXPECT_EQ(model.fault(),vecu::BrakeFault::ResponseError);
    EXPECT_DOUBLE_EQ(model.actual_pressure_pa(),200000);
}
TEST(BrakeExecutionBoundary, ExternalPressureContinuesWithoutEcuAndProtectionStartsAtResumeTime) {
    vecu::BrakeActuator ecu(configuration()); simulation::BrakePressureResponse plant({1500000,0,5000000,10000000,50*kMs});
    ASSERT_TRUE(ecu.start_session({1,1,kStart})); ASSERT_TRUE(plant.begin(kStart));
    can::BrakeMessage m; m.epoch=1; m.pressure_pa=1000000; m.source_time_ns=kStart+10*kMs;
    m.local_state=can::BrakeLocalState::Normal; m.origin=can::BrakeOrigin::NormalPath;
    can::BrakeTxState tx{m.kind}; ASSERT_EQ(ecu.receive(*can::encode_brake_frame(m,tx),m.source_time_ns).decision,can::BrakeReceiveDecision::Accepted);
    ASSERT_TRUE(ecu.prepare(m.source_time_ns)); ASSERT_TRUE(plant.advance(m.source_time_ns)); ASSERT_TRUE(ecu.complete(plant.capture(),m.source_time_ns));
    ASSERT_TRUE(plant.set_target(ecu.output().target_pa,ecu.output().issued_time_ns));
    ASSERT_TRUE(plant.advance(kStart+100*kMs)); EXPECT_DOUBLE_EQ(plant.actual_pressure_pa(),200000);
    ASSERT_TRUE(ecu.prepare(kStart+100*kMs)); EXPECT_EQ(ecu.fault(),vecu::BrakeFault::ControlDeadline);
    ASSERT_TRUE(plant.request_protection(ecu.output().target_pa,ecu.output().issued_time_ns));
    ASSERT_TRUE(ecu.complete(plant.capture(),kStart+100*kMs)); EXPECT_EQ(ecu.protection_floor_observed(),false);
    ASSERT_TRUE(plant.advance(kStart+110*kMs)); EXPECT_DOUBLE_EQ(plant.actual_pressure_pa(),250000);
}

class BrakeStartupTest : public BrakeActuatorTest {
protected:
    void SetUp() override { ASSERT_TRUE(model.start_session(1,kStart,ActuatorCommandStartup::NonDriving)); }
    void wait_until(int last) { for (int ms=10;ms<=last;ms+=10) ASSERT_TRUE(model.tick(kStart+ms*kMs)); }
};
TEST_F(BrakeStartupTest, LongStartupPublishesKnownInitWithoutNormalPackets) {
    can::BrakeMessage actual;
    for (int ms=10;ms<=1000;ms+=10) {
        actual=tick(ms); ASSERT_TRUE(actual.pressure_pa); EXPECT_EQ(actual.local_state,can::BrakeLocalState::Init);
        EXPECT_EQ(actual.origin,can::BrakeOrigin::NoAcceptedInput); EXPECT_EQ(actual.causal_sequence,0U);
    }
    EXPECT_EQ(model.fault(),vecu::BrakeFault::None); EXPECT_EQ(actual.sequence,99U);
    EXPECT_EQ(model.receiver().health(),can::BrakeReceiverHealth::NotInitialized);
    EXPECT_FALSE(model.current_sample(kStart+1000*kMs));
}
TEST_F(BrakeStartupTest, EarlyPacketsCannotArmOrConsumeFirstNormalIdentity) {
    wait_until(200); sequence=9;
    EXPECT_EQ(model.receive(command({200,1000000}),kStart+200*kMs).decision,can::BrakeReceiveDecision::NotInitialized);
    ASSERT_TRUE(model.tick(kStart+210*kMs)); ASSERT_TRUE(model.arm_normal_commands(kStart+210*kMs));
    EXPECT_FALSE(model.arm_normal_commands(kStart+210*kMs)); sequence=0;
    EXPECT_EQ(model.receive(command({200,1000000}),kStart+210*kMs).decision,can::BrakeReceiveDecision::SourceBeforeSession);
    sequence=0; EXPECT_EQ(model.receive(command({220,1000000}),kStart+220*kMs).decision,can::BrakeReceiveDecision::Accepted);
    ASSERT_TRUE(model.receiver().last_accepted()); EXPECT_EQ(model.receiver().last_accepted()->message.sequence,0U);
    EXPECT_EQ(tick(220).sequence,21U); EXPECT_EQ(model.fault(),vecu::BrakeFault::None);
}
TEST_F(BrakeStartupTest, ArmNeedsANewValidAcquisitionRatherThanCachedPublication) {
    EXPECT_FALSE(model.arm_normal_commands(kStart)); wait_until(100);
    ASSERT_TRUE(model.tick(kStart+110*kMs,{},simulation::BrakeSensorAction::Hold));
    EXPECT_FALSE(model.arm_normal_commands(kStart+110*kMs)); EXPECT_EQ(model.fault(),vecu::BrakeFault::None);
    ASSERT_TRUE(model.tick(kStart+120*kMs)); EXPECT_TRUE(model.arm_normal_commands(kStart+120*kMs));
}
TEST_F(BrakeStartupTest, ExpiredSensorAtArmLatchesBeforeLateFreshAcquisition) {
    wait_until(100); EXPECT_FALSE(model.arm_normal_commands(kStart+121*kMs));
    EXPECT_EQ(model.fault(),vecu::BrakeFault::SensorUnavailable);
    ASSERT_TRUE(model.tick(kStart+130*kMs)); EXPECT_FALSE(model.arm_normal_commands(kStart+130*kMs));
}
TEST_F(BrakeStartupTest, MissingSensorStillSelectsProtectionDuringStartup) {
    wait_until(100); ASSERT_TRUE(model.tick(kStart+110*kMs,{},simulation::BrakeSensorAction::Invalidate));
    EXPECT_EQ(model.fault(),vecu::BrakeFault::SensorUnavailable); EXPECT_FALSE(model.arm_normal_commands(kStart+110*kMs));
}
TEST_F(BrakeStartupTest, ControlGapCannotBeHiddenByArm) {
    wait_until(100); EXPECT_FALSE(model.arm_normal_commands(kStart+131*kMs));
    EXPECT_EQ(model.fault(),vecu::BrakeFault::ControlDeadline);
}
TEST_F(BrakeStartupTest, WaitingBudgetStartsAtArmAndCannotBeRearmed) {
    wait_until(1000); ASSERT_TRUE(model.arm_normal_commands(kStart+1000*kMs));
    for (int ms=1010;ms<1080;ms+=10) { ASSERT_TRUE(model.tick(kStart+ms*kMs)); EXPECT_EQ(model.fault(),vecu::BrakeFault::None); }
    EXPECT_FALSE(model.arm_normal_commands(kStart+1070*kMs)); ASSERT_TRUE(model.tick(kStart+1080*kMs));
    EXPECT_EQ(model.fault(),vecu::BrakeFault::CommandUnavailable);
}
TEST_F(BrakeStartupTest, NewNonDrivingEpochPreservesPhysicsButNotOldCommandCausality) {
    wait_until(10); ASSERT_TRUE(model.arm_normal_commands(kStart+10*kMs));
    for (int ms=20;ms<=300;ms+=10) drive(ms,1000000);
    const auto physical=model.actual_pressure_pa(); ASSERT_TRUE(model.start_session(2,kStart+300*kMs,ActuatorCommandStartup::NonDriving));
    const auto actual=tick(310); ASSERT_TRUE(actual.pressure_pa); EXPECT_NEAR(*actual.pressure_pa,physical,500.1);
    EXPECT_EQ(actual.sequence,0U); EXPECT_EQ(actual.causal_sequence,0U); EXPECT_EQ(actual.origin,can::BrakeOrigin::NoAcceptedInput);
    EXPECT_FALSE(model.current_sample(kStart+310*kMs)); EXPECT_EQ(model.fault(),vecu::BrakeFault::None);
}
TEST_F(BrakeStartupTest, StartupClockAndInitCannotRegressBehindIngress) {
    wait_until(100); EXPECT_EQ(model.receive(command({110,1000000}),kStart+110*kMs).decision,can::BrakeReceiveDecision::NotInitialized);
    EXPECT_FALSE(model.start_session(2,kStart+109*kMs,ActuatorCommandStartup::NonDriving));
    EXPECT_FALSE(model.arm_normal_commands(kStart+109*kMs)); EXPECT_EQ(model.fault(),vecu::BrakeFault::ClockError);
}
}  // namespace
