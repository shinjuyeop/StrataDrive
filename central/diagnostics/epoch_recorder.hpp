#pragma once
#include "diagnostics_journal.hpp"

namespace stratadrive::diagnostics {
struct EpochRetention {
    Limits limits{};
    std::uint32_t rotate_after_entries{256}, maximum_segments{1024};
};
// Opt-in local single-writer journal family. Auto rollover at a NEW application
// epoch; retained DTCs survive while the active event/receipt window is reclaimed.
// Predecessor bytes are immutable and remain required for duplicate receipts and
// restart verification. No RT IO, silent deletion, synthetic epoch or authority.
class EpochRecorder {
public:
    static void initialize(const std::string& root,std::uint64_t store_id,EpochRetention = {});
    explicit EpochRecorder(const std::string& root);
    ~EpochRecorder();
    EpochRecorder(const EpochRecorder&)=delete;
    EpochRecorder& operator=(const EpochRecorder&)=delete;
    Receipt record(const Event&);
    Receipt clear(const Clear&);
    Receipt review(const ContinuityReview&);
    std::size_t drain(EventQueue&,std::size_t budget=EventQueue::kCapacity);
    void recording_gap() noexcept;
    const Ledger& ledger() const noexcept;
    std::uint64_t segment() const noexcept;
    std::uint64_t watermark() const noexcept;
private:
    struct Impl;std::unique_ptr<Impl> impl_;
};
} // namespace stratadrive::diagnostics
