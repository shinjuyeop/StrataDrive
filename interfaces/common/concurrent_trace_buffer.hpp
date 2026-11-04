#pragma once
#include <atomic>
#include <cstddef>
#include <type_traits>
#include <vector>

namespace stratadrive::runtime {
// Multiple writers reserve distinct, preallocated slots. A slow writer does not
// hold a recording mutex. There is no concurrent reader: size()/operator[] are
// valid ONLY after every writer has joined. Reservation is not publication.
template<class Row> class ConcurrentTraceBuffer {
    static_assert(std::is_nothrow_copy_assignable_v<Row>);
    static_assert(std::atomic<std::size_t>::is_always_lock_free);
    std::vector<Row> rows_;
    std::atomic<std::size_t> next_{0};
    std::atomic<bool> overflow_{false};
public:
    explicit ConcurrentTraceBuffer(std::size_t capacity):rows_(capacity) {}
    bool append(const Row& row) noexcept {
        auto slot=next_.load(std::memory_order_relaxed);
        do {
            if(slot==rows_.size()){overflow_.store(true,std::memory_order_relaxed);return false;}
        }while(!next_.compare_exchange_weak(slot,slot+1,std::memory_order_relaxed));
        rows_[slot]=row;
        return true;
    }
    bool overflowed() const noexcept {return overflow_.load(std::memory_order_relaxed);}
    std::size_t size() const noexcept {return next_.load(std::memory_order_relaxed);}
    const Row& operator[](std::size_t slot) const noexcept {return rows_[slot];}
};
} // namespace stratadrive::runtime
