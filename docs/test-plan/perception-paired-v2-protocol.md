# M10 paired diagnostic V2

Prospective protocol, 2026-11-13. One normal attempt first; one separately
declared stall/crash attempt only after the normal case passes its audits.
Each attempt retains all failures and images, including preparation callbacks.
Changes after a failed live attempt require a new source freeze and case declaration.

Two runner-owned Town03_Opt servers use the original restored runtime. Port2200
owns native5ms physics,400 intervals,150 passive warmup ticks,320 substeps,
HV30ms and the existing ECU/preview/command deadlines. Port2300 renders with a
50ms model step at2560×1536/Epic. No camera is created on the physical server.
One ego Lincoln, one parked Tesla and one stationary walker form the declared
dynamic actor inventory. One explicit pre-bind preparation tick supplies an
actual immutable ego snapshot before the walker is placed at ego-local(8,3,1);
an immediate post-spawn Actor.get_transform is not accepted as placement evidence.
The original150 passive warmup ticks follow this preparation. Weather and
traffic-light states are fixed before bind.

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

Conditional fault case sends SIGSTOP to the owned renderer after220 physical
intervals, observes its actual Linux stopped state, and sends SIGCONT at least
250ms after the stop request. It intentionally kills that owned renderer after320
intervals. At least11 original physical intervals must begin while the renderer
is observed stopped, and at least11 must begin after its actual process death is
observed by the parent, not merely after an exit request. Death observation must
be within1s of the injected SIGKILL. The intentional renderer exit-9 is admitted
only for this declared condition; every normal/owner exit still requires130 and
no forced stop. An unplanned-9 or a failed graceful shutdown remains FAIL.

The original400 intervals and all native guards must pass. Expected renderer SDK
errors must follow the declared crash; inference errors, recorder loss, forced
client stop or unrelated cleanup errors still fail. Original scene age remains
unchanged, and stale images remain unavailable. This diagnostic case does not
establish Required-mode perception protection or complete visual fidelity.
