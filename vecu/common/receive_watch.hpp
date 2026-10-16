#pragma once

#include <cstdint>
#include <optional>
#include <stdexcept>

namespace stratadrive::runtime {
enum class ReceiveHealth { Waiting, Receiving, Timeout, ClockError };

// Independent monitor owner only. Capture the accepted timestamp BEFORE now:
// an executor may publish concurrently, so a later timestamp must not be
// compared with an earlier monitor clock sample. Raw RX is never this input.
class ReceiveWatch {
public:
    ReceiveWatch(std::uint64_t enable_ns, std::uint64_t timeout_ns)
        : enable_(enable_ns), timeout_(timeout_ns) {
        if(enable_ns==0 || timeout_ns==0 || timeout_ns>1000000000) throw std::invalid_argument("ReceiveWatch timing");
    }
    ReceiveHealth poll(std::optional<std::uint64_t> last_valid, std::uint64_t now_ns) {
        if(health_==ReceiveHealth::ClockError || health_==ReceiveHealth::Timeout) return health_;
        if(now_ns<enable_ || (last_poll_ && now_ns<*last_poll_) ||
            (last_valid && (*last_valid<enable_ || *last_valid>now_ns || (accepted_ && *last_valid<*accepted_)))) {
            health_=ReceiveHealth::ClockError; detected_=now_ns; return health_;
        }
        last_poll_=now_ns;
        if(last_valid) accepted_=last_valid;
        if(now_ns-accepted_.value_or(enable_)>=timeout_) { health_=ReceiveHealth::Timeout; detected_=now_ns; }
        else health_=accepted_ ? ReceiveHealth::Receiving : ReceiveHealth::Waiting;
        return health_;
    }
    ReceiveHealth health() const { return health_; }
    std::optional<std::uint64_t> last_valid() const { return accepted_; }
    std::optional<std::uint64_t> detected() const { return detected_; }
private:
    const std::uint64_t enable_,timeout_;
    ReceiveHealth health_{ReceiveHealth::Waiting};
    std::optional<std::uint64_t> last_poll_,accepted_,detected_;
};
} // namespace stratadrive::runtime
