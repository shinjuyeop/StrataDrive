#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <utility>

namespace stratadrive::can {
enum class RxQueueFault { None, ApplicationOverflow, KernelDrop };
// Single-owner FIFO. Capacity/ingress/dispatch budgets are explicit. Continuity
// loss discards the backlog and latches; recovery requires a newer trusted Epoch.
template <typename T, std::size_t Capacity>
class BoundedRxQueue {
    static_assert(Capacity > 0);
public:
    bool start_session(std::uint32_t epoch) {
        if (epoch == 0 || epoch <= epoch_) return false;
        epoch_ = epoch; clear(); fault_ = RxQueueFault::None; drops_ = 0;
        return true;
    }
    bool push(T value, std::uint32_t cumulative_kernel_drops = 0) {
        if (epoch_ == 0 || fault_ != RxQueueFault::None) return false;
        if (cumulative_kernel_drops != drops_) {
            drops_ = cumulative_kernel_drops; latch(RxQueueFault::KernelDrop); return false;
        }
        if (size_ == Capacity) { latch(RxQueueFault::ApplicationOverflow); return false; }
        items_[(head_ + size_) % Capacity] = std::move(value); ++size_;
        return true;
    }
    std::optional<T> pop() {
        if (size_ == 0 || fault_ != RxQueueFault::None) return std::nullopt;
        auto result = std::move(items_[head_]); items_[head_].reset();
        head_ = (head_ + 1) % Capacity; --size_;
        return result;
    }
    RxQueueFault fault() const { return fault_; }
    std::size_t size() const { return size_; }
private:
    void clear() { for (auto& item : items_) item.reset(); head_ = size_ = 0; }
    void latch(RxQueueFault fault) { clear(); fault_ = fault; }
    std::array<std::optional<T>, Capacity> items_{};
    std::size_t head_{0}, size_{0};
    std::uint32_t epoch_{0}, drops_{0};
    RxQueueFault fault_{RxQueueFault::None};
};
}  // namespace stratadrive::can
