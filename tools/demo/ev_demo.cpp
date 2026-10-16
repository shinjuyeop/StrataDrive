#include "battery_model.hpp"
#include "bms_controller.hpp"
#include "power_controller.hpp"
#include "power_model.hpp"
#include "ev_power_model.hpp"
#include "drive_controller.hpp"
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

} // namespace stratadrive::demo
