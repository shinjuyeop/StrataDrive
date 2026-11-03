#pragma once
#include "producer_lifecycle.hpp"
#include <optional>

namespace stratadrive::diagnostics {
struct StreamBinding {std::uint64_t stream,producer;};
// Frozen, single-writer observations. Caller quiesces producer/transport users;
// these references are never read concurrently with a journal mutation.
struct StreamState {
    const FileJournal* source{nullptr};const FileJournal* replica{nullptr};
    std::uint64_t acknowledged{0},pending{0};EventQueue::Health queue{};
};
enum class ReviewBlock { None, Request, Session, Incident, Streams, Pending, Storage };
struct ContinuityPlan {Event proof;ContinuityReview review;Event passed;};
struct ReviewPreparation {ReviewBlock blocked;std::optional<ContinuityPlan> plan;};
// Local non-RT service boundary. Manifest and request/evidence are trusted input,
// not learned from the network. No file repair, actuator or control authority.
class ContinuityInspector {
public:
    ContinuityInspector(ControlContext service,std::vector<StreamBinding> manifest);
    ReviewPreparation prepare(const Ledger&,EventId incident,const Event& original_global,
        const std::vector<StreamState>& frozen,ContinuityDisposition,const ServiceEvidence&,
        std::uint64_t first_sequence) const;
private:
    ControlContext service_;std::vector<StreamBinding> manifest_;
};
} // namespace stratadrive::diagnostics
