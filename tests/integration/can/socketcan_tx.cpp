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
    const auto first = publish(0);
    const auto first_source_ns = message.source_time_ns;
    const auto initial_value = fixture_value(message);
    send(socketcan::to_socketcan(first), "first");
    if (scenario == "normal") {
        for (std::uint32_t sequence = 1; sequence < 5; ++sequence) {
            at(static_cast<int>(sequence) * 10);
            send(socketcan::to_socketcan(publish(sequence)), "normal");
        }
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

int main(int argc, char** argv) {
    try {
        using namespace stratadrive;
        if (argc != 5) {
            throw std::invalid_argument("usage: actuator_socketcan_tx IFACE cmd|actual|brake-cmd|brake-actual|drive-cmd|drive-actual EPOCH normal|faults|silent|flood|wire|feedback");
        }
        const auto epoch = fixture::positive_number(argv[3]);
        const std::string scenario = argv[4];
        const std::string stream = argv[2];
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
        if (scenario != "normal" && scenario != "faults" && scenario != "silent" && scenario != "flood") {
            throw std::invalid_argument("unknown fixture scenario");
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
