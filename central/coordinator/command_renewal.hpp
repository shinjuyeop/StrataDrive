#pragma once
#include <cstdint>

namespace stratadrive::central {
// Explicit Host deployment choice; legacy component tests retain 20 ms.
// Neither profile changes input freshness, command expiry or the 20 ms wire
// envelope. Host normal renewal reserves 8 ms after the next nominal release
// for the 4 ms management phase and asynchronous grant/command handover.
// This is admission headroom, not a promise that arbitrary 20 ms delays succeed.
enum class CommandRenewal { Legacy20ms, Host10ms };
constexpr std::uint64_t allocation_period(CommandRenewal profile) {
    return profile==CommandRenewal::Host10ms?10000000ULL:20000000ULL;
}
constexpr std::uint64_t permission_support(CommandRenewal profile) {
    return allocation_period(profile)+(profile==CommandRenewal::Host10ms?8000000ULL:0ULL);
}
} // namespace stratadrive::central
