#pragma once

#include "perception_frame.hpp"
#include <optional>

namespace stratadrive::central {
enum class PerceptionReason { Accepted, Session, Clock, Identity, Invalid, Stale, Replay };
// Single owner. Session authority is supplied by the trusted root, never learned
// from an image/result. This component has no vehicle/controller dependency.
class PerceptionReceiver {
public:
    bool start_session(std::uint32_t epoch, std::uint64_t clock_instance,
                       std::uint64_t enable_ns) noexcept;
    bool receive(const PerceptionFrame&, std::uint64_t now_ns) noexcept;
    const PerceptionFrame* snapshot(std::uint64_t now_ns) noexcept;
    PerceptionReason reason() const noexcept { return reason_; }
private:
    bool observe_clock(std::uint64_t now_ns) noexcept;
    bool reject(PerceptionReason reason) noexcept;
    std::uint32_t epoch_{0};
    std::uint64_t clock_{0}, enable_{0}, last_now_{0}, last_frame_{0}, last_source_{0};
    bool clock_fault_{false};
    PerceptionReason reason_{PerceptionReason::Session};
    std::optional<PerceptionFrame> current_;
};
} // namespace stratadrive::central
