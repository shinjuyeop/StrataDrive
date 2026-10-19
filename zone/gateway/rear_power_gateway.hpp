#pragma once

#include "local_safety.hpp"
#include "actuator_stop_lease.hpp"
#include "power_commands.hpp"
#include "bounded_rx_queue.hpp"

namespace stratadrive::zone {
struct RearPowerDelivery {
    can::BmsMessage message;
    std::optional<can::BmsParentContext> parent; // retain independently authorized context
    std::uint64_t expires_at_ns{0};
};
class RearPowerControlPort : public ProtectionPort {
public:
    virtual bool stage_context(const can::BmsFrame& frame, const RearPowerDelivery& delivery) noexcept = 0;
    virtual bool arm_normal_commands(std::uint32_t epoch, std::uint64_t now_ns) noexcept = 0;
};
class RearPowerPort : public ProtectionPort {
public:
    virtual std::uint64_t now_ns() noexcept = 0;
    virtual bool send(const can::BmsFrame& frame, const RearPowerDelivery& delivery) noexcept = 0;
    // Trusted coordinator invocation, never triggered by an AllowNormal packet.
    virtual bool arm_normal_commands(std::uint32_t epoch, std::uint64_t now_ns) noexcept = 0;
};
enum class RearPowerResult { Accepted, Rejected, NotInitialized, Latched, ParentRejected, NotReady };
struct RearPowerDecision {
    SafetyDecision safety;
    bool normal_armed{false};
    std::size_t pending{0};
};
class RearPowerGateway {
public:
    static constexpr std::size_t kCapacity = 8;
    explicit RearPowerGateway(RearPowerPort& port);
    bool start_session(std::uint32_t epoch, std::uint64_t enable_ns);
    RearPowerResult authorize_request(const central::LifecycleRequest& root);
    RearPowerResult enqueue_power(const can::BmsMessage& request);
    RearPowerResult enqueue_permission(const can::BmsMessage& permission);
    RearPowerResult receive_limits(const can::BmsFrame& frame);
    RearPowerResult receive_status(const can::BmsFrame& frame);
    bool arm_normal_commands();
    bool select_normal_stop(const ActuatorStopLease& lease);
    std::uint32_t application_epoch() const { return epoch_; }
    std::uint64_t observed_time_ns() const { return observed_ns_; }
    std::size_t dispatch(); // <=8 scans / <=3 independent BMS writes
    RearPowerDecision poll();
    void mark_continuity_lost();
    std::optional<can::BmsCurrentSample> power_status();
    std::optional<can::BmsCurrentSample> power_limits();
private:
    struct SentPower { can::BmsMessage message; std::optional<can::BmsParentContext> parent; std::uint64_t expires_at_ns; };
    bool refresh();
    void fail(ProtectionCause cause);
    bool ready() const;
    const SentPower* acknowledged(const can::BmsCurrentSample& status) const;
    bool grant_supported(const can::BmsMessage& grant) const;
    RearPowerResult enqueue(const can::BmsMessage& message, bool permission);
    RearPowerPort& port_;
    LocalSafety safety_;
    can::BmsReceiver power_rx_, permission_rx_, limits_rx_, status_rx_;
    can::BmsTxState power_validation_{can::BmsFrameKind::PowerRequest}, permission_validation_{can::BmsFrameKind::DrivePermission};
    can::BmsTxState power_tx_{can::BmsFrameKind::PowerRequest}, permission_tx_{can::BmsFrameKind::DrivePermission}, limits_tx_{can::BmsFrameKind::DriveBatteryLimits};
    can::BoundedRxQueue<RearPowerDelivery,kCapacity> queue_;
    std::optional<central::LifecycleRequest> root_;
    std::array<std::optional<can::BmsCurrentSample>,8> status_history_{};
    std::array<std::optional<SentPower>,16> sent_power_{};
    std::array<std::optional<std::uint64_t>,4> expiry_{};
    StopLeaseState stop_;
    std::uint32_t epoch_{0};
    std::uint64_t enable_ns_{0}, observed_ns_{0};
    bool normal_armed_{false};
};
}  // namespace stratadrive::zone
