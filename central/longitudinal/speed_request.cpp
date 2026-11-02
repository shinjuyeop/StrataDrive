#include "speed_request.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace stratadrive::central {
SpeedRequest::SpeedRequest(double radius,bool antiwindup):wheel_radius_m_(radius),propulsion_antiwindup_(antiwindup) {
    if(!std::isfinite(radius) || radius<=0 || radius>1) throw std::invalid_argument("wheel radius");
}
bool SpeedRequest::start_session(std::uint32_t epoch, std::uint64_t enable) noexcept {
    if (enable < enable_ns_ || (pi_.state().last_ns && enable < *pi_.state().last_ns) || !pi_.initialize(epoch)) return false;
    enable_ns_ = enable;
    sequence_ = 0;
    last_selection_ns_.reset();
    fault_ = SpeedRequestFault::None;
    return true;
}
std::optional<VehicleRequest> SpeedRequest::step(std::uint64_t now, double target,
    const std::optional<can::DriveMessage>& current, bool permission,std::optional<PropulsionSelection> selection) noexcept {
    const auto fail = [this](SpeedRequestFault fault) -> std::optional<VehicleRequest> { fault_ = fault; return std::nullopt; };
    if (fault_ != SpeedRequestFault::None) return std::nullopt;
    if (!pi_.state().epoch || now < enable_ns_) return fail(SpeedRequestFault::Session);
    if (!permission) return fail(SpeedRequestFault::Permission);
    if (!current || current->kind != can::DriveFrameKind::Actual || current->epoch != pi_.state().epoch ||
        !current->wheel_speed || !std::isfinite(current->wheel_speed->value_rad_s) ||
        current->wheel_speed->value_rad_s < 0 || current->wheel_speed->value_rad_s > 100) return fail(SpeedRequestFault::Feedback);
    const auto source = current->wheel_speed->source_time_ns;
    if (source < enable_ns_ || source > now || now-source > kSourceAgeNs ||
        (pi_.state().sample && source <= pi_.state().sample->source_ns)) return fail(SpeedRequestFault::Source);
    if (sequence_ > std::numeric_limits<std::uint32_t>::max()) return fail(SpeedRequestFault::Sequence);
    // Wheel acquisitions have no separate sequence on the wire. Use their
    // original timestamp as the cursor, NOT the renewed Actual envelope sequence.
    const SpeedSample sample{current->epoch, source, source, current->wheel_speed->value_rad_s*wheel_radius_m_};
    // First release has no previous allocation: conservatively freeze positive
    // integration. Later feedback must refer to exactly the previous request.
    bool saturated=propulsion_antiwindup_;
    if(propulsion_antiwindup_ && sequence_) {
        if(!selection || selection->epoch!=current->epoch || selection->request_sequence!=sequence_-1 ||
           selection->selection_ns<*pi_.state().last_ns || selection->selection_ns>=now ||
           now-selection->selection_ns>kSourceAgeNs ||
           (last_selection_ns_ && selection->selection_ns<=*last_selection_ns_) ||
           selection->requested_acceleration_mps2!=pi_.state().previous_mps2 ||
           !std::isfinite(selection->requested_propulsion_nm) || !std::isfinite(selection->selected_propulsion_nm) ||
           selection->requested_propulsion_nm<0 || selection->selected_propulsion_nm<0 ||
           selection->selected_propulsion_nm>selection->requested_propulsion_nm ||
           selection->limited!=(selection->requested_propulsion_nm>selection->selected_propulsion_nm))
            return fail(SpeedRequestFault::PropulsionSelection);
        saturated=selection->limited;
    } else if(selection) return fail(SpeedRequestFault::PropulsionSelection);
    const auto out = pi_.step(now, target, sample, permission,saturated);
    if (!out.valid) return fail(SpeedRequestFault::Controller);
    if(selection)last_selection_ns_=selection->selection_ns;
    const auto expiry = source > std::numeric_limits<std::uint64_t>::max()-kSourceAgeNs-1 ?
        std::numeric_limits<std::uint64_t>::max() : source+kSourceAgeNs+1;
    // Conservatively root authority at the speed acquisition. Allocation and
    // Zone admission already carry this oldest dependency and bound all children.
    return VehicleRequest{current->epoch, static_cast<std::uint32_t>(sequence_++), source, expiry,
        *out.acceleration_mps2, 0, 0, target == 0};
}
std::optional<DerivedVehicleRequest> SpeedRequest::step_derived(std::uint64_t now,double target,
    const std::optional<can::DriveMessage>& current,bool permission,std::optional<PropulsionSelection> selection) noexcept {
    auto request=step(now,target,current,permission,selection);
    if(!request)return std::nullopt;
    const auto source=request->source_time_ns;
    if(now>std::numeric_limits<std::uint64_t>::max()-kSourceAgeNs-1 ||
       source>std::numeric_limits<std::uint64_t>::max()-SpeedPI::kMaxAgeNs-1) {
        fault_=SpeedRequestFault::Source;return std::nullopt;
    }
    // The 30ms current-feedback gate above remains independent of the model's
    // 60ms validity for a derived result. Both clocks survive allocation.
    const VehicleInputDependency input{source,source+SpeedPI::kMaxAgeNs+1};
    request->source_time_ns=now;
    request->expires_at_ns=std::min(now+kSourceAgeNs+1,input.expires_at_ns);
    return DerivedVehicleRequest{*request,input};
}
} // namespace stratadrive::central
