#pragma once

#include "session_mailbox.hpp"
#include "normal_stop.hpp"
#include "command_gateway.hpp"
#include "rear_power_gateway.hpp"

#include <atomic>

namespace stratadrive::transport {
class Clock {
public:
    virtual ~Clock() = default;
    virtual std::uint64_t now_ns() noexcept = 0;
};
class RunGate {
public:
    void close() noexcept { epoch_.store(0,std::memory_order_release); }
    void release(std::uint32_t epoch) noexcept { epoch_.store(epoch,std::memory_order_release); }
    bool allows(std::uint32_t epoch) const noexcept { return epoch!=0 && epoch_.load(std::memory_order_acquire)==epoch; }
    std::uint32_t epoch() const noexcept { return epoch_.load(std::memory_order_acquire); }
private:
    std::atomic<std::uint32_t> epoch_{0};
};
// Priority protection survives a failed/full normal FIFO. Epoch is never reset
// in place; newer trusted INIT makes old signals irrelevant, not vice versa.
struct Protection {
    std::atomic<std::uint32_t> requested{0},selected{0};
    void request(std::uint32_t epoch) noexcept {
        auto old=requested.load(std::memory_order_relaxed);
        while(old<epoch && !requested.compare_exchange_weak(old,epoch,std::memory_order_release,std::memory_order_relaxed)) {}
    }
    bool pending(std::uint32_t epoch) const noexcept { return epoch!=0 && requested.load(std::memory_order_acquire)>=epoch; }
    bool acknowledged(std::uint32_t epoch) const noexcept { return epoch!=0 && selected.load(std::memory_order_acquire)==epoch; }
};
constexpr std::size_t kBudget=8;
constexpr std::uint64_t kResultBudgetNs=20000000ULL;
struct InputEvidence { std::uint32_t epoch{0}; std::uint64_t source_ns{0},received_ns{0}; };
template<class Sample> InputEvidence input_evidence(const std::optional<Sample>& accepted) {
    return accepted?InputEvidence{accepted->message.epoch,accepted->message.source_time_ns,accepted->received_time_ns}:InputEvidence{};
}
enum class Operation : std::size_t { Lifecycle, Vehicle, Power, Commands, Arm, Stop };
struct Arm {};
using ZoneWork=std::variant<central::LifecycleRequest,central::VehicleRequest,central::VehicleManagementOutput,
    central::ScopedCommands,Arm,central::NormalStopPlan>;
struct ZoneRequest {
    std::uint32_t epoch{0}; std::uint64_t token{0},sent_ns{0},deadline_ns{0}; ZoneWork work;
};
struct TxResult {
    std::uint32_t epoch{0}; std::uint64_t token{0},source_ns{0}; Operation operation{Operation::Lifecycle};
    bool accepted{false}; std::size_t frames{0};
};
using Feedback=std::variant<can::SteeringFrame,can::BrakeFrame,can::DriveFrame,can::BmsFrame,zone::ZoneHealthSnapshot>;
struct ZoneLink {
    session::SessionMailbox<ZoneRequest,kBudget> work;
    session::SessionMailbox<TxResult,kBudget> results;
    session::SessionMailbox<Feedback,kBudget> feedback;
    Protection protection;
    bool failed() const { return work.failed() || results.failed() || feedback.failed(); }
};
enum class Leaf : std::size_t { Steering,Brake,Drive,Bms,Power,Count };
constexpr std::size_t kLeaves=static_cast<std::size_t>(Leaf::Count);
enum class LeafOperation { Frame,Arm,Stop };
struct LeafRequest {
    std::uint32_t epoch{0}; std::uint64_t token{0},sent_ns{0},deadline_ns{0}; LeafOperation operation{LeafOperation::Frame};
    Feedback frame;
    std::optional<central::CommandContext> command;
    std::optional<can::BmsParentContext> parent;
    std::optional<ActuatorStopLease> lease;
};
struct LeafResult { std::uint32_t epoch; std::uint64_t token,source_ns; LeafOperation operation; bool accepted; };
using LeafReport=std::variant<Feedback,LeafResult>;
struct LeafLink {
    session::SessionMailbox<LeafRequest,kBudget> work;
    session::SessionMailbox<LeafReport,kBudget> reports;
    Protection protection;
    bool failed() const { return work.failed() || reports.failed(); }
};
inline Operation operation(const ZoneWork& work) { return static_cast<Operation>(work.index()); }
}  // namespace stratadrive::transport
