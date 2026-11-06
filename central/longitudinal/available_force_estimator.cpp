#include "available_force_estimator.hpp"
#include "brake_pressure_codec.hpp"
#include "drive_value_codec.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>

namespace stratadrive::central {
AvailableForceEstimator::AvailableForceEstimator(AllocationConfig c,RoadLoadBounds load):config_(c),load_(load) {
    // Use the allocator's configuration validation, including its wire bounds.
    const ControlAllocation validated(c);
    if(!std::isfinite(load.minimum_n) || !std::isfinite(load.maximum_n) || load.minimum_n>load.maximum_n)
        throw std::invalid_argument("road load envelope");
}
std::optional<AvailableForce> AvailableForceEstimator::estimate(const NormalDriveReadinessInputs& in,std::uint64_t now) const noexcept {
    if(!evaluate_normal_drive_readiness(in,now,config_.readiness).ready())return std::nullopt;
    const auto& drive=*in.rear.drive_actual;
    const auto& limits=in.rear.power_limits->message;
    const auto& power=std::get<can::BmsPowerLimits>(limits.content);
    if(!drive.wheel_speed || !std::isfinite(drive.wheel_speed->value_rad_s) ||
       drive.wheel_speed->value_rad_s<0 || drive.wheel_speed->value_rad_s>config_.max_wheel_speed_rad_s ||
       drive.wheel_speed->source_time_ns>now || now-drive.wheel_speed->source_time_ns>config_.readiness.actual_source_age_ns)return std::nullopt;
    const auto source=std::min({drive.wheel_speed->source_time_ns,drive.source_time_ns,limits.source_time_ns,power.input_time_ns});
    const auto newest=std::max({drive.wheel_speed->source_time_ns,drive.source_time_ns,limits.source_time_ns,power.input_time_ns});
    if(source<in.session_enable_ns || newest>now || now-source>70000000 ||
       newest>std::numeric_limits<std::uint64_t>::max()-70000001)return std::nullopt;
    const auto& timing=config_.readiness;
    // Current actuator/zone health is rechecked by allocation on every release.
    // Capacity depends on wheel acquisition and BMS limits, not an old torque
    // Actual. Its derived wheel validity matches SpeedRequest's 60ms contract.
    const auto expiry=std::min({drive.wheel_speed->source_time_ns+60000001,
        limits.source_time_ns+timing.bms_source_age_ns+1,power.input_time_ns+timing.bms_dependency_age_ns+1});
    // Match the allocator's quantization so the reference never reserves a
    // fraction of actuator capacity that cannot be encoded on the actual wire.
    const double torque=std::floor(propulsion_capacity_nm(config_,drive.wheel_speed->value_rad_s,
        *power.discharge_power_w)/can::kDriveTorqueResolutionNm)*can::kDriveTorqueResolutionNm;
    const double pressure=std::floor(config_.max_pressure_pa/can::kBrakePressureResolutionPa)*can::kBrakePressureResolutionPa;
    const double braking=std::min(config_.max_service_braking_nm,pressure*config_.friction_nm_per_pa);
    return AvailableForce{in.epoch,source,source,expiry,torque/config_.wheel_radius_m,
        braking/config_.wheel_radius_m,load_.minimum_n,load_.maximum_n,ForceProfile::ReceiverPowerLimits};
}
} // namespace stratadrive::central
