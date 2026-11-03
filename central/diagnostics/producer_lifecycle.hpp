#pragma once
#include "control_diagnostics.hpp"
#include "diagnostics_journal.hpp"

namespace stratadrive::diagnostics {
// Startup/shutdown only, with the FileJournal lifetime lock held. This private
// journal's epoch counts process incarnations; it is never a global Session or
// a transport stream. No destructor marks a process clean.
class ProducerLifecycle {
public:
    ProducerLifecycle(const std::string& directory,ControlContext identity,std::uint64_t started_ns);
    std::uint32_t generation() const noexcept { return generation_; }
    bool previous_unclean() const noexcept { return previous_unclean_; }
    std::uint64_t producer(std::uint32_t logical_source) const;
    Result close(std::uint64_t stopped_ns);
private:
    FileJournal journal_;Recorder recorder_;const ControlContext identity_;const std::uint64_t started_;
    std::uint32_t generation_{0};bool previous_unclean_{false},closed_{false};
};
// One real unclean restart, not a guessed number of lost events. Publish only
// after the new genuine Session/accepted local credit. Unmapped is sticky:
// unknown pre-commit loss prevents clear while durable delivery remains usable.
Event continuity_fault(ControlContext,std::uint32_t logical_source,std::uint32_t generation,
    Component,std::uint32_t session_epoch,std::uint64_t enable_ns,
    std::uint64_t original_boot_ns,std::uint64_t observed_ns);
} // namespace stratadrive::diagnostics
