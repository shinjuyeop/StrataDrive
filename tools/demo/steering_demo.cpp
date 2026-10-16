#include "steering_angle_codec.hpp"
#include "steering_actuator.hpp"
#include "demo_commands.hpp"
#include "demo_support.hpp"

#include <array>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>

namespace stratadrive::demo {

void demo_angle(const std::string& input) {
    const double angle = parse_angle(input);
    const auto bytes = encode_steering_angle(angle);
    if (!bytes) throw std::runtime_error("finite 값이며 wire 표현 범위 안이어야 합니다.");
    const auto decoded = decode_steering_angle(*bytes);
    if (!decoded) throw std::runtime_error("reserved raw code입니다.");
    std::cout << std::setprecision(10) << "입력: " << angle << " rad\nBytes:";
    for (const auto byte : *bytes) {
        std::cout << ' ' << std::uppercase << std::hex << std::setfill('0')
                  << std::setw(2) << static_cast<unsigned int>(byte);
    }
    std::cout << std::dec << "\n복원: " << *decoded << " rad\n";
}

void demo_frame(const std::string& kind, const std::string& input) {
    if (kind != "command" && kind != "actual") {
        throw std::invalid_argument("command 또는 actual을 선택하세요.");
    }
    SteeringMessage message;
    message.kind = kind == "command" ? SteeringFrameKind::Command : SteeringFrameKind::Actual;
    message.epoch = 1;
    // 산술 검토용 고정 fixture. 실제 wall clock의 fresh frame이나 actuator 모델 결과가 아니다.
    message.source_time_ns = kind == "command" ? 1000000000ULL : 1010000000ULL;
    message.causal_sequence = kind == "command" ? 7 : 0;
    message.local_state = SteeringLocalState::Normal;
    message.origin = SteeringOrigin::NormalPath;
    if (input == "invalid") {
        message.local_state = SteeringLocalState::Init;
        if (kind == "actual") message.origin = SteeringOrigin::NoAcceptedInput;
    } else {
        message.angle_rad = parse_angle(input);
    }
    SteeringTxState tx{message.kind};
    const auto frame = encode_steering_frame(message, tx);
    if (!frame) throw std::runtime_error("frame field가 유효한 표현 범위여야 합니다.");
    const auto decoded = decode_steering_frame(*frame);
    if (!decoded) throw std::runtime_error("frame 구조 또는 CRC가 일치하지 않습니다.");
    SteeringRxState rx{message.kind};
    const auto check = check_steering_e2e(&*frame, rx);
    if (!stratadrive::e2e::p05_is_ok(check, rx.check.status)) {
        throw std::runtime_error("E2E Counter 검사가 실패했습니다.");
    }
    std::cout << "Fixture: " << kind << " (송수신/actuator 모델 실행 아님)\n"
              << "ID: 0x" << std::uppercase << std::hex << frame->can_id << "\nPayload:";
    for (const auto byte : frame->payload) {
        std::cout << ' ' << std::setfill('0') << std::setw(2) << static_cast<unsigned int>(byte);
    }
    std::cout << "\nCRC: 0x" << std::setw(4)
              << *steering_frame_crc(static_cast<std::uint16_t>(frame->can_id), frame->payload)
              << std::dec << "\n복원: ";
    if (decoded->angle_rad) std::cout << std::setprecision(10) << *decoded->angle_rad << " rad\n";
    else std::cout << "invalid/unavailable (Validity=0)\n";
    std::cout << "Sequence: " << decoded->sequence << " Epoch: " << decoded->epoch
              << " SourceTimeNs: " << decoded->source_time_ns << '\n';
    std::cout << "E2E: Profile 5 Counter=" << static_cast<unsigned int>(frame->payload[31])
              << " Status=OK (actuator 수용 판정은 별도)\n";
}

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

void show_e2e(const char* label, const stratadrive::can::SteeringFrame* frame,
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

void demo_e2e() {
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
    show_e2e("정상 첫 frame", &frame, rx);
    show_e2e("같은 frame 재수신", &frame, rx);
    publish();  // counter 1, 2의 전송은 수신하지 않아 loss를 주입한다.
    publish();
    frame = publish();
    show_e2e("2개 누락 후 수신", &frame, rx);
    frame = publish();
    frame.payload[0] ^= 1;
    show_e2e("payload 손상", &frame, rx);
    frame = publish();
    show_e2e("손상 뒤 정상 frame", &frame, rx);
    for (unsigned int index = 0; index < 10; ++index) {
        publish();
    }
    frame = publish();
    show_e2e("허용 차이 초과", &frame, rx);
    frame = publish();
    show_e2e("E2E counter 재동기화", &frame, rx);
    show_e2e("새 데이터 없는 cycle", nullptr, rx);

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
            show_e2e("Counter 순환", &*wrapped, wrap_rx);
        } else {
            const auto result = stratadrive::can::check_steering_e2e(&*wrapped, wrap_rx);
            if (!stratadrive::e2e::p05_is_ok(result, wrap_rx.check.status)) {
                throw std::runtime_error("wrap fixture check 실패");
            }
        }
    }
    std::cout << "E2E OK와 command 수용은 별도입니다. 조향 freshness/timeout은 actuator_demo receiver에서 확인합니다.\n";
}

void demo_receiver() {
    // 수동 timestamp를 쓰는 Host fixture. +/-0.5 rad는 시험용 설정이다.
    SteeringReceiver receiver({SteeringFrameKind::Command, -0.5, 0.5});
    if (!receiver.start_session(1, kStart)) {
        throw std::runtime_error("session 설정 실패");
    }
    SteeringTxState tx{SteeringFrameKind::Command};
    SteeringMessage message;
    message.angle_rad = 0.2;
    message.epoch = 1;
    message.source_time_ns = kStart;
    message.local_state = SteeringLocalState::Normal;
    message.origin = SteeringOrigin::NormalPath;

    std::cout << "Host Receiver fixture (수동 시계, socket/actuator 실행 아님)\n";
    const auto first = encode(message, tx);
    show_receive("정상 첫 frame", first, receiver, kStart, SteeringReceiveDecision::Accepted);
    show_receive("같은 frame 반복", first, receiver, kStart + 5 * kMs, SteeringReceiveDecision::E2eRejected);
    show_receive("cached sample 재포장", encode(message, tx), receiver, kStart + 10 * kMs,
         SteeringReceiveDecision::SequenceRejected);
    message.sequence = 1;
    message.source_time_ns = kStart + kMs;
    show_receive("오래된 sample", encode(message, tx), receiver, kStart + 40 * kMs,
         SteeringReceiveDecision::SourceStale);
    message.source_time_ns = kStart + 50 * kMs;
    show_receive("새 정상 sample", encode(message, tx), receiver, message.source_time_ns,
         SteeringReceiveDecision::Accepted);
    if (receiver.current_sample(kStart + 80 * kMs + 1)) {
        throw std::runtime_error("source age가 끝난 sample이 사용 가능함");
    }
    std::cout << "source age 30 ms 초과 -> current sample 없음\n";
    message.sequence = 2;
    message.source_time_ns = kStart + 90 * kMs;
    message.angle_rad.reset();
    show_receive("invalid sample", encode(message, tx), receiver, message.source_time_ns,
         SteeringReceiveDecision::Unavailable);
    message.angle_rad = 0.2;
    message.epoch = 2;
    message.source_time_ns = kStart + 100 * kMs;
    show_receive("다른 Epoch", encode(message, tx), receiver, message.source_time_ns,
         SteeringReceiveDecision::EpochMismatch);
    if (receiver.poll(kStart + 130 * kMs) != SteeringReceiverHealth::Timeout) {
        throw std::runtime_error("마지막 valid RX +80 ms에서 timeout이 검출되지 않음");
    }
    std::cout << "last-valid RX +80 ms -> TIMEOUT\n";
    message.epoch = 1;
    message.source_time_ns = kStart + 140 * kMs;
    show_receive("timeout 뒤 정상 frame", encode(message, tx), receiver, message.source_time_ns,
         SteeringReceiveDecision::Timeout);
    if (!receiver.start_session(2, kStart + 150 * kMs)) {
        throw std::runtime_error("새 Epoch의 explicit INIT 실패");
    }
    SteeringTxState restarted{SteeringFrameKind::Command};
    message.epoch = 2;
    message.sequence = 0;
    message.source_time_ns = kStart + 150 * kMs;
    show_receive("새 Epoch + explicit INIT", encode(message, restarted), receiver, message.source_time_ns,
         SteeringReceiveDecision::Accepted);
}

void demo_steering_model(const std::string& scenario) {
    using namespace stratadrive;
    if (scenario != "normal" && scenario != "jam" && scenario != "slow" && scenario != "sensor-hold" &&
        scenario != "sensor-invalid" && scenario != "transient") throw std::invalid_argument("unknown steering-model scenario");
    vecu::SteeringActuator model({-0.5, 0.5, -0.3, 0.3, 0, 1, 50*kMs});
    if (!model.start_session(1, kStart)) throw std::runtime_error("model session failed");
    can::SteeringTxState tx{can::SteeringFrameKind::Command};
    const std::array<const char*, 9> faults{"none", "command_unavailable", "continuity_lost", "clock_error", "control_deadline",
        "sensor_unavailable", "sensor_invalid", "tracking_error", "physical_model_error"};
    std::cout << "Steering response / " << scenario << ": manual clock, independent local sensor; interval fault onset at 100 ms; no vehicle/OS timing\n";
    for (std::uint32_t step = 1; step <= (scenario == "normal" ? 40U : 80U); ++step) {
        const auto ms = step*10, begin_ms = ms-10;
        const auto now = kStart+static_cast<std::uint64_t>(ms)*kMs;
        if (scenario != "normal" || step <= 30) {
            can::SteeringMessage input; input.angle_rad = 0.2; input.epoch = 1; input.sequence = step-1;
            input.source_time_ns = now; input.local_state = can::SteeringLocalState::Normal; input.origin = can::SteeringOrigin::NormalPath;
            const auto frame = can::encode_steering_frame(input, tx);
            if (!frame) throw std::runtime_error("model input encoding failed");
            const auto result = model.receive(*frame, now);
            if (result.decision != can::SteeringReceiveDecision::Accepted &&
                !(model.fault() != vecu::SteeringFault::None && result.decision == can::SteeringReceiveDecision::ModeRejected)) {
                throw std::runtime_error("model input failed");
            }
        }
        simulation::SteeringResponseInjection injection;
        auto action = simulation::SteeringSensorAction::Acquire;
        std::optional<double> sensed;
        if (begin_ms >= 100) {
            if (scenario == "jam") injection.jammed = true;
            if (scenario == "slow") injection.rate_scale = 0.25;
            if (scenario == "sensor-hold") action = simulation::SteeringSensorAction::Hold;
            if (scenario == "sensor-invalid") sensed = std::numeric_limits<double>::quiet_NaN();
        }
        if (scenario == "transient" && ms == 160) sensed = 0.3;
        const auto frame = model.tick(now, injection, action, sensed);
        const auto actual = frame ? can::decode_steering_frame(*frame) : std::nullopt;
        if (!actual) throw std::runtime_error("model publication failed");
        const auto& d = model.monitor_decision();
        const auto print_optional = [](std::optional<double> x) { if (x) std::cout << *x; else std::cout << "unknown"; };
        std::cout << "MODEL ms=" << ms << " angle_rad="; print_optional(actual->angle_rad);
        std::cout << " valid=" << actual->angle_rad.has_value() << " physical_rad=" << model.actual_angle_rad()
                  << " causal=" << actual->causal_sequence << " state=" << static_cast<int>(actual->local_state)
                  << " origin=" << static_cast<int>(actual->origin) << " expected_min_rad="; print_optional(d.expected_min_rad);
        std::cout << " expected_max_rad="; print_optional(d.expected_max_rad);
        std::cout << " residual_rad=" << d.residual_rad << " sensor_source_ms=";
        if (d.source_time_ns) std::cout << (*d.source_time_ns-kStart)/kMs; else std::cout << "unknown";
        std::cout << " violation_ms=";
        if (d.violation_since_ns) std::cout << (*d.violation_since_ns-kStart)/kMs; else std::cout << "unknown";
        std::cout << " fault=" << faults.at(static_cast<std::size_t>(model.fault())) << '\n';
    }
}

} // namespace stratadrive::demo
