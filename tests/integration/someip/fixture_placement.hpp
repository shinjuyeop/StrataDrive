#pragma once

#include <charconv>
#include <cstdlib>
#include <sched.h>
#include <stdexcept>
#include <string_view>

namespace stratadrive::someip::test {
// Test IO only. The launcher resolves and records physical topology before any
// participant starts; configure_thread verifies the actual affinity/policy.
inline int auxiliary_io_cpu() {
    const auto* value=std::getenv("STRATADRIVE_AUX_IO_CPU");
    if(!value)return 15; // Existing native-watch and diagnostic profiles.
    const std::string_view text(value);int cpu=-1;
    const auto parsed=std::from_chars(text.data(),text.data()+text.size(),cpu);
    if(!std::getenv("STRATADRIVE_SPLIT_OWNER_IO") || parsed.ec!=std::errc{} ||
       parsed.ptr!=text.data()+text.size() || cpu<0 || cpu>=CPU_SETSIZE)
        throw std::invalid_argument("invalid auxiliary IO CPU");
    return cpu;
}
}
