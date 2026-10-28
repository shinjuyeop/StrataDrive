#pragma once
#include "functional_rig.hpp"

namespace stratadrive::m7_functional {
inline constexpr Time wall_domain=0x4d374d4f4e4f3031ULL;
// This interface accepts ONLY original observations already in the owner's
// CLOCK_MONOTONIC domain. A simulation timestamp cannot be supplied as a wall
// timestamp. CARLA/model clock conversion is deliberately not implicit here.
struct WallReceipt {
    WheelSample wheel;
    m7_external::SolverWork work;
    Time clock=0;
    std::optional<m7_external::CarlaWork> carla{};
};
struct WallReport {
    Report native;
    Time initial=0,protected_at=0;
    bool failed=false;
    std::string reason;
};
// New INIT in a new domain. Exactly one thread mutates the native actors and
// response/EV models. Each service call executes at NOW once, never replays old
// ECU jobs. Receipt parsing/blocking IO belongs outside this owner.
class WallRig {
public:
    WallRig(Scope scope,std::uint32_t actor,Time initial,Time model_initial=0);
    ~WallRig();
    WallRig(const WallRig&)=delete;
    WallRig& operator=(const WallRig&)=delete;
    void request_profile(std::vector<RequestPhase> profile);
    void execution_watch(WallExecutionWatch* watch);
    WallReport service(Time now,const std::optional<WallReceipt>& receipt={});
    void protect(const char* reason);
private:
    std::unique_ptr<FunctionalRig::Native> native_;
    Scope scope_;
    std::uint32_t actor_;
    Time model_initial_=0;
    Time initial_,last_=0,last_frame_=0,last_source_=0;
    std::thread::id owner_=std::this_thread::get_id();
    std::string failure_;
};
}
