#pragma once

#include "bms_frame_codec.hpp"
#include "bms_parent_context.hpp"

namespace stratadrive::central {
// Independently trusted lifecycle ingress, distinct from VehicleRequest.
struct LifecycleRequest {
    can::BmsParentContext identity;
    can::BmsPowerAction action;
};
struct VehicleManagementOutput {
    can::BmsMessage power_request;
    can::BmsMessage drive_permission;
    std::optional<can::BmsParentContext> power_parent, permission_parent;
};
}  // namespace stratadrive::central
