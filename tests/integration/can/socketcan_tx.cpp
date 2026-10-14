#include "actuator_socketcan.hpp"

#include <exception>
#include <iostream>

#include "socketcan_support.hpp"

#include <chrono>
#include <string>
#include <thread>

namespace {
using namespace stratadrive;

double fixture_value(const can::SteeringMessage& message) { return *message.angle_rad; }
double fixture_value(const can::BrakeMessage& message) { return *message.pressure_pa; }
double fixture_value(const can::DriveMessage& message) { return *message.torque_nm; }
void set_fixture_value(can::SteeringMessage& message, std::optional<double> value) { message.angle_rad = value; }
void set_fixture_value(can::BrakeMessage& message, std::optional<double> value) { message.pressure_pa = value; }
void set_fixture_value(can::DriveMessage& message, std::optional<double> value) { message.torque_nm = value; }
template <typename Message>
void refresh_feedback(Message&) {}
void refresh_feedback(can::DriveMessage& message) {
    if (message.kind == can::DriveFrameKind::Actual) {
        message.wheel_speed = can::DriveWheelSpeed{12.34, message.source_time_ns};
        message.regen_capability = can::DriveRegenCapability{200, message.source_time_ns, message.source_time_ns};
        message.regen_limit_reason = can::DriveRegenLimitReason::ChargeAcceptanceLimited;
    }
}
}  // namespace

// 기존 wire/E2E/transport 회귀 검사. Application fixture와 별도로 유지한다.
void brake_wire_fixture(const char* interface, bool actual, std::uint32_t epoch) {
    using namespace stratadrive;
    const auto kind = actual ? can::BrakeFrameKind::Actual : can::BrakeFrameKind::Command;
    socketcan::Endpoint endpoint(interface);
    std::cout << std::unitbuf << "TX_READY\n";
    fixture::await_start();
    can::BrakeTxState tx{kind};
    can::BrakeMessage message;
    message.kind = kind;
    message.epoch = epoch;
    message.pressure_pa = actual ? 1500000.0 : 2000000.0;
    message.local_state = can::BrakeLocalState::Normal;
    message.origin = can::BrakeOrigin::NormalPath;
    const auto start = std::chrono::steady_clock::now();
    const auto at = [&](int ms) { std::this_thread::sleep_until(start + std::chrono::milliseconds(ms)); };
    const auto encode = [&]() {
        message.source_time_ns = socketcan::monotonic_time_ns();
        const auto frame = can::encode_brake_frame(message, tx);
        if (!frame) throw std::runtime_error("Brake fixture encode failed");
        ++message.sequence;
        return *frame;
    };
    const auto first = encode();
    endpoint.send(socketcan::to_socketcan(first));
    at(10);
    endpoint.send(socketcan::to_socketcan(first));
    at(20);
    auto corrupt = encode();
    corrupt.payload[0] ^= 1;
    endpoint.send(socketcan::to_socketcan(corrupt));
    at(30);
    message.pressure_pa = 0;
    endpoint.send(socketcan::to_socketcan(encode()));
    at(40);
    message.pressure_pa.reset();
    message.local_state = can::BrakeLocalState::Init;
    message.origin = can::BrakeOrigin::NoAcceptedInput;
    endpoint.send(socketcan::to_socketcan(encode()));
    at(50);
    auto wide = socketcan::to_socketcan(first);
    wide.payload_length = 64;
    endpoint.send(wide);
    at(60);
    message.pressure_pa = actual ? 1500000.0 : 2000000.0;
    message.local_state = can::BrakeLocalState::Normal;
    message.origin = can::BrakeOrigin::NormalPath;
    endpoint.send(socketcan::to_socketcan(encode()));
    at(70);
    auto short_frame = socketcan::to_socketcan(first);
    short_frame.payload_length = 16;
    endpoint.send(short_frame);
    std::cout << "TX wire_frames=8\n";
}

template <typename Message, typename TxState, typename Encode>
void application_fixture(const char* interface, const std::string& scenario, Message message,
                         TxState& tx, Encode encode_frame, bool pressure, bool drive = false) {
    using namespace stratadrive;
    socketcan::Endpoint endpoint(interface);
    std::cout << std::unitbuf << "TX_READY\n";
    fixture::await_start();
    if (scenario == "silent") return;

    const auto start = std::chrono::steady_clock::now();
    const auto at = [&](int ms) { std::this_thread::sleep_until(start + std::chrono::milliseconds(ms)); };
    const auto send = [&](const socketcan::Frame& frame, const char* label) {
        endpoint.send(frame);
        std::cout << "TX label=" << label << " at_ns=" << socketcan::monotonic_time_ns() << '\n';
    };
    const auto publish = [&](std::uint32_t sequence) {
        message.sequence = sequence;
        message.source_time_ns = socketcan::monotonic_time_ns();
        refresh_feedback(message);
        const auto frame = encode_frame(message, tx);
        if (!frame) throw std::runtime_error("fixture encode failed");
        return *frame;
    };
    if (scenario == "restart") { --message.epoch; tx.protection.counter = 200; }
    const auto first = publish(0);
    if (scenario == "restart") ++message.epoch;
    const auto first_source_ns = message.source_time_ns;
    const auto initial_value = fixture_value(message);
    send(socketcan::to_socketcan(first), "first");
    if (scenario == "restart") {
        at(10); e2e::p05_protect_init(tx.protection); send(socketcan::to_socketcan(publish(0)), "new_epoch_first");
        at(40); --message.epoch; const auto previous = tx.protection; tx.protection.counter = 200;
        send(socketcan::to_socketcan(publish(1)), "old_epoch_counter"); tx.protection = previous; ++message.epoch;
        at(50); send(socketcan::to_socketcan(publish(1)), "new_epoch_next");
        at(190); send(socketcan::to_socketcan(publish(2)), "late_after_timeout");
    } else if (scenario == "normal") {
        for (std::uint32_t sequence = 1; sequence < 5; ++sequence) {
            at(static_cast<int>(sequence) * 10);
            send(socketcan::to_socketcan(publish(sequence)), "normal");
        }
    } else if (scenario == "app-overflow" || scenario == "kernel-overflow") {
        at(20);
        const int burst = scenario == "kernel-overflow" ? 2048 : 64;
        for (int index = 0; index < burst; ++index) endpoint.send(socketcan::to_socketcan(first));
        std::cout << "TX label=overflow_burst at_ns=" << socketcan::monotonic_time_ns() << '\n';
        at(50); send(socketcan::to_socketcan(publish(1)), "fresh_after_overflow");
        at(70); send(socketcan::to_socketcan(publish(2)), "late_after_overflow");
    } else if (scenario == "flood") {
        // 처리 budget 8보다 많은 반복 frame을 여러 번 burst한다. last-valid를 갱신하면 안 된다.
        for (int ms = 5; ms <= 120; ms += 5) {
            at(ms);
            for (int index = 0; index < 32; ++index) endpoint.send(socketcan::to_socketcan(first));
        }
        std::cout << "TX label=flood_end at_ns=" << socketcan::monotonic_time_ns() << '\n';
    } else {
        at(10);
        send(socketcan::to_socketcan(first), "duplicate");
        at(20);
        auto corrupt = publish(1);
        corrupt.payload[0] ^= 1;
        send(socketcan::to_socketcan(corrupt), "corrupt");
        at(40);
        message.sequence = 1;
        message.source_time_ns = first_source_ns;
        const auto stale_frame = encode_frame(message, tx);
        if (!stale_frame) throw std::runtime_error("stale fixture encode failed");
        send(socketcan::to_socketcan(*stale_frame), "stale");
        at(50);
        send(socketcan::to_socketcan(publish(1)), "fresh");
        if (pressure || drive) {
            at(55);
            set_fixture_value(message, 0.0);
            send(socketcan::to_socketcan(publish(2)), drive ? "zero_torque" : "zero_pressure");
            set_fixture_value(message, initial_value);
        }
        at(60);
        auto short_frame = socketcan::to_socketcan(publish(2));
        short_frame.payload_length = 16;
        send(short_frame, "short");
        at(65);
        auto wide_frame = socketcan::to_socketcan(publish(2));
        wide_frame.payload_length = wide_frame.payload_length == 64 ? 48 : 64;
        send(wide_frame, "wide");
        at(70);
        auto extended = socketcan::to_socketcan(publish(2));
        extended.can_id |= 0x80000000U;
        send(extended, "extended");
        at(75);
        auto brs = socketcan::to_socketcan(publish(2));
        brs.fd_flags = 1;
        send(brs, "brs");
        at(80);
        auto classic = socketcan::to_socketcan(first);
        classic.is_fd = false;
        classic.fd_flags = 0;
        classic.payload_length = 2;
        send(classic, "classic");
        at(90);
        send(socketcan::to_socketcan(publish(1)), "cached_sequence");
        if (pressure || drive) {
            at(95);
            set_fixture_value(message, drive ? 600.0 : 3000000.0);
            send(socketcan::to_socketcan(publish(3)), drive ? "torque_out_of_range" : "pressure_out_of_range");
            at(100);
            set_fixture_value(message, std::nullopt);
            send(socketcan::to_socketcan(publish(3)), "unavailable");
            at(105);
            set_fixture_value(message, initial_value);
            message.origin = can::ActuatorOrigin::NoAcceptedInput;
            send(socketcan::to_socketcan(publish(3)), "invalid_mode");
            message.origin = can::ActuatorOrigin::NormalPath;
            at(110);
            const auto original_epoch = message.epoch;
            message.epoch = original_epoch == 1 ? 2 : 1;
            send(socketcan::to_socketcan(publish(3)), "other_epoch");
            message.epoch = original_epoch;
        }
        at(160);
        send(socketcan::to_socketcan(publish(2)), "late_after_timeout");
    }
}

void drive_feedback_fixture(const char* interface, std::uint32_t epoch) {
    using namespace stratadrive;
    socketcan::Endpoint endpoint(interface);
    std::cout << std::unitbuf << "TX_READY\n";
    fixture::await_start();
    const auto start = std::chrono::steady_clock::now();
    can::DriveTxState tx{can::DriveFrameKind::Actual};
    can::DriveMessage message;
    message.kind = tx.kind;
    message.epoch = epoch;
    message.torque_nm = -150;
    message.local_state = can::ActuatorLocalState::Normal;
    message.origin = can::ActuatorOrigin::NormalPath;
    message.regen_limit_reason = can::DriveRegenLimitReason::ChargeAcceptanceLimited;
    std::uint64_t cached_time = 0;
    for (unsigned int index = 0; index < 7; ++index) {
        const int at_ms[] = {0, 10, 20, 50, 60, 70, 80};
        std::this_thread::sleep_until(start + std::chrono::milliseconds(at_ms[index]));
        message.sequence = index;
        message.source_time_ns = socketcan::monotonic_time_ns();
        message.wheel_speed = can::DriveWheelSpeed{12.34, message.source_time_ns};
        if (index == 0 || index == 1 || index >= 5) {
            const auto limit = index == 1 ? 0.0 : 200.0;
            message.regen_capability = can::DriveRegenCapability{limit, message.source_time_ns, message.source_time_ns};
            message.regen_limit_reason = can::DriveRegenLimitReason::ChargeAcceptanceLimited;
            if (index == 1) cached_time = message.source_time_ns;
        } else if (index == 2) {
            message.regen_capability.reset();
            message.regen_limit_reason = can::DriveRegenLimitReason::InputsInvalid;
        } else {
            message.regen_capability = can::DriveRegenCapability{
                0, index == 3 ? cached_time : message.source_time_ns, cached_time};
            message.regen_limit_reason = can::DriveRegenLimitReason::ChargeAcceptanceLimited;
        }
        if (index == 6) message.torque_nm.reset();
        const auto frame = can::encode_drive_frame(message, tx);
        if (!frame) throw std::runtime_error("Drive feedback fixture encode failed");
        endpoint.send(socketcan::to_socketcan(*frame));
        std::cout << "TX feedback_seq=" << index << " at_ns=" << message.source_time_ns << '\n';
    }
}

void bms_fixture(const char* interface, can::BmsFrameKind kind,
                 const std::string& scenario, std::uint32_t epoch) {
    socketcan::Endpoint endpoint(interface);
    std::cout << std::unitbuf << "TX_READY\n";
    const auto plan = fixture::await_bms_start();
    const auto at = [&](unsigned int ms) {
        const auto deadline = plan.enable_ns + ms*fixture::kMs;
        const auto now = socketcan::monotonic_time_ns();
        if (deadline > now) std::this_thread::sleep_for(std::chrono::nanoseconds(deadline - now));
    };
    can::BmsTxState tx{kind};
    const auto sample = [&](std::uint32_t sequence, std::uint32_t parent_sequence) {
        auto message = fixture::bms_message(kind, {epoch, sequence, socketcan::monotonic_time_ns()},
                                            plan.parent(epoch, parent_sequence));
        if (scenario == "forward") std::get<can::BmsPowerLimits>(message.content).input_time_ns -= 10*fixture::kMs;
        return message;
    };
    const auto send_frame = [&](const can::BmsFrame& frame, const char* label) {
        endpoint.send(socketcan::to_socketcan(frame));
        const auto decoded = can::decode_bms_frame(frame);
        const auto* limits = decoded ? std::get_if<can::BmsPowerLimits>(&decoded->content) : nullptr;
        std::cout << "EV_TX label=" << label << " at_ns=" << socketcan::monotonic_time_ns()
                  << " id=" << frame.can_id << " length=" << static_cast<unsigned int>(frame.payload_length)
                  << " seq=" << (decoded ? decoded->sequence : 0)
                  << " source_ns=" << (decoded ? decoded->source_time_ns : 0)
                  << " causal_seq=" << (decoded ? decoded->causal_sequence : 0)
                  << " input_ns=" << (limits ? limits->input_time_ns : 0)
                  << " counter=" << static_cast<unsigned int>(frame.payload[31]) << '\n';
    };
    const auto publish = [&](const can::BmsMessage& message, const char* label) {
        const auto frame = can::encode_bms_frame(message, tx);
        if (!frame) throw std::runtime_error("EV fixture encode failed");
        send_frame(*frame, label);
        return *frame;
    };
    at(0);
    if (scenario == "silent") return;
    if (scenario == "forward") at(20);
    auto initial = sample(0, 7);
    if (scenario == "restart") { --initial.epoch; tx.protection.counter = 200; }
    if (scenario == "cached") {
        if (auto* value = std::get_if<can::BmsPowerLimits>(&initial.content)) value->input_time_ns = plan.enable_ns;
        else std::get<can::BmsPowerStatus>(initial.content).input_time_ns = plan.enable_ns;
    } else if (scenario == "observation") std::get<can::BmsBatteryState>(initial.content).soc->source_time_ns = plan.enable_ns;
    const auto first = publish(initial, "first");
    const bool observation = kind == can::BmsFrameKind::BatteryState;
    if (scenario == "restart") {
        at(10); e2e::p05_protect_init(tx.protection); publish(sample(0, 7), "new_epoch_first");
        at(40); auto old = sample(1, 7); --old.epoch; const auto previous = tx.protection; tx.protection.counter = 200;
        publish(old, "old_epoch_counter"); tx.protection = previous;
        at(50); publish(sample(1, 8), "new_epoch_next");
        at(190); publish(sample(2, 9), "late_after_timeout");
    } else if (scenario == "normal" || scenario == "forward") {
        for (std::uint32_t index = 1; index < 5; ++index) {
            at(index*fixture::bms_period_ms(kind) + (scenario == "forward" ? 20 : 0));
            publish(sample(index, 7 + index), "normal");
        }
    } else if (scenario == "app-overflow" || scenario == "kernel-overflow") {
        at(20);
        const int burst = scenario == "kernel-overflow" ? 2048 : 64;
        for (int index = 0; index < burst; ++index) endpoint.send(socketcan::to_socketcan(first));
        std::cout << "EV_TX label=overflow_burst at_ns=" << socketcan::monotonic_time_ns() << '\n';
        at(50); publish(sample(1, 8), "fresh_after_overflow");
        at(70); publish(sample(2, 9), "late_after_overflow");
    } else if (scenario == "flood") {
        const unsigned int last_ms = observation ? 340 : 120;
        for (unsigned int ms = 5; ms <= last_ms; ms += 5) {
            at(ms);
            for (int index = 0; index < 32; ++index) endpoint.send(socketcan::to_socketcan(first));
        }
        std::cout << "EV_TX label=flood_end at_ns=" << socketcan::monotonic_time_ns() << '\n';
    } else if (scenario == "faults") {
        at(10); send_frame(first, "duplicate");
        at(20); auto corrupt = can::encode_bms_frame(sample(1, 7), tx).value();
        corrupt.payload[32] ^= 1; send_frame(corrupt, "corrupt_extension");
        const auto malformed = [&](unsigned int ms, const char* label, unsigned int fault) {
            at(ms); auto frame = socketcan::to_socketcan(can::encode_bms_frame(sample(1, 7), tx).value());
            if (fault == 0) frame.payload_length = 16;
            else if (fault == 1) frame.payload_length = frame.payload_length == 64 ? 48 : 64;
            else if (fault == 2) frame.can_id |= 0x80000000U;
            else if (fault == 3) frame.fd_flags = 1;
            else { frame.is_fd = false; frame.fd_flags = 0; frame.payload_length = 2; }
            endpoint.send(frame);
            std::cout << "EV_TX label=" << label << " at_ns=" << socketcan::monotonic_time_ns() << '\n';
        };
        malformed(30, "short", 0); malformed(35, "wide", 1); malformed(40, "extended", 2);
        malformed(45, "brs", 3); malformed(50, "classic", 4);
        at(55); auto wrong_epoch = sample(1, 7); wrong_epoch.epoch = epoch + 1;
        publish(wrong_epoch, "wrong_epoch");
        const unsigned int stale_ms = observation ? 160 : 60;
        at(stale_ms);
        // Every dependency must remain <= envelope source even in an old fixture.
        const auto stale = fixture::bms_message(kind, {epoch, 1, plan.enable_ns}, plan.parent(epoch, 7));
        publish(stale, "stale");
        at(stale_ms + 5); publish(sample(1, 8), "fresh");
        at(stale_ms + 10); publish(sample(1, 8), "cached_sequence");
        at(stale_ms + 15); auto canonical = can::encode_bms_frame(sample(2, 8), tx).value();
        canonical.payload[26] = 1;
        const auto crc = can::bms_frame_crc(canonical).value();
        canonical.payload[29] = static_cast<std::uint8_t>(crc); canonical.payload[30] = static_cast<std::uint8_t>(crc >> 8U);
        send_frame(canonical, "resealed_reserved");
        at(stale_ms + 30); auto unknown = sample(2, 8); fixture::clear_bms_content(unknown);
        publish(unknown, "unknown");
        at(observation ? 600 : 220); publish(sample(3, 9), "late_after_timeout");
    } else if (scenario == "partial") {
        for (std::uint32_t index = 1; index < 5; ++index) {
            at(index*20); auto message = sample(index, 7);
            auto& value = std::get<can::BmsPowerLimits>(message.content);
            if (index == 1) { value.charge_power_w = 0; value.charge_reason = can::BmsLimitReason::Disabled; }
            else { value.charge_power_w.reset(); value.charge_reason = can::BmsLimitReason::InputsInvalid; }
            publish(message, index == 1 ? "zero" : "charge_unknown");
        }
        at(130); publish(sample(6, 7), "late_after_timeout");
    } else if (scenario == "cached") {
        for (std::uint32_t index = 1; index < 6; ++index) {
            at(index*20 + (kind == can::BmsFrameKind::PowerStatus && index > 3 ? 10 : 0));
            auto message = sample(index, 7);
            if (auto* value = std::get_if<can::BmsPowerLimits>(&message.content)) {
                value->input_time_ns = plan.enable_ns; message.causal_sequence = 0;
            } else {
                auto& power = std::get<can::BmsPowerStatus>(message.content);
                power.input_time_ns = plan.enable_ns; power.input_sequence = 0;
            }
            publish(message, "cached_input");
        }
    } else if (scenario == "observation") {
        for (std::uint32_t index = 1; index < 6; ++index) {
            at(index*100); auto message = sample(index, 7);
            auto& value = std::get<can::BmsBatteryState>(message.content);
            value.soc->source_time_ns = plan.enable_ns;
            value.temperature.reset();
            publish(message, "partial_cached_soc");
        }
    } else if (scenario == "expiry") {
        at(45); publish(fixture::bms_message(kind, {epoch, 1, plan.enable_ns + 30*fixture::kMs},
                                            plan.parent(epoch, 7)), "expired_parent");
        at(65); publish(sample(2, 7), "renewed_same_parent");
        at(130); publish(sample(3, 9), "late_after_timeout");
    } else if (scenario == "parent") {
        at(10); publish(sample(1, 900), "missing_parent");
        at(20); auto mismatch = sample(1, 7);
        if (auto* value = std::get_if<can::BmsPowerRequest>(&mismatch.content)) value->parent_source_time_ns += fixture::kMs;
        else std::get<can::BmsDriveGrant>(mismatch.content).expires_at_ns += fixture::kMs;
        publish(mismatch, "mismatched_parent");
        at(30); publish(sample(1, 8), "fresh_parent");
        at(40); publish(sample(2, 7), "rollback_parent");
        at(60); auto extended = sample(2, 8);
        if (auto* value = std::get_if<can::BmsPowerRequest>(&extended.content)) value->expires_at_ns += fixture::kMs;
        else std::get<can::BmsDriveGrant>(extended.content).expires_at_ns += fixture::kMs;
        publish(extended, "deadline_extension");
        at(70); auto safe = sample(2, 900);
        safe.causal_sequence = 0; safe.origin = can::ActuatorOrigin::LocalProtection;
        if (auto* value = std::get_if<can::BmsPowerRequest>(&safe.content)) {
            value->action = can::BmsPowerAction::Shutdown; value->parent_source_time_ns = 0;
        } else std::get<can::BmsDriveGrant>(safe.content).permission = can::BmsDrivePermission::Inhibit;
        publish(safe, "explicit_non_driving");
        at(200); publish(sample(3, 9), "late_after_timeout");
    } else if (scenario == "rejoin") {
        at(100); auto unauthorized = sample(1, 8); unauthorized.epoch = epoch + 1;
        publish(unauthorized, "unauthorized_epoch");
        at(160); publish(sample(1, 7), "late_old_epoch");
        at(200); epoch += 1; e2e::p05_protect_init(tx.protection); publish(sample(0, 7), "trusted_rejoin");
        at(210); auto old = sample(1, 7); old.epoch -= 1; publish(old, "old_epoch");
        at(220); publish(sample(1, 8), "fresh_after_rejoin");
    } else throw std::invalid_argument("unknown EV fixture scenario");
}

int main(int argc, char** argv) {
    try {
        using namespace stratadrive;
        if (argc != 5) {
            throw std::invalid_argument("usage: actuator_socketcan_tx IFACE STREAM EPOCH SCENARIO; actuator or bms-request|bms-power|bms-limits|bms-battery|drive-limits|drive-permission (harness stdin required)");
        }
        const auto epoch = fixture::positive_number(argv[3]);
        const std::string scenario = argv[4];
        const std::string stream = argv[2];
        if (const auto ev_kind = fixture::bms_kind(stream)) {
            bms_fixture(argv[1], *ev_kind, scenario, epoch);
            return 0;
        }
        const bool brake = stream == "brake-cmd" || stream == "brake-actual";
        const bool drive = stream == "drive-cmd" || stream == "drive-actual";
        if (stream == "drive-actual" && scenario == "feedback") {
            drive_feedback_fixture(argv[1], epoch);
            return 0;
        }
        if (brake && scenario == "wire") {
            brake_wire_fixture(argv[1], stream == "brake-actual", epoch);
            return 0;
        }
        if (scenario != "normal" && scenario != "faults" && scenario != "silent" && scenario != "flood" &&
            scenario != "app-overflow" && scenario != "kernel-overflow") {
            if (scenario != "restart") throw std::invalid_argument("unknown fixture scenario");
        }
        if (drive) {
            const auto kind = stream == "drive-actual" ? can::DriveFrameKind::Actual : can::DriveFrameKind::Command;
            can::DriveTxState tx{kind};
            can::DriveMessage message;
            message.kind = kind;
            message.epoch = epoch;
            message.torque_nm = kind == can::DriveFrameKind::Command ? -200.0 : -150.0;
            message.local_state = can::ActuatorLocalState::Normal;
            message.origin = can::ActuatorOrigin::NormalPath;
            application_fixture(argv[1], scenario, message, tx,
                [](const auto& sample, auto& state) { return can::encode_drive_frame(sample, state); }, false, true);
        } else if (brake) {
            const auto kind = stream == "brake-actual" ? can::BrakeFrameKind::Actual : can::BrakeFrameKind::Command;
            can::BrakeTxState tx{kind};
            can::BrakeMessage message;
            message.kind = kind;
            message.epoch = epoch;
            message.pressure_pa = kind == can::BrakeFrameKind::Command ? 2000000.0 : 1500000.0;
            message.local_state = can::BrakeLocalState::Normal;
            message.origin = can::BrakeOrigin::NormalPath;
            application_fixture(argv[1], scenario, message, tx,
                [](const auto& sample, auto& state) { return can::encode_brake_frame(sample, state); }, true);
        } else {
            const auto kind = fixture::kind(stream);
            can::SteeringTxState tx{kind};
            can::SteeringMessage message;
            message.kind = kind;
            message.epoch = epoch;
            // Actual은 독립 sample이며 actuator model/Command echo가 아니다.
            message.angle_rad = kind == can::SteeringFrameKind::Command ? 0.2 : 0.15;
            message.local_state = can::SteeringLocalState::Normal;
            message.origin = can::SteeringOrigin::NormalPath;
            application_fixture(argv[1], scenario, message, tx,
                [](const auto& sample, auto& state) { return can::encode_steering_frame(sample, state); }, false);
        }
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
    return 0;
}
