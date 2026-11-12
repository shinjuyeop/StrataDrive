#pragma once

#include "perception_frame.hpp"

namespace stratadrive::central {
// Opt-in m10-native-2k-boundary-v1. A typed Host boundary, not a wire format.
// Never reinterpret the frozen S/640 frame or native4K coordinates as this type.
inline constexpr std::uint32_t kNative2kWidth=2560, kNative2kHeight=1536;
inline constexpr std::array<std::uint8_t,32> kNative2kModelHash{
    0xb8,0x65,0xac,0x0f,0x25,0x97,0xaf,0xd6,0xfc,0xb9,0xe8,0x87,0xed,0x77,0x38,0xe9,
    0x8e,0x76,0x90,0xec,0xb4,0xd5,0xce,0xbf,0x42,0x72,0x4a,0x3e,0x6b,0x38,0x48,0x84};
struct Native2kSession {
    std::uint32_t epoch{0};
    std::uint64_t source_clock{0}, wall_clock{0}, source_enable_ns{0}, wall_enable_ns{0};
};
// Supplied by the trusted state/control owner, independently of the image.
// Wall coordinates must share the original callback's monotonic clock domain.
struct Native2kNow {
    std::uint64_t source_ns{0}, wall_ns{0}, state_received_wall_ns{0};
};
struct Native2kFrame {
    std::uint32_t schema{1}, candidate{1}, epoch{0};
    std::uint64_t source_clock{0}, wall_clock{0}, frame{0};
    std::uint64_t source_ns{0}, expires_ns{0}, received_wall_ns{0}, wall_expires_ns{0};
    std::uint32_t camera_id{1}, calibration_revision{1}, width{kNative2kWidth}, height{kNative2kHeight};
    std::array<std::uint8_t,32> model_hash{kNative2kModelHash};
    std::array<ImageDetection,kMaxDetections> detections{};
    std::size_t count{0};
    bool valid{false};
};
// An observed history is context, not a prediction or metric velocity.
struct Native2kObservation {
    std::uint64_t frame{0}, source_ns{0};
    ImageDetection detection{};
};
struct Native2kTrack {
    std::uint64_t id{0};
    std::array<Native2kObservation,10> history{};
    std::size_t count{0};
};
struct Native2kTracks {
    std::array<Native2kTrack,kMaxDetections> tracks{};
    std::size_t count{0};
};
} // namespace stratadrive::central
