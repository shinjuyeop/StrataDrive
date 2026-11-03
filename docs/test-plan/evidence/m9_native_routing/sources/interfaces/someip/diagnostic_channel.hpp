#pragma once
#include "diagnostic_binding.hpp"
#include <vsomeip/vsomeip.hpp>
#include <atomic>
#include <deque>
#include <memory>
#include <mutex>
#include <optional>

namespace stratadrive::someip::diagnostic {
// Dedicated bounded lane on an externally owned SDK application. Configure
// before dispatch, notify registered on its SDK state callback, and keep alive
// until all SDK callbacks have joined. This object never stops the shared app.
class Channel {
public:
    static constexpr std::size_t kCapacity=8;
    Channel(Role,std::uint64_t stream,std::uint32_t registry,Services={});
    void configure(const std::shared_ptr<vsomeip::application>&);
    void registered();
    bool send(const diagnostics::wire::Bytes&);
    std::optional<diagnostics::wire::Bytes> pop();
    bool available() const noexcept {return available_.load();}
    struct Stats {std::uint64_t received,rejected,send_returned,dropped;std::size_t highwater;};
    Stats stats() const noexcept;
private:
    const Role role_;const std::uint64_t stream_;const std::uint32_t registry_;const Services services_;
    std::shared_ptr<vsomeip::application> app_;
    std::mutex mutex_;std::deque<diagnostics::wire::Bytes> received_;
    std::atomic<bool> available_{false};
    std::atomic<std::uint64_t> count_{0},rejected_{0},sent_{0},dropped_{0};std::atomic<std::size_t> highwater_{0};
};
} // namespace stratadrive::someip::diagnostic
