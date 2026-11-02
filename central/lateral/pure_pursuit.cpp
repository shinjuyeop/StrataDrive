#include "pure_pursuit.hpp"
#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <utility>

namespace stratadrive::central {
namespace {
constexpr double pi=3.14159265358979323846;
double wrap(double angle) {return std::atan2(std::sin(angle),std::cos(angle));}
}
PurePursuit::PurePursuit(std::vector<RoutePoint> route,double wheelbase)
    :route_(std::move(route)),wheelbase_(wheelbase) {
    if(route_.size()<2 || route_.size()>2001 || !std::isfinite(wheelbase) || wheelbase<1 || wheelbase>5)
        throw std::invalid_argument("route geometry");
    distance_.reserve(route_.size());distance_.push_back(0);
    for(std::size_t i=0;i<route_.size();++i) {
        const auto& p=route_[i];
        if(!std::isfinite(p.x_m) || !std::isfinite(p.y_m) || std::abs(p.x_m)>1e6 || std::abs(p.y_m)>1e6)
            throw std::invalid_argument("route coordinate");
        if(!i)continue;
        const auto& a=route_[i-1];const double d=std::hypot(p.x_m-a.x_m,p.y_m-a.y_m);
        if(d<.05 || d>5)throw std::invalid_argument("route spacing");
        distance_.push_back(distance_.back()+d);
    }
}
bool PurePursuit::start_session(std::uint32_t epoch,std::uint64_t enable) {
    if(epoch<=epoch_ || enable<enable_ || (last_ns_ && enable<*last_ns_))return false;
    epoch_=epoch;enable_=enable;last_ns_.reset();last_pose_.reset();progress_=angle_=0;fault_=false;return true;
}
std::optional<PursuitOutput> PurePursuit::step(std::uint64_t now,const RoutePose& p,double speed) {
    const auto fail=[&]() -> std::optional<PursuitOutput> {fault_=true;return std::nullopt;};
    if(fault_ || !epoch_ || p.epoch!=epoch_ || now<enable_ ||
       (last_ns_ && (now<*last_ns_ || now-*last_ns_!=20000000)) ||
       p.source_ns<enable_ || p.source_ns>now || now-p.source_ns>30000000 ||
       (last_pose_ && (p.sequence<=last_pose_->sequence || p.source_ns<=last_pose_->source_ns)) ||
       !std::isfinite(p.x_m) || !std::isfinite(p.y_m) || !std::isfinite(p.yaw_rad) || std::abs(p.yaw_rad)>pi ||
       !std::isfinite(speed) || speed<0 || speed>40/3.6)return fail();
    double best=std::numeric_limits<double>::infinity(),s=0,cross=0,heading=0;
    for(std::size_t i=0;i+1<route_.size();++i) {
        if(distance_[i+1]<progress_-2 || distance_[i]>progress_+20)continue;
        const auto& a=route_[i];const auto& b=route_[i+1];
        const double dx=b.x_m-a.x_m,dy=b.y_m-a.y_m,len=distance_[i+1]-distance_[i];
        const double u=std::clamp(((p.x_m-a.x_m)*dx+(p.y_m-a.y_m)*dy)/(len*len),0.,1.);
        const double ex=p.x_m-a.x_m-u*dx,ey=p.y_m-a.y_m-u*dy,d=std::hypot(ex,ey);
        if(d<best) {best=d;s=distance_[i]+u*len;cross=(dx*ey-dy*ex)/len;heading=wrap(p.yaw_rad-std::atan2(dy,dx));}
    }
    if(!std::isfinite(best) || best>1.5 || std::abs(heading)>.5 || s<progress_-.5 ||
       (!last_pose_ && (s>2 || best>.3 || std::abs(heading)>3*pi/180)))return fail();
    const double lookahead=std::max(4.,1.2*speed),goal=std::min(distance_.back(),s+lookahead);
    const auto it=std::lower_bound(distance_.begin()+1,distance_.end(),goal);
    const auto i=static_cast<std::size_t>(it-distance_.begin()-1);
    const auto& a=route_[i];const auto& b=route_[i+1];
    const double u=(goal-distance_[i])/(distance_[i+1]-distance_[i]);
    const double dx=a.x_m+u*(b.x_m-a.x_m)-p.x_m,dy=a.y_m+u*(b.y_m-a.y_m)-p.y_m;
    const double local_x=std::cos(p.yaw_rad)*dx+std::sin(p.yaw_rad)*dy;
    const double local_y=-std::sin(p.yaw_rad)*dx+std::cos(p.yaw_rad)*dy;
    if(local_x<=.1 || dx*dx+dy*dy<.01)return fail();
    const double wanted=std::atan(wheelbase_*2*local_y/(dx*dx+dy*dy));
    const double bounded=std::clamp(wanted,-.3,.3);
    const double selected=std::clamp(bounded,angle_-.02,angle_+.02); // 1 rad/s, 20ms
    angle_=selected;progress_=std::max(progress_,s);last_pose_=p;last_ns_=now;
    return PursuitOutput{std::tan(selected)/wheelbase_,s,cross,heading,lookahead,p.source_ns,selected!=wanted};
}
} // namespace stratadrive::central
