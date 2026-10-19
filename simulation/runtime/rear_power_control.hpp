#pragma once

#include "rear_power_gateway.hpp"
#include "drive_controller.hpp"
#include "power_controller.hpp"

namespace stratadrive::simulation {
// Same-host SIL sideband/control binding. Stage only from trusted gateway TX,
// never from received CAN. Exact issued frames recover independently supplied roots.
class RearPowerControl final : public zone::RearPowerControlPort {
public:
    RearPowerControl(vecu::DriveController& drive,vecu::PowerController& power):drive_(drive),power_(power) {}
    bool start_session(std::uint32_t epoch);
    bool stage_context(const can::BmsFrame& frame,const zone::RearPowerDelivery& delivery) noexcept override;
    std::optional<zone::RearPowerDelivery> context_for(const can::BmsFrame& frame,std::uint64_t now_ns) const;
    bool arm_normal_commands(std::uint32_t epoch,std::uint64_t now_ns) noexcept override;
    bool protect(zone::ZoneScope scope,zone::ProtectionCause cause,std::uint64_t now_ns) noexcept override;
private:
    struct Entry { can::BmsFrame frame; zone::RearPowerDelivery delivery; };
    vecu::DriveController& drive_;
    vecu::PowerController& power_;
    std::array<std::optional<Entry>,16> issued_{};
    std::size_t next_{0};
    std::uint32_t epoch_{0};
};
} // namespace stratadrive::simulation
