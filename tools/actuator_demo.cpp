#include "steering_angle_codec.hpp"
#include "steering_receiver.hpp"
#include "brake_frame_codec.hpp"
#include "brake_pressure_codec.hpp"
#include "brake_receiver.hpp"
#include "drive_receiver.hpp"
#include "bms_receiver.hpp"
#include "bms_value_codec.hpp"
#ifdef STRATADRIVE_LINUX_SESSION
#include "epoch_store.hpp"
#endif

#include <cstdint>
#include <exception>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {
using namespace stratadrive::can;
constexpr std::uint64_t kStart = 1000000000ULL;
constexpr std::uint64_t kMs = 1000000ULL;

void usage(std::ostream& output) {
    output << "사용법:\n"
           << "  actuator_demo angle <angle_rad>\n"
           << "  actuator_demo frame <command|actual> <angle_rad|invalid>\n"
           << "  actuator_demo e2e\n"
           << "  actuator_demo receiver\n"
           << "  actuator_demo brake-pressure <pressure_pa>\n"
           << "  actuator_demo brake-frame <command|actual> <pressure_pa|invalid>\n"
           << "  actuator_demo brake-receiver\n"
           << "  actuator_demo drive-frame <command|actual> <torque_nm|invalid>\n"
           << "  actuator_demo drive-feedback\n"
           << "  actuator_demo bms-value <soc|voltage|current|temperature|power> <value>\n"
           << "  actuator_demo bms-frame <request|power-status|limits|battery|drive-limits|permission> [nominal|zero|invalid|partial]\n"
           << "  actuator_demo bms-receiver\n";
#ifdef STRATADRIVE_LINUX_SESSION
    output << "  actuator_demo epoch <init|next> <store_directory>\n";
#endif
}

double parse_angle(const std::string& input) {
    std::size_t consumed = 0;
    const double angle = std::stod(input, &consumed);
    if (consumed != input.size()) throw std::invalid_argument("rad 숫자만 입력하세요.");
    return angle;
}

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

double parse_pressure(const std::string& input) {
    std::size_t consumed = 0;
    const double value = std::stod(input, &consumed);
    if (consumed != input.size()) throw std::invalid_argument("Pa 숫자만 입력하세요.");
    return value;
}

void demo_brake_pressure(const std::string& input) {
    const double value = parse_pressure(input);
    const auto bytes = encode_brake_pressure(value);
    if (!bytes) throw std::runtime_error("압력은 finite이며 0..65534000 Pa여야 합니다.");
    std::cout << std::setprecision(10) << "입력: " << value << " Pa\nBytes:";
    for (const auto byte : *bytes) {
        std::cout << ' ' << std::uppercase << std::hex << std::setfill('0')
                  << std::setw(2) << static_cast<unsigned int>(byte);
    }
    std::cout << std::dec << "\n복원: " << *decode_brake_pressure(*bytes) << " Pa\n";
}

void demo_brake_frame(const std::string& kind, const std::string& input) {
    if (kind != "command" && kind != "actual") {
        throw std::invalid_argument("command 또는 actual을 선택하세요.");
    }
    BrakeMessage message;
    message.kind = kind == "command" ? BrakeFrameKind::Command : BrakeFrameKind::Actual;
    message.epoch = 1;
    message.source_time_ns = kind == "command" ? kStart : kStart + 10 * kMs;
    message.causal_sequence = kind == "command" ? 7 : 0;
    message.local_state = BrakeLocalState::Normal;
    message.origin = BrakeOrigin::NormalPath;
    if (input == "invalid") {
        message.local_state = BrakeLocalState::Init;
        message.origin = BrakeOrigin::NoAcceptedInput;
    } else {
        message.pressure_pa = parse_pressure(input);
    }
    BrakeTxState tx{message.kind};
    const auto frame = encode_brake_frame(message, tx);
    if (!frame) throw std::runtime_error("Brake frame field가 유효한 표현 범위여야 합니다.");
    const auto decoded = decode_brake_frame(*frame);
    BrakeRxState rx{message.kind};
    const auto result = check_brake_e2e(&*frame, rx);
    if (!decoded || !stratadrive::e2e::p05_is_ok(result, rx.check.status)) {
        throw std::runtime_error("Brake wire/E2E 검사가 실패했습니다.");
    }
    std::cout << "Fixture: brake " << kind << " (송수신/압력 응답 모델 실행 아님)\n"
              << "ID: 0x" << std::uppercase << std::hex << frame->can_id << "\nPayload:";
    for (const auto byte : frame->payload) {
        std::cout << ' ' << std::setfill('0') << std::setw(2) << static_cast<unsigned int>(byte);
    }
    std::cout << "\nCRC: 0x" << std::setw(4)
              << *brake_frame_crc(static_cast<std::uint16_t>(frame->can_id), frame->payload)
              << std::dec << "\n복원: ";
    if (decoded->pressure_pa) std::cout << std::setprecision(10) << *decoded->pressure_pa << " Pa\n";
    else std::cout << "invalid/unavailable (Validity=0)\n";
    std::cout << "Sequence: " << decoded->sequence << " Epoch: " << decoded->epoch
              << " SourceTimeNs: " << decoded->source_time_ns << '\n'
              << "E2E: Profile 5 Counter=" << static_cast<unsigned int>(frame->payload[31])
              << " Status=OK (Brake 수신 수용 판정은 미구현)\n";
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

const char* decision_name(ActuatorReceiveDecision decision, bool pressure = false) {
    switch (decision) {
        case SteeringReceiveDecision::Accepted: return "ACCEPTED";
        case SteeringReceiveDecision::NotInitialized: return "NOT_INITIALIZED";
        case SteeringReceiveDecision::ClockError: return "CLOCK_ERROR";
        case SteeringReceiveDecision::Timeout: return "TIMEOUT";
        case SteeringReceiveDecision::MalformedEnvelope: return "MALFORMED_ENVELOPE";
        case SteeringReceiveDecision::E2eRejected: return "E2E_REJECTED";
        case SteeringReceiveDecision::MalformedPayload: return "MALFORMED_PAYLOAD";
        case SteeringReceiveDecision::EpochMismatch: return "EPOCH_MISMATCH";
        case SteeringReceiveDecision::SourceBeforeSession: return "SOURCE_BEFORE_SESSION";
        case SteeringReceiveDecision::SourceInFuture: return "SOURCE_IN_FUTURE";
        case SteeringReceiveDecision::SourceStale: return "SOURCE_STALE";
        case SteeringReceiveDecision::SequenceRejected: return "SEQUENCE_REJECTED";
        case SteeringReceiveDecision::SourceNotIncreasing: return "SOURCE_NOT_INCREASING";
        case SteeringReceiveDecision::Unavailable: return "UNAVAILABLE";
        case SteeringReceiveDecision::ModeRejected: return "MODE_REJECTED";
        case SteeringReceiveDecision::ValueOutOfRange: return pressure ? "PRESSURE_OUT_OF_RANGE" : "ANGLE_OUT_OF_RANGE";
        case SteeringReceiveDecision::ContinuityLost: return "CONTINUITY_LOST";
    }
    return "UNKNOWN";
}

SteeringFrame encode(const SteeringMessage& message, SteeringTxState& tx) {
    const auto frame = encode_steering_frame(message, tx);
    if (!frame) {
        throw std::runtime_error("fixture encode 실패");
    }
    return *frame;
}

template <typename Frame, typename Receiver>
void show_receive(const char* label, const Frame& frame, Receiver& receiver,
          std::uint64_t now_ns, ActuatorReceiveDecision expected, bool pressure = false) {
    const auto result = receiver.receive(frame, now_ns);
    if (result.decision != expected) {
        throw std::runtime_error("예상한 receiver 결과와 다름");
    }
    std::cout << label << " -> " << decision_name(result.decision, pressure);
    if (result.e2e_status) {
        std::cout << " (E2E status=" << static_cast<unsigned int>(*result.e2e_status) << ')';
    }
    if (receiver.last_accepted()) {
        std::cout << " last-valid RX=" << receiver.last_accepted()->received_time_ns;
    }
    std::cout << '\n';
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
void demo_brake_receiver() {
    // fixture 압력 범위. 실제 차량 calibration이나 압력 dynamics를 실행하지 않는다.
    BrakeReceiver receiver({BrakeFrameKind::Command, 0.0, 2000000.0});
    if (!receiver.start_session(1, kStart)) throw std::runtime_error("Brake session 설정 실패");
    BrakeTxState tx{BrakeFrameKind::Command};
    BrakeMessage message;
    message.pressure_pa = 1500000.0;
    message.epoch = 1;
    message.source_time_ns = kStart;
    message.local_state = BrakeLocalState::Normal;
    message.origin = BrakeOrigin::NormalPath;
    const auto publish = [&](const char* label, std::uint64_t now_ns, BrakeReceiveDecision expected) {
        const auto frame = encode_brake_frame(message, tx);
        if (!frame) throw std::runtime_error("Brake fixture encode 실패");
        show_receive(label, *frame, receiver, now_ns, expected, true);
        return *frame;
    };
    std::cout << "Host Brake Receiver fixture (수동 시계, actuator 응답 모델 아님)\n";
    const auto first = publish("정상 압력", kStart, BrakeReceiveDecision::Accepted);
    show_receive("같은 frame 반복", first, receiver, kStart + 5 * kMs, BrakeReceiveDecision::E2eRejected, true);
    publish("cached sample 재포장", kStart + 10 * kMs, BrakeReceiveDecision::SequenceRejected);
    message.sequence = 1;
    message.source_time_ns = kStart + 15 * kMs;
    message.pressure_pa = 3000000.0;
    publish("fixture 압력 한계 초과", message.source_time_ns, BrakeReceiveDecision::PressureOutOfRange);
    message.source_time_ns = kStart + 20 * kMs;
    message.pressure_pa = 0.0;
    publish("유효한 제동 해제 0 Pa", message.source_time_ns, BrakeReceiveDecision::Accepted);
    message.sequence = 2;
    message.source_time_ns = kStart + 25 * kMs;
    message.pressure_pa.reset();
    publish("값 없음", message.source_time_ns, BrakeReceiveDecision::Unavailable);
    if (receiver.current_sample(kStart + 50 * kMs + 1)) throw std::runtime_error("오래된 압력이 current sample로 남음");
    std::cout << "source age 30 ms 초과 -> current sample 없음\n";
    if (receiver.poll(kStart + 100 * kMs) != BrakeReceiverHealth::Timeout) {
        throw std::runtime_error("Brake last-valid RX +80 ms timeout 미검출");
    }
    std::cout << "last-valid RX +80 ms -> TIMEOUT\n";
    message.pressure_pa = 1500000.0;
    message.source_time_ns = kStart + 101 * kMs;
    publish("timeout 뒤 정상 frame", message.source_time_ns, BrakeReceiveDecision::Timeout);
    if (!receiver.start_session(2, kStart + 110 * kMs)) throw std::runtime_error("Brake explicit INIT 실패");
    BrakeTxState restarted{BrakeFrameKind::Command};
    message.epoch = 2;
    message.sequence = 0;
    message.source_time_ns = kStart + 110 * kMs;
    const auto frame = encode_brake_frame(message, restarted);
    if (!frame) throw std::runtime_error("Brake restart encode 실패");
    show_receive("새 Epoch + explicit INIT", *frame, receiver, message.source_time_ns, BrakeReceiveDecision::Accepted, true);
}
DriveMessage drive_fixture(DriveFrameKind kind) {
    DriveMessage message;
    message.kind = kind;
    message.epoch = 1;
    message.source_time_ns = kind == DriveFrameKind::Command ? kStart : kStart + 10 * kMs;
    message.causal_sequence = kind == DriveFrameKind::Command ? 7 : 0;
    message.local_state = ActuatorLocalState::Normal;
    message.origin = ActuatorOrigin::NormalPath;
    if (kind == DriveFrameKind::Actual) {
        message.wheel_speed = DriveWheelSpeed{12.34, message.source_time_ns};
        message.regen_capability = DriveRegenCapability{200, message.source_time_ns, kStart + 5 * kMs};
        message.regen_limit_reason = DriveRegenLimitReason::ChargeAcceptanceLimited;
    }
    return message;
}

void demo_drive_frame(const std::string& kind, const std::string& input) {
    if (kind != "command" && kind != "actual") throw std::invalid_argument("command 또는 actual을 선택하세요.");
    auto message = drive_fixture(kind == "command" ? DriveFrameKind::Command : DriveFrameKind::Actual);
    if (input == "invalid") {
        message.local_state = ActuatorLocalState::Init;
        message.origin = ActuatorOrigin::NoAcceptedInput;
        message.wheel_speed.reset();
        message.regen_capability.reset();
        message.regen_limit_reason = DriveRegenLimitReason::InputsInvalid;
    } else {
        std::size_t consumed = 0;
        message.torque_nm = std::stod(input, &consumed);
        if (consumed != input.size()) throw std::invalid_argument("N·m 숫자만 입력하세요.");
    }
    DriveTxState tx{message.kind};
    const auto frame = encode_drive_frame(message, tx);
    if (!frame) throw std::runtime_error("Drive wire 표현 범위를 벗어났습니다.");
    const auto decoded = decode_drive_frame(*frame);
    if (!decoded) throw std::runtime_error("Drive decode 실패");
    std::cout << "Fixture: Drive " << kind << " (모터/회생 모델 실행 아님)\n"
              << "ID: 0x" << std::uppercase << std::hex << frame->can_id << "\nPayload:";
    for (std::size_t index = 0; index < frame->payload_length; ++index) {
        std::cout << ' ' << std::setfill('0') << std::setw(2) << static_cast<unsigned int>(frame->payload[index]);
    }
    std::cout << std::dec << "\nTorque valid: " << decoded->torque_nm.has_value()
              << "\nTorque: " << decoded->torque_nm.value_or(0) << " N·m\n";
    if (decoded->regen_capability) {
        std::cout << "Regen limit: " << decoded->regen_capability->torque_limit_nm << " N·m\n"
                  << "Capability source/input ns: " << decoded->regen_capability->source_time_ns
                  << '/' << decoded->regen_capability->input_time_ns << '\n';
    }
}

void demo_drive_feedback() {
    DriveReceiver receiver({DriveFrameKind::Actual, {-300, 500}, 100, 300});
    if (!receiver.start_session(1, kStart)) throw std::runtime_error("Drive session 설정 실패");
    auto message = drive_fixture(DriveFrameKind::Actual);
    message.source_time_ns = kStart;
    message.torque_nm = -150;
    message.wheel_speed->source_time_ns = kStart;
    message.regen_capability = DriveRegenCapability{200, kStart, kStart};
    DriveTxState tx{message.kind};
    const auto publish = [&](const char* label, unsigned int ms, DriveFeedbackQuality expected) {
        message.source_time_ns = kStart + ms * kMs;
        message.wheel_speed->source_time_ns = message.source_time_ns;
        const auto frame = encode_drive_frame(message, tx);
        if (!frame) throw std::runtime_error("Drive fixture encode 실패");
        const auto result = receiver.receive(*frame, message.source_time_ns);
        if (result.decision != ActuatorReceiveDecision::Accepted || result.regen_capability != expected) {
            throw std::runtime_error("Drive feedback quality 예상과 다름");
        }
        const auto current = receiver.current_sample(message.source_time_ns);
        if (!current) throw std::runtime_error("fresh torque가 사용 불가");
        std::cout << label << " -> 실제 토크 " << *current->torque_nm << " N·m, 회생 가용량 ";
        if (current->regen_capability) std::cout << current->regen_capability->torque_limit_nm << " N·m";
        else std::cout << "사용 불가";
        std::cout << '\n';
        ++message.sequence;
    };
    std::cout << "Host Drive feedback fixture (수동 시계, 응답/배분/에너지 모델 아님)\n";
    publish("정상 피드백", 0, DriveFeedbackQuality::Usable);
    publish("토크만 새 sample, 가용량은 cached", 20, DriveFeedbackQuality::Usable);
    publish("cached 가용량의 원천 age 30 ms 초과", 31, DriveFeedbackQuality::Stale);
    message.regen_capability->source_time_ns = kStart + 32 * kMs;
    publish("가용량 재계산 시각만 새 값, 입력은 오래됨", 32, DriveFeedbackQuality::Stale);
    message.regen_capability = DriveRegenCapability{0, kStart + 40 * kMs, kStart + 40 * kMs};
    publish("유효한 회생 가능량 0", 40, DriveFeedbackQuality::Usable);
    if (receiver.poll(kStart + 120 * kMs) != ActuatorReceiverHealth::Timeout ||
        receiver.current_sample(kStart + 120 * kMs)) throw std::runtime_error("Drive timeout 검사 실패");
    std::cout << "실제 토크 stream 상실 +80 ms -> latched TIMEOUT, 제어 sample 없음\n";
}
BmsFrameKind parse_bms_kind(const std::string& input) {
    if (input == "request") return BmsFrameKind::PowerRequest;
    if (input == "power-status") return BmsFrameKind::PowerStatus;
    if (input == "limits") return BmsFrameKind::PowerLimits;
    if (input == "battery") return BmsFrameKind::BatteryState;
    if (input == "drive-limits") return BmsFrameKind::DriveBatteryLimits;
    if (input == "permission") return BmsFrameKind::DrivePermission;
    throw std::invalid_argument("BMS kind: request/power-status/limits/battery/drive-limits/permission");
}
BmsMessage bms_fixture(BmsFrameKind kind, const std::string& variant) {
    if (variant != "nominal" && variant != "zero" && variant != "invalid" && variant != "partial") {
        throw std::invalid_argument("BMS fixture: nominal/zero/invalid/partial");
    }
    BmsMessage message;
    message.kind = kind; message.epoch = 1; message.source_time_ns = kStart;
    message.causal_sequence = 7; message.local_state = ActuatorLocalState::Normal; message.origin = ActuatorOrigin::NormalPath;
    switch (kind) {
    case BmsFrameKind::PowerRequest:
        message.content = BmsPowerRequest{BmsPowerAction::Enable, kStart+80*kMs, kStart-10*kMs}; break;
    case BmsFrameKind::PowerStatus:
        message.content = BmsPowerStatus{BmsPowerState::HvReady, true, true, false, 7, 31, 390, kStart-5*kMs, kStart-10*kMs, 12}; break;
    case BmsFrameKind::PowerLimits:
    case BmsFrameKind::DriveBatteryLimits:
        message.content = BmsPowerLimits{120000, 200000, BmsLimitReason::Nominal, BmsLimitReason::Nominal, kStart-10*kMs}; break;
    case BmsFrameKind::BatteryState:
        message.content = BmsBatteryState{BmsSocSample{0.6, kStart-10*kMs}, BmsElectricalSample{400, -120, kStart-10*kMs}, BmsTemperatureSample{25, kStart-10*kMs}}; break;
    case BmsFrameKind::DrivePermission:
        message.content = BmsDriveGrant{BmsDrivePermission::AllowNormal, 12, kStart-5*kMs, kStart-10*kMs, kStart+70*kMs}; break;
    }
    if (variant == "invalid") {
        message.local_state = ActuatorLocalState::Init; message.origin = ActuatorOrigin::NoAcceptedInput; message.causal_sequence = 0;
        switch (kind) {
        case BmsFrameKind::PowerRequest: message.content = BmsPowerRequest{}; break;
        case BmsFrameKind::PowerStatus: message.content = BmsPowerStatus{}; break;
        case BmsFrameKind::PowerLimits:
        case BmsFrameKind::DriveBatteryLimits: message.content = BmsPowerLimits{}; break;
        case BmsFrameKind::BatteryState: message.content = BmsBatteryState{}; break;
        case BmsFrameKind::DrivePermission: message.content = BmsDriveGrant{}; break;
        }
    } else if (variant == "zero") {
        if (auto* v = std::get_if<BmsPowerLimits>(&message.content)) {
            v->charge_power_w = v->discharge_power_w = 0; v->charge_reason = v->discharge_reason = BmsLimitReason::Disabled;
        } else if (auto* v = std::get_if<BmsBatteryState>(&message.content)) {
            v->soc->fraction = 0; v->electrical->voltage_v = v->electrical->current_a = 0; v->temperature->celsius = 0;
        } else if (auto* v = std::get_if<BmsPowerRequest>(&message.content)) v->action = BmsPowerAction::KeepOff;
        else if (auto* v = std::get_if<BmsPowerStatus>(&message.content)) {
            v->state = BmsPowerState::Off; v->positive_contactor_closed = v->negative_contactor_closed = false; v->hv_bus_voltage_v = 0;
        } else std::get<BmsDriveGrant>(message.content).permission = BmsDrivePermission::Inhibit;
    } else if (variant == "partial") {
        if (auto* v = std::get_if<BmsPowerLimits>(&message.content)) {
            v->charge_power_w.reset(); v->charge_reason = BmsLimitReason::InputsInvalid;
        } else if (auto* v = std::get_if<BmsBatteryState>(&message.content)) v->temperature.reset();
        else if (auto* v = std::get_if<BmsPowerStatus>(&message.content)) v->condition_validity = 15;
        else throw std::invalid_argument("partial fixture는 limits/drive-limits/battery/power-status에서 지원합니다.");
    }
    return message;
}
BmsValueKind parse_bms_value_kind(const std::string& field) {
    BmsValueKind kind;
    if (field == "soc") kind = BmsValueKind::Soc;
    else if (field == "voltage") kind = BmsValueKind::Voltage;
    else if (field == "current") kind = BmsValueKind::Current;
    else if (field == "temperature") kind = BmsValueKind::Temperature;
    else if (field == "power") kind = BmsValueKind::PowerLimit;
    else throw std::invalid_argument("BMS field: soc/voltage/current/temperature/power");
    return kind;
}
void demo_bms_value(BmsValueKind kind, double value) {
    const auto bytes = encode_bms_value(kind, value);
    if (!bytes) throw std::runtime_error("BMS 물리값의 finite/wire 범위를 확인하세요.");
    std::cout << "Bytes:";
    for (const auto byte : *bytes) std::cout << ' ' << std::hex << std::uppercase << std::setfill('0') << std::setw(2) << static_cast<unsigned int>(byte);
    std::cout << std::dec << "\n복원: " << std::setprecision(12) << *decode_bms_value(kind, *bytes) << '\n';
}
void demo_bms_frame(const std::string& kind, const std::string& variant) {
    const auto message = bms_fixture(parse_bms_kind(kind), variant);
    BmsTxState tx{message.kind}; const auto frame = encode_bms_frame(message, tx);
    if (!frame || !decode_bms_frame(*frame)) throw std::runtime_error("BMS wire encode/decode 실패");
    std::cout << "Fixture: EV/BMS " << kind << '/' << variant << " (모델/송수신 실행 아님)\n"
              << "ID: 0x" << std::hex << std::uppercase << frame->can_id << "\nPayload:";
    for (std::size_t i = 0; i < frame->payload_length; ++i) {
        std::cout << ' ' << std::setfill('0') << std::setw(2) << static_cast<unsigned int>(frame->payload[i]);
    }
    std::cout << std::dec << "\nLength: " << static_cast<unsigned int>(frame->payload_length)
              << "\nSourceTimeNs: " << message.source_time_ns << '\n';
}
void demo_bms_receiver() {
    std::cout << "Host BMS receiver fixture (수동 시계, 모델/배분/송수신 실행 아님)\n";
    const BmsPhysicalRanges physical{{0, 1000}, {-500, 500}, {-60, 200}, 200000};
    BmsReceiver receiver({BmsFrameKind::PowerLimits, physical});
    if (!receiver.start_session(1, kStart)) throw std::runtime_error("BMS session 설정 실패");
    auto message = bms_fixture(BmsFrameKind::PowerLimits, "nominal");
    auto& value = std::get<BmsPowerLimits>(message.content); value.input_time_ns = kStart;
    BmsTxState tx{message.kind};
    const auto publish = [&](unsigned int ms, BmsFieldQuality charge_quality) {
        message.source_time_ns = kStart+ms*kMs; value.input_time_ns = message.source_time_ns;
        const auto frame = encode_bms_frame(message, tx);
        if (!frame) throw std::runtime_error("BMS fixture encode 실패");
        const auto result = receiver.receive(*frame, message.source_time_ns);
        if (result.decision != ActuatorReceiveDecision::Accepted || result.quality[0] != charge_quality || result.quality[1] != BmsFieldQuality::Usable) {
            throw std::runtime_error("BMS partial quality 예상과 다름");
        }
        const auto current = receiver.current_sample(message.source_time_ns);
        if (!current) throw std::runtime_error("BMS envelope 사용 불가");
        const auto& usable = std::get<BmsPowerLimits>(current->message.content);
        std::cout << '+' << ms << " ms: 충전 한계 ";
        if (usable.charge_power_w) std::cout << *usable.charge_power_w << " W";
        else std::cout << "unknown";
        std::cout << ", 방전 한계 " << *usable.discharge_power_w << " W\n";
        ++message.sequence; ++message.causal_sequence;
    };
    publish(0, BmsFieldQuality::Usable);
    value.charge_power_w = 0; value.charge_reason = BmsLimitReason::Disabled;
    publish(20, BmsFieldQuality::Usable);
    value.charge_power_w.reset(); value.charge_reason = BmsLimitReason::InputsInvalid;
    publish(40, BmsFieldQuality::Unavailable); publish(60, BmsFieldQuality::Unavailable); publish(80, BmsFieldQuality::Unavailable);
    if (receiver.poll(kStart+100*kMs) != ActuatorReceiverHealth::Timeout || receiver.current_sample(kStart+100*kMs)) {
        throw std::runtime_error("충전 항목의 독립 timeout 검사 실패");
    }
    std::cout << "+100 ms: 방전/metadata가 진행해도 충전 마지막 valid RX(+20)부터 80 ms -> latched TIMEOUT\n";
    BmsReceiver permission({BmsFrameKind::DrivePermission, physical});
    if (!permission.start_session(1, kStart-10*kMs)) throw std::runtime_error("Permission session 설정 실패");
    auto grant_message = bms_fixture(BmsFrameKind::DrivePermission, "nominal");
    std::get<BmsDriveGrant>(grant_message.content).expires_at_ns = kStart+20*kMs;
    const BmsParentContext root{1, 7, kStart-10*kMs, kStart+20*kMs}; // independently supplied trusted fixture
    BmsTxState grant_tx{grant_message.kind}; const auto grant = encode_bms_frame(grant_message, grant_tx);
    if (!grant || permission.receive(*grant, kStart, &root).quality[0] != BmsFieldQuality::Usable ||
        !bms_permission_allows_normal(*permission.current_sample(kStart))) throw std::runtime_error("Grant 검사 실패");
    const auto expired = permission.current_sample(kStart+20*kMs);
    if (!expired || bms_permission_allows_normal(*expired)) throw std::runtime_error("Grant expiry 검사 실패");
    std::cout << "Permission: 검증된 parent의 허가 -> expiry(+20 ms)에서 사용 금지; 실제 torque/HV gate는 별도\n";
}

}  // namespace

int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--help") {
            usage(std::cout);
            return 0;
        }
        if (argc >= 2) {
            const std::string command = argv[1];
            if (command == "angle" && argc == 3) demo_angle(argv[2]);
            else if (command == "frame" && argc == 4) demo_frame(argv[2], argv[3]);
            else if (command == "e2e" && argc == 2) demo_e2e();
            else if (command == "receiver" && argc == 2) demo_receiver();
            else if (command == "brake-pressure" && argc == 3) demo_brake_pressure(argv[2]);
            else if (command == "brake-frame" && argc == 4) demo_brake_frame(argv[2], argv[3]);
            else if (command == "brake-receiver" && argc == 2) demo_brake_receiver();
            else if (command == "drive-frame" && argc == 4) demo_drive_frame(argv[2], argv[3]);
            else if (command == "drive-feedback" && argc == 2) demo_drive_feedback();
            else if (command == "bms-value" && argc == 4) demo_bms_value(parse_bms_value_kind(argv[2]), parse_angle(argv[3]));
            else if (command == "bms-frame" && (argc == 3 || argc == 4)) demo_bms_frame(argv[2], argc == 4 ? argv[3] : "nominal");
            else if (command == "bms-receiver" && argc == 2) demo_bms_receiver();
#ifdef STRATADRIVE_LINUX_SESSION
            else if (command == "epoch" && argc == 4) {
                const std::string action = argv[2];
                if (action == "init") { stratadrive::session::EpochStore::initialize(argv[3]); std::cout << "EPOCH_STORE_INITIALIZED\n"; }
                else if (action == "next") std::cout << "EPOCH value=" << stratadrive::session::EpochStore(argv[3]).issue() << '\n';
                else throw std::invalid_argument("epoch action must be init or next");
            }
#endif
            else {
                usage(std::cerr);
                return 1;
            }
        } else {
            usage(std::cerr);
            return 1;
        }
    } catch (const std::exception& error) {
        std::cerr << "REJECT: " << error.what() << '\n';
        return 1;
    }
    return 0;
}
