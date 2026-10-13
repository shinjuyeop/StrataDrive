#include "actuator_socketcan.hpp"

#include <exception>
#include <iostream>

#include "socketcan_support.hpp"

#include <chrono>
#include <thread>

namespace {
template <typename Message>
void trace_feedback(const std::optional<Message>&) {}
void trace_feedback(const std::optional<stratadrive::can::DriveMessage>& current) {
    const bool cap = current && current->regen_capability;
    std::cout << " regen_valid=" << cap
              << " regen_limit_nm=" << (cap ? current->regen_capability->torque_limit_nm : 0)
              << " cap_source_ns=" << (cap ? current->regen_capability->source_time_ns : 0)
              << " cap_input_ns=" << (cap ? current->regen_capability->input_time_ns : 0)
              << " speed_valid=" << (current && current->wheel_speed);
}
}  // namespace

// 기존 wire 회귀 검사 경로다. WIRE_VALID와 application 수용을 구분한다.
void brake_wire_fixture(const char* interface, bool actual, std::uint32_t epoch,
                        std::chrono::milliseconds duration) {
    using namespace stratadrive;
    const auto kind = actual ? can::BrakeFrameKind::Actual : can::BrakeFrameKind::Command;
    socketcan::Endpoint endpoint(interface, static_cast<std::uint16_t>(kind));
    can::BrakeRxState rx{kind};
    std::cout << std::unitbuf << "RX_READY\n";
    fixture::await_start();
    const auto enable_ns = socketcan::monotonic_time_ns();
    std::cout << "SESSION enable_ns=" << enable_ns << " epoch=" << epoch << '\n' << std::nounitbuf;
    unsigned int decoded_count = 0, rejected = 0;
    while (socketcan::monotonic_time_ns() - enable_ns <
           static_cast<std::uint64_t>(duration.count()) * 1000000ULL) {
        for (unsigned int count = 0; count < 8; ++count) {
            const auto received = endpoint.receive();
            if (!received) break;
            if (received->dropped_frames != 0) throw std::runtime_error("RX queue overflow: continuity lost");
            const auto frame = socketcan::to_brake(received->frame);
            const auto result = can::check_brake_e2e(&frame, rx);
            const auto decoded = can::decode_brake_frame(frame);
            const char* decision = "WIRE_REJECTED";
            if (result == e2e::P05Return::Ok) {
                if (!e2e::p05_is_ok(result, rx.check.status)) decision = "E2E_REJECTED";
                else if (decoded) decision = decoded->pressure_pa ? "WIRE_VALID" : "WIRE_UNAVAILABLE";
            }
            const bool wire_valid = decoded && e2e::p05_is_ok(result, rx.check.status);
            if (wire_valid) ++decoded_count;
            else ++rejected;
            std::cout << "BRAKE decision=" << decision
                      << " id=" << frame.can_id
                      << " e2e=" << (result == e2e::P05Return::Ok ? static_cast<int>(rx.check.status) : -1)
                      << " valid=" << (wire_valid && decoded->pressure_pa.has_value())
                      << " pressure_pa=" << (wire_valid ? decoded->pressure_pa.value_or(0) : 0)
                      << " epoch=" << (wire_valid ? decoded->epoch : 0)
                      << " seq=" << (wire_valid ? decoded->sequence : 0)
                      << " source_ns=" << (wire_valid ? decoded->source_time_ns : 0) << '\n';
        }
        std::cout.flush();
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    std::cout << "END decoded=" << decoded_count << " rejected=" << rejected << '\n';
}

template <typename Receiver, typename Convert, typename Value>
void application_fixture(const char* interface, std::uint16_t can_id, std::chrono::milliseconds duration,
                         std::uint32_t epoch, Receiver& receiver, Convert convert,
                         Value value, const char* value_field, bool pressure, bool torque = false) {
    stratadrive::socketcan::Endpoint endpoint(interface, can_id);
    std::cout << std::unitbuf << "RX_READY\n";
    stratadrive::fixture::await_start();
    const auto enable_ns = stratadrive::socketcan::monotonic_time_ns();
    if (!receiver.start_session(epoch, enable_ns)) throw std::runtime_error("trusted session init failed");
    std::cout << "SESSION enable_ns=" << enable_ns << " epoch=" << epoch << '\n';
    // Ready/session handshake는 즉시 전달하고, 수신 trace는 cycle마다 한 번 flush한다.
    std::cout << std::nounitbuf;
    unsigned int accepted = 0;
    unsigned int rejected = 0;
    bool timeout_reported = false;
    bool had_current_sample = false;
    while (stratadrive::socketcan::monotonic_time_ns() - enable_ns < static_cast<std::uint64_t>(duration.count()) * 1000000ULL) {
        // Queue를 끝까지 비우지 않는다. Flood 중에도 매 cycle poll/age 검사를 실행한다.
        for (unsigned int count = 0; count < 8; ++count) {
            const auto received = endpoint.receive();
            if (!received) break;
            if (received->dropped_frames != 0) throw std::runtime_error("RX queue overflow: continuity lost");
            const auto now = stratadrive::socketcan::monotonic_time_ns();
            const auto result = receiver.receive(convert(received->frame), now);
            if (result.decision == stratadrive::can::ActuatorReceiveDecision::Accepted) ++accepted;
            else ++rejected;
            const auto& history = receiver.last_accepted();
            std::cout << "RX decision=" << stratadrive::fixture::decision_name(result.decision, pressure, torque)
                      << " at_ns=" << now
                      << " e2e=" << (result.e2e_status ? static_cast<int>(*result.e2e_status) : -1)
                      << " last_valid_ns=" << (history ? history->received_time_ns : 0)
                      << " last_source_ns=" << (history ? history->message.source_time_ns : 0)
                      << " last_seq=" << (history ? history->message.sequence : 0)
                      << " payload_length=" << static_cast<unsigned int>(received->frame.payload_length)
                      << ' ' << value_field << '=' << (history ? value(history->message) : 0.0);
            trace_feedback(receiver.current_sample(now));
            std::cout << '\n';
        }
        const auto now = stratadrive::socketcan::monotonic_time_ns();
        const bool current = receiver.current_sample(now).has_value();
        if (had_current_sample && !current) {
            std::cout << "SOURCE_EXPIRED at_ns=" << now
                      << " source_ns=" << receiver.last_accepted()->message.source_time_ns << '\n';
        }
        had_current_sample = current;
        if (receiver.health() == stratadrive::can::ActuatorReceiverHealth::ClockError) {
            throw std::runtime_error("receiver clock fault");
        }
        if (receiver.health() == stratadrive::can::ActuatorReceiverHealth::Timeout && !timeout_reported) {
            const auto& history = receiver.last_accepted();
            const auto reference = history ? history->received_time_ns : enable_ns;
            std::cout << "TIMEOUT at_ns=" << now << " reference_ns=" << reference
                      << " elapsed_ns=" << now - reference << " usable=" << current << '\n';
            timeout_reported = true;
        }
        std::cout.flush();
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    std::cout << "END accepted=" << accepted << " rejected=" << rejected
              << " timeout=" << timeout_reported
              << " usable=" << receiver.current_sample(stratadrive::socketcan::monotonic_time_ns()).has_value() << '\n';
}

int main(int argc, char** argv) {
    try {
        using namespace stratadrive;
        if (argc != 5 && argc != 6) {
            throw std::invalid_argument("usage: actuator_socketcan_rx IFACE cmd|actual|brake-cmd|brake-actual|drive-cmd|drive-actual EPOCH DURATION_MS [wire]");
        }
        const auto epoch = fixture::positive_number(argv[3]);
        const auto duration_ms = fixture::positive_number(argv[4]);
        if (duration_ms > 10000) throw std::invalid_argument("fixture duration limit is 10000 ms");
        const auto duration = std::chrono::milliseconds{duration_ms};
        const std::string stream = argv[2];
        const bool brake = stream == "brake-cmd" || stream == "brake-actual";
        const bool drive = stream == "drive-cmd" || stream == "drive-actual";
        if (argc == 6) {
            if (!brake || std::string(argv[5]) != "wire") throw std::invalid_argument("wire mode is Brake-only");
            brake_wire_fixture(argv[1], stream == "brake-actual", epoch, duration);
        } else if (drive) {
            const auto kind = stream == "drive-actual" ? can::DriveFrameKind::Actual : can::DriveFrameKind::Command;
            can::DriveReceiver receiver({kind, {-300, 500}, 100, 300});
            application_fixture(argv[1], static_cast<std::uint16_t>(kind), duration, epoch, receiver,
                [](const auto& frame) { return socketcan::to_drive(frame); },
                [](const auto& message) { return *message.torque_nm; }, "history_torque_nm", false, true);
        } else if (brake) {
            const auto kind = stream == "brake-actual" ? can::BrakeFrameKind::Actual : can::BrakeFrameKind::Command;
            // 0..2 MPa는 fixture 설정이며 실제 차량 압력 calibration이 아니다.
            can::BrakeReceiver receiver({kind, 0, 2000000});
            application_fixture(argv[1], static_cast<std::uint16_t>(kind), duration, epoch, receiver,
                [](const auto& frame) { return socketcan::to_brake(frame); },
                [](const auto& message) { return *message.pressure_pa; }, "history_pressure_pa", true);
        } else {
            const auto kind = fixture::kind(stream);
            can::SteeringReceiver receiver({kind, -0.5, 0.5});
            application_fixture(argv[1], static_cast<std::uint16_t>(kind), duration, epoch, receiver,
                [](const auto& frame) { return socketcan::to_steering(frame); },
                [](const auto& message) { return *message.angle_rad; }, "history_angle_rad", false);
        }
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
    return 0;
}
