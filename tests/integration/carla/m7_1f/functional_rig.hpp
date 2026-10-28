#pragma once
#include "frame_clock.hpp"
#include "actuator_electrical.hpp"
#include "native_export.hpp"
#include <array>
#include <memory>
#include <optional>
#include <vector>

namespace stratadrive::m7_functional {
class WallExecutionWatch;
struct BarrierStop {Time logical_ns;unsigned selected_mask,credit_mask;bool normal;};
// Trusted local sensor binding, not a CAN command/actuation permission. The
// source is one PhysX telemetry RPC bracketed by the same CARLA snapshot frame.
struct WheelSample {
    std::uint32_t actor=0;
    Time frame=0,source=0;
    std::array<double,4> omega{}; // FL, FR, RL, RR; rad/s, signed, no abs/clamp
};
struct RequestPhase { Time end_ms; double acceleration,curvature,braking; bool hold; };
struct WheelAudit {Time source;double rad_s;};
enum class PlantMode { StationaryFixture,ExternalWheelZoh,ExternalSolverWork };
struct Report {
    Time now=0,next_frame=0,lease_source=0,lease_expiry=0;
    unsigned release_mask=0,credit_mask=0,service_mask=0;
    bool armed=false,actual_interval=false;
    std::array<Time,3> actual_sources{};
    std::array<std::size_t,5> commands{};
    std::array<Time,5> leaf_body{};
    std::size_t controller_releases=0;
    std::optional<WheelAudit> sensor_wheel,returned_wheel;
    std::optional<double> returned_torque;
    std::optional<Time> regen_oldest;
    std::optional<m7_external::ElectricalAudit> electrical;
    std::array<m7_external::ElectricalAudit,12> electrical_steps{};
    unsigned electrical_count=0;
    std::optional<NativeExport> native_export;
};
// Real native actors/session/credit + M6 actuator/electrical fixture. Optional
// M7-1g mode replaces only the ECU sensor. M7-1h explicitly selects a separate
// external-wheel electrical/actuator owner. M7-1r explicitly replaces ZOH with
// observed solver work; the external adapter remains the sole CARLA writer.
class FunctionalRig {
public:
    explicit FunctionalRig(Scope scope,std::uint32_t trusted_wheel_actor=0,PlantMode mode=PlantMode::StationaryFixture,bool export_actual=false);
    ~FunctionalRig();
    FunctionalRig(const FunctionalRig&)=delete;
    FunctionalRig& operator=(const FunctionalRig&)=delete;
    Report observe(const Observation& observation);
    Report observe(const Observation& observation,const WheelSample& wheel);
    Report observe(const Observation& observation,const WheelSample& wheel,const m7_external::SolverWork& work);
    // Explicit test fault injection, set before observe. Missing processing is
    // never counted as an ACK. Credit loss keeps the original native age rules.
    // Fixed before INIT; evaluated at each original 20ms Controller release.
    void request_profile(std::vector<RequestPhase> phases);
    void omit_role(int role);
    void stop_credit(bool value);
    void drop_actual(bool value);
    // Trusted local safety request; original actors produce the protection Actual.
    void request_protection();
    // Diagnostic instrumentation only, never a clock conversion or tick permit.
    void execution_watch(WallExecutionWatch* watch);
    // Terminal local selection at the LAST completed barrier. No replay, new
    // acquisition, model advance, Actual export, or further observe is allowed.
    BarrierStop stop_at_barrier();
private:
    struct Native;
    Report observe_impl(const Observation&,const std::optional<WheelSample>&);
    Scope scope_;FrameClock clock_;std::unique_ptr<Native> native_;
    std::uint32_t wheel_actor_;
    PlantMode plant_mode_;
    bool export_actual_;
    std::optional<m7_external::SolverWork> work_;
    std::vector<RequestPhase> profile_;
    int omitted_=-1;bool stop_credit_=false,drop_actual_=false;
    bool protect_=false;
    WallExecutionWatch* watch_=nullptr;
};
} // namespace stratadrive::m7_functional
