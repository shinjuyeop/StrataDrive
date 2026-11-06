#pragma once
#include "diagnostics_delivery.hpp"

namespace stratadrive::diagnostics {
// Locally provisioned publisher pairs; never learned from incoming events.
struct EpochPublishers {std::uint64_t startup,control;std::uint32_t first_epoch;};
// Non-RT merger of a Central startup publisher and its control observer. The
// caller's retired_epoch is published only AFTER the actual old owner stops.
// Drain both SPSC queues after acquiring that cut, before committing a newer
// Attempt. Context distribution consumes originals separately from merge ACKs.
class EpochLocalSpool {
public:
    EpochLocalSpool(EpochRecorder&,std::uint64_t startup_producer,std::uint64_t control_producer);
    EpochLocalSpool(EpochRecorder&,std::uint64_t startup_producer,std::uint64_t control_producer,
                    std::vector<EpochPublishers> lineage);
    ~EpochLocalSpool();
    std::size_t drain(EventQueue& startup,EventQueue& control,std::uint32_t retired_epoch);
    std::size_t pending() const noexcept {return pending_.size();}
    bool healthy() const noexcept {return out_.healthy();}
    Outbox& delivery() noexcept {return out_;}
private:
    bool bound(const Event&,bool startup) const noexcept;
    Outbox out_;const std::uint64_t startup_,control_;
    const std::vector<EpochPublishers> lineage_;
    std::uint32_t retired_{0};std::vector<Event> pending_;
};
} // namespace stratadrive::diagnostics
