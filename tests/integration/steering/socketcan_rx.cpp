#include "steering_socketcan.hpp"

#include <exception>
#include <iostream>

#include "socketcan_support.hpp"

#include <chrono>
#include <thread>

int main(int argc, char** argv) {
    try {
        if (argc != 5) {
            throw std::invalid_argument("usage: steering_socketcan_rx IFACE cmd|actual EPOCH DURATION_MS");
        }
        const auto kind = stratadrive::fixture::kind(argv[2]);
        const auto epoch = stratadrive::fixture::positive_number(argv[3]);
        const auto duration = stratadrive::fixture::positive_number(argv[4]);
        if (duration > 10000) throw std::invalid_argument("fixture duration limit is 10000 ms");
        stratadrive::socketcan::Endpoint endpoint(argv[1], static_cast<std::uint16_t>(kind));
        // +/-0.5 rad는 실험용 설정이다. 차량 calibration 값이 아니다.
        stratadrive::can::SteeringReceiver receiver({kind, -0.5, 0.5});
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
        while (stratadrive::socketcan::monotonic_time_ns() - enable_ns < duration * 1000000ULL) {
            // Queue를 끝까지 비우지 않는다. Flood 중에도 매 cycle poll/age 검사를 실행한다.
            for (unsigned int count = 0; count < 8; ++count) {
                const auto received = endpoint.receive();
                if (!received) break;
                if (received->dropped_frames != 0) throw std::runtime_error("RX queue overflow: continuity lost");
                const auto now = stratadrive::socketcan::monotonic_time_ns();
                const auto result = receiver.receive(stratadrive::socketcan::to_steering(received->frame), now);
                if (result.decision == stratadrive::can::SteeringReceiveDecision::Accepted) ++accepted;
                else ++rejected;
                const auto& history = receiver.last_accepted();
                std::cout << "RX decision=" << stratadrive::fixture::decision_name(result.decision)
                          << " at_ns=" << now
                          << " e2e=" << (result.e2e_status ? static_cast<int>(*result.e2e_status) : -1)
                          << " last_valid_ns=" << (history ? history->received_time_ns : 0)
                          << " last_source_ns=" << (history ? history->message.source_time_ns : 0)
                          << " last_seq=" << (history ? history->message.sequence : 0)
                          << " history_angle_rad=" << (history ? *history->message.angle_rad : 0.0) << '\n';
            }
            const auto now = stratadrive::socketcan::monotonic_time_ns();
            const bool current = receiver.current_sample(now).has_value();
            if (had_current_sample && !current) {
                std::cout << "SOURCE_EXPIRED at_ns=" << now
                          << " source_ns=" << receiver.last_accepted()->message.source_time_ns << '\n';
            }
            had_current_sample = current;
            if (receiver.health() == stratadrive::can::SteeringReceiverHealth::ClockError) {
                throw std::runtime_error("receiver clock fault");
            }
            if (receiver.health() == stratadrive::can::SteeringReceiverHealth::Timeout && !timeout_reported) {
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
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
    return 0;
}
