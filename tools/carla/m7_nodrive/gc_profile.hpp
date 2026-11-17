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

// Opt-in incremental work scheduling, separate from the collection delegates.
// A slice replaces the engine's default 2ms incremental slice for this frame;
// it never requests a collection or changes the periodic collection timer.
struct PurgeCycle {
  WaitAggregate work{};
  OwnerStamp first{},last{};
  std::uint64_t first_frame=0,last_frame=0;
  bool pending_at_collection_end=false,complete=false;
};
struct PurgeProfile {
  static constexpr std::uint64_t BudgetNs=100000;
  std::array<PurgeCycle,GcProfile::Capacity> cycles{};
  std::uint64_t count=0,errors=0,last_frame=0;
  bool have_frame=false;
  void collection_end(bool pending) noexcept {
    if(count==cycles.size()){++errors;return;}
    if(count && !cycles[count-1].complete)++errors;
    auto& row=cycles[count++];row.pending_at_collection_end=pending;
    row.complete=!pending;
  }
  template<class Pending,class Work,class Delay,class Stamp>
  void step(std::uint64_t frame,Pending pending,Work work,Delay delay,Stamp stamp) {
    if(have_frame && frame==last_frame)return;
    if(have_frame && frame<last_frame){++errors;return;}
    last_frame=frame;have_frame=true;
    // Startup collections outside the measured journal remain engine-owned.
    if(!count)return;
    auto& row=cycles[count-1];
    if(row.complete)return;
    if(!pending()){++errors;row.complete=true;return;}
    const auto begin=stamp();work();const auto end=stamp();
    // The engine would have selected incremental work at entry. Avoid running
    // a second default slice later in this same frame, even if ours drained it.
    // Full/forced collection branches precede this flag in ConditionalCollectGarbage.
    delay();
    if(!row.work.count){row.first=begin;row.first_frame=frame;}
    row.work.add(begin,end);row.last=end;row.last_frame=frame;
    row.complete=!pending();
  }
};
static_assert(std::is_trivially_copyable<PurgeProfile>::value,"bounded purge journal");
static_assert(sizeof(PurgeProfile)<32768,"small fixed purge journal");
static_assert(sizeof(PurgeProfile)+sizeof(GcProfile)<65536,"bounded GC diagnostics");
}}
