#pragma once
#include "planner_proposal.hpp"
#include "speed_request.hpp"
#include "available_force_reference.hpp"

namespace stratadrive::central {
std::optional<PlannerProposal> bind_speed_proposal(const PlannerInput&,const ModelSpeedOutput&,
    std::uint64_t sequence,std::uint64_t model_revision) noexcept;
enum class ProposalSource { Learned, Classical, Protection };
enum class ProposalReason { Accepted, Missing, Invalid, Stale, Identity, Hazard, NoFallback, Authority, Reference, Controller, CapacityInput };
struct SupervisedSpeed {
    ProposalSource source{ProposalSource::Protection};
    ProposalReason reason{ProposalReason::NoFallback};
    std::optional<double> target_mps;
    std::uint64_t oldest_source_ns{0}, expires_ns{0};
};
struct SupervisedSpeedFault {
    std::uint32_t epoch{0};
    std::uint64_t clock_instance{0},enable_ns{0},detected_ns{0};
    ProposalReason reason{ProposalReason::NoFallback};
    ReferenceFault reference_fault{ReferenceFault::None};
};
struct SupervisedSpeedSuccess {
    std::uint32_t epoch;
    std::uint64_t clock_instance,enable_ns,issued_ns;
    can::DriveMessage input;
    AvailableForce force;
    DerivedVehicleRequest output;
};
// Single owner. Supervisor approval does not grant vehicle permission.
class SpeedSupervisor {
public:
    explicit SpeedSupervisor(double maximum_risk=0.2);
    bool start_session(std::uint32_t epoch,std::uint64_t clock_instance,std::uint64_t enable_ns) noexcept;
    SupervisedSpeed select(std::uint64_t now_ns,const std::optional<PlannerProposal>&,
        const ClassicalSpeedProposal&,bool normal_permission) noexcept;
private:
    const double maximum_risk_;
    std::uint32_t epoch_{0};
    std::uint64_t clock_{0}, enable_{0}, last_now_{0};
    std::optional<PlannerProposal> previous_;
};
// Opt-in complete host path: proposal -> supervisor -> force governor ->
// existing PI/VehicleRequest. Caller MUST route a missing result to the existing
// protection coordinator; it must not hold/reissue the last normal request.
class SupervisedSpeedRequest {
public:
    explicit SupervisedSpeedRequest(ReferenceConfig config={},double wheel_radius_m=0.3);
    bool start_session(std::uint32_t epoch,std::uint64_t clock_instance,std::uint64_t enable_ns) noexcept;
    std::optional<DerivedVehicleRequest> step(std::uint64_t now_ns,const std::optional<PlannerProposal>&,
        const ClassicalSpeedProposal&,const std::optional<can::DriveMessage>&,
        const std::optional<AvailableForce>&,bool permission,std::optional<PropulsionSelection> selection=std::nullopt) noexcept;
    const SupervisedSpeed& decision() const noexcept { return decision_; }
    const std::optional<FeasibleReference>& reference() const noexcept { return reference_; }
    bool protection_required() const noexcept { return latched_; }
    const SpeedRequest& controller() const noexcept { return controller_; }
    const std::optional<SupervisedSpeedFault>& fault_observation() const noexcept { return fault_; }
    const std::optional<SupervisedSpeedSuccess>& success_observation() const noexcept { return success_; }
    const ReferenceConfig& configuration() const noexcept { return config_; }
    double wheel_radius_m() const noexcept { return radius_; }
private:
    ReferenceConfig config_;
    double radius_;
    SpeedSupervisor supervisor_;
    AvailableForceReference governor_;
    SpeedRequest controller_;
    SupervisedSpeed decision_{};
    std::optional<FeasibleReference> reference_;
    std::optional<std::uint64_t> last_dependency_;
    bool latched_{false};
    std::uint32_t epoch_{0};
    std::uint64_t clock_{0},enable_{0};
    std::optional<SupervisedSpeedFault> fault_;
    std::optional<SupervisedSpeedSuccess> success_;
};
} // namespace stratadrive::central
