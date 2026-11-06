#pragma once
#include "diagnostic_wire.hpp"
#include "diagnostics_journal.hpp"
#include "epoch_recorder.hpp"
#include <optional>
#include <memory>

namespace stratadrive::diagnostics {
// Shared non-RT event-only view. Epoch families expose global committed
// ordinals without flattening retained history into an unbounded vector.
class DeliveryStore {
public:
    explicit DeliveryStore(FileJournal&);
    explicit DeliveryStore(EpochRecorder&);
    std::uint64_t store_id() const noexcept;
    std::uint32_t registry_revision() const noexcept;
    std::uint64_t size() const noexcept;
    Event event(std::uint64_t ordinal) const;
    Receipt record(const Event&);
    std::size_t drain(EventQueue&,std::size_t);
    bool healthy() const noexcept;
    const Ledger& ledger() const noexcept;
    void recording_gap() noexcept;
private:
    FileJournal* journal_{nullptr};EpochRecorder* epochs_{nullptr};
    std::unique_ptr<Recorder> recorder_;
};
// One non-RT owner per object/store. Explicitly provision both journals with
// the same unique stream ID/registry; use a trusted transport peer. Event only.
// ACK never removes history. Sender restart replays from ordinal 1.
class Outbox {
public:
    explicit Outbox(FileJournal&);
    explicit Outbox(EpochRecorder&);
    Receipt record(const Event& e) { return store_.record(e); }
    std::size_t drain(EventQueue& q,std::size_t budget=EventQueue::kCapacity) { return store_.drain(q,budget); }
    std::optional<wire::Bytes> next();
    Result acknowledge(const wire::Bytes&);
    // Explicit non-RT handover to a fresh replica. Same immutable history;
    // ACKs cannot skip the new in-flight ordinal. No authority or clear effect.
    void restart_delivery() noexcept { acknowledged_=0;in_flight_=0; }
    std::uint64_t acknowledged() const noexcept { return acknowledged_; }
    bool healthy() const noexcept { return store_.healthy(); }
    const Ledger& ledger() const noexcept { return store_.ledger(); }
    std::uint64_t size() const noexcept { return store_.size(); }
    Event event(std::uint64_t ordinal) const { return store_.event(ordinal); }
    void recording_gap() noexcept { store_.recording_gap(); }
private:
    DeliveryStore store_;
    std::uint64_t acknowledged_{0},in_flight_{0};
};
struct DeliveryReceipt { Result result; std::optional<wire::Bytes> ack; std::uint64_t watermark; };
class Inbox {
public:
    explicit Inbox(FileJournal&);
    explicit Inbox(EpochRecorder&);
    DeliveryReceipt receive(const wire::Bytes&);
    bool healthy() const noexcept { return store_.healthy(); }
    const Ledger& ledger() const noexcept { return store_.ledger(); }
private:
    DeliveryStore store_;
};
// Historical committed prefix only, including a valid prefix of an unclean
// source with an uncommitted tail. No append/repair/clear API. The caller must
// report unverified continuity in the new producer's stream; delivery does not
// certify completeness of the old source or qualify current readiness.
class CommittedReplay {
public:
    explicit CommittedReplay(const FileJournal&);
    std::optional<wire::Bytes> next();
    Result acknowledge(const wire::Bytes&);
    std::uint64_t acknowledged() const noexcept { return acknowledged_; }
    bool source_complete() const noexcept;
private:
    const FileJournal& journal_; Ledger checked_;
    std::uint64_t acknowledged_{0},in_flight_{0};
};
// One non-RT owner, one merged recorder, all explicitly provisioned replicas.
// Construct before live input. Reconcile durable replica prefixes left by a
// crash between replica and merged commit; reset current projections to Unknown.
// Never ACK until both stores contain the exact original event.
class MergedCollector {
public:
    MergedCollector(FileJournal& merged,const std::vector<FileJournal*>& replicas,
                    const std::vector<const FileJournal*>& predecessor_history = {});
    DeliveryReceipt receive(const wire::Bytes&);
    Receipt record(const Event& e) { return recorder_.record(e); }
    bool healthy() const noexcept;
    const Ledger& ledger() const noexcept { return recorder_.ledger(); }
private:
    struct Replica { FileJournal* journal; std::unique_ptr<Inbox> inbox; };
    FileJournal& merged_; Recorder recorder_; std::vector<Replica> replicas_;
};
// Fixed, explicitly provisioned source set; every source must send an ordered
// Session/Attempt boundary before events of a newer epoch. One unmerged entry
// per stream, no timeout exclusion, no synthetic Session. All events (including
// Central startup events) enter through replicas, never direct merged writes.
// Context distribution must remain independent of these delivery ACKs.
class EpochMergedCollector {
public:
    static constexpr std::size_t kSources=32;
    EpochMergedCollector(EpochRecorder& merged,const std::vector<EpochRecorder*>& replicas);
    DeliveryReceipt receive(const wire::Bytes&);
    bool healthy() const noexcept;
    const Ledger& ledger() const noexcept { return merged_.ledger(); }
private:
    struct Replica {
        EpochRecorder* store;std::unique_ptr<Inbox> inbox;
        std::uint64_t consumed{0};std::optional<Event> head;
    };
    Result reconcile();
    EpochRecorder& merged_;std::vector<Replica> replicas_;std::uint32_t epoch_{0};std::uint64_t run_{0};
};
} // namespace stratadrive::diagnostics
