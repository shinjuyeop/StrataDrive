#include "steering_socketcan.hpp"

#include <algorithm>
#include <stdexcept>

namespace stratadrive::socketcan {
Frame to_socketcan(const can::SteeringFrame& input) {
    if (input.payload_length > input.payload.size()) {
        throw std::invalid_argument("Steering TX payload exceeds storage");
    }
    Frame output;
    output.can_id = input.can_id;
    output.is_fd = input.is_fd;
    output.fd_flags = input.fd_flags;
    output.payload_length = input.payload_length;
    std::copy(input.payload.begin(), input.payload.end(), output.payload.begin());
    return output;
}

can::SteeringFrame to_steering(const Frame& input) {
    can::SteeringFrame output;
    output.can_id = input.can_id;
    output.is_fd = input.is_fd;
    output.fd_flags = input.fd_flags;
    output.payload_length = input.payload_length;
    // 길이를 32로 바꾸지 않는다. 64-byte frame도 실제 길이를 유지하여 receiver가 거부한다.
    std::copy_n(input.payload.begin(), output.payload.size(), output.payload.begin());
    return output;
}
}  // namespace stratadrive::socketcan
