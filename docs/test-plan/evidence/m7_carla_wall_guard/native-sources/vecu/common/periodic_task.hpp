#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <optional>

namespace stratadrive::runtime {
struct TaskScheduleConfig {
    std::uint64_t first_release_ns;
    std::uint64_t period_ns;
    std::uint64_t relative_deadline_ns;
    std::size_t jobs;
};

// A finite absolute schedule. A late caller selects the newest released job;
// earlier jobs remain visible as skipped work, never a catch-up burst.
class TaskSchedule {
public:
    explicit TaskSchedule(TaskScheduleConfig config);
    std::uint64_t release(std::size_t job) const;
    std::uint64_t deadline(std::size_t job) const;
    std::optional<std::size_t> newest_released(std::uint64_t now_ns, std::size_t next_job) const;
    const TaskScheduleConfig& config() const { return config_; }
private:
    TaskScheduleConfig config_;
};

struct DeadlineFault {
    std::size_t job;
    std::uint64_t deadline_ns;
    std::uint64_t detected_ns;
};

// One executor publishes completion; one independent monitor calls poll.
// Monitoring never calls the executor or takes its handoff lock. Storage is
// allocated before execution. Readers may inspect a latched fault concurrently.
class DeadlineMonitor {
public:
    explicit DeadlineMonitor(TaskSchedule schedule);
    bool finish(std::size_t job, std::uint64_t finished_ns);
    void poll(std::uint64_t now_ns);
    std::uint64_t finished(std::size_t job) const;
    std::uint64_t detected(std::size_t job) const;
    bool faulted() const { return fault_job_.load(std::memory_order_acquire) != kNoJob; }
    std::optional<DeadlineFault> first_fault() const;
    bool clock_error() const { return clock_error_.load(std::memory_order_acquire); }
private:
    static constexpr std::size_t kNoJob = static_cast<std::size_t>(-1);
    struct Slot {
        std::atomic<std::uint64_t> finished_ns{0};
        std::atomic<std::uint64_t> detected_ns{0};
    };
    const TaskSchedule schedule_;
    std::unique_ptr<Slot[]> slots_;
    std::size_t cursor_{0}; // monitor owner only
    std::optional<std::uint64_t> last_poll_ns_;
    std::atomic<std::size_t> fault_job_{kNoJob};
    std::atomic<bool> clock_error_{false};
};
} // namespace stratadrive::runtime
