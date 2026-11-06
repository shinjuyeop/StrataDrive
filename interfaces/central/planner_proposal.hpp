#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace stratadrive::central {
// Initial M10 state-only baseline: tensor [4,6], oldest row first. Image
// perception/model training is a separate profile, not implicit zero features.
struct PlannerState {
    double speed_mps{0}, route_speed_mps{0};
    double propulsion_n{0}, braking_n{0}, road_load_min_n{0}, road_load_max_n{0};
};
struct PlannerInput {
    std::uint32_t epoch{0};
    std::uint64_t clock_instance{0};
    std::array<std::uint64_t,4> source_ns{};
    std::array<PlannerState,4> history{};
    bool valid{false};
};
// A model returns values/status only. The trusted adapter supplies identity and
// timestamps from PlannerInput; inference completion cannot renew acquisition.
struct ModelSpeedOutput {
    std::array<double,16> speed_mps{};
    double risk{1};
    bool valid{false};
};
// m10-speed-proposal-v1: in-process host contract, NOT CAN/SDK serialization.
// Four chronological 20ms state bundles -> 16 forward speed samples at
// 100ms offsets (0..1.5s). The input adapter owns calibration/preprocessing.
// This initial profile proposes speed only; no steering/actuator authority.
struct PlannerProposal {
    static constexpr std::uint32_t kSchema=1;
    static constexpr std::size_t kHistory=4, kHorizon=16;
    std::uint32_t schema{kSchema}, epoch{0};
    std::uint64_t clock_instance{0}, sequence{0}, model_revision{0};
    std::uint64_t source_ns{0}, expires_ns{0};
    std::array<std::uint64_t,kHistory> history_ns{};
    std::array<double,kHorizon> speed_mps{};
    double speed_limit_mps{0}; // Trusted current route ceiling, supplied by the adapter.
    double risk{1}; // Finite [0,1] profile score; not a calibrated probability.
    bool valid{false}; // Missing/failed inference is never encoded as zero speed.
};
struct ClassicalSpeedProposal {
    std::uint32_t epoch{0};
    std::uint64_t clock_instance{0}, source_ns{0}, expires_ns{0};
    double speed_mps{0};
    bool valid{false};
};
} // namespace stratadrive::central
