#pragma once

#include <filesystem>
#include <string>

namespace stratadrive::simulation {
struct MultirateRuntimeOptions {
    std::string scenario;
    std::string interface_name;
    std::filesystem::path directory;
    bool detailed_trace{true};
};
void run_multirate_runtime(const MultirateRuntimeOptions& options);
} // namespace stratadrive::simulation
