#pragma once

#include "perception_2k_receiver.hpp"
#include "vehicle_coordinator.hpp"

namespace stratadrive::central {
enum class PerceptionUse { Shadow, Required };
struct PerceptionLoss {
    Native2kSession session;
    Native2kNow detected;
    Native2kReason reason;
};
struct PerceptionRelease {
    bool available{false}, would_protect{true}, latched{false}, protection_requested{false};
    Native2kReason reason{Native2kReason::Session};
    std::uint64_t frame{0};
};
// Call before the existing coordinator/controller release on the SAME owner.
// Required mode is an explicit experimental policy; no grace interval or new
// expiry. Shadow is observational. Neither mode grants normal authority.
class Native2kControl {
public:
    explicit Native2kControl(PerceptionUse use=PerceptionUse::Shadow) noexcept : use_(use) {}
    // Caller must supply the already accepted global INIT; image recovery is not INIT.
    bool start_session(Native2kSession s) noexcept {
        if(!receiver_.start_session(s)) return false;
        loss_.reset(); latched_=false; return true;
    }
    bool receive(const Native2kFrame& f,Native2kNow now) noexcept {
        const bool accepted=receiver_.receive(f,now);
        if(!accepted) record_loss(now);
        return accepted;
    }
    void unavailable(Native2kNow now) noexcept { receiver_.unavailable(now); record_loss(now); }
    PerceptionRelease release(Native2kNow now,VehicleCoordinator& coordinator) {
        const auto* current=receiver_.snapshot(now);
        if(!current) record_loss(now);
        if(latched_) coordinator.request_protection(now.source_ns);
        return {current!=nullptr,current==nullptr,latched_,latched_,receiver_.reason(),current?current->frame:0};
    }
    const Native2kReceiver& receiver() const noexcept { return receiver_; }
    const std::optional<PerceptionLoss>& first_loss() const noexcept { return loss_; }
private:
    void record_loss(Native2kNow now) noexcept {
        if(!loss_) loss_=PerceptionLoss{receiver_.session(),now,receiver_.reason()};
        if(use_==PerceptionUse::Required)latched_=true;
    }
    const PerceptionUse use_;
    Native2kReceiver receiver_;
    bool latched_{false};
    std::optional<PerceptionLoss> loss_;
};
} // namespace stratadrive::central
