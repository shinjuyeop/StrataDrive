#pragma once

#include <cstdint>
#include <optional>

namespace stratadrive::central {

struct SpeedSample {
    std::uint32_t epoch;
    std::uint64_t sequence, source_ns;
    double speed_mps;
};

enum class SpeedPIReason {
    Normal, Uninitialized, Latched, SampleTime, Permission, Target,
    InvalidSpeed, Epoch, SourceAge, Identity
};

struct SpeedPIOutput {
    std::optional<double> acceleration_mps2;
    bool valid;
    SpeedPIReason reason;
    double integral;
    std::uint64_t source_ns;
};

// Read-only state observation supports model/code replay. Only initialize/step
// change state; neither method issues session, command or actuator authority.
struct SpeedPIState {
    std::uint32_t epoch{0};
    double integral{0}, previous_mps2{0};
    std::optional<std::uint64_t> last_ns;
    std::optional<SpeedSample> sample;
    bool fault{false};
    std::optional<double> target_mps;
};

// Hand-written C++ port of the independent m6-pi-v1 Python design model.
// Single owner, binary64 round-to-nearest, fixed logical 20 ms releases.
// The caller must validate runtime authority and map sensor/session identity.
// A failed step has NO acceleration demand and latches until a newer INIT.
class SpeedPI {
public:
    static constexpr std::uint64_t kPeriodNs = 20000000;
    static constexpr std::uint64_t kMaxAgeNs = 60000000;
    static constexpr double kKp = 1.0, kKi = 0.2;
    static constexpr double kSlewMps3 = 2.0, kLowMps2 = -5.0, kHighMps2 = 2.0;
    static constexpr double kMaxTargetMps = 40.0 / 3.6;
    static constexpr double kBrakingPreviewS = 0.12;

    bool initialize(std::uint32_t epoch) noexcept;
    SpeedPIOutput step(std::uint64_t now_ns, double target_mps,
                       const std::optional<SpeedSample>& sample, bool permission,
                       bool propulsion_saturated = false) noexcept;
    const SpeedPIState& state() const noexcept { return state_; }

private:
    SpeedPIReason validate(std::uint64_t now_ns, double target_mps,
                           const std::optional<SpeedSample>& sample, bool permission) const noexcept;
    SpeedPIState state_;
};

}  // namespace stratadrive::central
