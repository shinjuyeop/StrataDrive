#include "brake_sil.hpp"
#include "brake_pressure_codec.hpp"
#include "demo_commands.hpp"
#include "demo_support.hpp"

#include <array>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>

namespace stratadrive::demo {

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

void demo_brake_model(const std::string& scenario) {
    using namespace stratadrive;
    if (scenario != "normal" && scenario != "stuck-rise" && scenario != "slow-rise" && scenario != "stuck-release" && scenario != "slow-release" && scenario != "sensor-hold" &&
        scenario != "sensor-invalid" && scenario != "transient") throw std::invalid_argument("unknown brake-model scenario");
    simulation::BrakeSil model({2000000, 1500000, 0, 5000000, 10000000, 1000000, 50*kMs});
    if (!model.start_session(1, kStart)) throw std::runtime_error("model session failed");
    can::BrakeTxState tx{can::BrakeFrameKind::Command};
    const std::array<const char*, 9> faults{"none", "command_unavailable", "continuity_lost", "clock_error", "control_deadline",
        "sensor_unavailable", "sensor_invalid", "response_error", "physical_model_error"};
    std::cout << "Brake response / " << scenario << ": manual clock, independent local sensor; rise fault onset at 100 ms / release fault onset at 360 ms; no vehicle/OS timing\n";
    for (std::uint32_t step = 1; step <= (scenario == "normal" ? 90U : 80U); ++step) {
        const auto ms = step*10, begin_ms = ms-10;
        const auto now = kStart+static_cast<std::uint64_t>(ms)*kMs;
        if (scenario != "normal" || step <= 65) {
            can::BrakeMessage input; input.pressure_pa = scenario == "normal" ? (step<35 ? 2000000:0) :
                (scenario == "stuck-release" || scenario == "slow-release") && ms>300 ? 0:1000000; input.epoch = 1; input.sequence = step-1;
            input.source_time_ns = now; input.local_state = can::BrakeLocalState::Normal; input.origin = can::BrakeOrigin::NormalPath;
            const auto frame = can::encode_brake_frame(input, tx);
            if (!frame) throw std::runtime_error("model input encoding failed");
            const auto result = model.receive(*frame, now);
            if (result.decision != can::BrakeReceiveDecision::Accepted &&
                !(model.fault() != vecu::BrakeFault::None && result.decision == can::BrakeReceiveDecision::ModeRejected)) {
                throw std::runtime_error("model input failed");
            }
        }
        simulation::BrakePressureResponseInjection injection;
        auto action = simulation::BrakeSensorAction::Acquire;
        std::optional<double> sensed;
        if (begin_ms >= 100) {
            if (scenario == "stuck-rise") injection.stuck = true;
            if (scenario == "slow-rise") injection.rise_rate_scale = 0.25;
            if (scenario == "sensor-hold") action = simulation::BrakeSensorAction::Hold;
            if (scenario == "sensor-invalid") sensed = std::numeric_limits<double>::quiet_NaN();
        }
        if (begin_ms >= 360) {
            if (scenario == "stuck-release") injection.stuck = true;
            if (scenario == "slow-release") injection.fall_rate_scale = 0.25;
        }
        if (scenario == "transient" && ms == 160) sensed = 1500000;
        const auto frame = model.tick(now, injection, action, sensed);
        const auto actual = frame ? can::decode_brake_frame(*frame) : std::nullopt;
        if (!actual) throw std::runtime_error("model publication failed");
        const auto& d = model.monitor_decision();
        const auto print_optional = [](std::optional<double> x) { if (x) std::cout << *x; else std::cout << "unknown"; };
        std::cout << "BRAKE_MODEL ms=" << ms << " pressure_pa="; print_optional(actual->pressure_pa);
        std::cout << " valid=" << actual->pressure_pa.has_value() << " physical_pa=" << model.actual_pressure_pa()
                  << " causal=" << actual->causal_sequence << " state=" << static_cast<int>(actual->local_state)
                  << " origin=" << static_cast<int>(actual->origin) << " expected_min_pa="; print_optional(d.expected_min_pa);
        std::cout << " expected_max_pa="; print_optional(d.expected_max_pa);
        std::cout << " residual_pa=" << d.residual_pa << " sensor_source_ms=";
        if (d.source_time_ns) std::cout << (*d.source_time_ns-kStart)/kMs; else std::cout << "unknown";
        std::cout << " violation_ms=";
        if (d.violation_since_ns) std::cout << (*d.violation_since_ns-kStart)/kMs; else std::cout << "unknown";
        std::cout << " fault=" << faults.at(static_cast<std::size_t>(model.fault()));
        std::cout << " protection_floor_observed=";
        const auto floor = model.protection_floor_observed();
        if (floor) std::cout << *floor; else std::cout << "unknown";
        std::cout << '\n';
    }
}

} // namespace stratadrive::demo
