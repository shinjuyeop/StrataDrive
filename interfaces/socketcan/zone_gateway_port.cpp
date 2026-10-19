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

namespace stratadrive::socketcan {
bool RearPowerGatewayPort::send(const can::BmsFrame& frame,const zone::RearPowerDelivery& delivery) noexcept {
    try {
        const auto native=to_socketcan(frame);
        return now_ns()<delivery.expires_at_ns && control_.stage_context(frame,delivery) && endpoint_.send_before(native,delivery.expires_at_ns);
    } catch (...) { return false; }
}
} // namespace stratadrive::socketcan
