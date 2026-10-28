#pragma once
#include "periodic_task.hpp"
#include <array>
#include <memory>
#include <vector>

namespace stratadrive::simulation {
struct M4ExecutionRow {
    std::size_t owner{0},slot{0};
    std::uint64_t release_ns{0},deadline_ns{0},start_ns{0},end_ns{0},cpu_ns{0},detected_ns{0};
    std::uint64_t requested_wake_ns{0}; // native timer target; 0 for logical/no executed body
};
// All native workers and guards share the run origin. No private launch phase
// and no catch-up burst after an overrun. The deadline/missed-slot policy is unchanged.
struct M4ReleaseGrid {
    std::uint64_t origin_ns,period_ns;
    std::uint64_t after(std::uint64_t now_ns) const;
};
struct M4ExecutionFault { std::size_t target; runtime::DeadlineFault timing; };
// Existing M3 monitor: one executor/guard, one independent polling cursor.
// Monitor(9) observes 0..8; Physical(8) observes Monitor(9).
class M4ExecutionWatch {
public:
    M4ExecutionWatch(std::uint64_t enable_ns,std::uint64_t stop_ns,std::uint16_t active_mask=0x3ff);
    std::optional<std::size_t> begin(std::size_t owner,std::uint64_t now,bool executing,std::uint64_t requested_wake=0);
    std::optional<std::size_t> begin_requested(std::size_t owner,std::uint64_t now,bool executing,std::uint64_t requested_wake);
    void finish(std::size_t owner,std::optional<std::size_t> job,std::uint64_t end,std::uint64_t cpu);
    std::array<std::optional<M4ExecutionFault>,10> poll(std::size_t observer,std::uint64_t now);
    std::vector<M4ExecutionRow> rows() const; // joined only
private:
    struct Guard {
        explicit Guard(runtime::TaskScheduleConfig config);
        runtime::TaskSchedule schedule; runtime::DeadlineMonitor monitor;
        std::vector<M4ExecutionRow> rows; std::size_t next{0}; bool reported{false};
    };
    std::array<std::unique_ptr<Guard>,10> guards_;
    std::uint16_t active_mask_;
};
} // namespace stratadrive::simulation
