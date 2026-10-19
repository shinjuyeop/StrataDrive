#include "local_safety.hpp"

namespace stratadrive::zone {
bool LocalSafety::start_session(std::uint32_t epoch) {
    if (epoch == 0 || epoch <= epoch_) return false;
    epoch_ = epoch; decision_ = {}; return true;
}
void LocalSafety::request(ProtectionCause cause) {
    if (epoch_ != 0 && decision_.cause == ProtectionCause::None && cause != ProtectionCause::None) decision_.cause = cause;
}
void LocalSafety::dispatch(ProtectionPort& port, ZoneScope scope, std::uint64_t now) {
    if (decision_.cause != ProtectionCause::None && !decision_.handoff_accepted) {
        decision_.handoff_accepted = port.protect(scope, decision_.cause, now);
    }
}
}  // namespace stratadrive::zone
