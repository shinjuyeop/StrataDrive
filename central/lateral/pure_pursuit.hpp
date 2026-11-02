#pragma once
#include <cstdint>
#include <optional>
#include <vector>

namespace stratadrive::central {
struct RoutePoint { double x_m,y_m; };
// Project x-forward/y-left world coordinates, rear axle center; original sensor time.
struct RoutePose {
    std::uint32_t epoch;
    std::uint64_t sequence,source_ns;
    double x_m,y_m,yaw_rad;
};
struct PursuitOutput {
    double curvature_inv_m,progress_m,cross_track_m,heading_error_rad,lookahead_m;
    std::uint64_t source_ns;
    bool limited;
};
class PurePursuit {
public:
    explicit PurePursuit(std::vector<RoutePoint> route,double wheelbase_m);
    bool start_session(std::uint32_t epoch,std::uint64_t enable_ns);
    std::optional<PursuitOutput> step(std::uint64_t now_ns,const RoutePose& pose,double speed_mps);
    bool faulted() const {return fault_;}
private:
    const std::vector<RoutePoint> route_;
    std::vector<double> distance_;
    const double wheelbase_;
    std::uint32_t epoch_=0;
    std::uint64_t enable_=0;
    std::optional<std::uint64_t> last_ns_;
    std::optional<RoutePose> last_pose_;
    double progress_=0,angle_=0;
    bool fault_=false;
};
} // namespace stratadrive::central
