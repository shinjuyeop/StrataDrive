#include "perception_2k_receiver.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <tuple>

namespace stratadrive::central {
namespace {
constexpr auto max_ns=std::numeric_limits<std::uint64_t>::max();
bool deadline(std::uint64_t source,std::uint64_t expiry) noexcept {
    return source<=max_ns-kPerceptionLifetimeNs && expiry==source+kPerceptionLifetimeNs;
}
bool valid_detection(const ImageDetection& d) noexcept {
    double threshold=2;
    switch(d.class_id) {
    case 0:case 2:case 7:threshold=.6;break;
    case 1:threshold=.4;break;
    case 3:case 5:threshold=.5;break;
    default:break;
    }
    return std::isfinite(d.score) && d.score>=threshold && d.score<=1 &&
        std::isfinite(d.x1) && std::isfinite(d.y1) && std::isfinite(d.x2) && std::isfinite(d.y2) &&
        d.x1>=0 && d.y1>=0 && d.x1<d.x2 && d.y1<d.y2 && d.x2<=kNative2kWidth && d.y2<=kNative2kHeight;
}
double overlap(const ImageDetection& a,const ImageDetection& b) noexcept {
    const auto intersection=std::max(0.,std::min(a.x2,b.x2)-std::max(a.x1,b.x1))*
                            std::max(0.,std::min(a.y2,b.y2)-std::max(a.y1,b.y1));
    const auto area=(a.x2-a.x1)*(a.y2-a.y1)+(b.x2-b.x1)*(b.y2-b.y1)-intersection;
    return area>0 ? intersection/area : 0;
}
}
bool Native2kReceiver::start_session(Native2kSession s) noexcept {
    if(!s.epoch || s.epoch<=session_.epoch || !s.source_clock || !s.wall_clock ||
       (s.source_clock==session_.source_clock && s.source_enable_ns<last_.source_ns) ||
       (s.wall_clock==session_.wall_clock && s.wall_enable_ns<last_.wall_ns)) return false;
    session_=s; last_={s.source_enable_ns,s.wall_enable_ns,s.wall_enable_ns};
    last_frame_=last_source_=last_receipt_=0; next_track_=1; clock_fault_=false;
    current_.reset(); tracks_={}; reason_=Native2kReason::Session;
    return true;
}
bool Native2kReceiver::reject(Native2kReason reason) noexcept {
    current_.reset(); tracks_={}; reason_=reason;
    return false;
}
bool Native2kReceiver::observe(Native2kNow now) noexcept {
    if(!session_.epoch) return reject(Native2kReason::Session);
    if(clock_fault_ || now.source_ns<last_.source_ns || now.wall_ns<last_.wall_ns ||
       now.state_received_wall_ns<last_.state_received_wall_ns ||
       now.state_received_wall_ns>now.wall_ns || now.state_received_wall_ns<session_.wall_enable_ns) {
        clock_fault_=true;
        return reject(Native2kReason::Clock);
    }
    last_=now;
    if(now.wall_ns-now.state_received_wall_ns>=kPerceptionLifetimeNs)
        return reject(Native2kReason::StateStale);
    return true;
}
bool Native2kReceiver::receive(const Native2kFrame& f,Native2kNow now) noexcept {
    if(!observe(now)) return false;
    if(f.epoch!=session_.epoch || f.source_clock!=session_.source_clock || f.wall_clock!=session_.wall_clock ||
       f.camera_id!=1 || f.calibration_revision!=1 || f.model_hash!=kNative2kModelHash)
        return reject(Native2kReason::Identity);
    if(!f.valid || f.schema!=1 || f.candidate!=1 || !f.frame || f.width!=kNative2kWidth ||
       f.height!=kNative2kHeight || f.count>kMaxDetections) return reject(Native2kReason::Invalid);
    for(std::size_t i=0;i<f.count;++i)
        if(!valid_detection(f.detections[i])) return reject(Native2kReason::Invalid);
    if(f.source_ns<session_.source_enable_ns || f.source_ns>now.source_ns ||
       !deadline(f.source_ns,f.expires_ns) || now.source_ns>=f.expires_ns)
        return reject(Native2kReason::SourceExpired);
    if(f.received_wall_ns<session_.wall_enable_ns || f.received_wall_ns>now.wall_ns ||
       !deadline(f.received_wall_ns,f.wall_expires_ns) || now.wall_ns>=f.wall_expires_ns)
        return reject(Native2kReason::ReceiptExpired);
    if(f.frame<=last_frame_ || (last_frame_ && (f.source_ns<=last_source_ || f.received_wall_ns<last_receipt_)))
        return reject(Native2kReason::Replay);
    // Even when the caller did not poll during a gap, expired histories cannot coast.
    if(current_ && (now.source_ns>=current_->expires_ns || now.wall_ns>=current_->wall_expires_ns)) tracks_={};
    if(last_frame_ && (f.source_ns-last_source_>kPerceptionLifetimeNs ||
                      f.received_wall_ns-last_receipt_>kPerceptionLifetimeNs)) tracks_={};
    // Never wrap track identities in the same session.
    if(next_track_>max_ns-kMaxDetections) return reject(Native2kReason::Invalid);
    update_tracks(f);
    last_frame_=f.frame; last_source_=f.source_ns; last_receipt_=f.received_wall_ns;
    current_=f; reason_=Native2kReason::Accepted;
    return true;
}
void Native2kReceiver::unavailable(Native2kNow now) noexcept {
    if(observe(now)) reject(Native2kReason::Unavailable);
}
const Native2kFrame* Native2kReceiver::snapshot(Native2kNow now) noexcept {
    if(!observe(now)) return nullptr;
    if(current_ && now.source_ns>=current_->expires_ns) reject(Native2kReason::SourceExpired);
    if(current_ && now.wall_ns>=current_->wall_expires_ns) reject(Native2kReason::ReceiptExpired);
    return current_ ? &*current_ : nullptr;
}
void Native2kReceiver::update_tracks(const Native2kFrame& f) noexcept {
    struct Match { double negative_overlap; std::uint64_t id; std::size_t track,detection; };
    std::array<Match,kMaxDetections*kMaxDetections> matches{};
    std::size_t count=0;
    for(std::size_t ti=0;ti<tracks_.count;++ti) {
        const auto& track=tracks_.tracks[ti];
        const auto& previous=track.history[track.count-1].detection;
        for(std::size_t di=0;di<f.count;++di) if(previous.class_id==f.detections[di].class_id) {
            const auto iou=overlap(previous,f.detections[di]);
            if(iou>=.3) matches[count++]={-iou,track.id,ti,di};
        }
    }
    std::sort(matches.begin(),matches.begin()+count,[](const Match& a,const Match& b) {
        return std::tie(a.negative_overlap,a.id,a.detection)<std::tie(b.negative_overlap,b.id,b.detection);
    });
    std::array<bool,kMaxDetections> used{};
    std::array<std::size_t,kMaxDetections> assigned{}; assigned.fill(kMaxDetections);
    for(std::size_t i=0;i<count;++i) {
        const auto& m=matches[i];
        if(!used[m.track] && assigned[m.detection]==kMaxDetections) {
            used[m.track]=true; assigned[m.detection]=m.track;
        }
    }
    Native2kTracks next{}; next.count=f.count;
    for(std::size_t di=0;di<f.count;++di) {
        auto& t=next.tracks[di];
        if(assigned[di]!=kMaxDetections) t=tracks_.tracks[assigned[di]];
        else t.id=next_track_++;
        if(t.count==t.history.size()) {
            for(std::size_t i=1;i<t.count;++i)t.history[i-1]=t.history[i];
            --t.count;
        }
        t.history[t.count++]={f.frame,f.source_ns,f.detections[di]};
    }
    tracks_=next;
}
} // namespace stratadrive::central
