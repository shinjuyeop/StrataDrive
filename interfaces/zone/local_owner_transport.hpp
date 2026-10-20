#pragma once
// Same-process transport only. Remote adapters must implement protection explicitly.
#include "owner_messages.hpp"
#include "session_mailbox.hpp"
#include <atomic>

namespace stratadrive::transport {
class Clock {
public:
    virtual ~Clock() = default;
    virtual std::uint64_t now_ns() noexcept = 0;
};
class RunGate {
public:
    void close() noexcept { epoch_.store(0,std::memory_order_release); }
    void release(std::uint32_t epoch) noexcept { epoch_.store(epoch,std::memory_order_release); }
    bool allows(std::uint32_t epoch) const noexcept { return epoch!=0 && epoch_.load(std::memory_order_acquire)==epoch; }
    std::uint32_t epoch() const noexcept { return epoch_.load(std::memory_order_acquire); }
private:
    std::atomic<std::uint32_t> epoch_{0};
};
// Priority protection survives a failed/full normal FIFO. Epoch is never reset
// in place; newer trusted INIT makes old signals irrelevant, not vice versa.
struct Protection {
    std::atomic<std::uint32_t> requested{0},selected{0};
    void request(std::uint32_t epoch) noexcept {
        auto old=requested.load(std::memory_order_relaxed);
        while(old<epoch && !requested.compare_exchange_weak(old,epoch,std::memory_order_release,std::memory_order_relaxed)) {}
    }
    bool pending(std::uint32_t epoch) const noexcept { return epoch!=0 && requested.load(std::memory_order_acquire)>=epoch; }
    bool acknowledged(std::uint32_t epoch) const noexcept { return epoch!=0 && selected.load(std::memory_order_acquire)==epoch; }
};
struct InputEvidence { std::uint32_t epoch{0}; std::uint64_t source_ns{0},received_ns{0}; };
template<class Sample> InputEvidence input_evidence(const std::optional<Sample>& accepted) {
    return accepted?InputEvidence{accepted->message.epoch,accepted->message.source_time_ns,accepted->received_time_ns}:InputEvidence{};
}
struct ZoneLink {
    session::SessionMailbox<ZoneRequest,kBudget> work;
    session::SessionMailbox<TxResult,kBudget> results;
    session::SessionMailbox<Feedback,kBudget> feedback;
    Protection protection;
    bool failed() const { return work.failed() || results.failed() || feedback.failed(); }
};
struct LeafLink {
    session::SessionMailbox<LeafRequest,kBudget> work;
    session::SessionMailbox<LeafReport,kBudget> reports;
    Protection protection;
    bool failed() const { return work.failed() || reports.failed(); }
};
} // namespace stratadrive::transport
