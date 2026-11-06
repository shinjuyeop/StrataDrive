#pragma once
#include "frame_clock.hpp"
#include "actuator_electrical.hpp"
#include "native_export.hpp"
#include "pure_pursuit.hpp"
#include "route_speed_profile.hpp"
#include "normal_stop.hpp"
#include "diagnostics.hpp"
#include "available_force_estimator.hpp"
#include "speed_supervisor.hpp"
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
struct SpeedControlAudit {
    Time release_ns,origin_ns,source_ns,expiry_ns,input_expiry_ns;
    std::uint32_t sequence;
    double target_mps,speed_mps,acceleration_mps2,integral;
};
struct RouteReferenceAudit {
    double requested_mps;
    std::optional<Time> slow_elapsed_ns,stop_elapsed_ns;
};
struct SupervisedSpeedAudit {
    central::SupervisedSpeed decision;
    std::optional<central::AvailableForce> force;
    std::optional<central::FeasibleReference> reference;
    std::optional<central::SupervisedSpeedFault> fault;
};
enum class SpeedTerminal { None, NormalStop, SpeedInputLoss, StopProtection, NormalStop30 };
enum class DiagnosticFault { Disabled, None, SpeedInputLoss, StopAckLoss, FrontCommandLoss, BrakingTimeout, FrontLinkFailure };
struct Report {
    DiagnosticFault diagnostic_fault=DiagnosticFault::Disabled;
    std::uint64_t fault_omissions=0;
    // Absent in wall mode; immutable batch keeps Report noexcept-copyable.
    std::shared_ptr<const std::vector<diagnostics::Event>> diagnostic_events;
    SpeedTerminal terminal_mode=SpeedTerminal::None;
    Time trigger_ns=0,detection_ns=0,handoff_ns=0;
    central::NormalStopState stop_state=central::NormalStopState::NotInitialized;
    bool power_off=false;
    central::NormalStopConfig stop_configuration{};
    int stop_fault=0,speed_fault=0;
    std::optional<remote::OwnerPacket> power_status;
    bool propulsion_antiwindup=false;
    bool saturation_used=false,braking_saturation_used=false;
    std::optional<central::PropulsionSelection> allocation_selection,speed_selection;
    std::optional<SpeedControlAudit> speed_control;
    std::optional<SupervisedSpeedAudit> supervised_speed;
    std::optional<RouteReferenceAudit> route_reference;
    std::optional<central::PursuitOutput> lateral_control;
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
    power::CoilCommand coils{};
    Time coil_source=0,electrical_acquired=0;
    Time hv_source=0,hv_dependency=0;
    std::optional<NativeExport> native_export;
};
// Real native actors/session/credit + M6 actuator/electrical fixture. Optional
// M7-1g mode replaces only the ECU sensor. M7-1h explicitly selects a separate
// external-wheel electrical/actuator owner. M7-1r explicitly replaces ZOH with
// observed solver work; the external adapter remains the sole CARLA writer.
class FunctionalRig {
public:
    explicit FunctionalRig(Scope scope,std::uint32_t trusted_wheel_actor=0,PlantMode mode=PlantMode::StationaryFixture,bool export_actual=false,Time horizon_ms=10000);
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
    // M8 fixed V1 0->10->0 km/h profile, simulation time only.
    void speed_profile(SpeedTerminal terminal=SpeedTerminal::None);
    void route_profile(std::vector<central::RoutePoint> points,RouteProfile profile=RouteProfile::Curve30,bool antiwindup=false);
    // Opt-in runtime composition; fixed SIL road-load envelope must be supplied
    // explicitly. Uses live receiver BMS limits and original wheel acquisition.
    void supervise_speed(central::RoadLoadBounds);
    // Explicit consumer-boundary injection. Restoration cannot clear the latch.
    void omit_force_input(bool value);
    void pose(central::RoutePose sample,std::uint32_t actor);
    // M7-only scheduling phase study; periods/expiry rules remain unchanged.
    void controller_phase(Time delay_after_enable);
    void omit_role(int role);
    void stop_credit(bool value);
    void drop_actual(bool value);
    // Fixed STOP30 diagnostic campaign; select before INIT. Each omission acts
    // at its actual consumer/transport boundary, never on a diagnostic record.
    void diagnostic_profile(DiagnosticFault fault);
    // Trusted local safety request; original actors produce the protection Actual.
    void request_protection();
    // Diagnostic instrumentation only, never a clock conversion or tick permit.
    void execution_watch(WallExecutionWatch* watch);
    // Terminal local selection at the LAST completed barrier. No replay, new
    // acquisition, model advance, Actual export, or further observe is allowed.
    BarrierStop stop_at_barrier();
    // Terminal diagnostic branch only: local response time advances by actual
    // monotonic elapsed time from a completed barrier. Not a CARLA clock mapping
    // and never yields another tick. Same thread owns models and all ECU calls.
    void begin_terminal_response(Time monotonic_ns);
    Report service_terminal_response(Time monotonic_ns);
private:
    friend class WallRig;
    struct Native;
    Report observe_impl(const Observation&,const std::optional<WheelSample>&);
    Scope scope_;FrameClock clock_;std::unique_ptr<Native> native_;
    std::uint32_t wheel_actor_;
    PlantMode plant_mode_;
    bool export_actual_;
    const Time horizon_ms_;
    std::optional<m7_external::SolverWork> work_;
    std::vector<RequestPhase> profile_;
    Time controller_phase_=14*ms;
    int omitted_=-1;bool stop_credit_=false,drop_actual_=false;
    SpeedTerminal terminal_mode_=SpeedTerminal::None;
    DiagnosticFault diagnostic_fault_=DiagnosticFault::Disabled;
    bool speed_profile_=false;
    std::vector<central::RoutePoint> route_;
    bool antiwindup_=false;
    std::optional<central::RoadLoadBounds> road_load_;
    bool omit_force_=false;
    RouteProfile route_profile_=RouteProfile::Curve30;
    std::optional<central::RoutePose> pose_;
    bool protect_=false;
    WallExecutionWatch* watch_=nullptr;
    Time terminal_wall_=0,terminal_local_=0,last_terminal_wall_=0;
    std::thread::id owner_=std::this_thread::get_id();
};
} // namespace stratadrive::m7_functional
