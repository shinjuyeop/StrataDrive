#pragma once
#include "allocated_commands.hpp"
#include "power_commands.hpp"

namespace stratadrive::zone {
using CommandFrame = std::variant<can::SteeringFrame, can::BrakeFrame, can::DriveFrame>;
struct RearPowerDelivery {
    can::BmsMessage message;
    std::optional<can::BmsParentContext> parent; // retain independently authorized context
    std::uint64_t expires_at_ns{0};
};
} // namespace stratadrive::zone
