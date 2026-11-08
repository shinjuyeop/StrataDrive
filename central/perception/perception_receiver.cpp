#include "perception_receiver.hpp"

#include <cmath>
#include <limits>

namespace stratadrive::central {
namespace {
bool valid_detection(const ImageDetection& d) noexcept {
    const bool supported = d.class_id==0 || d.class_id==1 || d.class_id==2 ||
                           d.class_id==3 || d.class_id==5 || d.class_id==7;
    return supported && std::isfinite(d.score) && d.score>=0.35 && d.score<=1 &&
        std::isfinite(d.x1) && std::isfinite(d.y1) && std::isfinite(d.x2) && std::isfinite(d.y2) &&
        d.x1>=0 && d.y1>=0 && d.x1<d.x2 && d.y1<d.y2 && d.x2<=640 && d.y2<=384;
}
}
bool PerceptionReceiver::start_session(std::uint32_t epoch, std::uint64_t clock,
                                     std::uint64_t enable) noexcept {
    if(epoch<=epoch_ || !clock || (clock==clock_ && enable<last_now_)) return false;
    epoch_=epoch; clock_=clock; enable_=enable; last_now_=enable;
    last_frame_=last_source_=0; clock_fault_=false; current_.reset();
    reason_=PerceptionReason::Session;
    return true;
}
bool PerceptionReceiver::reject(PerceptionReason reason) noexcept {
    current_.reset(); reason_=reason;
    return false;
}
bool PerceptionReceiver::observe_clock(std::uint64_t now) noexcept {
    if(!epoch_) return reject(PerceptionReason::Session);
    if(clock_fault_ || now<last_now_ || now<enable_) {
        clock_fault_=true;
        return reject(PerceptionReason::Clock);
    }
    last_now_=now;
    return true;
}
bool PerceptionReceiver::receive(const PerceptionFrame& f, std::uint64_t now) noexcept {
    if(!observe_clock(now)) return false;
    if(f.epoch!=epoch_ || f.clock_instance!=clock_ || f.camera_id!=1 ||
       f.calibration_revision!=1 || f.model_hash!=kPerceptionModelHash)
        return reject(PerceptionReason::Identity);
    if(!f.valid || f.schema!=1 || !f.frame || f.width!=640 || f.height!=384 || f.count>kMaxDetections)
        return reject(PerceptionReason::Invalid);
    for(std::size_t i=0;i<f.count;++i)
        if(!valid_detection(f.detections[i])) return reject(PerceptionReason::Invalid);
    if(f.source_ns<enable_ || f.source_ns>now ||
       f.source_ns>std::numeric_limits<std::uint64_t>::max()-kPerceptionLifetimeNs ||
       f.expires_ns!=f.source_ns+kPerceptionLifetimeNs || now>=f.expires_ns)
        return reject(PerceptionReason::Stale);
    if(f.frame<=last_frame_ || (last_frame_ && f.source_ns<=last_source_))
        return reject(PerceptionReason::Replay);
    last_frame_=f.frame; last_source_=f.source_ns; current_=f;
    reason_=PerceptionReason::Accepted;
    return true;
}
const PerceptionFrame* PerceptionReceiver::snapshot(std::uint64_t now) noexcept {
    if(!observe_clock(now)) return nullptr;
    if(current_ && now>=current_->expires_ns) reject(PerceptionReason::Stale);
    return current_ ? &*current_ : nullptr;
}
} // namespace stratadrive::central
