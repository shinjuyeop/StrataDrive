#include "steering_frame_codec.hpp"

#include <exception>
#include <iomanip>
#include <iostream>
#include <string>

int main(int argc, char* argv[]) {
    if (argc != 3) {
        std::cerr << "사용법: steering_frame_demo <command|actual> <angle_rad|invalid>\n";
        return 1;
    }
    try {
        const std::string kind{argv[1]};
        const std::string input{argv[2]};
        if (kind != "command" && kind != "actual") {
            std::cerr << "REJECT: command 또는 actual을 선택하세요.\n";
            return 1;
        }
        stratadrive::can::SteeringMessage message;
        message.kind = kind == "command" ? stratadrive::can::SteeringFrameKind::Command
                                         : stratadrive::can::SteeringFrameKind::Actual;
        message.epoch = 1;
        // 산술 검토용 고정 fixture. 실제 wall clock의 fresh frame이나 actuator 모델 결과가 아니다.
        message.source_time_ns = kind == "command" ? 1000000000ULL : 1010000000ULL;
        message.causal_sequence = kind == "command" ? 7 : 0;
        message.local_state = stratadrive::can::SteeringLocalState::Normal;
        message.origin = stratadrive::can::SteeringOrigin::NormalPath;
        if (input == "invalid") {
            message.local_state = stratadrive::can::SteeringLocalState::Init;
            if (kind == "actual") {
                message.origin = stratadrive::can::SteeringOrigin::NoAcceptedInput;
            }
        } else {
            std::size_t consumed = 0;
            message.angle_rad = std::stod(input, &consumed);
            if (consumed != input.size()) {
                std::cerr << "REJECT: rad 숫자만 입력하세요.\n";
                return 1;
            }
        }
        stratadrive::can::SteeringTxState tx{message.kind};
        const auto frame = stratadrive::can::encode_steering_frame(message, tx);
        if (!frame) {
            std::cerr << "REJECT: frame field가 유효한 표현 범위여야 합니다.\n";
            return 1;
        }
        const auto decoded = stratadrive::can::decode_steering_frame(*frame);
        if (!decoded) {
            std::cerr << "REJECT: frame 구조 또는 CRC가 일치하지 않습니다.\n";
            return 1;
        }
        stratadrive::can::SteeringRxState rx{message.kind};
        const auto check = stratadrive::can::check_steering_e2e(&*frame, rx);
        if (!stratadrive::e2e::p05_is_ok(check, rx.check.status)) {
            std::cerr << "REJECT: E2E Counter 검사가 실패했습니다.\n";
            return 1;
        }
        std::cout << "Fixture: " << kind << " (송수신/actuator 모델 실행 아님)\n"
                  << "ID: 0x" << std::uppercase << std::hex << frame->can_id << "\nPayload:";
        for (const auto byte : frame->payload) {
            std::cout << ' ' << std::setfill('0') << std::setw(2) << static_cast<unsigned int>(byte);
        }
        std::cout << "\nCRC: 0x" << std::setw(4)
                  << *stratadrive::can::steering_frame_crc(
                         static_cast<std::uint16_t>(frame->can_id), frame->payload)
                  << std::dec << "\n복원: ";
        if (decoded->angle_rad) {
            std::cout << std::setprecision(10) << *decoded->angle_rad << " rad\n";
        } else {
            std::cout << "invalid/unavailable (Validity=0)\n";
        }
        std::cout << "Sequence: " << decoded->sequence << " Epoch: " << decoded->epoch
                  << " SourceTimeNs: " << decoded->source_time_ns << '\n';
        std::cout << "E2E: Profile 5 Counter=" << static_cast<unsigned int>(frame->payload[31])
                  << " Status=OK (actuator 수용 판정은 별도)\n";
    } catch (const std::exception& error) {
        std::cerr << "REJECT: " << error.what() << '\n';
        return 1;
    }
    return 0;
}
