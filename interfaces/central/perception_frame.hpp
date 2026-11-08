#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace stratadrive::central {
// m10-perception-host-v1, typed Host boundary, NOT a network serialization.
// Coordinates are half-open original-image pixels, never metric world state.
inline constexpr std::size_t kMaxDetections = 100;
inline constexpr std::uint64_t kPerceptionLifetimeNs = 100000000;
inline constexpr std::array<std::uint8_t,32> kPerceptionModelHash{
    0xc5,0xc2,0xd1,0x3e,0x59,0xae,0x88,0x3e,0x6a,0xf3,0xb4,0x5d,0xae,0xa6,0x4a,0xf4,
    0x83,0x3a,0x49,0x51,0xc9,0x2d,0x11,0x6e,0xc2,0x70,0xd9,0xdd,0xbe,0x99,0x80,0x63};
struct ImageDetection {
    std::uint32_t class_id{0};
    double score{0};
    double x1{0}, y1{0}, x2{0}, y2{0};
};
struct PerceptionFrame {
    std::uint32_t schema{1}, epoch{0};
    std::uint64_t clock_instance{0}, frame{0}, source_ns{0}, expires_ns{0};
    std::uint32_t camera_id{1}, calibration_revision{1}, width{640}, height{384};
    std::array<std::uint8_t,32> model_hash{kPerceptionModelHash};
    std::array<ImageDetection,kMaxDetections> detections{};
    std::size_t count{0};
    bool valid{false}; // valid empty != unavailable, neither proves a clear road.
};
} // namespace stratadrive::central
