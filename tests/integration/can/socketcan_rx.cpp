#include "actuator_socketcan.hpp"

#include <exception>
#include <iostream>

#include "socketcan_support.hpp"

#include <chrono>
#include <thread>

namespace {
template <typename Message>
void trace_feedback(const std::optional<Message>&) {}
void trace_feedback(const std::optional<stratadrive::can::DriveMessage>& current) {
    const bool cap = current && current->regen_capability;
    std::cout << " regen_valid=" << cap
              << " regen_limit_nm=" << (cap ? current->regen_capability->torque_limit_nm : 0)
              << " cap_source_ns=" << (cap ? current->regen_capability->source_time_ns : 0)
              << " cap_input_ns=" << (cap ? current->regen_capability->input_time_ns : 0)
              << " speed_valid=" << (current && current->wheel_speed);
}
}  // namespace

// 기존 wire 회귀 검사 경로다. WIRE_VALID와 application 수용을 구분한다.
void brake_wire_fixture(const char* interface, bool actual, std::uint32_t epoch,
                        std::chrono::milliseconds duration) {
    using namespace stratadrive;
    const auto kind = actual ? can::BrakeFrameKind::Actual : can::BrakeFrameKind::Command;
    socketcan::Endpoint endpoint(interface, static_cast<std::uint16_t>(kind));
    can::BrakeRxState rx{kind};
    std::cout << std::unitbuf << "RX_READY\n";
    fixture::await_start();
    const auto enable_ns = socketcan::monotonic_time_ns();
    std::cout << "SESSION enable_ns=" << enable_ns << " epoch=" << epoch << '\n' << std::nounitbuf;
    unsigned int decoded_count = 0, rejected = 0;
    while (socketcan::monotonic_time_ns() - enable_ns <
           static_cast<std::uint64_t>(duration.count()) * 1000000ULL) {
        for (unsigned int count = 0; count < 8; ++count) {
            const auto received = endpoint.receive();
            if (!received) break;
            if (received->dropped_frames != 0) throw std::runtime_error("RX queue overflow: continuity lost");
            const auto frame = socketcan::to_brake(received->frame);
            const auto result = can::check_brake_e2e(&frame, rx);
            const auto decoded = can::decode_brake_frame(frame);
            const char* decision = "WIRE_REJECTED";
            if (result == e2e::P05Return::Ok) {
                if (!e2e::p05_is_ok(result, rx.check.status)) decision = "E2E_REJECTED";
                else if (decoded) decision = decoded->pressure_pa ? "WIRE_VALID" : "WIRE_UNAVAILABLE";
            }
            const bool wire_valid = decoded && e2e::p05_is_ok(result, rx.check.status);
            if (wire_valid) ++decoded_count;
            else ++rejected;
            std::cout << "BRAKE decision=" << decision
                      << " id=" << frame.can_id
                      << " e2e=" << (result == e2e::P05Return::Ok ? static_cast<int>(rx.check.status) : -1)
                      << " valid=" << (wire_valid && decoded->pressure_pa.has_value())
                      << " pressure_pa=" << (wire_valid ? decoded->pressure_pa.value_or(0) : 0)
                      << " epoch=" << (wire_valid ? decoded->epoch : 0)
                      << " seq=" << (wire_valid ? decoded->sequence : 0)
                      << " source_ns=" << (wire_valid ? decoded->source_time_ns : 0) << '\n';
        }
        std::cout.flush();
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    std::cout << "END decoded=" << decoded_count << " rejected=" << rejected << '\n';
}

template <typename Receiver, typename Convert, typename Value>
void application_fixture(const char* interface, std::uint16_t can_id, std::chrono::milliseconds duration,
                         std::uint32_t epoch, Receiver& receiver, Convert convert,
                         Value value, const char* value_field, bool pressure, bool torque = false,
                         const std::string& mode = "") {
    stratadrive::socketcan::Endpoint endpoint(interface, can_id,
        {mode == "kernel-overflow" ? std::optional<int>{1024} : std::nullopt});
    stratadrive::fixture::RxPump pump(endpoint, mode);
    std::cout << std::unitbuf << "RX_READY\n";
    stratadrive::fixture::await_start();
    const auto enable_ns = stratadrive::socketcan::monotonic_time_ns();
    if (!receiver.start_session(epoch, enable_ns)) throw std::runtime_error("trusted session init failed");
    if (!pump.start_session({epoch, enable_ns})) throw std::runtime_error("trusted queue init failed");
    std::cout << "SESSION enable_ns=" << enable_ns << " epoch=" << epoch << '\n';
    // Ready/session handshake는 즉시 전달하고, 수신 trace는 cycle마다 한 번 flush한다.
    std::cout << std::nounitbuf;
    unsigned int accepted = 0;
    unsigned int rejected = 0;
    bool timeout_reported = false;
    bool had_current_sample = false;
    while (stratadrive::socketcan::monotonic_time_ns() - enable_ns < static_cast<std::uint64_t>(duration.count()) * 1000000ULL) {
        pump.collect(receiver);
        // Queue를 끝까지 비우지 않는다. Flood 중에도 매 cycle poll/age 검사를 실행한다.
        for (unsigned int count = 0; count < 8; ++count) {
            const auto received = pump.pop();
            if (!received) break;
            const auto now = stratadrive::socketcan::monotonic_time_ns();
            const auto result = receiver.receive(convert(*received), now);
            if (result.decision == stratadrive::can::ActuatorReceiveDecision::Accepted) ++accepted;
            else ++rejected;
            const auto& history = receiver.last_accepted();
            std::cout << "RX decision=" << stratadrive::fixture::decision_name(result.decision, pressure, torque)
                      << " at_ns=" << now
                      << " e2e=" << (result.e2e_status ? static_cast<int>(*result.e2e_status) : -1)
                      << " last_valid_ns=" << (history ? history->received_time_ns : 0)
                      << " last_source_ns=" << (history ? history->message.source_time_ns : 0)
                      << " last_seq=" << (history ? history->message.sequence : 0)
                      << " state=" << (history ? static_cast<int>(history->message.local_state) : -1)
                      << " origin=" << (history ? static_cast<int>(history->message.origin) : -1)
                      << " causal=" << (history ? history->message.causal_sequence : 0)
                      << " payload_length=" << static_cast<unsigned int>(received->payload_length)
                      << ' ' << value_field << '=' << (history ? value(history->message) : 0.0);
            trace_feedback(receiver.current_sample(now));
            std::cout << '\n';
        }
        const auto now = stratadrive::socketcan::monotonic_time_ns();
        const bool current = receiver.current_sample(now).has_value();
        if (had_current_sample && !current && receiver.health() != stratadrive::can::ActuatorReceiverHealth::ContinuityError) {
            std::cout << "SOURCE_EXPIRED at_ns=" << now
                      << " source_ns=" << receiver.last_accepted()->message.source_time_ns << '\n';
        }
        had_current_sample = current;
        if (receiver.health() == stratadrive::can::ActuatorReceiverHealth::ClockError) {
            throw std::runtime_error("receiver clock fault");
        }
        if (receiver.health() == stratadrive::can::ActuatorReceiverHealth::Timeout && !timeout_reported) {
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
              << " continuity=" << (receiver.health() == stratadrive::can::ActuatorReceiverHealth::ContinuityError)
              << " usable=" << receiver.current_sample(stratadrive::socketcan::monotonic_time_ns()).has_value() << '\n';
}

namespace {
void trace_bms(const std::optional<stratadrive::can::BmsCurrentSample>& current) {
    using namespace stratadrive::can;
    for (std::size_t group = 0; group < 3; ++group) {
        std::cout << " q" << group << '=' << (current ? stratadrive::fixture::quality_name(current->quality[group]) : "NONE");
    }
    bool allowed = false, ready = false;
    std::uint64_t input_ns = 0, expiry_ns = 0, soc_ns = 0;
    double charge = 0, discharge = 0, soc = 0;
    double voltage = 0, current_a = 0, temperature = 0;
    if (current) {
        allowed = bms_permission_allows_normal(*current); ready = bms_power_is_ready(*current);
        if (const auto* value = std::get_if<BmsPowerLimits>(&current->message.content)) {
            charge = value->charge_power_w.value_or(0); discharge = value->discharge_power_w.value_or(0); input_ns = value->input_time_ns;
        } else if (const auto* value = std::get_if<BmsPowerStatus>(&current->message.content)) {
            input_ns = value->input_time_ns; voltage = value->hv_bus_voltage_v.value_or(0);
        }
        else if (const auto* value = std::get_if<BmsPowerRequest>(&current->message.content)) {
            expiry_ns = value->expires_at_ns; allowed = value->action == BmsPowerAction::Enable;
        } else if (const auto* value = std::get_if<BmsDriveGrant>(&current->message.content)) {
            input_ns = value->input_time_ns; expiry_ns = value->expires_at_ns;
        } else if (const auto* value = std::get_if<BmsBatteryState>(&current->message.content)) {
            if (value->soc) { soc = value->soc->fraction; soc_ns = value->soc->source_time_ns; }
            if (value->electrical) {
                input_ns = value->electrical->source_time_ns; voltage = value->electrical->voltage_v;
                current_a = value->electrical->current_a;
            }
            if (value->temperature) temperature = value->temperature->celsius;
        }
    }
    std::cout << " allow=" << allowed << " ready=" << ready << " charge_w=" << charge
              << " discharge_w=" << discharge << " input_ns=" << input_ns
              << " expiry_ns=" << expiry_ns << " soc=" << soc << " soc_ns=" << soc_ns
              << " voltage_v=" << voltage << " current_a=" << current_a << " temperature_c=" << temperature;
}
}  // namespace

void bms_fixture(const char* interface, stratadrive::can::BmsFrameKind kind,
                 std::chrono::milliseconds duration, std::uint32_t epoch, bool forward,
                 const std::string& mode) {
    using namespace stratadrive;
    socketcan::Endpoint endpoint(interface, static_cast<std::uint16_t>(kind),
        {mode == "kernel-overflow" ? std::optional<int>{1024} : std::nullopt});
    fixture::RxPump pump(endpoint, mode);
    can::BmsReceiver receiver({kind, {{0, 1000}, {-500, 500}, {-60, 200}, 200000}});
    can::BmsTxState downstream{can::BmsFrameKind::DriveBatteryLimits};
    downstream.protection.counter = 5; // independent stream, within P05 startup window
    std::cout << std::unitbuf << "RX_READY\n";
    const auto plan = fixture::await_bms_start();
    const auto before_start = socketcan::monotonic_time_ns();
    if (plan.enable_ns > before_start) std::this_thread::sleep_for(std::chrono::nanoseconds(plan.enable_ns - before_start));
    if (!receiver.start_session(epoch, plan.enable_ns)) throw std::runtime_error("EV trusted session init failed");
    if (!pump.start_session({epoch, plan.enable_ns})) throw std::runtime_error("EV trusted queue init failed");
    std::cout << "SESSION enable_ns=" << plan.enable_ns << " epoch=" << epoch << '\n' << std::nounitbuf;
    bool rejoined = false, reported = false;
    auto monitoring_enable_ns = plan.enable_ns;
    can::BmsQualities previous{can::BmsFieldQuality::NotApplicable, can::BmsFieldQuality::NotApplicable, can::BmsFieldQuality::NotApplicable};
    while (socketcan::monotonic_time_ns() - plan.enable_ns < static_cast<std::uint64_t>(duration.count())*fixture::kMs) {
        auto now = socketcan::monotonic_time_ns();
        if (plan.rejoin_ns && !rejoined && now >= plan.rejoin_ns) {
            if (!receiver.start_session(epoch + 1, now)) throw std::runtime_error("EV explicit rejoin failed");
            if (!pump.start_session({epoch + 1, now})) throw std::runtime_error("EV queue rejoin failed");
            ++epoch; rejoined = true; reported = false;
            monitoring_enable_ns = now;
            std::cout << "REINIT at_ns=" << now << " epoch=" << epoch << '\n';
        }
        pump.collect(receiver);
        for (unsigned int count = 0; count < 8; ++count) {
            const auto received = pump.pop();
            if (!received) break;
            now = socketcan::monotonic_time_ns();
            const auto frame = socketcan::to_bms(*received);
            const auto decoded = can::decode_bms_frame(frame);
            // CAN provides only the lookup key. Values/authority come from stdin plan.
            const auto* parent = decoded ? plan.parent(decoded->epoch, decoded->causal_sequence) : nullptr;
            const auto result = receiver.receive(frame, now, parent);
            const auto& history = receiver.last_accepted();
            std::cout << "EV_RX decision=" << fixture::decision_name(result.decision)
                      << " issue=" << fixture::issue_name(result.issue) << " at_ns=" << now
                      << " id=" << frame.can_id << " length=" << static_cast<unsigned int>(frame.payload_length)
                      << " e2e=" << (result.e2e_status ? static_cast<int>(*result.e2e_status) : -1)
                      << " counter=" << static_cast<unsigned int>(frame.payload[31])
                      << " history_rx_ns=" << (history ? history->received_time_ns : 0)
                      << " source_ns=" << (history ? history->message.source_time_ns : 0)
                      << " seq=" << (history ? history->message.sequence : 0)
                      << " epoch=" << (history ? history->message.epoch : 0)
                      << " causal_seq=" << (history ? history->message.causal_sequence : 0)
                      << " local_state=" << (history ? static_cast<int>(history->message.local_state) : -1);
            for (std::size_t group = 0; group < 3; ++group) {
                std::cout << " rx_q" << group << '=' << fixture::quality_name(result.quality[group]);
            }
            trace_bms(receiver.current_sample(now)); std::cout << '\n';
            if (forward && result.decision == can::ActuatorReceiveDecision::Accepted) {
                const auto forwarded = can::forward_bms_limits(history->message, downstream);
                if (!forwarded) throw std::runtime_error("EV source-preserving relay encode failed");
                endpoint.send(socketcan::to_socketcan(*forwarded));
                std::cout << "FORWARD source_ns=" << history->message.source_time_ns << " seq=" << history->message.sequence
                          << " counter=" << static_cast<unsigned int>(forwarded->payload[31]) << '\n';
            }
        }
        now = socketcan::monotonic_time_ns();
        const auto current = receiver.current_sample(now);
        const can::BmsQualities qualities = current ? current->quality : can::BmsQualities{
            can::BmsFieldQuality::NotApplicable, can::BmsFieldQuality::NotApplicable, can::BmsFieldQuality::NotApplicable};
        if (qualities != previous) {
            std::cout << "EV_VIEW at_ns=" << now; trace_bms(current); std::cout << '\n'; previous = qualities;
        }
        if (receiver.health() == can::ActuatorReceiverHealth::ClockError) throw std::runtime_error("EV clock fault");
        if (receiver.health() == can::ActuatorReceiverHealth::Timeout && !reported) {
            const auto observation = kind == can::BmsFrameKind::BatteryState;
            auto reference = observation && receiver.last_accepted() ? receiver.last_accepted()->received_time_ns :
                             monitoring_enable_ns;
            if (!observation) {
                const std::size_t groups = kind == can::BmsFrameKind::PowerStatus || kind == can::BmsFrameKind::PowerLimits ||
                                           kind == can::BmsFrameKind::DriveBatteryLimits ? 2 : 1;
                for (std::size_t group = 0; group < groups; ++group) {
                    const auto value = receiver.last_usable_rx_time_ns(group).value_or(monitoring_enable_ns);
                    if (group == 0 || value < reference) reference = value;
                }
            }
            std::cout << "EV_TIMEOUT at_ns=" << now << " reference_ns=" << reference
                      << " elapsed_ns=" << now - reference << " epoch=" << epoch << " usable=" << current.has_value() << '\n';
            reported = true;
        }
        std::cout.flush(); std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    std::cout << "EV_END epoch=" << epoch << " timeout=" << reported
              << " continuity=" << (receiver.health() == can::ActuatorReceiverHealth::ContinuityError)
              << " usable=" << receiver.current_sample(socketcan::monotonic_time_ns()).has_value() << '\n';
}

template <typename Model, typename Convert, typename Decode, typename Value>
void response_model_fixture(const char* interface, std::uint32_t epoch, std::chrono::milliseconds duration,
                            Model& model, std::uint16_t command_id, Convert convert, Decode decode,
                            Value value, const char* value_field) {
    using namespace stratadrive;
    socketcan::Endpoint endpoint(interface, command_id);
    fixture::RxPump pump(endpoint, "");
    std::cout << std::unitbuf << "RX_READY\n";
    fixture::await_start();
    const auto enable = socketcan::monotonic_time_ns();
    if (!model.start_session(epoch, enable) || !pump.start_session({epoch, enable}))
        throw std::runtime_error("model trusted INIT failed");
    std::cout << "SESSION enable_ns=" << enable << " epoch=" << epoch << '\n' << std::nounitbuf;
    auto next_tick = enable + 10000000;
    while (socketcan::monotonic_time_ns() - enable < static_cast<std::uint64_t>(duration.count())*1000000) {
        pump.collect(model);
        for (unsigned int count = 0; count < 8; ++count) {
            const auto frame = pump.pop(); if (!frame) break;
            const auto now = socketcan::monotonic_time_ns();
            const auto result = model.receive(convert(*frame), now);
            std::cout << "MODEL_RX at_ns=" << now << " decision=" << fixture::decision_name(result.decision) << '\n';
        }
        const auto now = socketcan::monotonic_time_ns();
        if (now >= next_tick) {
            const auto frame = model.tick(now);
            if (!frame) throw std::runtime_error("model publication/clock failure");
            endpoint.send(socketcan::to_socketcan(*frame));
            const auto actual = decode(*frame).value();
            std::cout << "MODEL at_ns=" << now << ' ' << value_field << '=' << value(actual).value_or(0.0)
                      << " valid=" << value(actual).has_value()
                      << " state=" << static_cast<int>(actual.local_state)
                      << " origin=" << static_cast<int>(actual.origin)
                      << " causal=" << actual.causal_sequence << " seq=" << actual.sequence
                      << " fault=" << static_cast<int>(model.fault()) << '\n';
            next_tick = now + 10000000; // no backfilled ticks after a missed period
        }
        std::cout.flush(); std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
}

int main(int argc, char** argv) {
    try {
        using namespace stratadrive;
        if (argc != 5 && argc != 6) {
            throw std::invalid_argument("usage: actuator_socketcan_rx IFACE STREAM EPOCH DURATION_MS [wire|forward]; actuator or EV stream (harness stdin required)");
        }
        const auto epoch = fixture::positive_number(argv[3]);
        const auto duration_ms = fixture::positive_number(argv[4]);
        if (duration_ms > 10000) throw std::invalid_argument("fixture duration limit is 10000 ms");
        const auto duration = std::chrono::milliseconds{duration_ms};
        const std::string stream = argv[2];
        const std::string mode = argc == 6 ? argv[5] : "";
        const bool overflow = mode == "app-overflow" || mode == "kernel-overflow";
        if (stream == "cmd" && mode == "model") {
            vecu::SteeringActuator model(fixture::steering_model_config());
            response_model_fixture(argv[1], epoch, duration, model, can::kSteeringCommandId,
                socketcan::to_steering, can::decode_steering_frame,
                [](const auto& actual) { return actual.angle_rad; }, "angle_rad"); return 0;
        }
        if (stream == "brake-cmd" && mode == "model") {
            vecu::BrakeActuator model(fixture::brake_model_config());
            response_model_fixture(argv[1], epoch, duration, model, can::kBrakeCommandId,
                socketcan::to_brake, can::decode_brake_frame,
                [](const auto& actual) { return actual.pressure_pa; }, "pressure_pa"); return 0;
        }
        if (const auto ev_kind = fixture::bms_kind(stream)) {
            const bool forward = argc == 6 && std::string(argv[5]) == "forward";
            if ((argc == 6 && !forward && !overflow) || (forward && *ev_kind != can::BmsFrameKind::PowerLimits)) {
                throw std::invalid_argument("EV forwarding fixture is bms-limits only");
            }
            bms_fixture(argv[1], *ev_kind, duration, epoch, forward, mode);
            return 0;
        }
        const bool brake = stream == "brake-cmd" || stream == "brake-actual";
        const bool drive = stream == "drive-cmd" || stream == "drive-actual";
        if (argc == 6 && !overflow) {
            if (!brake || std::string(argv[5]) != "wire") throw std::invalid_argument("wire mode is Brake-only");
            brake_wire_fixture(argv[1], stream == "brake-actual", epoch, duration);
        } else if (drive) {
            const auto kind = stream == "drive-actual" ? can::DriveFrameKind::Actual : can::DriveFrameKind::Command;
            can::DriveReceiver receiver({kind, {-300, 500}, 100, 300});
            application_fixture(argv[1], static_cast<std::uint16_t>(kind), duration, epoch, receiver,
                [](const auto& frame) { return socketcan::to_drive(frame); },
                [](const auto& message) { return *message.torque_nm; }, "history_torque_nm", false, true, mode);
        } else if (brake) {
            const auto kind = stream == "brake-actual" ? can::BrakeFrameKind::Actual : can::BrakeFrameKind::Command;
            // 0..2 MPa는 fixture 설정이며 실제 차량 압력 calibration이 아니다.
            can::BrakeReceiver receiver({kind, 0, 2000000});
            application_fixture(argv[1], static_cast<std::uint16_t>(kind), duration, epoch, receiver,
                [](const auto& frame) { return socketcan::to_brake(frame); },
                [](const auto& message) { return *message.pressure_pa; }, "history_pressure_pa", true, false, mode);
        } else {
            const auto kind = fixture::kind(stream);
            can::SteeringReceiver receiver({kind, -0.5, 0.5});
            application_fixture(argv[1], static_cast<std::uint16_t>(kind), duration, epoch, receiver,
                [](const auto& frame) { return socketcan::to_steering(frame); },
                [](const auto& message) { return *message.angle_rad; }, "history_angle_rad", false, false, mode);
        }
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
    return 0;
}
