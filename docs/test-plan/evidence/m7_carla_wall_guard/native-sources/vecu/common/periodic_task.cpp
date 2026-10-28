#include "periodic_task.hpp"

#include <algorithm>
#include <limits>
#include <stdexcept>

namespace stratadrive::runtime {
TaskSchedule::TaskSchedule(TaskScheduleConfig config) : config_(config) {
    constexpr auto maximum = std::numeric_limits<std::uint64_t>::max();
    if (config.jobs == 0 || config.jobs > 10000 || config.first_release_ns == 0 ||
        config.period_ns == 0 || config.relative_deadline_ns == 0 ||
        config.first_release_ns > maximum-config.relative_deadline_ns ||
        config.jobs-1 > (maximum-config.first_release_ns-config.relative_deadline_ns)/config.period_ns) {
        throw std::invalid_argument("TaskSchedule: nonzero, finite schedule required (max 10000 jobs)");
    }
}
std::uint64_t TaskSchedule::release(std::size_t job) const {
    if (job >= config_.jobs) throw std::out_of_range("TaskSchedule job");
    return config_.first_release_ns + job*config_.period_ns;
}
std::uint64_t TaskSchedule::deadline(std::size_t job) const {
    return release(job) + config_.relative_deadline_ns;
}
std::optional<std::size_t> TaskSchedule::newest_released(std::uint64_t now_ns, std::size_t next_job) const {
    if (next_job >= config_.jobs || now_ns < release(next_job)) return std::nullopt;
    return static_cast<std::size_t>(std::min<std::uint64_t>((now_ns-config_.first_release_ns)/config_.period_ns, config_.jobs-1));
}

DeadlineMonitor::DeadlineMonitor(TaskSchedule schedule)
    : schedule_(schedule), slots_(std::make_unique<Slot[]>(schedule.config().jobs)) {
    if (!slots_[0].finished_ns.is_lock_free() || !slots_[0].detected_ns.is_lock_free() ||
        !fault_job_.is_lock_free() || !clock_error_.is_lock_free()) {
        throw std::runtime_error("DeadlineMonitor requires lock-free progress atomics on this host");
    }
}
bool DeadlineMonitor::finish(std::size_t job, std::uint64_t finished_ns) {
    if (job >= schedule_.config().jobs || finished_ns < schedule_.release(job)) return false;
    std::uint64_t empty = 0;
    return slots_[job].finished_ns.compare_exchange_strong(empty, finished_ns, std::memory_order_release);
}
void DeadlineMonitor::poll(std::uint64_t now_ns) {
    if (last_poll_ns_ && now_ns < *last_poll_ns_) {
        clock_error_.store(true, std::memory_order_release);
        return;
    }
    last_poll_ns_ = now_ns;
    while (cursor_ < schedule_.config().jobs && schedule_.deadline(cursor_) <= now_ns) {
        const auto end = slots_[cursor_].finished_ns.load(std::memory_order_acquire);
        if (end == 0 || end > schedule_.deadline(cursor_)) {
            slots_[cursor_].detected_ns.store(now_ns, std::memory_order_release);
            if (!faulted()) fault_job_.store(cursor_, std::memory_order_release);
        }
        ++cursor_;
    }
}
std::uint64_t DeadlineMonitor::finished(std::size_t job) const {
    if (job >= schedule_.config().jobs) throw std::out_of_range("DeadlineMonitor job");
    return slots_[job].finished_ns.load(std::memory_order_acquire);
}
std::uint64_t DeadlineMonitor::detected(std::size_t job) const {
    if (job >= schedule_.config().jobs) throw std::out_of_range("DeadlineMonitor job");
    return slots_[job].detected_ns.load(std::memory_order_acquire);
}
std::optional<DeadlineFault> DeadlineMonitor::first_fault() const {
    const auto job = fault_job_.load(std::memory_order_acquire);
    if (job == kNoJob) return std::nullopt;
    return DeadlineFault{job, schedule_.deadline(job), detected(job)};
}
} // namespace stratadrive::runtime
