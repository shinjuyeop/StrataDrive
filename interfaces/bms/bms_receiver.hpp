#pragma once

#include "actuator_receiver_state.hpp"
#include "bms_frame_codec.hpp"
#include "bms_parent_context.hpp"

namespace stratadrive::can {
struct BmsPhysicalRanges {
    ActuatorValueRange voltage_v;
    ActuatorValueRange current_a;
    ActuatorValueRange temperature_c;
    double max_power_limit_w;
};
struct BmsReceiverConfig {
    BmsFrameKind kind;
    BmsPhysicalRanges physical;
    std::uint64_t max_source_age_ns{50000000ULL};
    std::uint64_t max_dependency_age_ns{70000000ULL};
    std::uint64_t timeout_ns{80000000ULL};
    std::uint64_t observation_age_ns{150000000ULL};
    std::uint64_t observation_timeout_ns{300000000ULL};
    bool allow_degraded_permission{false};
};
enum class BmsFieldQuality { NotApplicable, Unavailable, Usable, Stale, Invalid };
enum class BmsReceiveIssue { None, Expired, ParentMissing, ParentMismatch, ParentRollback };
using BmsQualities = std::array<BmsFieldQuality, 3>;
struct BmsReceiveResult {
    ActuatorReceiveDecision decision;
    std::optional<e2e::P05Status> e2e_status;
    BmsQualities quality{BmsFieldQuality::NotApplicable, BmsFieldQuality::NotApplicable,
                         BmsFieldQuality::NotApplicable};
    BmsReceiveIssue issue{BmsReceiveIssue::None};
};
struct BmsAcceptedSample { BmsMessage message; std::uint64_t received_time_ns; };
struct BmsCurrentSample { BmsMessage message; BmsQualities quality; };

// Metadata acceptance and each field's usable-RX clock are separate.
// Group map: Battery SOC/electrical/temperature, Limits charge/discharge,
// PowerStatus lifecycle/physical inputs, request/permission primary only.
class BmsReceiver {
public:
    explicit BmsReceiver(const BmsReceiverConfig& config);
    bool start_session(std::uint32_t epoch, std::uint64_t monitoring_enable_ns);
    BmsReceiveResult receive(const BmsFrame& frame, std::uint64_t now_ns,
                             const BmsParentContext* parent = nullptr);
    ActuatorReceiverHealth poll(std::uint64_t now_ns);
    void mark_continuity_lost(std::uint64_t now_ns);
    std::optional<BmsCurrentSample> current_sample(std::uint64_t now_ns);
    ActuatorReceiverHealth health() const { return health_; }
    std::uint32_t application_epoch() const { return cursor_.epoch(); }
    const std::optional<BmsAcceptedSample>& last_accepted() const { return accepted_; }
    const std::optional<std::uint64_t>& last_raw_rx_time_ns() const { return cursor_.last_raw_rx_time_ns(); }
    const std::optional<std::uint64_t>& last_usable_rx_time_ns(std::size_t group) const { return last_usable_rx_.at(group); }
private:
    BmsFieldQuality classify(std::size_t group, const BmsMessage& message, std::uint64_t now_ns) const;
    bool progresses(const BmsMessage& message, std::size_t group) const;
    BmsReceiveIssue check_parent(const BmsMessage& message, std::uint64_t now_ns,
                                const BmsParentContext* parent) const;
    const BmsReceiverConfig config_;
    BmsRxState e2e_;
    ActuatorReceiverState cursor_;
    ActuatorReceiverHealth health_{ActuatorReceiverHealth::NotInitialized};
    std::uint64_t session_start_ns_{0};
    std::optional<BmsAcceptedSample> accepted_;
    std::optional<BmsMessage> usable_;
    BmsQualities quality_{};
    std::array<std::optional<BmsMessage>, 3> group_cursor_{};
    std::array<std::optional<std::uint64_t>, 3> last_usable_rx_{};
    std::optional<BmsParentContext> parent_;
};
// Physical readiness is distinct from NORMAL or permission to apply torque.
bool bms_power_is_ready(const BmsCurrentSample& sample);
bool bms_permission_allows_normal(const BmsCurrentSample& sample);
}  // namespace stratadrive::can
