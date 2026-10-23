#pragma once
// Opt-in test harness contract, NOT the Host owner-wire clock agreement.
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <thread>

namespace stratadrive::m7_functional {
using Time=std::uint64_t;
inline constexpr Time ms=1000000, tick_ns=10*ms, domain=0x4d3746554e435449ULL;
struct Scope {
    Time run; std::uint32_t application,plant;
    bool operator==(const Scope& b) const {return run==b.run && application==b.application && plant==b.plant;}
};
struct Observation {Scope scope;Time clock,frame;double elapsed_s,delta_s;};
// One thread owns input, all eight owners, and the next-tick permission. Any
// unexpected frame/time poisons this instance. Reset requires a fresh instance,
// a trusted new Scope, and real INIT; it cannot clear this instance's latch.
class FrameClock {
public:
    explicit FrameClock(Scope scope):scope_(scope),owner_(std::this_thread::get_id()) {
        if(!scope.run || !scope.application || !scope.plant)throw std::invalid_argument("scope");
    }
    Time accept(const Observation& o) {
        check(!failed_ && owner_==std::this_thread::get_id(),"owner/latch");
        check(!pending_,"previous barrier not consumed");
        check(o.scope==scope_ && o.clock==domain && o.frame>0 && o.frame<UINT64_MAX,"scope/domain/frame");
        check(std::isfinite(o.elapsed_s) && o.elapsed_s>0 && o.elapsed_s<1e8 &&
              std::isfinite(o.delta_s) && std::abs(o.delta_s-.01)<1e-6,"simulation time/delta");
        const auto ns=static_cast<Time>(std::llround(o.elapsed_s*1e9));
        if(frame_)check(o.frame==frame_+1 && ns>now_ &&
            std::abs(static_cast<double>(ns-now_)-static_cast<double>(tick_ns))<1000,"frame/time discontinuity");
        // Original rounded elapsed time, not callback arrival or a re-stamped cache.
        frame_=o.frame;now_=ns;pending_=true;serviced_=0;return now_;
    }
    void serviced(unsigned role) {
        check(owner_==std::this_thread::get_id() && pending_ && !failed_ && role<8,"service scope");
        check(!(serviced_&(1U<<role)),"duplicate service receipt");serviced_|=1U<<role;
    }
    Time permit_non_driving_tick() {
        check(owner_==std::this_thread::get_id() && !failed_ && pending_ && serviced_==255,"incomplete barrier");
        pending_=false;return frame_+1;
    }
    void fail() {failed_=true;}
    Time now() const {return now_;}
    bool failed() const {return failed_;}
private:
    void check(bool good,const char* why) {if(!good){failed_=true;throw std::runtime_error(why);}}
    Scope scope_;std::thread::id owner_;Time frame_=0,now_=0;unsigned serviced_=0;
    bool pending_=false,failed_=false;
};
} // namespace stratadrive::m7_functional
