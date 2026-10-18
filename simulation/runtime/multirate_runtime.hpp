#pragma once

#include <filesystem>
#include <array>
#include <optional>
#include <string>

namespace stratadrive::simulation {
struct MultirateRuntimeOptions {
    std::string scenario;
    std::string interface_name;
    std::filesystem::path directory;
    bool detailed_trace{true};
    // brake, drive, bms, power, rx, monitor, plant_fixture; absent = inherit.
    std::optional<std::array<int,7>> owner_cpus;
    // Explicit Linux FIFO priorities in the same owner order; absent = inherit.
    std::optional<std::array<int,7>> owner_fifo_priorities;
};
std::array<int,7> parse_runtime_owner_cpus(const std::string& value);
std::array<int,7> parse_runtime_owner_fifo(const std::string& value);
void run_multirate_runtime(const MultirateRuntimeOptions& options);
} // namespace stratadrive::simulation
