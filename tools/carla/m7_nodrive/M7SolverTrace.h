// Project-owned, versioned POD boundary; no PhysX/Unreal implementation here.
#pragma once
#include <stdint.h>
struct M7SolverStep {
  uint32_t ordinal, count, block;
  float dt, before[4], after[4], drive[4], brake[4], tire[4], damping[4];
};
struct M7SolverTrace {
  uint32_t abi, begins, ends, sleeping, wheels, count, overflow;
  float dt;
  M7SolverStep steps[320];
};
extern "C" {
__attribute__((visibility("default"))) void M7SolverStart(const void* vehicle);
__attribute__((visibility("default"))) const M7SolverTrace* M7SolverFinish(const void* vehicle);
}
