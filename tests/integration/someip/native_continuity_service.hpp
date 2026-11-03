#pragma once
#include "continuity_service.hpp"
#include "service_evidence.hpp"
#include "latest_snapshot.hpp"
#include <filesystem>
#include <thread>

namespace stratadrive::someip::test {
// Terminal opt-in service composition. Capture producers have ended; SDK/control
// owners stay alive in protection solely to supply real current physical Actuals.
class NativeContinuityService {
public:
    explicit NativeContinuityService(const std::filesystem::path& folder);
    ~NativeContinuityService();
    void publish(const diagnostics::ServiceEvidence& evidence) {current_.publish(evidence);}
    void start();
    bool done() const noexcept {return done_.load(std::memory_order_acquire);}
    bool passed() const noexcept {return done() && passed_;}
private:
    void work();
    std::filesystem::path folder_;
    runtime::LatestSnapshot<diagnostics::ServiceEvidence> current_;
    std::thread worker_;std::atomic<bool> done_{false},stop_{false};bool passed_{false};
};
} // namespace stratadrive::someip::test
