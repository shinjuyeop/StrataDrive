#pragma once
#include "diagnostic_wire.hpp"
#include "diagnostics_journal.hpp"
#include <optional>

namespace stratadrive::diagnostics {
// One non-RT owner per object/store. Explicitly provision both journals with
// the same unique stream ID/registry; use a trusted transport peer. Event only.
// ACK never removes history. Sender restart replays from ordinal 1.
class Outbox {
public:
    explicit Outbox(FileJournal&);
    Receipt record(const Event& e) { return recorder_.record(e); }
    std::size_t drain(EventQueue& q,std::size_t budget=EventQueue::kCapacity) { return recorder_.drain(q,budget); }
    std::optional<wire::Bytes> next();
    Result acknowledge(const wire::Bytes&);
    std::uint64_t acknowledged() const noexcept { return acknowledged_; }
    bool healthy() const noexcept { return journal_.writable() && recorder_.ledger().complete(); }
    const Ledger& ledger() const noexcept { return recorder_.ledger(); }
    void recording_gap() noexcept { recorder_.recording_gap(); }
private:
    FileJournal& journal_; Recorder recorder_;
    std::uint64_t acknowledged_{0},in_flight_{0};
};
struct DeliveryReceipt { Result result; std::optional<wire::Bytes> ack; std::uint64_t watermark; };
class Inbox {
public:
    explicit Inbox(FileJournal&);
    DeliveryReceipt receive(const wire::Bytes&);
    bool healthy() const noexcept { return journal_.writable() && recorder_.ledger().complete(); }
    const Ledger& ledger() const noexcept { return recorder_.ledger(); }
private:
    FileJournal& journal_; Recorder recorder_;
};
} // namespace stratadrive::diagnostics
