#include "socketcan_endpoint.hpp"

#include <linux/can.h>
#include <linux/can/raw.h>
#include <net/if.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#include <algorithm>
#include <cerrno>
#include <cstring>
#include <stdexcept>
#include <system_error>

namespace stratadrive::socketcan {
namespace {
[[noreturn]] void system_failure(const char* operation) {
    throw std::system_error(errno, std::generic_category(), operation);
}

void option(int fd, int level, int name, const void* value, socklen_t size) {
    if (setsockopt(fd, level, name, value, size) != 0) {
        system_failure("SocketCAN setsockopt");
    }
}

bool fd_length(std::uint8_t length) {
    return length <= 8 || length == 12 || length == 16 || length == 20 ||
           length == 24 || length == 32 || length == 48 || length == 64;
}
}  // namespace

Endpoint::Endpoint(const std::string& interface_name, std::optional<std::uint16_t> receive_id,
                   EndpointOptions options) {
    if (interface_name.empty() || interface_name.size() >= IFNAMSIZ ||
        interface_name.find('\0') != std::string::npos ||
        (receive_id && *receive_id > CAN_SFF_MASK) ||
        (options.receive_buffer_bytes && (*options.receive_buffer_bytes < 1024 || *options.receive_buffer_bytes > 1048576))) {
        throw std::invalid_argument("SocketCAN interface/receive ID");
    }
    fd_ = socket(PF_CAN, SOCK_RAW | SOCK_NONBLOCK | SOCK_CLOEXEC, CAN_RAW);
    if (fd_ < 0) {
        system_failure("SocketCAN socket");
    }
    try {
        const int enabled = 1;
        option(fd_, SOL_CAN_RAW, CAN_RAW_FD_FRAMES, &enabled, sizeof(enabled));
        option(fd_, SOL_SOCKET, SO_RXQ_OVFL, &enabled, sizeof(enabled));
        if (options.receive_buffer_bytes) {
            option(fd_, SOL_SOCKET, SO_RCVBUF, &*options.receive_buffer_bytes, sizeof(int));
        }
        if (receive_id) {
            const can_filter filter{*receive_id, CAN_SFF_MASK};
            option(fd_, SOL_CAN_RAW, CAN_RAW_FILTER, &filter, sizeof(filter));
        } else {
            option(fd_, SOL_CAN_RAW, CAN_RAW_FILTER, nullptr, 0);
        }
        ifreq request{};
        std::copy(interface_name.begin(), interface_name.end(), request.ifr_name);
        if (ioctl(fd_, SIOCGIFINDEX, &request) != 0) {
            system_failure("SocketCAN interface index");
        }
        const int index = request.ifr_ifindex;
        if (ioctl(fd_, SIOCGIFMTU, &request) != 0) {
            system_failure("SocketCAN interface MTU");
        }
        if (request.ifr_mtu != CANFD_MTU) {
            throw std::runtime_error("SocketCAN interface requires CAN FD MTU 72");
        }
        sockaddr_can address{};
        address.can_family = AF_CAN;
        address.can_ifindex = index;
        if (bind(fd_, reinterpret_cast<const sockaddr*>(&address), sizeof(address)) != 0) {
            system_failure("SocketCAN bind");
        }
    } catch (...) {
        close(fd_);
        fd_ = -1;
        throw;
    }
}

Endpoint::~Endpoint() {
    if (fd_ >= 0) {
        close(fd_);
    }
}

int Endpoint::receive_buffer_bytes() const {
    int value = 0; socklen_t size = sizeof(value);
    if (getsockopt(fd_, SOL_SOCKET, SO_RCVBUF, &value, &size) != 0) system_failure("SocketCAN SO_RCVBUF");
    return value;
}

void Endpoint::send(const Frame& frame) {
    send_impl(frame, std::nullopt);
}
bool Endpoint::send_before(const Frame& frame, std::uint64_t expires_at_ns) {
    return send_impl(frame, expires_at_ns);
}
bool Endpoint::send_impl(const Frame& frame, std::optional<std::uint64_t> expires_at_ns) {
    const auto identifier = frame.can_id & CAN_EFF_MASK;
    if ((frame.can_id & CAN_ERR_FLAG) != 0 ||
        ((frame.can_id & CAN_EFF_FLAG) == 0 && identifier > CAN_SFF_MASK) ||
        (frame.is_fd && ((frame.can_id & CAN_RTR_FLAG) != 0 || !fd_length(frame.payload_length) ||
                        (frame.fd_flags & ~(CANFD_BRS | CANFD_ESI | CANFD_FDF)) != 0)) ||
        (!frame.is_fd && (frame.payload_length > CAN_MAX_DLEN || frame.fd_flags != 0))) {
        throw std::invalid_argument("SocketCAN TX envelope/length/flags");
    }
    // 송신 종류마다 해당 Linux ABI struct를 만든다.
    canfd_frame fd_frame{};
    can_frame classic_frame{};
    const void* data;
    std::size_t size;
    if (frame.is_fd) {
        fd_frame.can_id = frame.can_id;
        fd_frame.len = frame.payload_length;
        fd_frame.flags = frame.fd_flags;
        std::copy_n(frame.payload.begin(), frame.payload_length, fd_frame.data);
        data = &fd_frame;
        size = sizeof(fd_frame);
    } else {
        classic_frame.can_id = frame.can_id;
        classic_frame.len = frame.payload_length;
        std::copy_n(frame.payload.begin(), frame.payload_length, classic_frame.data);
        data = &classic_frame;
        size = sizeof(classic_frame);
    }
    if (expires_at_ns && monotonic_time_ns() >= *expires_at_ns) return false;
    const auto sent = write(fd_, data, size);
    if (sent < 0) {
        system_failure("SocketCAN nonblocking write");
    }
    if (static_cast<std::size_t>(sent) != size) {
        throw std::runtime_error("SocketCAN incomplete write");
    }
    return true;
}

std::optional<ReceivedFrame> Endpoint::receive() {
    canfd_frame native{};
    alignas(cmsghdr) std::array<unsigned char, CMSG_SPACE(sizeof(std::uint32_t))> control{};
    iovec buffer{&native, sizeof(native)};
    msghdr message{};
    message.msg_iov = &buffer;
    message.msg_iovlen = 1;
    message.msg_control = control.data();
    message.msg_controllen = control.size();
    const auto size = recvmsg(fd_, &message, MSG_DONTWAIT);
    if (size < 0) {
        if (errno == EAGAIN || errno == EWOULDBLOCK || errno == EINTR) {
            return std::nullopt;
        }
        system_failure("SocketCAN recvmsg");
    }
    if ((size != CAN_MTU && size != CANFD_MTU) ||
        (message.msg_flags & (MSG_TRUNC | MSG_CTRUNC)) != 0) {
        throw std::runtime_error("SocketCAN truncated/unknown native frame");
    }
    for (auto* header = CMSG_FIRSTHDR(&message); header; header = CMSG_NXTHDR(&message, header)) {
        if (header->cmsg_level == SOL_SOCKET && header->cmsg_type == SO_RXQ_OVFL) {
            if (header->cmsg_len != CMSG_LEN(sizeof(dropped_frames_))) {
                throw std::runtime_error("SocketCAN malformed drop counter");
            }
            std::memcpy(&dropped_frames_, CMSG_DATA(header), sizeof(dropped_frames_));
        }
    }
    Frame frame;
    frame.can_id = native.can_id;
    frame.is_fd = size == CANFD_MTU;
    frame.fd_flags = frame.is_fd ? native.flags : 0;  // Classical padding은 FD flag가 아니다.
    frame.payload_length = native.len;
    if (frame.payload_length > (frame.is_fd ? CANFD_MAX_DLEN : CAN_MAX_DLEN)) {
        throw std::runtime_error("SocketCAN invalid native payload length");
    }
    std::copy_n(native.data, frame.payload_length, frame.payload.begin());
    return ReceivedFrame{frame, dropped_frames_};
}

std::uint64_t monotonic_time_ns() {
    timespec now{};
    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0) {
        system_failure("CLOCK_MONOTONIC");
    }
    return static_cast<std::uint64_t>(now.tv_sec) * 1000000000ULL +
           static_cast<std::uint64_t>(now.tv_nsec);
}
}  // namespace stratadrive::socketcan
