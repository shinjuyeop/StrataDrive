#pragma once

#include "bms_receiver.hpp"
#include "brake_frame_codec.hpp"
#include "drive_frame_codec.hpp"
#include "steering_frame_codec.hpp"

namespace stratadrive::feedback {
struct FeedbackTiming {
    std::uint64_t zone_source_age_ns{30000000ULL};
    std::uint64_t actual_source_age_ns{30000000ULL};
    std::uint64_t bms_source_age_ns{50000000ULL};
    std::uint64_t bms_dependency_age_ns{70000000ULL};
};
struct SourceContext {
    std::uint32_t epoch;
    std::uint64_t session_enable_ns, now_ns;
    FeedbackTiming timing{};
};
// Shared Zone/Central predicates. Callers supply independent receiver current
// samples, retaining each original source/dependency time and quality.
bool steering_available(const std::optional<can::SteeringMessage>& sample,const SourceContext& context);
bool brake_available(const std::optional<can::BrakeMessage>& sample,const SourceContext& context);
bool drive_available(const std::optional<can::DriveMessage>& sample,const SourceContext& context);
bool power_available(const std::optional<can::BmsCurrentSample>& sample,const SourceContext& context,bool normal_drive);
bool limits_available(const std::optional<can::BmsCurrentSample>& sample,const SourceContext& context,bool normal_drive);
}  // namespace stratadrive::feedback
