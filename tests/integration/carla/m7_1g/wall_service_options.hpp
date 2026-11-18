#pragma once
#include <cstdint>
#include <stdexcept>
#include <string>

namespace stratadrive::m7_functional {
struct WallServiceOptions {
    bool profile_path{false};
    std::uint64_t period_ns{1000000};
};
inline WallServiceOptions wall_service_options(int argc,char** argv,unsigned endurance) {
    WallServiceOptions result;bool selected=false;
    for(int i=10;i<argc;++i) {
        const std::string option(argv[i]);
        if(option=="--profile-state-path" && !result.profile_path)result.profile_path=true;
        else if(option=="--service-us" && !selected && i+1<argc) {
            const std::string value(argv[++i]);selected=true;
            if(value!="500" && value!="1000")throw std::runtime_error("declared native service cadence");
            result.period_ns=value=="500"?500000:1000000;
        } else throw std::runtime_error("explicit unique native service options");
    }
    if(selected && (!endurance || !result.profile_path))throw std::runtime_error("service cadence requires profiled endurance");
    return result;
}
inline std::uint64_t next_wall_service(std::uint64_t initial,std::uint64_t now,std::uint64_t period) {
    if(now<initial || (period!=500000 && period!=1000000))throw std::runtime_error("absolute service clock");
    return initial+((now-initial)/period+1)*period;
}
}
