#pragma once

#include <filesystem>
#include <string>

namespace stratadrive::simulation {
// Finite Linux Host experiment. Writes after the three owners have joined.
// Does not replace deterministic SteeringSil or provide a production scheduler.
void run_steering_runtime(const std::string& scenario, const std::filesystem::path& directory, bool detailed_trace);
} // namespace stratadrive::simulation
