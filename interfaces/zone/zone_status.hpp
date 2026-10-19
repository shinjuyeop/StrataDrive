#pragma once

#include "actuator_receiver_state.hpp"

namespace stratadrive::zone {
enum class ZoneScope { Front, Rear };
enum class ZonePhase { Waiting, Ready, Active, Terminal, FailSafe };
// Same-host typed contract. No serialization, authentication or clock mapping.
// Source time belongs to this status observation, never to its child feedback.
struct ZoneHealthSnapshot : can::ActuatorMetadata {
    ZoneScope scope{ZoneScope::Front};
    ZonePhase phase{ZonePhase::Waiting};
    bool ready_for_normal{false};
};
bool valid_zone_status(const ZoneHealthSnapshot& status);
bool zone_inputs_healthy(const ZoneHealthSnapshot& status);

// Independent ingress per Zone. Replays/rejected packets cannot renew liveness;
// timeout/continuity and reported protection latch until trusted newer INIT.
class ZoneStatusReceiver {
public:
    explicit ZoneStatusReceiver(ZoneScope scope);
    bool start_session(std::uint32_t epoch, std::uint64_t enable_ns);
    can::ActuatorReceiveDecision receive(const ZoneHealthSnapshot& status, std::uint64_t now_ns);
    void mark_continuity_lost(std::uint64_t now_ns);
    std::optional<ZoneHealthSnapshot> current_sample(std::uint64_t now_ns);
private:
    ZoneScope scope_;
    can::ActuatorReceiverState state_{{30000000ULL,80000000ULL}};
    std::optional<ZoneHealthSnapshot> accepted_;
    bool protection_seen_{false}, terminal_seen_{false}, inputs_seen_{false};
};
}  // namespace stratadrive::zone
