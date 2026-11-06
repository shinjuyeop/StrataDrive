#pragma once
#include "control_diagnostics.hpp"
#include "diagnostics_delivery.hpp"
#include "run_lease_gate.hpp"

namespace stratadrive::diagnostics {
// Trusted manifest entry, never learned from received traffic. Ranges begin at
// first_epoch and end before the next entry. First range starts at epoch1.
struct CentralIssuer {std::uint64_t producer;std::uint32_t first_epoch;};
// Single non-RT writer. The manifest binds the authenticated/trusted Central
// peer; CRC/this object do not authenticate it. Supply the unmodified Session
// from that peer and a snapshot copied by the actual local endpoint owner.
// Local Ready alone cannot admit a Session. No control gate or clear authority.
class ContextualOutbox {
public:
    static constexpr std::size_t kPending=32;
    ContextualOutbox(FileJournal&,ControlContext local,std::uint64_t central_producer);
    ContextualOutbox(FileJournal&,ControlContext local,std::vector<CentralIssuer> trusted_lineage);
    ContextualOutbox(EpochRecorder&,ControlContext local,std::uint64_t central_producer);
    ContextualOutbox(EpochRecorder&,ControlContext local,std::vector<CentralIssuer> trusted_lineage);
    ~ContextualOutbox();
    ContextualOutbox(const ContextualOutbox&)=delete;
    ContextualOutbox& operator=(const ContextualOutbox&)=delete;
    Result context(const Event& central_session,const remote::RunLeaseEvidence&);
    // Re-admit the original durable Session only against evidence captured by
    // the still-authoritative local endpoint. Never creates/renews RunLease.
    Result restore(const remote::RunLeaseEvidence&);
    // Accepted means queued or committed, not a durable delivery receipt.
    // Only next() exposes committed events. Pending events retain original IDs.
    Result submit(const Event& local_event);
    std::size_t drain(EventQueue&,std::size_t budget=EventQueue::kCapacity);
    std::size_t pending() const noexcept { return pending_.size(); }
    std::optional<wire::Bytes> next() { return outbox_.next(); }
    Result acknowledge(const wire::Bytes& b) { return outbox_.acknowledge(b); }
    std::uint64_t acknowledged() const noexcept { return outbox_.acknowledged(); }
    bool healthy() const noexcept { return outbox_.healthy(); }
    const Ledger& ledger() const noexcept { return outbox_.ledger(); }
private:
    void initialize();
    Result commit(const Event&);
    bool matches(const Event&) const noexcept;
    std::uint64_t issuer(std::uint32_t epoch) const noexcept;
    Outbox outbox_; const ControlContext local_; const std::vector<CentralIssuer> issuers_;
    std::optional<Event> context_,retained_context_; std::vector<Event> pending_;
};
} // namespace stratadrive::diagnostics
