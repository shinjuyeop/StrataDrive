#pragma once
#include <cstdint>
#include <filesystem>
#include <string>
namespace stratadrive::simulation {
struct SteeringRtosPlantOptions {
    std::string scenario,interface_name;
    int channel;
    std::uint64_t enable;
    std::filesystem::path directory;
};
void run_steering_rtos_plant(const SteeringRtosPlantOptions& options);
}
