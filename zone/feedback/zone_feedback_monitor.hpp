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
struct ZoneFeedbackObservation {
    ZoneFeedbackFault fault{ZoneFeedbackFault::None};
    ZoneScope scope{ZoneScope::Front};
    std::uint32_t epoch{0},healthy_mask{0};
    std::uint64_t enable_ns{0},observed_ns{0};
    ZoneFeedbackInputs inputs,last_healthy;
    std::optional<std::uint64_t> violation_ns;
};
// Single owner, 10 ms runnable. Feedback must come from independent receiver
// current_sample(now), never diagnostic last_accepted(). Gateway polling and
// protection use the same owner's clock. Does not reset any remote controller.
class ZoneFeedbackMonitor {
public:
    explicit ZoneFeedbackMonitor(CommandGateway& commands, RearPowerGateway* power = nullptr,std::uint64_t minimum_interval_ns = 10000000ULL);
    bool start_session(std::uint32_t epoch, std::uint64_t enable_ns);
    std::optional<ZoneHealthSnapshot> tick(const ZoneFeedbackInputs& inputs, std::uint64_t now_ns);
    ZoneFeedbackFault fault() const { return fault_; }
    const std::optional<ZoneFeedbackObservation>& fault_observation() const { return first_fault_; }
    const std::optional<ZoneFeedbackObservation>& success_observation() const { return success_; }
private:
    void fail(ZoneFeedbackFault fault,std::uint64_t now,const ZoneFeedbackInputs&,std::optional<std::uint64_t> violation=std::nullopt);
    ZoneFeedbackObservation observation(ZoneFeedbackFault,std::uint64_t,const ZoneFeedbackInputs&) const;
    CommandGateway& commands_;
    RearPowerGateway* power_;
    const std::uint64_t minimum_interval_ns_;
    std::uint32_t epoch_{0};
    std::uint64_t enable_ns_{0}, observed_ns_{0}, sequence_{0};
    std::optional<std::uint64_t> tick_ns_;
    std::array<bool,5> seen_{};
    ZoneFeedbackFault fault_{ZoneFeedbackFault::None};
    ZoneFeedbackInputs last_healthy_;
    std::optional<ZoneFeedbackObservation> first_fault_,success_;
};
}  // namespace stratadrive::zone
