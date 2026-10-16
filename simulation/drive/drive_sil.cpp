#include "drive_sil.hpp"

namespace stratadrive::simulation {
bool DriveSil::start_session(std::uint32_t epoch, std::uint32_t model_epoch, std::uint64_t enable_ns) {
    if (!ecu_.start_session({epoch, model_epoch, enable_ns})) return false;
    plant_.begin(model_epoch, enable_ns); return true;
}
can::DriveReceiveResult DriveSil::receive_command(const can::DriveFrame& frame, std::uint64_t now_ns) {
    const auto result = ecu_.receive_command(frame, now_ns); plant_.apply(ecu_.output()); return result;
}
can::BmsReceiveResult DriveSil::receive_limits(const can::BmsFrame& frame, std::uint64_t now_ns) {
    const auto result = ecu_.receive_limits(frame, now_ns); plant_.apply(ecu_.output()); return result;
}
can::BmsReceiveResult DriveSil::receive_permission(const can::BmsFrame& frame, std::uint64_t now_ns, const can::BmsParentContext* parent) {
    const auto result = ecu_.receive_permission(frame, now_ns, parent); plant_.apply(ecu_.output()); return result;
}
drive::SensorResult DriveSil::observe_local(const drive::LocalSensors& sensors, std::uint64_t now_ns) {
    const auto result = ecu_.observe_local(sensors, now_ns); plant_.apply(ecu_.output()); return result;
}
void DriveSil::mark_continuity_lost(std::uint64_t now_ns) { ecu_.mark_continuity_lost(now_ns); plant_.apply(ecu_.output()); }
std::optional<can::DriveFrame> DriveSil::tick(std::uint64_t now_ns) {
    if (!ecu_.prepare(now_ns)) return std::nullopt;
    // Preserve M2 endpoint policy: skip an unobserved control interval; newly
    // detected zero requests are not applied retroactively to prior physics.
    if (ecu_.execution_gap()) plant_.advance(now_ns, true);
    if (!plant_.apply(ecu_.output()) || !plant_.advance(now_ns, false)) { ecu_.mark_output_rejected(now_ns); return std::nullopt; }
    const auto frame = ecu_.complete(plant_.capture(now_ns), now_ns);
    plant_.apply(ecu_.output()); return frame;
}
} // namespace stratadrive::simulation
