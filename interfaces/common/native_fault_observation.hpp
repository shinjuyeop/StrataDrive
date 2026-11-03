#pragma once
#include <array>
#include <cstdint>
#include <optional>

namespace stratadrive {
// Bounded owner-local evidence only; not a wire/diagnostic service contract.
struct NativeSample {
    bool present{false}; std::uint32_t epoch{0}; std::uint64_t sequence{0},source_ns{0},dependency_ns{0};
    std::array<std::optional<double>,4> values{};
};
struct NativeRoot {
    std::uint32_t epoch{0},sequence{0}; std::uint64_t source_ns{0},expiry_ns{0},dependency_ns{0};
};
struct NativeObservation {
    std::uint32_t epoch{0},model_epoch{0},reason{0},detail{0},state{0},writes{0};
    std::uint64_t enable_ns{0},observed_ns{0},phase_origin_ns{0};
    bool propagation{false},qualified{false};
    std::optional<std::uint64_t> violation_ns;
    std::optional<std::uint64_t> valid_until_ns;
    std::optional<NativeRoot> root;
    std::array<NativeSample,5> samples{};
    std::array<double,8> trip{},release{};
    std::array<std::uint64_t,12> timing{};
};
template<class T> NativeSample native_sample(const std::optional<T>& sample) {
    if(!sample) return {};
    return {true,sample->identity.epoch,sample->identity.sequence,sample->identity.source_time_ns,sample->input_time_ns,{}};
}
} // namespace stratadrive
