#include "steering_frame_codec.hpp"

#include <exception>
#include <iostream>
#include <stdexcept>

namespace {
const char* status_name(stratadrive::e2e::P05Status status) {
    using stratadrive::e2e::P05Status;
    switch (status) {
        case P05Status::Ok: return "OK";
        case P05Status::OkSomeLost: return "OKSOMELOST";
        case P05Status::Repeated: return "REPEATED";
        case P05Status::WrongSequence: return "WRONGSEQUENCE";
        case P05Status::NoNewData: return "NONEWDATA";
        case P05Status::Error: return "ERROR";
    }
    return "UNKNOWN";
}

void show(const char* label, const stratadrive::can::SteeringFrame* frame,
          stratadrive::can::SteeringRxState& rx) {
    const auto result = stratadrive::can::check_steering_e2e(frame, rx);
    if (result != stratadrive::e2e::P05Return::Ok) {
        throw std::runtime_error("E2E API 입력 오류");
    }
    std::cout << label;
    if (frame != nullptr) {
        std::cout << " Counter=" << static_cast<unsigned int>(frame->payload[31]);
    }
    std::cout << " -> " << status_name(rx.check.status) << '\n';
}
}  // namespace

int main() {
    using stratadrive::can::SteeringFrameKind;
    try {
        stratadrive::can::SteeringMessage message;
        message.angle_rad = 0.2;
        message.epoch = 1;
        message.source_time_ns = 1000000000ULL;
        message.local_state = stratadrive::can::SteeringLocalState::Normal;
        message.origin = stratadrive::can::SteeringOrigin::NormalPath;
        stratadrive::can::SteeringTxState tx{SteeringFrameKind::Command};
        stratadrive::can::SteeringRxState rx{SteeringFrameKind::Command};
        const auto publish = [&]() {
            const auto frame = stratadrive::can::encode_steering_frame(message, tx);
            if (!frame) {
                throw std::runtime_error("fixture encode 실패");
            }
            ++message.sequence;
            message.source_time_ns += 10000000ULL;
            return *frame;
        };
        std::cout << "Host Profile 5 fixture (socket/actuator 실행 아님)\n";
        auto frame = publish();
        show("정상 첫 frame", &frame, rx);
        show("같은 frame 재수신", &frame, rx);
        publish();  // counter 1, 2의 전송은 수신하지 않아 loss를 주입한다.
        publish();
        frame = publish();
        show("2개 누락 후 수신", &frame, rx);
        frame = publish();
        frame.payload[0] ^= 1;
        show("payload 손상", &frame, rx);
        frame = publish();
        show("손상 뒤 정상 frame", &frame, rx);
        for (unsigned int index = 0; index < 10; ++index) {
            publish();
        }
        frame = publish();
        show("허용 차이 초과", &frame, rx);
        frame = publish();
        show("E2E counter 재동기화", &frame, rx);
        show("새 데이터 없는 cycle", nullptr, rx);

        // 독립 세션 fixture: wrap 앞뒤를 실제 Protect/Check 호출로 생성한다.
        stratadrive::can::SteeringTxState wrap_tx{SteeringFrameKind::Command};
        stratadrive::can::SteeringRxState wrap_rx{SteeringFrameKind::Command};
        message.epoch = 2;
        for (unsigned int index = 0; index <= 256; ++index) {
            message.sequence = index;
            message.source_time_ns = 2000000000ULL + index * 10000000ULL;
            const auto wrapped = stratadrive::can::encode_steering_frame(message, wrap_tx);
            if (!wrapped) {
                throw std::runtime_error("wrap fixture encode 실패");
            }
            if (index >= 254) {
                show("Counter 순환", &*wrapped, wrap_rx);
            } else {
                const auto result = stratadrive::can::check_steering_e2e(&*wrapped, wrap_rx);
                if (!stratadrive::e2e::p05_is_ok(result, wrap_rx.check.status)) {
                    throw std::runtime_error("wrap fixture check 실패");
                }
            }
        }
        std::cout << "E2E OK와 command 수용은 별도입니다. Freshness/timeout은 steering_receiver_demo에서 확인합니다.\n";
    } catch (const std::exception& error) {
        std::cerr << "REJECT: " << error.what() << '\n';
        return 1;
    }
    return 0;
}
