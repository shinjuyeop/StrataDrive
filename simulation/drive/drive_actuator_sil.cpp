#include "drive_actuator_sil.hpp"

namespace stratadrive::simulation {
bool DriveActuatorSil::start_session(std::uint32_t epoch, std::uint64_t enable_ns) {
    if (!ecu_.start_session({epoch, 1, enable_ns})) return false;
    plant_.begin(1, enable_ns); return true;
}
can::DriveReceiveResult DriveActuatorSil::receive(const can::DriveFrame& frame, std::uint64_t now_ns) {
    const auto result = ecu_.receive(frame, now_ns); plant_.apply(ecu_.output()); return result;
}
void DriveActuatorSil::mark_continuity_lost(std::uint64_t now_ns) { ecu_.mark_continuity_lost(now_ns); plant_.apply(ecu_.output()); }
std::optional<can::DriveFrame> DriveActuatorSil::tick(std::uint64_t now_ns) {
    if (!ecu_.prepare(now_ns)) return std::nullopt;
    // Preserve M2 endpoint policy: skip an unobserved control interval; newly
    // detected zero requests are not applied retroactively to prior physics.
    if (ecu_.execution_gap()) plant_.advance(now_ns, true);
    if (!plant_.apply(ecu_.output()) || !plant_.advance(now_ns, false)) { ecu_.mark_output_rejected(now_ns); return std::nullopt; }
    const auto frame = ecu_.complete(plant_.capture(now_ns), now_ns);
    plant_.apply(ecu_.output()); return frame;
}
} // namespace stratadrive::simulation
