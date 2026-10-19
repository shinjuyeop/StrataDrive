#include "brake_sil.hpp"

namespace stratadrive::simulation {
bool BrakeSil::start_session(std::uint32_t epoch, std::uint64_t enable_ns, ActuatorCommandStartup startup) {
    if (!ecu_.start_session({epoch, plant_.model_epoch(), enable_ns}, startup)) return false;
    if (!plant_.begin(enable_ns)) return false;
    applied_.reset(); return true;
}
bool BrakeSil::apply(std::uint64_t now_ns) {
    const auto& out = ecu_.output();
    (void)now_ns;
    if (out.mode == brake::ActuationMode::Hold) return plant_.hold(now_ns);
    if (applied_ && applied_->mode == out.mode && applied_->target_pa == out.target_pa &&
        applied_->issued_time_ns == out.issued_time_ns) return true;
    const bool ok = out.mode == brake::ActuationMode::Protect ?
        plant_.request_protection(out.target_pa, out.issued_time_ns) : plant_.set_target(out.target_pa, out.issued_time_ns);
    if (!ok) return false;
    applied_ = out; return true;
}
can::BrakeReceiveResult BrakeSil::receive(const can::BrakeFrame& frame, std::uint64_t now_ns) {
    const auto result = ecu_.receive(frame, now_ns); apply(now_ns); return result;
}
void BrakeSil::mark_continuity_lost(std::uint64_t now_ns) { ecu_.mark_continuity_lost(now_ns); apply(now_ns); }
std::optional<can::BrakeFrame> BrakeSil::tick(std::uint64_t now_ns, const BrakePressureResponseInjection& injection,
        BrakeSensorAction action, std::optional<double> sensed_override) {
    if (!ecu_.prepare(now_ns)) return std::nullopt;
    if (!apply(now_ns)) ecu_.mark_output_rejected(now_ns);
    const bool valid = ecu_.execution_gap() ? plant_.skip_to(now_ns) : plant_.advance(now_ns, injection);
    if (!valid) ecu_.mark_io_error(now_ns);
    const auto sensor = valid ? plant_.capture(action, sensed_override) : std::nullopt;
    const auto frame = ecu_.complete(sensor, now_ns);
    if (!apply(now_ns)) { ecu_.mark_output_rejected(now_ns); apply(now_ns); return std::nullopt; }
    return frame;
}
} // namespace stratadrive::simulation
