#pragma once
#include <array>
#include <atomic>
#include <cstddef>
#include <optional>

namespace stratadrive::m7_functional {
// One producer, one consumer; neither waits for the other. A full queue is a
// permanent delivery fault, never latest-value overwrite of unaccounted work.
// The consumer may drain already queued receipts to account for completed work.
template<class T,std::size_t Capacity> class WallMailbox {
    static_assert(Capacity>0,"nonempty bounded mailbox");
public:
    bool push(const T& value) {
        if(failed())return false;
        const auto head=head_.load(std::memory_order_relaxed);
        if(head-tail_.load(std::memory_order_acquire)==Capacity) {
            fault_.store(true,std::memory_order_release);return false;
        }
        entries_[head%Capacity]=value;
        head_.store(head+1,std::memory_order_release);return true;
    }
    std::optional<T> pop() {
        const auto tail=tail_.load(std::memory_order_relaxed);
        if(tail==head_.load(std::memory_order_acquire))return {};
        T value=entries_[tail%Capacity];
        tail_.store(tail+1,std::memory_order_release);return value;
    }
    bool failed() const {return fault_.load(std::memory_order_acquire);}
    void fail() {fault_.store(true,std::memory_order_release);}
private:
    std::array<T,Capacity> entries_{};
    std::atomic<std::size_t> head_{0},tail_{0};
    std::atomic<bool> fault_{false};
};
}
