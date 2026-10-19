#pragma once

#include <array>
#include <cstdint>
#include <optional>
#include <string>

namespace stratadrive::socketcan {

// Linux ABI를 application codec에 노출하지 않는 transport 표현.
// can_id의 EFF/RTR/ERR bit와 수신 종류/길이를 그대로 보존한다.
struct Frame {
    std::uint32_t can_id{0};
    bool is_fd{true};
    std::uint8_t fd_flags{0};
    std::uint8_t payload_length{0};
    std::array<std::uint8_t, 64> payload{};
};

struct ReceivedFrame {
    Frame frame;
    // SO_RXQ_OVFL: 이 socket에서 누적된 kernel RX drop 수. 0도 유효하다.
    std::uint32_t dropped_frames{0};
};
struct EndpointOptions { std::optional<int> receive_buffer_bytes; };

// 실패는 exception, 빈 nonblocking RX queue는 nullopt. 소유 thread 한 개에서 사용한다.
class Endpoint {
public:
    // ID가 없으면 TX 전용. ID가 있으면 하위 11 bit만 prefilter하여
    // EFF/RTR 같은 잘못된 envelope를 application 검사까지 보존한다.
    explicit Endpoint(const std::string& interface_name,
                      std::optional<std::uint16_t> receive_id = std::nullopt,
                      EndpointOptions options = {});
    int receive_buffer_bytes() const;
    ~Endpoint();
    Endpoint(const Endpoint&) = delete;
    Endpoint& operator=(const Endpoint&) = delete;
    Endpoint(Endpoint&&) = delete;
    Endpoint& operator=(Endpoint&&) = delete;

    void send(const Frame& frame);
    // Exclusive enqueue deadline, checked after ABI serialization immediately
    // before nonblocking write. Does not cancel kernel queues or bound wire RX.
    bool send_before(const Frame& frame, std::uint64_t expires_at_ns);
    std::optional<ReceivedFrame> receive();

private:
    bool send_impl(const Frame& frame, std::optional<std::uint64_t> expires_at_ns);
    int fd_{-1};
    std::uint32_t dropped_frames_{0};
};

// SourceTimeNs와 receiver now를 같은 Linux CLOCK_MONOTONIC에서 만든다.
std::uint64_t monotonic_time_ns();

}  // namespace stratadrive::socketcan
