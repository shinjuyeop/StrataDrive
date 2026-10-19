#include "zone_gateway_port.hpp"

namespace stratadrive::socketcan {
bool ZoneGatewayPort::send(const zone::CommandFrame& frame, const central::CommandContext& context) noexcept {
    try {
        const auto native = std::visit([](const auto& f) { return to_socketcan(f); }, frame);
        return endpoint_.send_before(native, context.expires_at_ns);
    } catch (...) {
        // No retry/restamp after partial writes, EAGAIN or an invalid endpoint.
        return false;
    }
}
}  // namespace stratadrive::socketcan
