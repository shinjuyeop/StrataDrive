#pragma once

#include "socketcan_endpoint.hpp"
#include "steering_frame_codec.hpp"

namespace stratadrive::socketcan {
Frame to_socketcan(const can::SteeringFrame& frame);
can::SteeringFrame to_steering(const Frame& frame);
}  // namespace stratadrive::socketcan
