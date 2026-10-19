#pragma once

#include "command_gateway.hpp"
#include "rear_power_gateway.hpp"
#include "feedback_health.hpp"

namespace stratadrive::zone {
struct ZoneFeedbackInputs {
    std::optional<can::SteeringMessage> steering;
    std::optional<can::BrakeMessage> brake;
    std::optional<can::DriveMessage> drive;
    std::optional<can::BmsCurrentSample> power_status, power_limits;
};
enum class ZoneFeedbackFault { None, ClockError, ControlDeadline, InputsUnavailable, SourceProtection, GatewayProtection, SequenceExhausted };
// Single owner, 10 ms runnable. Feedback must come from independent receiver
// current_sample(now), never diagnostic last_accepted(). Gateway polling and
// protection use the same owner's clock. Does not reset any remote controller.
class ZoneFeedbackMonitor {
public:
    explicit ZoneFeedbackMonitor(CommandGateway& commands, RearPowerGateway* power = nullptr,std::uint64_t minimum_interval_ns = 10000000ULL);
    bool start_session(std::uint32_t epoch, std::uint64_t enable_ns);
    std::optional<ZoneHealthSnapshot> tick(const ZoneFeedbackInputs& inputs, std::uint64_t now_ns);
    ZoneFeedbackFault fault() const { return fault_; }
private:
    void fail(ZoneFeedbackFault fault);
    CommandGateway& commands_;
    RearPowerGateway* power_;
    const std::uint64_t minimum_interval_ns_;
    std::uint32_t epoch_{0};
    std::uint64_t enable_ns_{0}, observed_ns_{0}, sequence_{0};
    std::optional<std::uint64_t> tick_ns_;
    std::array<bool,5> seen_{};
    ZoneFeedbackFault fault_{ZoneFeedbackFault::None};
};
}  // namespace stratadrive::zone
