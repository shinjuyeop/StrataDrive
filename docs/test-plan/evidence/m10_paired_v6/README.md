# M10 paired V6: fault observation window insufficient

2026-11-13. This separately declared conditional fault case followed V5's normal
pass with the same20Hz observation workload and original guards. It is **FAIL**:
the frozen auditor requires progress after actual observed process death, and
none was recorded inside the400-interval physical horizon.

The actual SIGSTOP state was observed at1567820048232392. Resume was requested
at1567820300813135 after a252.914ms requested pause. SIGKILL at interval320 was
requested at1567820547229983; the parent observed death at1567820959671402,
412.441ms later. The last acquisition ended at1567820933671809,26.000ms before
that observation. Progress after the kill request cannot substitute for this.

The independent original physical audit passes:400 receipts,238 normal,
0 protective/fault intervals, model2.0s/wall2.002562s and maximum normal HV
dependency22.564ms. All2007 native service rows and400 receipts replay exactly.
These narrower results do not override the whole-case fault observation failure.

The renderer client retained its expected post-crash RPC timeout and four false
actor-destroy returns. The latter would independently fail the original cleanup
criterion; they are not waived or rewritten. V7 uses actual inherited pidfd death
observation to skip server RPC cleanup only after the owned process is dead,
while requiring complete local inference/raw-recorder cleanup.

All32 real images and25 numerical calls are retained; every call detected a person.
Future independent-evaluation exclusion increases from9213 to9245. No holdout or
native perception acceptance occurred. The1344-file freeze passes43 focused
checks and the same456 regression tests. Full visual fidelity remains unavailable.

V7 is prospectively separate: stop after180 intervals, resume after250ms, crash
after260, retaining the400 horizon and the same actual-death progress threshold.
The earlier injection reserves observation time and does not change native guards.
`check-live.py` must reproduce this original failure from its frozen sources.
