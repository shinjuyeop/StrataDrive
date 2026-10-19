#include "zone_leaf_protection.hpp"

namespace stratadrive::simulation {
bool ZoneLeafProtection::protect(zone::ZoneScope scope, zone::ProtectionCause cause, std::uint64_t now) noexcept {
    if (cause == zone::ProtectionCause::None) return false;
    if (scope == zone::ZoneScope::Front && steering_ && brake_) {
        steering_->request_local_protection(now); brake_->request_local_protection(now);
        return steering_->fault() != vecu::SteeringFault::None && brake_->fault() != vecu::BrakeFault::None &&
            steering_->output().mode == steering::ActuationMode::Hold && brake_->output().mode == brake::ActuationMode::Protect;
    }
    if (scope == zone::ZoneScope::Rear && drive_) {
        drive_->request_local_protection(now);
        return drive_->decision().fault != vecu::DriveGateFault::None && drive_->output().mode == drive::ActuationMode::Zero;
    }
    return false;
}
}  // namespace stratadrive::simulation
