#pragma once

#include "session_control.hpp"

#include <array>
#include <atomic>
#include <optional>
#include <type_traits>

namespace stratadrive::session {
// Exactly one producer and one consumer. No allocation, blocking or overwrite.
// Overflow closes the link permanently. Replace it only after both owners join;
// a new application Epoch cannot repair a transport with lost continuity.
template<class T, std::size_t Capacity> class SessionMailbox {
    static_assert(Capacity>0);
    static_assert(std::is_trivially_copyable_v<T>);
    static_assert(std::atomic<std::size_t>::is_always_lock_free);
    static_assert(std::atomic<bool>::is_always_lock_free);
public:
    bool push(const T& item) noexcept {
        if(failed()) return false;
        const auto write=write_.load(std::memory_order_relaxed);
        const auto next=(write+1)%(Capacity+1);
        if(next==read_.load(std::memory_order_acquire)) {
            failed_.store(true,std::memory_order_release); return false;
        }
        items_[write]=item;
        write_.store(next,std::memory_order_release);
        return !failed();
    }
    std::optional<T> pop() noexcept {
        if(failed()) return std::nullopt;
        const auto read=read_.load(std::memory_order_relaxed);
        if(read==write_.load(std::memory_order_acquire)) return std::nullopt;
        const auto item=items_[read];
        read_.store((read+1)%(Capacity+1),std::memory_order_release);
        return failed()?std::nullopt:std::optional<T>{item};
    }
    bool failed() const noexcept { return failed_.load(std::memory_order_acquire); }
private:
    std::array<T,Capacity+1> items_{};
    std::atomic<std::size_t> read_{0},write_{0};
    std::atomic<bool> failed_{false};
};
constexpr std::size_t kSessionQueueCapacity=8;
struct SessionLink {
    SessionMailbox<Control,kSessionQueueCapacity> controls;
    SessionMailbox<Ack,kSessionQueueCapacity> acks;
    bool failed() const { return controls.failed() || acks.failed(); }
};
using SessionLinks=std::array<SessionLink,kRoleCount>;
}  // namespace stratadrive::session
