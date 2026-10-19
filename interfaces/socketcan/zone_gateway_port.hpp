#pragma once

#include "command_gateway.hpp"
#include "actuator_socketcan.hpp"

namespace stratadrive::socketcan {
// One TX endpoint per Zone. Physical/remote protection signaling is a separate
// supplied port, never an unchecked normal CAN frame or fabricated feedback.
class ZoneGatewayPort final : public zone::GatewayPort {
public:
    ZoneGatewayPort(Endpoint& endpoint, zone::ProtectionPort& protection) : endpoint_(endpoint), protection_(protection) {}
    std::uint64_t now_ns() noexcept override { return monotonic_time_ns(); }
    bool send(const zone::CommandFrame& frame, const central::CommandContext& context) noexcept override;
    bool protect(zone::ZoneScope scope, zone::ProtectionCause cause, std::uint64_t now_ns) noexcept override {
        return protection_.protect(scope, cause, now_ns);
    }
private:
    Endpoint& endpoint_;
    zone::ProtectionPort& protection_;
};
}  // namespace stratadrive::socketcan
