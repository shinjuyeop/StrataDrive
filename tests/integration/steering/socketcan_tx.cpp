#include "steering_socketcan.hpp"

#include <exception>
#include <iostream>

#include "socketcan_support.hpp"

#include <chrono>
#include <string>
#include <thread>

namespace {
using namespace stratadrive;

can::SteeringFrame encode(can::SteeringMessage& message, can::SteeringTxState& tx,
                          std::uint32_t sequence) {
    message.sequence = sequence;
    message.source_time_ns = socketcan::monotonic_time_ns();
    const auto frame = can::encode_steering_frame(message, tx);
    if (!frame) throw std::runtime_error("fixture encode failed");
    return *frame;
}
}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc != 5) {
            throw std::invalid_argument("usage: steering_socketcan_tx IFACE cmd|actual EPOCH normal|faults|silent|flood");
        }
        const auto kind = fixture::kind(argv[2]);
        const auto epoch = fixture::positive_number(argv[3]);
        const std::string scenario = argv[4];
        if (scenario != "normal" && scenario != "faults" && scenario != "silent" && scenario != "flood") {
            throw std::invalid_argument("unknown fixture scenario");
        }
        socketcan::Endpoint endpoint(argv[1]);
        std::cout << std::unitbuf << "TX_READY\n";
        fixture::await_start();
        if (scenario == "silent") return 0;

        can::SteeringTxState tx{kind};
        can::SteeringMessage message;
        message.kind = kind;
        // Actual은 별도 측정 fixture다. Command를 echo하거나 actuator 모델이라고 부르지 않는다.
        message.angle_rad = kind == can::SteeringFrameKind::Command ? 0.2 : 0.15;
        message.epoch = epoch;
        message.local_state = can::SteeringLocalState::Normal;
        message.origin = can::SteeringOrigin::NormalPath;
        const auto start = std::chrono::steady_clock::now();
        const auto at = [&](int ms) { std::this_thread::sleep_until(start + std::chrono::milliseconds(ms)); };
        const auto send = [&](const socketcan::Frame& frame, const char* label) {
            endpoint.send(frame);
            std::cout << "TX label=" << label << " at_ns=" << socketcan::monotonic_time_ns() << '\n';
        };
        const auto first = encode(message, tx, 0);
        send(socketcan::to_socketcan(first), "first");
        if (scenario == "normal") {
            for (std::uint32_t sequence = 1; sequence < 5; ++sequence) {
                at(static_cast<int>(sequence) * 10);
                send(socketcan::to_socketcan(encode(message, tx, sequence)), "normal");
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
            auto corrupt = encode(message, tx, 1);
            corrupt.payload[0] ^= 1;
            send(socketcan::to_socketcan(corrupt), "corrupt");
            at(40);
            message.sequence = 1;
            message.source_time_ns = can::decode_steering_frame(first)->source_time_ns;
            const auto stale_frame = can::encode_steering_frame(message, tx);
            if (!stale_frame) throw std::runtime_error("stale fixture encode failed");
            send(socketcan::to_socketcan(*stale_frame), "stale");
            at(50);
            send(socketcan::to_socketcan(encode(message, tx, 1)), "fresh");
            at(60);
            auto short_frame = socketcan::to_socketcan(encode(message, tx, 2));
            short_frame.payload_length = 16;
            send(short_frame, "short");
            at(65);
            auto wide_frame = socketcan::to_socketcan(encode(message, tx, 2));
            wide_frame.payload_length = 64;
            send(wide_frame, "wide");
            at(70);
            auto extended = socketcan::to_socketcan(encode(message, tx, 2));
            extended.can_id |= 0x80000000U;
            send(extended, "extended");
            at(75);
            auto brs = socketcan::to_socketcan(encode(message, tx, 2));
            brs.fd_flags = 1;
            send(brs, "brs");
            at(80);
            auto classic = socketcan::to_socketcan(first);
            classic.is_fd = false;
            classic.fd_flags = 0;
            classic.payload_length = 2;
            send(classic, "classic");
            at(90);
            send(socketcan::to_socketcan(encode(message, tx, 1)), "cached_sequence");
            at(160);
            send(socketcan::to_socketcan(encode(message, tx, 2)), "late_after_timeout");
        }
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
    return 0;
}
