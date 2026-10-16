#include "steering_angle_codec.hpp"
#include "steering_receiver.hpp"
#include "steering_actuator.hpp"
#include "brake_actuator.hpp"
#include "brake_frame_codec.hpp"
#include "brake_pressure_codec.hpp"
#include "brake_receiver.hpp"
#include "drive_receiver.hpp"
#include "drive_actuator.hpp"
#include "drive_controller.hpp"
#include "drive_energy_model.hpp"
#include "bms_receiver.hpp"
#include "bms_value_codec.hpp"
#include "battery_model.hpp"
#include "bms_controller.hpp"
#include "power_controller.hpp"
#include "power_model.hpp"
#include "ev_power_model.hpp"
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
           << "  actuator_demo bms-receiver\n"
           << "  actuator_demo steering-model\n"
           << "  actuator_demo brake-model\n"
           << "  actuator_demo drive-model\n"
           << "  actuator_demo battery-model\n"
           << "  actuator_demo bms-control\n"
           << "  actuator_demo power-model [normal|bms-trip|weld|blocked]\n"
           << "  actuator_demo drive-gated [normal|charge-zero|permission-loss|hv-loss|speed-stale|limits-stale]\n"
           << "  actuator_demo drive-energy [normal|charge-zero|near-full|auxiliary]\n"
           << "  actuator_demo ev-power [normal|weld|current-unknown|aux-blocked]\n";
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

void demo_battery_model() {
    using namespace stratadrive::simulation;
    // Small functional-SIL fixture, not an OEM battery calibration.
    BatteryModel model({180000000, 400, 0.05, 200000, 20, 25, 100, 0.01, 1, 100000});
    if (!model.initialize({1, kStart, 0.5, 25})) throw std::runtime_error("battery model initialization failed");
    std::cout << std::setprecision(10);
    for (std::uint32_t i = 0; i < 1500; ++i) {
        const auto begin = kStart + static_cast<std::uint64_t>(i)*20*kMs;
        const auto ms = (i+1)*20;
        const double traction = ms <= 10000 ? 20000 : ms <= 20000 ? -10000 : 0;
        BatterySensorCapture capture;
        if (ms > 12000 && ms <= 14000) capture.cell_voltage = SensorAction::Hold;
        if (ms == 15000) capture.temperature_override = CellExtrema{24, 80};
        if (ms > 22000 && ms <= 23000) capture.cell_temperature = SensorAction::Invalidate;
        const BatteryInterval interval{begin, begin + 20*kMs, {{1, i, begin}, begin, traction, 200}};
        if (model.step(interval, capture).fault != BatteryFault::None) throw std::runtime_error("battery model step failed");
        if (ms % 1000 != 0) continue;
        const auto& state = model.diagnostic_state();
        const auto& sensors = model.observation();
        std::cout << "BATTERY_MODEL ms=" << ms << " energy_j=" << state.energy_j << " soc=" << state.soc
                  << " voltage_v=" << sensors.electrical->value.voltage_v << " current_a=" << sensors.electrical->value.current_a
                  << " temperature_c=" << sensors.temperature->value << " loss_j=" << state.ohmic_loss_j
                  << " balance_error_j=" << state.balance_error_j << " batch=" << sensors.batch.sequence
                  << " cell_v_valid=" << sensors.cell_voltage.has_value()
                  << " cell_v_batch=" << (sensors.cell_voltage ? sensors.cell_voltage->identity.sequence : 0)
                  << " cell_t_valid=" << sensors.cell_temperature.has_value();
        if (sensors.cell_temperature) std::cout << " cell_t_max_c=" << sensors.cell_temperature->value.maximum;
        std::cout << '\n';
    }
}

stratadrive::vecu::BmsControllerConfig bms_fixture_config() {
    using namespace stratadrive;
    vecu::BmsControllerConfig config;
    // Functional SIL calibration only; these are not cell manufacturer limits.
    config.charge_current_a = 80; config.discharge_current_a = 200;
    config.max_charge_power_w = 30000; config.max_discharge_power_w = 80000;
    config.charge_soc = {0.95, 0.8}; config.discharge_soc = {0.05, 0.1};
    config.charge_cell_v = {4.2, 4.1}; config.discharge_cell_v = {3, 3.3};
    config.charge_temperature = {0, 10, 40, 45}; config.discharge_temperature = {-20, 0, 45, 55};
    config.cell_v = {2.8, 2.95, 4.15, 4.25}; config.pack_v = {280, 295, 415, 425};
    config.temperature_c = {-30, -15, 50, 60}; config.current_a = {-100, -80, 200, 250};
    config.series_cells = 100; config.pack_extrema_tolerance_v = 2;
    return config;
}

void demo_bms_control() {
    using namespace stratadrive;
    vecu::BmsController bms(bms_fixture_config());
    simulation::BatteryModel plant({180000000, 400, 0.05, 200000, 20, 25, 100, 0.01, 1, 100000});
    can::BmsReceiver rx({can::BmsFrameKind::PowerLimits, {{0, 1000}, {-300, 300}, {-50, 100}, 100000}});
    can::BmsTxState tx{can::BmsFrameKind::PowerLimits};
    std::uint32_t app_epoch = 1;
    if (!plant.initialize({7, kStart, 0.5, 25}) || !bms.start_session(app_epoch, 7, kStart) ||
        !rx.start_session(app_epoch, kStart)) throw std::runtime_error("BMS fixture initialization failed");
    std::cout << "BMS functional SIL: plant -> sensor port -> controller -> P05 codec -> receiver (manual clock, no socket/HV)\n";
    for (std::uint32_t i = 0; i < 100; ++i) {
        const auto begin = kStart+static_cast<std::uint64_t>(i)*20*kMs;
        const auto ms = (i+1)*20;
        if (i == 50 || i == 75) {
            ++app_epoch;
            if (!bms.start_session(app_epoch, 7, begin) || !rx.start_session(app_epoch, begin)) {
                throw std::runtime_error("BMS fixture trusted reinitialization failed");
            }
            tx.protection = {}; // new application stream, continuing physical model/energy ledger
        }
        simulation::BatterySensorCapture capture;
        if (ms > 400 && ms <= 600) capture.temperature_override = battery::CellExtrema{24, 42.5};
        if (ms > 600 && ms <= 660) capture.temperature_override = battery::CellExtrema{24, 60};
        if (ms > 1300 && ms <= 1340) capture.cell_temperature = simulation::SensorAction::Invalidate;
        if (ms > 1700 && ms <= 1840) capture.voltage_override = battery::CellExtrema{3.9, 4.2};
        if (plant.step({begin, begin+20*kMs, {{7, i, begin}, begin, 1000, 200}}, capture).fault != simulation::BatteryFault::None) {
            throw std::runtime_error("BMS fixture battery step failed");
        }
        const auto message = bms.tick(plant.observation(), begin+20*kMs);
        if (!message) throw std::runtime_error("BMS fixture publication missing");
        const auto frame = can::encode_bms_frame(*message, tx);
        if (!frame) throw std::runtime_error("BMS fixture limit encoding failed");
        const auto received = rx.receive(*frame, begin+20*kMs);
        if (received.decision != can::ActuatorReceiveDecision::Accepted &&
            received.decision != can::ActuatorReceiveDecision::Unavailable) throw std::runtime_error("BMS fixture receive failed");
        if (ms%100 != 0 && ms != 620 && ms != 660 && ms != 1320 && ms != 1360 && ms != 1720) continue;
        const auto& d = bms.decision();
        const std::array<const char*, 4> states{"NOT_INITIALIZED", "INITIAL_CHECKS", "ACTIVE", "LATCHED"};
        const std::array<const char*, 6> reasons{"nominal", "SOC", "temperature", "electrical", "disabled", "inputs_invalid"};
        const auto show = [](std::optional<double> value) { return value ? std::to_string(*value) : std::string("unknown"); };
        std::cout << "BMS_CONTROL ms=" << ms << " app_epoch=" << app_epoch << " model_epoch=7"
                  << " state=" << states.at(static_cast<std::size_t>(d.state))
                  << " charge_w=" << show(d.limits.charge_power_w) << " discharge_w=" << show(d.limits.discharge_power_w)
                  << " charge_reason=" << reasons.at(static_cast<std::size_t>(d.limits.charge_reason))
                  << " inhibit=" << d.inhibit_requested << " pending=" << d.pending_trips << " latched=" << d.latched_trips
                  << " recovery_ready=" << d.recovery_ready << " input_issue=" << static_cast<int>(d.input_issue)
                  << " batch=" << message->causal_sequence << " input_ns=" << d.limits.input_time_ns
                  << " soc=" << plant.observation().soc->value << '\n';
    }
}

void demo_power_model(const std::string& scenario) {
    using namespace stratadrive;
    if (scenario != "normal" && scenario != "bms-trip" && scenario != "weld" && scenario != "blocked") {
        throw std::invalid_argument("power-model: normal|bms-trip|weld|blocked");
    }
    simulation::PowerModel plant({0.002, 50, 0.02, 100, 1000, 500});
    vecu::PowerController controller({}); vecu::BmsController bms(bms_fixture_config());
    can::BmsTxState request_tx{can::BmsFrameKind::PowerRequest}, status_tx{can::BmsFrameKind::PowerStatus};
    can::BmsReceiver rx({can::BmsFrameKind::PowerStatus, {{0, 1000}, {-3000, 3000}, {-50, 100}, 100000}});
    if (!plant.initialize({7, 0, kStart}, 0) || !controller.start_session(1, 7, kStart) ||
        !bms.start_session(1, 7, kStart) || !rx.start_session(1, kStart)) throw std::runtime_error("power fixture startup failed");
    std::uint32_t request_sequence = 0;
    auto previous_phase = vecu::PowerPhase::Inspect;
    const std::array<const char*, 11> phases{"INSPECT", "OFF", "CHECKS", "CLOSE_NEGATIVE", "PRECHARGING", "CLOSE_POSITIVE",
        "OPEN_PRECHARGE", "READY", "WAIT_CURRENT", "OPEN_CONTACTORS", "DISCHARGING"};
    std::cout << "Power functional SIL / " << scenario << ": manual clock; fixed 400 V/SOC/thermal fixture, actual RC bus/contactors/current\n";
    for (std::uint32_t i = 0; i < 300; ++i) {
        const auto begin = kStart+static_cast<std::uint64_t>(i)*10*kMs;
        const auto now = begin+10*kMs; const auto ms = (i+1)*10;
        const bool closed = plant.diagnostic_state().contactors.positive && plant.diagnostic_state().contactors.negative;
        // Explicit actual-load fixture; a shutdown request is not an instantaneous current response.
        const double load = closed && ms >= 800 && (ms < 1200 || scenario == "blocked") ? 20 : 0;
        simulation::PowerFaultInjection injection;
        if (scenario == "weld" && ms >= 1000) injection.contactors[0] = simulation::ContactorFailure::StuckClosed;
        const auto coils = controller.output().coils.value_or(power::CoilCommand{});
        const simulation::PowerEnvironment env{400, load, true, true, true, false, false};
        if (plant.step({begin, now, {env, {7, i, begin}, begin}, coils}, injection) != simulation::PowerModelFault::None) {
            throw std::runtime_error("power fixture plant step failed");
        }
        const auto& physical = *plant.observation();
        // Fixed SOC/thermal/cell-spread fixture, not a BatteryModel energy run.
        const auto id = physical.identity; const auto dep = physical.input_time_ns;
        const double hot_cell = scenario == "bms-trip" && ms >= 1000 ? 60 : 26;
        battery::SensorSnapshot sensors{id, true, battery::ModelMeasurement<double>{0.5, id, dep},
            battery::ModelMeasurement<battery::ElectricalPair>{{*physical.pack_voltage_v, *physical.pack_current_a}, id, dep},
            battery::ModelMeasurement<double>{25, id, dep}, battery::ModelMeasurement<battery::CellExtrema>{{3.99, 4.01}, id, dep},
            battery::ModelMeasurement<battery::CellExtrema>{{24, hot_cell}, id, dep}};
        bms.tick(sensors, now);
        if (i%2 == 0) {
            can::BmsMessage request; request.kind = can::BmsFrameKind::PowerRequest;
            request.epoch = 1; request.sequence = request_sequence++; request.causal_sequence = request.sequence;
            request.source_time_ns = now; request.origin = can::ActuatorOrigin::NormalPath;
            const auto action = scenario != "bms-trip" && ms >= 1000 ? can::BmsPowerAction::Shutdown : can::BmsPowerAction::Enable;
            request.content = can::BmsPowerRequest{action, now+60*kMs, now};
            const can::BmsParentContext parent{1, request.causal_sequence, now, now+60*kMs};
            const auto frame = can::encode_bms_frame(request, request_tx);
            if (!frame || controller.receive(*frame, now, &parent).decision != can::ActuatorReceiveDecision::Accepted) {
                throw std::runtime_error("power fixture request validation failed");
            }
        }
        const auto message = controller.tick(plant.observation(), bms.power_gate(), now);
        const auto frame = message ? can::encode_bms_frame(*message, status_tx) : std::nullopt;
        if (!frame || rx.receive(*frame, now).decision != can::ActuatorReceiveDecision::Accepted) throw std::runtime_error("power fixture status failed");
        const auto& out = controller.output();
        if (out.phase == previous_phase && ms%100 != 0) continue;
        previous_phase = out.phase;
        const auto current = rx.current_sample(now);
        std::cout << "POWER_MODEL ms=" << ms << " phase=" << phases.at(static_cast<std::size_t>(out.phase))
                  << " bus_v=" << *physical.bus_voltage_v << " current_a=" << *physical.pack_current_a
                  << " actual_pos=" << physical.contactors->positive << " actual_neg=" << physical.contactors->negative
                  << " actual_pre=" << physical.contactors->precharge << " inhibit=" << out.inhibit_drive
                  << " blocked=" << out.shutdown_blocked << " fault=" << static_cast<int>(out.fault)
                  << " rx_ready=" << (current && can::bms_power_is_ready(*current))
                  << " model_batch=" << std::get<can::BmsPowerStatus>(message->content).input_sequence
                  << " request_seq=" << message->causal_sequence << '\n';
    }
}

void demo_drive_gated(const std::string& scenario) {
    using namespace stratadrive;
    if (scenario != "normal" && scenario != "charge-zero" && scenario != "permission-loss" && scenario != "hv-loss" &&
        scenario != "speed-stale" && scenario != "limits-stale") throw std::invalid_argument("unknown drive-gated scenario");
    vecu::DriveController controller({}); vecu::BmsController bms(bms_fixture_config());
    simulation::PowerModel power_plant({0.002, 50, 0.02, 100, 1000, 500});
    can::DriveTxState cmd_tx{can::DriveFrameKind::Command};
    can::BmsTxState relay{can::BmsFrameKind::DriveBatteryLimits}, grants{can::BmsFrameKind::DrivePermission};
    can::DriveReceiver feedback({can::DriveFrameKind::Actual, {-300, 500}, 100, 300, 30000000, 80000000, 30000000, 70000000});
    if (!controller.start_session(1, 7, kStart) || !bms.start_session(1, 7, kStart) || !feedback.start_session(1, kStart) ||
        !power_plant.initialize({7, 0, kStart}, 400, {true, true, false})) throw std::runtime_error("drive gate fixture startup failed");
    std::uint32_t permission_sequence = 0;
    std::optional<battery::ModelMeasurement<double>> held_speed;
    std::cout << "Drive EV gate / " << scenario << ": fixed SOC/thermal/speed/inverter-ready and Central fixtures; actual RC bus + torque response; no energy coupling\n";
    for (std::uint32_t i = 0; i < 220; ++i) {
        const auto begin = kStart+static_cast<std::uint64_t>(i)*10*kMs; const auto now = begin+10*kMs; const auto ms = (i+1)*10;
        const bool hv_loss = scenario == "hv-loss" && ms >= 1000;
        const simulation::PowerEnvironment env{400, 0, true, true, true, false, false};
        const power::CoilCommand coils = hv_loss ? power::CoilCommand{{}, true} : power::CoilCommand{{true, true, false}, false};
        if (power_plant.step({begin, now, {env, {7, i, begin}, begin}, coils}) != simulation::PowerModelFault::None) throw std::runtime_error("drive gate power plant failed");
        const auto& p = *power_plant.observation(); const auto id = p.identity; const auto dep = p.input_time_ns;
        const double soc = scenario == "charge-zero" && ms >= 1000 ? 1 : scenario == "normal" && ms >= 1000 && ms < 1400 ? 0.94 : 0.5;
        battery::SensorSnapshot battery_sensors{id, true, battery::ModelMeasurement<double>{soc, id, dep},
            battery::ModelMeasurement<battery::ElectricalPair>{{*p.pack_voltage_v, *p.pack_current_a}, id, dep},
            battery::ModelMeasurement<double>{25, id, dep}, battery::ModelMeasurement<battery::CellExtrema>{{3.99, 4.01}, id, dep},
            battery::ModelMeasurement<battery::CellExtrema>{{24, 26}, id, dep}};
        const auto limit = bms.tick(battery_sensors, now);
        can::DriveMessage cmd; cmd.epoch = 1; cmd.sequence = i; cmd.source_time_ns = now;
        cmd.torque_nm = ms < 130 ? 0 : ms < 700 ? 200 : -200;
        cmd.local_state = can::ActuatorLocalState::Normal; cmd.origin = can::ActuatorOrigin::NormalPath;
        const auto command_frame = can::encode_drive_frame(cmd, cmd_tx);
        if (!command_frame || controller.receive_command(*command_frame, now).decision != can::ActuatorReceiveDecision::Accepted) throw std::runtime_error("drive gate command failed");
        if (limit && !(scenario == "limits-stale" && ms >= 1000)) {
            const auto f = can::forward_bms_limits(*limit, relay);
            if (!f || controller.receive_limits(*f, now).decision != can::ActuatorReceiveDecision::Accepted) throw std::runtime_error("drive gate routed limits failed");
        }
        if (i%2 == 0) {
            const bool allow = ms >= 130 && !(scenario == "permission-loss" && ms >= 1000);
            // Independent trusted fixture issuer: never derive this context from an incoming CAN frame.
            const can::BmsParentContext parent{1, 1000+permission_sequence, now, now+60*kMs};
            can::BmsMessage grant; grant.kind = can::BmsFrameKind::DrivePermission; grant.epoch = 1;
            grant.sequence = permission_sequence++; grant.source_time_ns = now; grant.causal_sequence = parent.sequence;
            grant.local_state = can::ActuatorLocalState::Normal; grant.origin = can::ActuatorOrigin::NormalPath;
            grant.content = can::BmsDriveGrant{allow ? can::BmsDrivePermission::AllowNormal : can::BmsDrivePermission::Inhibit,
                allow ? i+1 : 0, allow ? now : 0, allow ? dep : 0, now+60*kMs};
            const auto f = can::encode_bms_frame(grant, grants);
            if (!f || controller.receive_permission(*f, now, allow ? &parent : nullptr).decision != can::ActuatorReceiveDecision::Accepted) throw std::runtime_error("drive gate permission failed");
        }
        const double omega = scenario == "normal" && ms > 1700 ? std::max(1.0, 20-(ms-1700)*19.0/300) : 20;
        battery::ModelMeasurement<double> speed{omega, id, dep};
        if (scenario == "speed-stale" && ms >= 1000 && held_speed) speed = *held_speed;
        else held_speed = speed;
        // inverter_ready/local_fault remain explicit sensor fixtures; the bus voltage is a separate actual observation.
        controller.observe_local({speed, battery::ModelMeasurement<drive::HvFeedback>{{*p.bus_voltage_v, true, false}, id, dep}}, now);
        const auto frame = controller.tick(now);
        if (!frame || feedback.receive(*frame, now).decision != can::ActuatorReceiveDecision::Accepted) throw std::runtime_error("drive gate actual failed");
        const auto actual = can::decode_drive_frame(*frame);
        if (!actual) throw std::runtime_error("drive gate decode failed");
        if (ms%100 != 0) continue;
        const auto& d = controller.decision();
        const auto show = [](std::optional<double> value) { return value ? std::to_string(*value) : std::string("unknown"); };
        std::cout << "DRIVE_GATED ms=" << ms << " active=" << d.active << " fault=" << static_cast<int>(d.fault)
                  << " target_nm=" << d.selected_target_nm << " actual_nm=" << *actual->torque_nm
                  << " speed=" << show(actual->wheel_speed ? std::optional<double>{actual->wheel_speed->value_rad_s} : std::nullopt)
                  << " bus_v=" << *p.bus_voltage_v << " regen_nm=" << show(actual->regen_capability ? std::optional<double>{actual->regen_capability->torque_limit_nm} : std::nullopt)
                  << " reason=" << static_cast<int>(actual->regen_limit_reason) << " residual=" << d.actual_outside_envelope
                  << " speed_source_ns=" << (actual->wheel_speed ? actual->wheel_speed->source_time_ns : 0)
                  << " capability_input_ns=" << (actual->regen_capability ? actual->regen_capability->input_time_ns : 0) << '\n';
    }
}

void demo_drive_energy(const std::string& scenario) {
    using namespace stratadrive;
    if (scenario != "normal" && scenario != "charge-zero" && scenario != "near-full" && scenario != "auxiliary") {
        throw std::invalid_argument("unknown drive-energy scenario");
    }
    simulation::DriveEnergyModel energy({}, {180000000, 400, 0.05, 200000, 20, 25, 100, 0.01, 1, 100000});
    vecu::DriveController drive({}); vecu::BmsController bms(bms_fixture_config());
    can::DriveTxState commands{can::DriveFrameKind::Command};
    can::BmsTxState relay{can::BmsFrameKind::DriveBatteryLimits}, grants{can::BmsFrameKind::DrivePermission};
    can::DriveReceiver feedback({can::DriveFrameKind::Actual, {-300, 500}, 100, 300, 30000000, 80000000, 30000000, 70000000});
    if (!energy.initialize({7, kStart, scenario == "near-full" ? 1.0 : 0.5, 25}) || !drive.start_session(1, 7, kStart) ||
        !bms.start_session(1, 7, kStart) || !feedback.start_session(1, kStart)) throw std::runtime_error("drive energy startup failed");
    std::cout << "Drive energy / " << scenario << ": ideal energized DC path; fixed 20 rad/s external speed and independent Central/relay fixtures; physical torque -> DC -> Battery -> BMS -> Drive; no RC/precharge or vehicle inertia coupling\n";
    for (std::uint32_t i = 0; i < 3000; ++i) {
        const auto begin = kStart+static_cast<std::uint64_t>(i)*10*kMs; const auto now = begin+10*kMs;
        const auto ms = (i+1)*10; const battery::ModelIdentity acquisition{7, i, begin};
        const simulation::DriveEnergyInputs inputs{battery::ModelMeasurement<double>{drive.actual_torque_nm(), acquisition, begin},
            battery::ModelMeasurement<double>{20, acquisition, begin}, battery::ModelMeasurement<double>{150, acquisition, begin}};
        simulation::BatterySensorCapture capture;
        // Explicit regional cell-temperature sensor injection; stored SOC/energy are never overridden.
        if (scenario == "charge-zero" && ms >= 5000) capture.temperature_override = battery::CellExtrema{44, 45};
        if (energy.step({begin, now, inputs}, capture).fault != simulation::DriveEnergyFault::None) {
            throw std::runtime_error("drive energy physical interval failed");
        }
        const auto& sensors = energy.observation(); const auto limits = bms.tick(sensors, now);
        const double demand = scenario == "near-full" ? -200 : scenario == "auxiliary" ? -5 :
            scenario == "charge-zero" ? (ms < 2000 ? 200 : -200) : ms < 10000 ? 200 : ms < 20000 ? -200 : 0;
        can::DriveMessage cmd; cmd.epoch = 1; cmd.sequence = i; cmd.source_time_ns = now; cmd.torque_nm = demand;
        cmd.local_state = can::ActuatorLocalState::Normal; cmd.origin = can::ActuatorOrigin::NormalPath;
        const auto command = can::encode_drive_frame(cmd, commands);
        if (!command || drive.receive_command(*command, now).decision != can::ActuatorReceiveDecision::Accepted) {
            throw std::runtime_error("drive energy command failed");
        }
        if (limits) {
            const auto routed = can::forward_bms_limits(*limits, relay);
            if (!routed || drive.receive_limits(*routed, now).decision != can::ActuatorReceiveDecision::Accepted) {
                throw std::runtime_error("drive energy limits relay failed");
            }
        }
        // Trusted Central fixture, independent of received CAN content and the BMS relay.
        const bool allow = ms >= 130 && bms.decision().state == vecu::BmsControlState::Active;
        const can::BmsParentContext parent{1, 1000+i, now, now+60*kMs};
        can::BmsMessage grant; grant.kind = can::BmsFrameKind::DrivePermission; grant.epoch = 1; grant.sequence = i;
        grant.causal_sequence = parent.sequence; grant.source_time_ns = now;
        grant.local_state = can::ActuatorLocalState::Normal; grant.origin = can::ActuatorOrigin::NormalPath;
        grant.content = can::BmsDriveGrant{allow ? can::BmsDrivePermission::AllowNormal : can::BmsDrivePermission::Inhibit,
            allow ? i+1 : 0, allow ? now : 0, allow ? begin : 0, now+60*kMs};
        const auto g = can::encode_bms_frame(grant, grants);
        if (!g || drive.receive_permission(*g, now, allow ? &parent : nullptr).decision != can::ActuatorReceiveDecision::Accepted) {
            throw std::runtime_error("drive energy permission failed");
        }
        // Ideal energized wire: local HV equals the actual battery terminal voltage.
        drive.observe_local({battery::ModelMeasurement<double>{20, sensors.batch, now},
            battery::ModelMeasurement<drive::HvFeedback>{{sensors.electrical->value.voltage_v, true, false}, sensors.batch,
                sensors.electrical->input_time_ns}}, now);
        const auto actual = drive.tick(now);
        if (!actual || feedback.receive(*actual, now).decision != can::ActuatorReceiveDecision::Accepted) {
            throw std::runtime_error("drive energy actual feedback failed");
        }
        if (ms%1000 != 0 && !(scenario == "charge-zero" && ms >= 5010 && ms <= 5150)) continue;
        const auto& e = energy.diagnostic_state(); const auto& b = energy.battery_state(); const auto& d = drive.decision();
        std::cout << std::setprecision(12) << "DRIVE_ENERGY ms=" << ms << " demand_nm=" << demand
                  << " interval_torque_nm=" << inputs.actual_torque_nm->value << " end_actual_nm=" << drive.actual_torque_nm()
                  << " mechanical_w=" << e.mechanical_w << " motor_loss_w=" << e.motor_loss_w << " dc_w=" << e.traction_dc_w
                  << " battery_w=" << b.electrical->voltage_v*b.electrical->current_a
                  << " soc=" << b.soc << " energy_j=" << b.energy_j << " return_dc_j=" << b.received_dc_j
                  << " motor_loss_j=" << e.motor_loss_j << " battery_heat_j=" << b.ohmic_loss_j
                  << " charge_limit_w=" << bms.decision().limits.charge_power_w.value_or(-1)
                  << " target_nm=" << d.selected_target_nm << " fault=" << static_cast<int>(d.fault)
                  << " residual=" << d.actual_outside_envelope << " balance_j=" << e.balance_error_j << '\n';
    }
}

void demo_ev_power(const std::string& scenario) {
    using namespace stratadrive;
    if (scenario != "normal" && scenario != "weld" && scenario != "current-unknown" && scenario != "aux-blocked") {
        throw std::invalid_argument("unknown ev-power scenario");
    }
    simulation::EvPowerModel plant({}, {180000000, 400, 0.05, 200000, 20, 25, 100, 0.01, 1, 100000},
        {0.002, 50, 0.02, 100, 1000, 500});
    vecu::PowerControllerConfig power_config; power_config.opening_current_max_a = 0.5;
    vecu::DriveControllerConfig drive_config; drive_config.fixed_power_reserve_w = 500; // idle + auxiliary + bounded main-path loss
    vecu::PowerController power_control(power_config); vecu::BmsController bms(bms_fixture_config()); vecu::DriveController drive(drive_config);
    can::BmsTxState requests{can::BmsFrameKind::PowerRequest}, status_tx{can::BmsFrameKind::PowerStatus},
        relay{can::BmsFrameKind::DriveBatteryLimits}, grants{can::BmsFrameKind::DrivePermission};
    can::DriveTxState commands{can::DriveFrameKind::Command};
    can::BmsReceiver status_rx({can::BmsFrameKind::PowerStatus, {{0, 1000}, {-3000, 3000}, {-50, 100}, 100000}});
    can::DriveReceiver actual_rx({can::DriveFrameKind::Actual, {-300, 500}, 100, 300, 30000000, 80000000, 30000000, 70000000});
    if (!plant.initialize({7, kStart, 0.5, 25}, 0) || !power_control.start_session(1, 7, kStart) ||
        !bms.start_session(1, 7, kStart) || !drive.start_session(1, 7, kStart) ||
        !status_rx.start_session(1, kStart) || !actual_rx.start_session(1, kStart)) throw std::runtime_error("ev power startup failed");
    const std::array<const char*, 11> phases{"INSPECT", "OFF", "CHECKS", "CLOSE_NEGATIVE", "PRECHARGING", "CLOSE_POSITIVE",
        "OPEN_PRECHARGE", "READY", "WAIT_CURRENT", "OPEN_CONTACTORS", "DISCHARGING"};
    auto previous_phase = vecu::PowerPhase::Inspect;
    std::uint32_t request_sequence = 0;
    std::cout << "EV circuit / " << scenario << ": actual Battery Rint + contactors/precharge/DC-link + inverter + BMS/Drive; fixed external 20 rad/s; independent Central/relay fixtures; no vehicle motion\n";
    for (std::uint32_t i = 0; i < 600; ++i) {
        const auto begin = kStart+static_cast<std::uint64_t>(i)*10*kMs, now = begin+10*kMs;
        const auto ms = (i+1)*10;
        const auto torque = drive.actual_torque_nm(); const auto& old_power = power_control.output();
        // Physical stage follows the fixture's enable output; residual torque must finish before disabling it.
        const bool energized = torque != 0 || (old_power.phase == vecu::PowerPhase::Ready && !old_power.inhibit_drive);
        const double auxiliary = scenario == "aux-blocked" && ms >= 2500 ? 10 : 0.375;
        const battery::ModelIdentity id{7, i, begin};
        const simulation::EvPowerInputs inputs{battery::ModelMeasurement<double>{torque, id, begin},
            battery::ModelMeasurement<double>{20, id, begin},
            battery::ModelMeasurement<simulation::EvElectricalEnvironment>{{auxiliary, energized}, id, begin}};
        simulation::PowerFaultInjection injection;
        if (scenario == "weld" && ms >= 2500) injection.contactors[0] = simulation::ContactorFailure::StuckClosed;
        if (scenario == "current-unknown" && ms >= 2500) injection.invalidate_current = true;
        const auto result = plant.step({begin, now, inputs, old_power.coils.value_or(power::CoilCommand{})}, injection);
        if (result.fault != simulation::EvPowerFault::None) {
            throw std::runtime_error("ev circuit interval fault="+std::to_string(static_cast<int>(result.fault))+
                " circuit="+std::to_string(static_cast<int>(result.circuit_fault))+" battery="+std::to_string(static_cast<int>(result.battery_fault)));
        }
        const auto limits = bms.tick(plant.battery_observation(), now);
        const auto action = ms >= 2500 ? can::BmsPowerAction::Shutdown : can::BmsPowerAction::Enable;
        if (i%2 == 0) {
            can::BmsMessage request; request.kind = can::BmsFrameKind::PowerRequest; request.epoch = 1;
            request.sequence = request_sequence++; request.causal_sequence = 10000+request.sequence;
            request.source_time_ns = now; request.origin = can::ActuatorOrigin::NormalPath;
            request.content = can::BmsPowerRequest{action, now+60*kMs, now};
            const can::BmsParentContext parent{1, request.causal_sequence, now, now+60*kMs};
            const auto f = can::encode_bms_frame(request, requests);
            if (!f || power_control.receive(*f, now, &parent).decision != can::ActuatorReceiveDecision::Accepted) throw std::runtime_error("ev request failed");
        }
        const auto status = power_control.tick(plant.power_observation(), bms.power_gate(), now);
        const auto status_frame = status ? can::encode_bms_frame(*status, status_tx) : std::nullopt;
        if (!status_frame || status_rx.receive(*status_frame, now).decision != can::ActuatorReceiveDecision::Accepted) throw std::runtime_error("ev power status failed");
        const auto current_status = status_rx.current_sample(now);
        const bool allow = action == can::BmsPowerAction::Enable && current_status && can::bms_power_is_ready(*current_status) &&
            !power_control.output().inhibit_drive && bms.decision().state == vecu::BmsControlState::Active;
        can::DriveMessage cmd; cmd.epoch = 1; cmd.sequence = i; cmd.source_time_ns = now;
        cmd.torque_nm = ms < 800 ? 0 : ms < 1600 ? 200 : -200;
        cmd.local_state = can::ActuatorLocalState::Normal; cmd.origin = can::ActuatorOrigin::NormalPath;
        const auto command = can::encode_drive_frame(cmd, commands);
        if (!command || drive.receive_command(*command, now).decision != can::ActuatorReceiveDecision::Accepted) throw std::runtime_error("ev drive command failed");
        if (limits) {
            const auto routed = can::forward_bms_limits(*limits, relay);
            if (!routed || drive.receive_limits(*routed, now).decision != can::ActuatorReceiveDecision::Accepted) throw std::runtime_error("ev limits relay failed");
        }
        const can::BmsParentContext parent{1, 100000+i, now, now+60*kMs}; // separately trusted Central fixture
        const auto& physical_status = std::get<can::BmsPowerStatus>(status->content);
        can::BmsMessage grant; grant.kind = can::BmsFrameKind::DrivePermission; grant.epoch = 1; grant.sequence = i;
        grant.causal_sequence = parent.sequence; grant.source_time_ns = now;
        grant.local_state = can::ActuatorLocalState::Normal; grant.origin = can::ActuatorOrigin::NormalPath;
        grant.content = can::BmsDriveGrant{allow ? can::BmsDrivePermission::AllowNormal : can::BmsDrivePermission::Inhibit,
            allow ? status->sequence : 0, allow ? status->source_time_ns : 0, allow ? physical_status.input_time_ns : 0, now+60*kMs};
        const auto grant_frame = can::encode_bms_frame(grant, grants);
        if (!grant_frame || drive.receive_permission(*grant_frame, now, allow ? &parent : nullptr).decision != can::ActuatorReceiveDecision::Accepted) throw std::runtime_error("ev grant failed");
        const auto& physical = plant.power_state();
        const bool inverter_ready = physical.bus_voltage_v >= 300 && physical.contactors.positive && physical.contactors.negative;
        // Dedicated physical HV acquisition, independent of the received CAN PowerStatus and its sensor injection.
        drive.observe_local({battery::ModelMeasurement<double>{20, physical.identity, now},
            battery::ModelMeasurement<drive::HvFeedback>{{physical.bus_voltage_v, inverter_ready, false}, physical.identity, begin}}, now);
        const auto actual = drive.tick(now);
        if (!actual || actual_rx.receive(*actual, now).decision != can::ActuatorReceiveDecision::Accepted) throw std::runtime_error("ev actual failed");
        const auto& out = power_control.output();
        if (out.phase == previous_phase && ms%100 != 0) continue;
        previous_phase = out.phase;
        const auto& energy = plant.diagnostic_state(); const auto& battery = plant.battery_state();
        const auto sensed_current = plant.power_observation()->pack_current_a;
        std::cout << std::setprecision(12) << "EV_POWER ms=" << ms << " phase=" << phases.at(static_cast<std::size_t>(out.phase))
                  << " bus_v=" << physical.bus_voltage_v << " pack_v=" << battery.electrical->voltage_v
                  << " sensor_current=" << (sensed_current ? std::to_string(*sensed_current) : "unknown")
                  << " actual_nm=" << drive.actual_torque_nm() << " soc=" << battery.soc << " cap_j=" << energy.capacitor_j
                  << " precharge_loss_j=" << energy.precharge_loss_j << " main_loss_j=" << energy.main_loss_j
                  << " discharge_loss_j=" << energy.discharge_loss_j << " auxiliary_j=" << battery.auxiliary_j
                  << " returned_dc_j=" << battery.received_dc_j << " drive_fault=" << static_cast<int>(drive.decision().fault)
                  << " power_fault=" << static_cast<int>(out.fault) << " blocked=" << out.shutdown_blocked
                  << " pos=" << physical.contactors.positive << " neg=" << physical.contactors.negative
                  << " balance_j=" << energy.balance_error_j << '\n';
    }
}

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
            else if (command == "steering-model" && argc == 2) {
                stratadrive::vecu::SteeringActuator model({-0.5, 0.5, -0.3, 0.3, 0, 1, 50*kMs});
                if (!model.start_session(1, kStart)) throw std::runtime_error("model session failed");
                SteeringTxState tx{SteeringFrameKind::Command};
                for (std::uint32_t step = 1; step <= 40; ++step) {
                    const auto now = kStart + static_cast<std::uint64_t>(step)*10*kMs;
                    if (step <= 30) {
                        SteeringMessage input;
                        input.angle_rad = 0.2; input.epoch = 1; input.sequence = step-1;
                        input.source_time_ns = now; input.local_state = SteeringLocalState::Normal;
                        input.origin = SteeringOrigin::NormalPath;
                        const auto frame = encode_steering_frame(input, tx);
                        if (!frame || model.receive(*frame, now).decision != SteeringReceiveDecision::Accepted)
                            throw std::runtime_error("model input failed");
                    }
                    const auto frame = model.tick(now);
                    const auto actual = frame ? decode_steering_frame(*frame) : std::nullopt;
                    if (!actual) throw std::runtime_error("model publication failed");
                    std::cout << "MODEL ms=" << step*10 << " angle_rad=" << *actual->angle_rad
                              << " causal=" << actual->causal_sequence << " state=" << static_cast<int>(actual->local_state)
                              << " origin=" << static_cast<int>(actual->origin) << '\n';
                }
            }
            else if (command == "brake-model" && argc == 2) {
                stratadrive::vecu::BrakeActuator model({2000000, 1500000, 0, 5000000, 10000000, 1000000, 50*kMs});
                if (!model.start_session(1, kStart)) throw std::runtime_error("brake model session failed");
                BrakeTxState tx{BrakeFrameKind::Command};
                for (std::uint32_t step = 1; step <= 90; ++step) {
                    const auto now = kStart + static_cast<std::uint64_t>(step)*10*kMs;
                    if (step <= 65) {
                        BrakeMessage input;
                        input.pressure_pa = step < 35 ? 2000000 : 0;
                        input.epoch = 1; input.sequence = step-1; input.source_time_ns = now;
                        input.local_state = BrakeLocalState::Normal; input.origin = BrakeOrigin::NormalPath;
                        const auto frame = encode_brake_frame(input, tx);
                        if (!frame || model.receive(*frame, now).decision != BrakeReceiveDecision::Accepted)
                            throw std::runtime_error("brake model input failed");
                    }
                    const auto frame = model.tick(now);
                    const auto actual = frame ? decode_brake_frame(*frame) : std::nullopt;
                    if (!actual) throw std::runtime_error("brake model publication failed");
                    std::cout << "BRAKE_MODEL ms=" << step*10 << " pressure_pa=" << actual->pressure_pa.value_or(0)
                              << " valid=" << actual->pressure_pa.has_value() << " causal=" << actual->causal_sequence
                              << " state=" << static_cast<int>(actual->local_state)
                              << " origin=" << static_cast<int>(actual->origin) << '\n';
                }
            }
            else if (command == "battery-model" && argc == 2) demo_battery_model();
            else if (command == "bms-control" && argc == 2) demo_bms_control();
            else if (command == "power-model" && (argc == 2 || argc == 3)) demo_power_model(argc == 3 ? argv[2] : "normal");
            else if (command == "drive-gated" && (argc == 2 || argc == 3)) demo_drive_gated(argc == 3 ? argv[2] : "normal");
            else if (command == "drive-energy" && (argc == 2 || argc == 3)) demo_drive_energy(argc == 3 ? argv[2] : "normal");
            else if (command == "ev-power" && (argc == 2 || argc == 3)) demo_ev_power(argc == 3 ? argv[2] : "normal");
            else if (command == "drive-model" && argc == 2) {
                stratadrive::vecu::DriveActuator model({{-300, 500}, {-200, 300, 0, 1000, 2000, 50*kMs}});
                if (!model.start_session(1, kStart)) throw std::runtime_error("drive model session failed");
                DriveTxState tx{DriveFrameKind::Command};
                for (std::uint32_t step = 1; step <= 160; ++step) {
                    const auto now = kStart + static_cast<std::uint64_t>(step)*10*kMs;
                    if (step <= 100) {
                        DriveMessage input;
                        input.torque_nm = step <= 40 ? 500 : -300;
                        input.epoch = 1; input.sequence = step-1; input.source_time_ns = now;
                        input.local_state = ActuatorLocalState::Normal; input.origin = ActuatorOrigin::NormalPath;
                        const auto frame = encode_drive_frame(input, tx);
                        if (!frame || model.receive(*frame, now).decision != ActuatorReceiveDecision::Accepted)
                            throw std::runtime_error("drive model input failed");
                    }
                    const auto frame = model.tick(now);
                    const auto actual = frame ? decode_drive_frame(*frame) : std::nullopt;
                    if (!actual) throw std::runtime_error("drive model publication failed");
                    std::cout << "DRIVE_MODEL ms=" << step*10 << " torque_nm=" << actual->torque_nm.value_or(0)
                              << " valid=" << actual->torque_nm.has_value() << " causal=" << actual->causal_sequence
                              << " state=" << static_cast<int>(actual->local_state)
                              << " origin=" << static_cast<int>(actual->origin)
                              << " regen_valid=" << actual->regen_capability.has_value() << '\n';
                }
            }
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
