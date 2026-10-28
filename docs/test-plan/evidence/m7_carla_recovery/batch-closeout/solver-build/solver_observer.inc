// Compiled only into an external, pinned copy of PxVehicleUpdate.cpp.
// Optional guarded protected-hold policy only suppresses unchanged steer wakeup.
// One bound diagnostic vehicle; registration occurs outside physics execution.
#include "M7SolverTrace.h"
namespace {
const void* m7_vehicle = 0;
M7SolverTrace m7_trace = {};
bool m7_keep_steer_sleep = false;
bool m7_steer_wakes(const void* v) { return v != m7_vehicle || !m7_keep_steer_sleep; }
void m7_begin(const void* v, unsigned wheels, float dt) {
  if (v != m7_vehicle) return;
  ++m7_trace.begins; m7_trace.wheels = wheels; m7_trace.dt = dt;
}
void m7_end(const void* v, bool sleeping) {
  if (v != m7_vehicle) return;
  ++m7_trace.ends; m7_trace.sleeping += unsigned(sleeping);
}
void m7_step(const void* v, unsigned k, unsigned n, unsigned block, float dt,
             const float* before, const float* after, const float* drive,
             const float* brake, const float* tire, const float* damping) {
  if (v != m7_vehicle) return;
  if (m7_trace.count == 320) { ++m7_trace.overflow; return; }
  M7SolverStep& s = m7_trace.steps[m7_trace.count++];
  s.ordinal=k; s.count=n; s.block=block; s.dt=dt;
  for (unsigned j=0;j<4;++j) {
    s.before[j]=before[j]; s.after[j]=after[j]; s.drive[j]=drive[j];
    s.brake[j]=brake[j]; s.tire[j]=tire[j]; s.damping[j]=damping[j];
  }
}
}
extern "C" void M7SolverStart(const void* vehicle) {
  m7_vehicle=vehicle; m7_trace=M7SolverTrace{}; m7_trace.abi=1; m7_keep_steer_sleep=false;
}
extern "C" const M7SolverTrace* M7SolverFinish(const void* vehicle) {
  if (!vehicle || vehicle != m7_vehicle) return 0;
  m7_vehicle=0; return &m7_trace;
}

extern "C" bool M7SolverKeepProtectedSteerSleep(const void* vehicle) {
  if (!vehicle || vehicle != m7_vehicle || m7_trace.begins) return false;
  m7_keep_steer_sleep=true; return true;
}
