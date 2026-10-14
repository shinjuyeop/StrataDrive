#include "actuator_socketcan.hpp"

#include <algorithm>
#include <stdexcept>

namespace stratadrive::socketcan {
namespace {
template <typename ApplicationFrame>
Frame to_native(const ApplicationFrame& input) {
    if (input.payload_length > input.payload.size()) {
        throw std::invalid_argument("Actuator TX payload exceeds storage");
    }
    Frame output;
    output.can_id = input.can_id;
    output.is_fd = input.is_fd;
    output.fd_flags = input.fd_flags;
    output.payload_length = input.payload_length;
    std::copy(input.payload.begin(), input.payload.end(), output.payload.begin());
    return output;
}

template <typename ApplicationFrame>
ApplicationFrame from_native(const Frame& input) {
    ApplicationFrame output;
    output.can_id = input.can_id;
    output.is_fd = input.is_fd;
    output.fd_flags = input.fd_flags;
    output.payload_length = input.payload_length;
    // 실제 길이를 보존한다. 각 domain receiver가 kind별 길이를 검사한다.
    std::copy_n(input.payload.begin(), output.payload.size(), output.payload.begin());
    return output;
}
}  // namespace

Frame to_socketcan(const can::SteeringFrame& frame) { return to_native(frame); }
Frame to_socketcan(const can::BrakeFrame& frame) { return to_native(frame); }
Frame to_socketcan(const can::DriveFrame& frame) { return to_native(frame); }
can::SteeringFrame to_steering(const Frame& frame) { return from_native<can::SteeringFrame>(frame); }
can::BrakeFrame to_brake(const Frame& frame) { return from_native<can::BrakeFrame>(frame); }
can::DriveFrame to_drive(const Frame& frame) { return from_native<can::DriveFrame>(frame); }
Frame to_socketcan(const can::BmsFrame& frame) { return to_native(frame); }
can::BmsFrame to_bms(const Frame& frame) { return from_native<can::BmsFrame>(frame); }
}  // namespace stratadrive::socketcan
