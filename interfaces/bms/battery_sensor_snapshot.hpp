#pragma once

#include <cstdint>
#include <optional>

namespace stratadrive::battery {
// Local sensor port contract, independent of the SIL plant and CAN encoding.
// Model epoch is a physical scenario identity, not an ECU application epoch.
struct ModelIdentity {
    std::uint32_t epoch{0}, sequence{0};
    std::uint64_t source_time_ns{0};
};
struct ElectricalPair { double voltage_v, current_a; }; // +discharge, -charge
struct CellExtrema { double minimum, maximum; };
template <typename T> struct ModelMeasurement {
    T value;
    ModelIdentity identity;       // original acquisition, including when held
    std::uint64_t input_time_ns; // oldest dependency, never the cached envelope time
};
struct SensorSnapshot {
    ModelIdentity batch{};
    bool available{false};
    std::optional<ModelMeasurement<double>> soc;
    std::optional<ModelMeasurement<ElectricalPair>> electrical;
    std::optional<ModelMeasurement<double>> temperature;
    std::optional<ModelMeasurement<CellExtrema>> cell_voltage;
    std::optional<ModelMeasurement<CellExtrema>> cell_temperature;
};
}  // namespace stratadrive::battery
