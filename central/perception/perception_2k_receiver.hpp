#pragma once

#include "perception_2k_frame.hpp"
#include <optional>

namespace stratadrive::central {
enum class Native2kReason { Session, Accepted, Clock, Identity, Invalid, SourceExpired,
    ReceiptExpired, Replay, Unavailable, StateStale };
// Single control/ingress owner. No inference, IO, blocking, clock advancement,
// heap allocation or vehicle authority. Copy data across threads before entry.
class Native2kReceiver {
public:
    bool start_session(Native2kSession session) noexcept;
    bool receive(const Native2kFrame&, Native2kNow) noexcept;
    void unavailable(Native2kNow) noexcept;
    const Native2kFrame* snapshot(Native2kNow) noexcept;
    // Valid only while snapshot() returns a current frame; empty when unavailable.
    const Native2kTracks& tracks() const noexcept { return tracks_; }
    Native2kReason reason() const noexcept { return reason_; }
    Native2kSession session() const noexcept { return session_; }
private:
    bool observe(Native2kNow) noexcept;
    bool reject(Native2kReason) noexcept;
    void update_tracks(const Native2kFrame&) noexcept;
    Native2kSession session_{};
    Native2kNow last_{};
    std::uint64_t last_frame_{0}, last_source_{0}, last_receipt_{0}, next_track_{1};
    bool clock_fault_{false};
    Native2kReason reason_{Native2kReason::Session};
    std::optional<Native2kFrame> current_;
    Native2kTracks tracks_{};
};
} // namespace stratadrive::central
