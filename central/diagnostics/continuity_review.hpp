#pragma once
#include "producer_lifecycle.hpp"
#include "epoch_recorder.hpp"
#include <optional>

namespace stratadrive::diagnostics {
struct StreamBinding {std::uint64_t stream,producer;};
// Frozen, single-writer observations. Caller quiesces producer/transport users;
// these references are never read concurrently with a journal mutation.
class FrozenStream {
public:
    FrozenStream()=default;
    FrozenStream(std::nullptr_t){}
    FrozenStream(const FileJournal* journal):journal_(journal){}
    FrozenStream(const EpochRecorder* epochs):epochs_(epochs){}
    explicit operator bool() const noexcept {return journal_ || epochs_;}
    bool operator==(const FrozenStream& b) const noexcept {return journal_==b.journal_ && epochs_==b.epochs_;}
    std::uint64_t store_id() const noexcept;
    std::uint32_t registry_revision() const noexcept;
    std::uint64_t size() const noexcept;
    Entry committed(std::uint64_t ordinal) const;
    bool verified() const;
private:
    const FileJournal* journal_{nullptr};const EpochRecorder* epochs_{nullptr};
};
struct StreamState {
    FrozenStream source{},replica{};
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
