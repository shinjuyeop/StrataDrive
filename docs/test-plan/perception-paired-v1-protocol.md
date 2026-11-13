# M10 paired diagnostic V1

Prospective protocol, 2026-11-13. One normal attempt first; one separately
declared stall/exit attempt only after the normal case passes its audits.
Each attempt retains all failures and images, including preparation callbacks.
Changes after a failed live attempt require a new source freeze and case declaration.

Two runner-owned Town03_Opt servers use the original restored runtime. Port2200
owns native5ms physics,400 intervals,150 passive warmup ticks,320 substeps,
HV30ms and the existing ECU/preview/command deadlines. Port2300 renders with a
50ms model step at2560×1536/Epic. No camera is created on the physical server.
One ego Lincoln, one parked Tesla and one stationary walker form the declared
dynamic actor inventory. Weather and traffic-light states are fixed before bind.

Export joins an immutable SDK WorldSnapshot to the cached original postphysics
receipt by exact frame/source time. The recorded rigid body-to-actor transform
must agree within1mm with the same-frame SDK actor root. Actor inventory changes
fail closed. Original acquisition timestamps are retained; the100ms exclusive
freshness rule is unchanged. One active scene and one pending latest scene are
allowed. The renderer verifies all clone transforms and the camera matrix after
its own actual tick; physical and rendering frame identities remain separate.

D-FINE-M960 diagnostics run on one numerical thread with one pending latest
image and three recorded synthetic preparation calls. At most96 measured model
calls and96 in-memory camera packets are permitted; overflow is a failed run
whose raw packets are still retained. All real BGRA and numerical outputs are
saved losslessly after the measurement, with hashes for future data exclusion.

This is actor-root rendering only. Same-frame wheel/bone animation and material
content equivalence are unavailable. Every image and inference result therefore
remains unavailable for control; zero perception results reach the native owner.
This case cannot establish full-scene fidelity, detector quality or closed-loop
perception acceptance. No holdout data is accessed.

Normal case requires: all400 original physical intervals settled, more than100
normal intervals, zero native protective/fault intervals, original physical and
shadow audits passing, at least5 verified renderer ticks,3 associated real images
and2 real model calls overlapping physical operation. Source receipt/scene/image
chains must rejoin exactly. All server exits must be130 without forced stop;
settings must be restored. Wall time, age and throughput are reported as observed,
without a20Hz target or revised safety deadlines.

Conditional fault case sends SIGSTOP to the owned renderer after120 physical
intervals, SIGCONT at least250ms later, then SIGINT after280 intervals. Native
physics must progress during the pause and after exit request, settle all400
intervals, and preserve the same native guards. Stale scenes must expire without
timestamp renewal. Renderer RPC errors are expected only after the declared exit;
they remain in the original records and are correlated by the audit. SIGINT has
the existing30s exit limit, including optional debugger collection after10s.
Cleanup cannot reset that deadline. Unexpected errors or forced exits fail.
