#include "session_reset.hpp"
#include <cmath>

namespace stratadrive::simulation {
namespace {
constexpr std::uint64_t kEvidenceAgeNs=20000000ULL;
bool fresh(std::uint64_t source,std::uint64_t input,std::uint64_t now) {
    return input<=source && source<=now && now-input<=kEvidenceAgeNs;
}
}
bool session_reset_safe(const SessionResetEvidence& e,std::uint32_t model_epoch,std::uint64_t now) {
    if(model_epoch==0 || !e.wheel_speed_rad_s || !e.torque || !e.power) return false;
    const auto& speed=*e.wheel_speed_rad_s; const auto& torque=*e.torque; const auto& power=*e.power;
    if(speed.identity.epoch!=model_epoch || torque.model_epoch!=model_epoch || power.identity.epoch!=model_epoch ||
        !fresh(speed.identity.source_time_ns,speed.input_time_ns,now) || !fresh(torque.source_time_ns,torque.source_time_ns,now) ||
        !fresh(power.identity.source_time_ns,power.input_time_ns,now)) return false;
    return std::isfinite(speed.value) && speed.value>=0 && speed.value<=.01 &&
        std::isfinite(torque.torque_nm) && std::abs(torque.torque_nm)<=.1 && power.bus_voltage_v &&
        std::isfinite(*power.bus_voltage_v) && *power.bus_voltage_v>=0 && *power.bus_voltage_v<=30 && power.contactors &&
        !power.contactors->positive && !power.contactors->negative && !power.contactors->precharge;
}
} // namespace stratadrive::simulation
