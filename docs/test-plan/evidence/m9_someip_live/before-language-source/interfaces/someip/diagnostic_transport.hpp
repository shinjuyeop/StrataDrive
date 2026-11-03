#pragma once
#include "diagnostic_binding.hpp"
#include <vsomeip/vsomeip.hpp>
#include <atomic>
#include <deque>
#include <memory>
#include <mutex>
#include <optional>
#include <thread>

namespace stratadrive::someip::diagnostic {
// Dedicated non-RT SDK application. Callback validates/enqueues only; callers
// own journal IO and retries. This object carries no control/clear authority.
class Transport {
public:
    static constexpr std::size_t kCapacity=8;
    Transport(Role,std::uint64_t stream,std::uint32_t registry,const std::string& application);
    ~Transport();
    Transport(const Transport&)=delete;
    Transport& operator=(const Transport&)=delete;
    void start();
    void stop();
    bool send(const diagnostics::wire::Bytes&);
    std::optional<diagnostics::wire::Bytes> pop();
    bool available() const noexcept { return available_.load(); }
    struct Stats { std::uint64_t received,rejected,send_returned,dropped; std::size_t highwater; };
    Stats stats() const noexcept;
private:
    const Role role_; const std::uint64_t stream_; const std::uint32_t registry_;
    std::shared_ptr<vsomeip::application> app_; std::thread dispatch_;
    std::mutex mutex_; std::deque<diagnostics::wire::Bytes> received_;
    std::atomic<bool> available_{false};
    std::atomic<std::uint64_t> count_{0},rejected_{0},sent_{0},dropped_{0};
    std::atomic<std::size_t> highwater_{0};
};
} // namespace stratadrive::someip::diagnostic
