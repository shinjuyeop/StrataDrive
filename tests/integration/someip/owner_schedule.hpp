#pragma once
#include <array>
#include <cstdint>
#include <optional>

namespace stratadrive::someip::test {
// One owner's bounded receive budget, shared by the early and pre-snapshot
// passes. A packet arriving during sensor IO need not wait another VM period.
class IngressTurn {
    std::array<unsigned,4> consumed_{};
public:
    template<class Network,class Receive> void drain(Network& network,Receive receive) {
        for(const unsigned lane:{1U,3U,0U,2U}) {
            if(lane>=network.channels())continue;
            while(consumed_[lane]<8) {
                auto message=network.pop(lane);if(!message)break;
                ++consumed_[lane];receive(*message);
            }
        }
    }
};
// Stop requests remain 20ms releases. Align them with VM's +4ms release grid,
// before deriving this cycle's lifecycle/power request. Relative sleep-based
// renewal can drift just past VM and waste nearly 10ms of original authority.
// The caller stamps a genuinely new request at execution time. Missed slots
// are skipped; this does not replay jobs or extend any request's lifetime.
class StopRequestRelease {
    std::optional<std::uint64_t> slot_;
public:
    bool due(std::uint64_t enable,std::uint64_t now,bool management_due) {
        if(!management_due || now<enable || now-enable<4000000)return false;
        const auto slot=(now-enable-4000000)/20000000;
        if(slot_ && slot<=*slot_)return false;
        slot_=slot;return true;
    }
};
}
