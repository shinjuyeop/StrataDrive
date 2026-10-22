#pragma once
#include <cstdint>
namespace stratadrive::someip::test {
// Scenario input only, after real arm. Never issues session/permission/ACK.
struct EnergyDemand {const char* phase;double acceleration;bool hold;};
inline EnergyDemand energy_demand(std::uint64_t elapsed_ns) {
    if(elapsed_ns<2000000000ULL)return {"accelerate",2,false};
    if(elapsed_ns<2600000000ULL)return {"coast",0,false};
    if(elapsed_ns<4500000000ULL)return {"brake",-1,true};
    return {"hold",0,true};
}
}
