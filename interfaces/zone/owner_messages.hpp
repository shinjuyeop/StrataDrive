#pragma once
// Typed application contracts. No controller, queue or atomic run/protection implementation.
#include "normal_stop_contract.hpp"
#include "zone_status.hpp"
#include <cstddef>
#include <optional>
#include <variant>

namespace stratadrive::transport {
// Application queue/drain capacity and TX/selection receipt budget, shared by adapters.
inline constexpr std::size_t kBudget=8;
inline constexpr std::uint64_t kResultBudgetNs=20000000ULL;
// Exclusive delivery bound, distinct from the inner command/lease lifetime.
// Subtract before adding: the sum cannot exceed the representable original.
inline constexpr std::uint64_t delivery_deadline(std::uint64_t first_sent,std::uint64_t original) {
    return original<=first_sent?original:first_sent+
        (original-first_sent<kResultBudgetNs?original-first_sent:kResultBudgetNs);
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
inline Operation operation(const ZoneWork& work) { return static_cast<Operation>(work.index()); }
} // namespace stratadrive::transport
