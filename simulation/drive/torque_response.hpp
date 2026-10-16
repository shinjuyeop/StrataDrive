#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>

namespace stratadrive::simulation {
struct TorqueResponseConfig {
    double minimum_nm;
    double maximum_nm;
    double initial_nm;
    double rate_nm_s;
    double zero_rate_nm_s;
    std::uint64_t delay_ns;
};
struct TorqueEnvelope { double minimum_nm, maximum_nm; }; // includes zero

// SIL plant only: no CAN, ECU state, permission, sensor or motor current loop.
// The caller owns the monotonic clock, control period and missed-tick policy.
class TorqueResponse {
public:
    explicit TorqueResponse(TorqueResponseConfig config);
    void begin(std::uint64_t now_ns); // preserve physical torque, cancel old demands
    bool set_target(double torque_nm, std::uint64_t now_ns);
    bool advance(std::uint64_t now_ns);
    // Finish the previous interval, then constrain active and queued goals.
    // Residual actual torque contracts at zero_rate; it never teleports to a limit.
    bool constrain(TorqueEnvelope envelope, std::uint64_t now_ns);
    void request_zero(std::uint64_t now_ns); // cancel delay; finite physical ramp
    void skip_to(std::uint64_t now_ns);      // discard delayed goals; zero target without catch-up
    double actual_nm() const { return actual_; }
private:
    enum class MotionRate { Normal, Protection };
    struct Demand { double torque_nm; std::uint64_t due_ns; };
    void move(std::uint64_t elapsed_ns, MotionRate rate);
    const TorqueResponseConfig config_;
    TorqueEnvelope envelope_;
    std::array<Demand, 128> pending_{};
    std::size_t head_{0}, size_{0};
    double actual_, target_{0};
    std::optional<double> staged_;
    std::uint64_t last_step_ns_{0}, last_observed_ns_{0}, zero_enable_ns_{0};
    bool initialized_{false}, zeroing_{true};
};
}  // namespace stratadrive::simulation
