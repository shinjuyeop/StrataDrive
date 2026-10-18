#include "normal_drive_readiness.hpp"

#include <gtest/gtest.h>
#include <limits>

namespace {
using namespace stratadrive;
using central::ReadinessBlock;
constexpr std::uint64_t kMs = 1000000, kStart = 1000000000, kNow = kStart + 100*kMs;
constexpr std::array<ReadinessBlock, 7> kSources{
    ReadinessBlock::FrontZone, ReadinessBlock::RearZone, ReadinessBlock::SteeringActual,
    ReadinessBlock::BrakeActual, ReadinessBlock::DriveActual, ReadinessBlock::PowerStatus,
    ReadinessBlock::PowerLimits};

template <typename Message>
void initialize(Message& message) {
    message.epoch = 3; message.sequence = 5; message.source_time_ns = kNow;
    message.local_state = can::ActuatorLocalState::Normal;
    message.origin = can::ActuatorOrigin::NormalPath;
}
central::NormalDriveReadinessInputs ready_inputs() {
    central::NormalDriveReadinessInputs in; in.epoch = 3; in.session_enable_ns = kStart;
    in.front.health.emplace(); in.rear.health.emplace();
    initialize(*in.front.health); initialize(*in.rear.health);
    in.front.health->ready_for_normal = in.rear.health->ready_for_normal = true;
    in.front.steering_actual.emplace(); initialize(*in.front.steering_actual);
    in.front.steering_actual->kind = can::SteeringFrameKind::Actual;
    in.front.steering_actual->angle_rad = 0;
    in.front.brake_actual.emplace(); initialize(*in.front.brake_actual);
    in.front.brake_actual->kind = can::BrakeFrameKind::Actual;
    in.front.brake_actual->pressure_pa = 0;
    in.rear.drive_actual.emplace(); initialize(*in.rear.drive_actual);
    in.rear.drive_actual->kind = can::DriveFrameKind::Actual;
    in.rear.drive_actual->torque_nm = 0;
    const can::BmsQualities usable{can::BmsFieldQuality::Usable, can::BmsFieldQuality::Usable,
                                  can::BmsFieldQuality::NotApplicable};
    in.rear.power_status = can::BmsCurrentSample{can::BmsMessage{}, usable};
    auto& power = in.rear.power_status->message; initialize(power);
    power.kind = can::BmsFrameKind::PowerStatus;
    can::BmsPowerStatus status; status.state = can::BmsPowerState::HvReady;
    status.positive_contactor_closed = status.negative_contactor_closed = true;
    status.precharge_contactor_closed = false; status.condition_bits = 7; status.condition_validity = 31;
    status.hv_bus_voltage_v = 400; status.input_time_ns = kNow - 10*kMs;
    status.input_sequence = 7; power.content = status;
    in.rear.power_limits = can::BmsCurrentSample{can::BmsMessage{}, usable};
    auto& limits = in.rear.power_limits->message; initialize(limits);
    limits.kind = can::BmsFrameKind::PowerLimits;
    limits.content = can::BmsPowerLimits{0, 80000, can::BmsLimitReason::Disabled,
                                       can::BmsLimitReason::Nominal, kNow - 10*kMs};
    return in;
}
template <typename Function>
void mutate_source(central::NormalDriveReadinessInputs& in, ReadinessBlock source, Function mutate) {
    switch (source) {
    case ReadinessBlock::FrontZone: mutate(*in.front.health); break;
    case ReadinessBlock::RearZone: mutate(*in.rear.health); break;
    case ReadinessBlock::SteeringActual: mutate(*in.front.steering_actual); break;
    case ReadinessBlock::BrakeActual: mutate(*in.front.brake_actual); break;
    case ReadinessBlock::DriveActual: mutate(*in.rear.drive_actual); break;
    case ReadinessBlock::PowerStatus: mutate(in.rear.power_status->message); break;
    case ReadinessBlock::PowerLimits: mutate(in.rear.power_limits->message); break;
    default: FAIL() << "not a source";
    }
}
void remove_source(central::NormalDriveReadinessInputs& in, ReadinessBlock source) {
    switch (source) {
    case ReadinessBlock::FrontZone: in.front.health.reset(); break;
    case ReadinessBlock::RearZone: in.rear.health.reset(); break;
    case ReadinessBlock::SteeringActual: in.front.steering_actual.reset(); break;
    case ReadinessBlock::BrakeActual: in.front.brake_actual.reset(); break;
    case ReadinessBlock::DriveActual: in.rear.drive_actual.reset(); break;
    case ReadinessBlock::PowerStatus: in.rear.power_status.reset(); break;
    case ReadinessBlock::PowerLimits: in.rear.power_limits.reset(); break;
    default: FAIL() << "not a source";
    }
}
auto evaluate(const central::NormalDriveReadinessInputs& in) {
    return central::evaluate_normal_drive_readiness(in, kNow);
}
void expect_blocked(const central::NormalDriveReadinessInputs& in, ReadinessBlock source) {
    const auto result = evaluate(in);
    EXPECT_FALSE(result.ready()); EXPECT_TRUE(result.is_blocked(source));
    EXPECT_FALSE(result.oldest_input_time_ns);
}

TEST(NormalDriveReadiness, DefaultAndUninitializedContextFailClosed) {
    EXPECT_FALSE(central::NormalDriveReadiness{}.ready());
    EXPECT_FALSE(evaluate({}).ready());
    auto in = ready_inputs(); in.epoch = 0; expect_blocked(in, ReadinessBlock::Context);
    in = ready_inputs(); in.session_enable_ns = kNow + 1; expect_blocked(in, ReadinessBlock::Context);
}
TEST(NormalDriveReadiness, FreshZeroActualAndZeroChargeLimitAreKnownValues) {
    const auto result = evaluate(ready_inputs());
    EXPECT_TRUE(result.ready()); EXPECT_EQ(result.oldest_input_time_ns, kNow - 10*kMs);
}
TEST(NormalDriveReadiness, NonDrivingInitActualDoesNotRequireAnExistingPermission) {
    auto in = ready_inputs();
    for (const auto source : {ReadinessBlock::SteeringActual, ReadinessBlock::BrakeActual, ReadinessBlock::DriveActual}) {
        mutate_source(in, source, [](auto& m) {
            m.local_state = can::ActuatorLocalState::Init; m.origin = can::ActuatorOrigin::NoAcceptedInput;
        });
    }
    EXPECT_TRUE(evaluate(in).ready());
}
TEST(NormalDriveReadiness, EachMissingSourceBlocksDespiteFreshOtherZoneAndHeartbeat) {
    for (const auto source : kSources) {
        SCOPED_TRACE(static_cast<int>(source)); auto in = ready_inputs();
        remove_source(in, source); expect_blocked(in, source);
    }
}
TEST(NormalDriveReadiness, OldEpochFutureAndPreSessionSourceAreRejectedIndependently) {
    for (const auto source : kSources) {
        SCOPED_TRACE(static_cast<int>(source)); auto in = ready_inputs();
        mutate_source(in, source, [](auto& m) { m.epoch = 2; }); expect_blocked(in, source);
        in = ready_inputs(); mutate_source(in, source, [](auto& m) { m.source_time_ns = kNow + 1; });
        expect_blocked(in, source);
        in = ready_inputs(); mutate_source(in, source, [](auto& m) { m.source_time_ns = kStart - 1; });
        expect_blocked(in, source);
    }
}
TEST(NormalDriveReadiness, SourceAgeBoundaryIsInclusiveAndNextNanosecondBlocks) {
    for (const auto source : kSources) {
        SCOPED_TRACE(static_cast<int>(source)); auto in = ready_inputs();
        const auto age = source == ReadinessBlock::PowerStatus || source == ReadinessBlock::PowerLimits ? 50*kMs : 30*kMs;
        mutate_source(in, source, [age](auto& m) { m.source_time_ns = kNow - age; });
        if (source == ReadinessBlock::PowerStatus) std::get<can::BmsPowerStatus>(in.rear.power_status->message.content).input_time_ns = kNow - age;
        if (source == ReadinessBlock::PowerLimits) std::get<can::BmsPowerLimits>(in.rear.power_limits->message.content).input_time_ns = kNow - age;
        EXPECT_TRUE(evaluate(in).ready());
        mutate_source(in, source, [](auto& m) { --m.source_time_ns; }); expect_blocked(in, source);
    }
}
TEST(NormalDriveReadiness, FreshRepublicationCannotRefreshOldDependencies) {
    for (const bool power : {false, true}) {
        auto in = ready_inputs();
        auto& time = power ? std::get<can::BmsPowerStatus>(in.rear.power_status->message.content).input_time_ns :
                             std::get<can::BmsPowerLimits>(in.rear.power_limits->message.content).input_time_ns;
        time = kNow - 70*kMs;
        const auto result = evaluate(in); EXPECT_TRUE(result.ready()); EXPECT_EQ(result.oldest_input_time_ns, time);
        --time; expect_blocked(in, power ? ReadinessBlock::PowerStatus : ReadinessBlock::PowerLimits);
    }
}
TEST(NormalDriveReadiness, InvalidDependencyOrderAndFutureDependencyBlock) {
    for (const auto time : {kNow + 1, kStart - 1}) {
        auto in = ready_inputs();
        std::get<can::BmsPowerStatus>(in.rear.power_status->message.content).input_time_ns = time;
        expect_blocked(in, ReadinessBlock::PowerStatus);
        in = ready_inputs(); std::get<can::BmsPowerLimits>(in.rear.power_limits->message.content).input_time_ns = time;
        expect_blocked(in, ReadinessBlock::PowerLimits);
    }
    auto in = ready_inputs(); in.rear.power_status->message.source_time_ns = kNow - 20*kMs;
    expect_blocked(in, ReadinessBlock::PowerStatus);
    in = ready_inputs(); in.rear.power_limits->message.source_time_ns = kNow - 20*kMs;
    expect_blocked(in, ReadinessBlock::PowerLimits);
}
TEST(NormalDriveReadiness, FaultAndUnreviewedDegradedModesBlockEverySource) {
    for (const auto source : kSources) {
        SCOPED_TRACE(static_cast<int>(source)); auto in = ready_inputs();
        mutate_source(in, source, [](auto& m) { m.local_state = can::ActuatorLocalState::FailSafe; });
        expect_blocked(in, source);
        in = ready_inputs(); mutate_source(in, source, [](auto& m) { m.local_state = can::ActuatorLocalState::Degraded; });
        expect_blocked(in, source);
        in = ready_inputs(); mutate_source(in, source, [](auto& m) { m.origin = can::ActuatorOrigin::LocalProtection; });
        expect_blocked(in, source);
    }
}
TEST(NormalDriveReadiness, EachZoneMustExplicitlyReportReadiness) {
    auto in = ready_inputs(); in.front.health->ready_for_normal = false; expect_blocked(in, ReadinessBlock::FrontZone);
    in = ready_inputs(); in.rear.health->ready_for_normal = false; expect_blocked(in, ReadinessBlock::RearZone);
    in = ready_inputs(); in.rear.health->local_state = can::ActuatorLocalState::Init; expect_blocked(in, ReadinessBlock::RearZone);
}
TEST(NormalDriveReadiness, UnknownOrNonFiniteActualIsNotKnownZero) {
    for (const auto value : {std::optional<double>{}, std::optional<double>{std::numeric_limits<double>::quiet_NaN()},
                             std::optional<double>{std::numeric_limits<double>::infinity()}}) {
        auto in = ready_inputs(); in.front.steering_actual->angle_rad = value; expect_blocked(in, ReadinessBlock::SteeringActual);
        in = ready_inputs(); in.front.brake_actual->pressure_pa = value; expect_blocked(in, ReadinessBlock::BrakeActual);
        in = ready_inputs(); in.rear.drive_actual->torque_nm = value; expect_blocked(in, ReadinessBlock::DriveActual);
    }
}
TEST(NormalDriveReadiness, CommandEchoAndWrongBmsKindCannotStandInForStatus) {
    auto in = ready_inputs(); in.front.steering_actual->kind = can::SteeringFrameKind::Command; expect_blocked(in, ReadinessBlock::SteeringActual);
    in = ready_inputs(); in.front.brake_actual->kind = can::BrakeFrameKind::Command; expect_blocked(in, ReadinessBlock::BrakeActual);
    in = ready_inputs(); in.rear.drive_actual->kind = can::DriveFrameKind::Command; expect_blocked(in, ReadinessBlock::DriveActual);
    in = ready_inputs(); in.rear.power_status->message.kind = can::BmsFrameKind::PowerLimits; expect_blocked(in, ReadinessBlock::PowerStatus);
    in = ready_inputs(); in.rear.power_limits->message.kind = can::BmsFrameKind::DriveBatteryLimits; expect_blocked(in, ReadinessBlock::PowerLimits);
    in = ready_inputs(); in.rear.power_status->message.content = can::BmsPowerLimits{}; expect_blocked(in, ReadinessBlock::PowerStatus);
}
TEST(NormalDriveReadiness, HvReadyAloneCannotOverrideChargingUnknownContactsOrFault) {
    for (const auto bits : {std::uint8_t{15}, std::uint8_t{23}, std::uint8_t{6}}) {
        auto in = ready_inputs(); std::get<can::BmsPowerStatus>(in.rear.power_status->message.content).condition_bits = bits;
        expect_blocked(in, ReadinessBlock::PowerStatus);
    }
    auto in = ready_inputs(); auto& status = std::get<can::BmsPowerStatus>(in.rear.power_status->message.content);
    status.positive_contactor_closed.reset(); expect_blocked(in, ReadinessBlock::PowerStatus);
    in = ready_inputs(); std::get<can::BmsPowerStatus>(in.rear.power_status->message.content).precharge_contactor_closed = true;
    expect_blocked(in, ReadinessBlock::PowerStatus);
    in = ready_inputs(); std::get<can::BmsPowerStatus>(in.rear.power_status->message.content).condition_validity = 15;
    expect_blocked(in, ReadinessBlock::PowerStatus);
    in = ready_inputs(); std::get<can::BmsPowerStatus>(in.rear.power_status->message.content).hv_bus_voltage_v = 0;
    expect_blocked(in, ReadinessBlock::PowerStatus);
}
TEST(NormalDriveReadiness, BothBmsLimitDirectionsAndPowerStatusGroupsMustBeUsable) {
    for (std::size_t group = 0; group < 2; ++group) {
        auto in = ready_inputs(); in.rear.power_status->quality[group] = can::BmsFieldQuality::Stale;
        expect_blocked(in, ReadinessBlock::PowerStatus);
        in = ready_inputs(); in.rear.power_limits->quality[group] = can::BmsFieldQuality::Unavailable;
        expect_blocked(in, ReadinessBlock::PowerLimits);
    }
    auto in = ready_inputs(); std::get<can::BmsPowerLimits>(in.rear.power_limits->message.content).charge_power_w.reset();
    expect_blocked(in, ReadinessBlock::PowerLimits);
    in = ready_inputs(); std::get<can::BmsPowerLimits>(in.rear.power_limits->message.content).discharge_power_w = -1;
    expect_blocked(in, ReadinessBlock::PowerLimits);
}
TEST(NormalDriveReadiness, AllBlockersAreVisibleAndOldestDependencyIncludesBothZones) {
    auto in = ready_inputs(); in.front.health->source_time_ns = kNow - 25*kMs;
    in.rear.drive_actual->source_time_ns = kNow - 30*kMs;
    const auto result = evaluate(in); EXPECT_TRUE(result.ready()); EXPECT_EQ(result.oldest_input_time_ns, kNow - 30*kMs);
    in.front.steering_actual.reset(); in.rear.power_status.reset();
    const auto blocked = evaluate(in);
    EXPECT_TRUE(blocked.is_blocked(ReadinessBlock::SteeringActual));
    EXPECT_TRUE(blocked.is_blocked(ReadinessBlock::PowerStatus));
    EXPECT_FALSE(blocked.is_blocked(ReadinessBlock::RearZone)); EXPECT_FALSE(blocked.oldest_input_time_ns);
}
TEST(NormalDriveReadiness, InvalidTimingCannotSilentlyWidenExistingBudgets) {
    for (const bool zero : {false, true}) {
        central::ReadinessTiming timing; timing.zone_source_age_ns = zero ? 0 : 30000001;
        EXPECT_FALSE(central::evaluate_normal_drive_readiness(ready_inputs(), kNow, timing).ready());
        timing = {}; timing.actual_source_age_ns = zero ? 0 : 30000001;
        EXPECT_FALSE(central::evaluate_normal_drive_readiness(ready_inputs(), kNow, timing).ready());
        timing = {}; timing.bms_source_age_ns = zero ? 0 : 50000001;
        EXPECT_FALSE(central::evaluate_normal_drive_readiness(ready_inputs(), kNow, timing).ready());
        timing = {}; timing.bms_dependency_age_ns = zero ? 0 : 70000001;
        EXPECT_FALSE(central::evaluate_normal_drive_readiness(ready_inputs(), kNow, timing).ready());
    }
}
}  // namespace
