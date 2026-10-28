#pragma once
// Same-host, process-shared terminal latch. Only the native mutation owner writes;
// the Plant Adapter reads immediately before physics. Never clears in a session.
#include <cstdint>
namespace stratadrive::m7_native {
struct alignas(8) WallSignal {
    std::uint64_t magic,initial,application,fault;
};
inline constexpr std::uint64_t wall_signal_magic=0x4d3757414c4c3031ULL;
inline bool wall_fault(const WallSignal* signal) {
    return !signal || __atomic_load_n(&signal->fault,__ATOMIC_ACQUIRE)!=0;
}
inline void wall_trip(WallSignal* signal) {__atomic_store_n(&signal->fault,1ULL,__ATOMIC_RELEASE);}
}
