#include "drive_actuator.hpp"
#include "drive_controller.hpp"
#include "drive_energy_model.hpp"
#include "power_model.hpp"
#include "bms_value_codec.hpp"
#include "demo_commands.hpp"
#include "demo_support.hpp"
#include "ev_fixture.hpp"

#include <array>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>

namespace stratadrive::demo {

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

void demo_drive_model() {
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

} // namespace stratadrive::demo
