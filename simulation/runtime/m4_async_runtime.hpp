#pragma once
#include "m4_faults.hpp"
#include "command_renewal.hpp"
#include "m4_execution_watch.hpp"
#include "transport_trace.hpp"

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace stratadrive::simulation {
enum class M4Scenario { Normal,NormalStop,PartialFront,FeedbackLoss,CommandLoss,PartialArm,Rejoin,OldEpoch,Fault };
struct M4Config {
    M4Scenario scenario{M4Scenario::Normal};
    central::CommandRenewal renewal{central::CommandRenewal::Legacy20ms};
    bool wall_time{false};
    std::uint64_t duration_ns{1800000000},injection_ns{1200000000},rejoin_ns{2300000000};
    std::uint32_t first_epoch{1},rejoin_epoch{2}; // already issued trusted startup grants
    std::vector<M4Fault> faults;
    std::uint64_t recovery_ns{0}; bool replace_links{false};
    bool execution_guards{false},fifo{false}; int cpu_a{-1},cpu_b{-1};
    bool transport_trace{false}; // opt-in intrusive diagnostics; separate timing cohort
};
struct M4Trace {
    std::uint64_t elapsed_ns,source_ns;
    std::uint32_t epoch;
    bool run_gate,normal_armed,protected_all;
    int management,coordinator_fault,stop_state;
    double angle_rad,pressure_pa,torque_nm,bus_v,soc;
    std::uint64_t steering_source_ns{0},brake_source_ns{0},drive_source_ns{0},command_source_ns{0};
    std::uint32_t command_root_sequence{0};
    std::uint64_t central_observation_ns{0};
    double speed_mps{0},distance_m{0},x_m{0},y_m{0},yaw_rad{0},vehicle_balance_j{0};
    double energy_j{0}; std::uint32_t model_epoch{0},model_sequence{0}; unsigned contacts{0};
};
struct M4Timing {
    std::string owner;
    std::size_t samples{0},body_over_4ms{0};
    double mean_body_us{0},p95_body_us{0},p99_body_us{0},max_body_us{0},max_poll_gap_ms{0},max_runnable_gap_ms{0};
    std::size_t audit_buffer_growths{0};
};
struct M4Result {
    bool passed{false},ownership_ok{true},physical_ok{true};
    std::string reason;
    std::uint64_t first_active_ns{0},first_fault_ns{0},all_protected_ns{0},rejoin_active_ns{0};
    std::size_t completed_batches{0},front_frames{0},rear_frames{0};
    std::vector<M4Trace> trace;
    std::vector<M4Timing> timing;
    std::vector<M4Event> events;
    std::vector<transport::TransportTraceRow> transport_events;
    std::size_t stopped_ack_violations{0},replaced_links{0};
    bool gate_latched{true},event_overflow{false};
    std::uint64_t effective_injection_ns{0},live_fault_ns{0},normal_blocked_ns{0};
    unsigned live_selection_mask{0},missing_selection_mask{0}; bool model_preserved{true};
    struct Thread { std::size_t owner; int policy{-1},priority{-1},cpu{-1},tid{-1},requested_cpu{-1},setup_error{0}; std::vector<int> affinity; };
    std::vector<Thread> threads;
    std::vector<M4ExecutionRow> execution;
    bool startup_ok{true},timing_ok{true}; std::size_t deadline_misses{0},skipped_opportunities{0};
};
// Finite Host SIL harness. Logical execution and independent wall-time owner
// threads share the same components/links. No DDS, target OS or speed dynamics.
M4Result run_m4_async(const M4Config& config);
const char* m4_scenario_name(M4Scenario scenario);
void write_m4_result(const M4Config& config,const M4Result& result,const std::string& directory);
}  // namespace stratadrive::simulation
