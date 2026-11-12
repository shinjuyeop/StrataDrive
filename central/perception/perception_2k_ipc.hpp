#pragma once

#include "perception_2k_receiver.hpp"
#include <array>

namespace stratadrive::central {
// Same-host, explicitly little-endian binary records over an inherited private
// SOCK_SEQPACKET pair. No model/controller work in the sender, no blocking IO in
// the native owner. This version is SHADOW ONLY and cannot request protection.
inline constexpr std::size_t kPerceptionIpcHeader=80, kPerceptionIpcResult=184;
inline constexpr std::size_t kPerceptionIpcMax=kPerceptionIpcResult+48*kMaxDetections;
enum class PerceptionIpcKind : std::uint32_t { Unavailable=0, Poll=1, Result=2 };
enum class PerceptionIpcFault { None, Encoding, Identity, Sequence, State, TransportAge, Disconnected, Io };
struct PerceptionIpcMessage {
    PerceptionIpcKind kind{PerceptionIpcKind::Unavailable};
    std::uint64_t sequence{0}, sender_wall_ns{0}, state_frame{0};
    std::uint32_t epoch{0};
    std::uint64_t source_clock{0},wall_clock{0};
    Native2kNow observed{};
    Native2kFrame result{};
};
bool decode_perception_ipc(const std::uint8_t*,std::size_t,PerceptionIpcMessage&) noexcept;
std::size_t encode_perception_ipc(const PerceptionIpcMessage&,std::array<std::uint8_t,kPerceptionIpcMax>&) noexcept;
struct PerceptionIpcView {
    bool initialized{false},available{false},disconnected{false},state_fault{false};
    Native2kReason reason{Native2kReason::Session};
    PerceptionIpcFault transport_fault{PerceptionIpcFault::None};
    std::uint64_t received{0},rejected{0},accepted_results{0},polls{0},unavailable{0},budget_hits{0};
    std::uint64_t sequence{0},observed_wall_ns{0},state_frame{0},state_source_ns{0},state_received_wall_ns{0};
    std::uint64_t source_enable_ns{0},wall_enable_ns{0};
    std::uint64_t frame{0},source_ns{0},expires_ns{0},received_wall_ns{0},wall_expires_ns{0};
    std::size_t count{0},tracks{0};
};
class PerceptionIpcShadow {
public:
    // Takes ownership on successful construction. Identity comes from trusted
    // process setup, never from an incoming message. No path-based discovery.
    PerceptionIpcShadow(int fd,std::uint32_t epoch,std::uint64_t source_clock,std::uint64_t wall_clock);
    ~PerceptionIpcShadow();
    PerceptionIpcShadow(const PerceptionIpcShadow&)=delete;
    PerceptionIpcShadow& operator=(const PerceptionIpcShadow&)=delete;
    // The actual native INIT export supplies this wall-domain enable time.
    bool observe_native_init(std::uint32_t epoch,std::uint64_t wall_enable_ns) noexcept;
    PerceptionIpcView poll(std::uint64_t wall_now_ns) noexcept;
private:
    void reject(PerceptionIpcFault,std::uint64_t) noexcept;
    void consume(const PerceptionIpcMessage&,std::uint64_t) noexcept;
    void clear_current(std::uint64_t) noexcept;
    int fd_;
    const std::uint32_t epoch_;
    const std::uint64_t source_clock_,wall_clock_;
    Native2kReceiver receiver_;
    PerceptionIpcView view_{};
    std::uint64_t last_wall_{0},root_enable_{0};
};
} // namespace stratadrive::central
