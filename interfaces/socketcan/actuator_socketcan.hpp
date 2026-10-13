#pragma once

#include "socketcan_endpoint.hpp"
#include "steering_frame_codec.hpp"
#include "brake_frame_codec.hpp"
#include "drive_frame_codec.hpp"

namespace stratadrive::socketcan {
Frame to_socketcan(const can::SteeringFrame& frame);
can::SteeringFrame to_steering(const Frame& frame);
Frame to_socketcan(const can::BrakeFrame& frame);
can::BrakeFrame to_brake(const Frame& frame);
Frame to_socketcan(const can::DriveFrame& frame);
can::DriveFrame to_drive(const Frame& frame);
}  // namespace stratadrive::socketcan
