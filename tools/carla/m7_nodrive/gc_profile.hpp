#pragma once
#include "owner_wait_profile.hpp"
#include <array>
#include <cstdint>
#include <type_traits>

namespace stratadrive { namespace m7_native {
// One game-thread writer. Delegate callbacks only stamp preallocated POD; no
// UObject ownership, allocation, output, GC scheduling or collection changes.
struct GcCycle {
  OwnerStamp begin{}, memory_trim{}, end{};
  std::uint64_t completed_frame=0;
};
struct GcProfile {
  static constexpr std::size_t Capacity=64;
  std::array<GcCycle,Capacity> cycles{};
  std::uint64_t count=0, errors=0;
  bool active=false;
  void begin(OwnerStamp now, std::uint64_t frame) noexcept {
    if(active || count==Capacity || !now.valid){++errors;return;}
    cycles[count].begin=now;cycles[count].completed_frame=frame;active=true;
  }
  void end(OwnerStamp now) noexcept {
    if(!active){++errors;return;}
    auto& value=cycles[count];value.end=now;
    WaitAggregate check{};check.add(value.begin,value.memory_trim);check.add(value.memory_trim,value.end);
    errors+=check.errors;++count;active=false;
  }
  void trim(OwnerStamp now) noexcept {
    if(!active || cycles[count].memory_trim.valid || !now.valid){++errors;return;}
    cycles[count].memory_trim=now;
  }
};
static_assert(std::is_trivially_copyable<GcProfile>::value,"bounded GC journal");
static_assert(sizeof(GcProfile)<16384,"small fixed GC journal");
}}
