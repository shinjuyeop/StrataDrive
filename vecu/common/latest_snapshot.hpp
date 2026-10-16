#pragma once

#include <array>
#include <atomic>
#include <cstdint>
#include <optional>
#include <stdexcept>
#include <type_traits>

namespace stratadrive::runtime {
// Exactly one publisher and one reader. Three slots have separate writer,
// reader and exchange ownership. No slot being copied can become writable
// until the reader exchanges it back on its NEXT call. This is latest-value
// delivery: unread intermediate publications may be superseded intentionally.
template<class T> class LatestSnapshot {
    static_assert(std::is_nothrow_copy_assignable_v<T> && std::is_nothrow_copy_constructible_v<T>);
public:
    LatestSnapshot() {
        if(!middle_.is_lock_free()) throw std::runtime_error("LatestSnapshot requires lock-free exchange");
    }
    void publish(const T& value) {
        slots_[back_]=value;
        const auto old=middle_.exchange(back_|kNew,std::memory_order_acq_rel);
        back_=old & kIndex;
        if((old & kNew)!=0) ++overwrites_;
    }
    std::optional<T> read() {
        if((middle_.load(std::memory_order_acquire) & kNew)!=0) {
            const auto old=middle_.exchange(front_,std::memory_order_acq_rel);
            front_=old & kIndex;
            have_front_=true;
        }
        return have_front_ ? std::optional<T>{slots_[front_]} : std::nullopt;
    }
    // Publisher-owned counter; inspect only after publisher has joined.
    std::uint64_t overwrites() const { return overwrites_; }
private:
    static constexpr unsigned kNew=4, kIndex=3;
    std::array<T,3> slots_{};
    std::atomic<unsigned> middle_{1};
    unsigned back_{2},front_{0};
    bool have_front_{false};
    std::uint64_t overwrites_{0};
};
} // namespace stratadrive::runtime
