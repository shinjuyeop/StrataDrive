#include "steering_sil.hpp"

namespace stratadrive::simulation {
bool SteeringSil::start_session(std::uint32_t epoch, std::uint64_t enable_ns, ActuatorCommandStartup startup) {
    if (!ecu_.start_session({epoch, plant_.model_epoch(), enable_ns}, startup)) return false;
    if (!plant_.begin(enable_ns)) return false;
    applied_.reset(); return true;
}
bool SteeringSil::apply(std::uint64_t now_ns) {
    const auto& out = ecu_.output();
    if (out.mode == steering::ActuationMode::Hold) return plant_.hold(now_ns);
    if (applied_ && applied_->mode == out.mode && applied_->target_rad == out.target_rad &&
        applied_->issued_time_ns == out.issued_time_ns) return true;
    if (!plant_.set_target(out.target_rad, out.issued_time_ns)) return false;
    applied_ = out; return true;
}
can::SteeringReceiveResult SteeringSil::receive(const can::SteeringFrame& frame, std::uint64_t now_ns) {
    const auto result = ecu_.receive(frame, now_ns); apply(now_ns); return result;
}
void SteeringSil::mark_continuity_lost(std::uint64_t now_ns) { ecu_.mark_continuity_lost(now_ns); apply(now_ns); }
std::optional<can::SteeringFrame> SteeringSil::tick(std::uint64_t now_ns, const SteeringResponseInjection& injection,
        SteeringSensorAction action, std::optional<double> sensed_override) {
    if (!ecu_.prepare(now_ns)) return std::nullopt;
    if (!apply(now_ns)) ecu_.mark_output_rejected(now_ns);
    bool valid = true;
    if (ecu_.output().mode == steering::ActuationMode::Hold) valid = plant_.hold(now_ns);
    else valid = plant_.advance(now_ns, injection);
    if (!valid) ecu_.mark_io_error(now_ns);
    const auto sensor = valid ? plant_.capture(action, sensed_override) : std::nullopt;
    const auto frame = ecu_.complete(sensor, now_ns);
    if (!apply(now_ns)) { ecu_.mark_output_rejected(now_ns); apply(now_ns); return std::nullopt; }
    return frame;
}
} // namespace stratadrive::simulation
