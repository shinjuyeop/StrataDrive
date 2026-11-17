# M10 admission window V1 — post-ingress clock and staging margin

Prospective 30s → 30s → 300s sequence; stop on the first original failure. Preserve
[GC V2](evidence/m10_owner_gc_v2/README.md): first30s PASS, second30s HV expiry at
28.053010185s, 300s NOT RUN. Neither30s contained owner GC. Future quality exclusions
continue from20556; this is development diagnosis, not holdout evaluation.

The exact retained native replay matches30002 service calls,6000 original admissions,
5797 ingress records and original proof bytes. On the failed frame, the old command
expires at1903272807511673ns. The original preview's extra4ms margin closes eligibility
before the scheduled release, even though the original5ms physical interval remains
covered.50us offline probes with2ms extra margin identify an earlier eligible window;
they do not predict a successful changed live trajectory.

Changes are limited to sampling the scheduling clock after canonical ingress and
reducing **additional preview staging slack** from4ms to2ms for the existing opt-in
structured path. The legacy path retains4ms. Both preview calls use the same setting,
reported as`wall_preview_reserve_ns`. The original final acceptance body, command
expiry,30ms age limits, source timestamps,5ms/320-step physics, native2/4ms periods,
HV old-held expiry before replacement and protective response remain unchanged.
Admission-to-applied maxima were0.425678/0.400424ms in the two original30s runs.
Acquisition maxima were2.467779/3.748481ms; the2ms value is extra staging slack,
not a claim that all physical work completes within2ms. Full5ms physical coverage,
actual completion checks and original native deadlines remain authoritative.

Before live execution: compile the isolated module; pass native admission regressions,
including backwards-clock isolation, preserved original expiry and default4ms;
verify source-body equivalence for physical/native code; run Python and frozen tests;
validate an empty renderer's readiness, normal shutdown and six-file restoration.
Freeze sources, module, original native/replay binaries and all audit entry points.
The separate asset-preparation maximum is600s at original100% boost. Each actual
invocation prepares assets before sudo authentication and fresh PID creation; reject
preparation older than300s. Physical startup180s and shutdown30s remain unchanged.

Host and image settings match GC V2: owner CPUs2,3,10,11; native1,9/FIFO18;
renderer/image4–7,12–15; observer0,8;2K2560×1536/Epic,D-FINE-M960 CUDA,
camera100ms, renderer20Hz/MaxFPS60, passive ORT, blocking CUDA, tensor workspace,
raw NVMe capture, owner serial GC and unchanged61.1s GC period. No forced/suppressed
GC, IRQ/fan/global RT changes or Jetson-specific optimization. Native perception
acceptance remains0 and this early acceleration/braking/hold scenario is not a route test.

Only the existing narrow root helper may request70% maximum boost after explicit
operator authentication. PID identity and1800s lease/owner-exit restoration apply.
Preflight CPU<=70°C, memory>=4GiB, declared raw storage bound plus4GiB, live2GiB
reserves; no builds, archive compression or independent tests during measured work.
For each case require original physical,shadow,GC,workspace,state-path,structured,
monitor,host-clock,owner-wait audits, new admission-window integrity, exact native
and first-fault replay, raw/archive validation and frozen audit reproduction.
Configuration integrity alone never upgrades a physical failure. Preserve all failures
and restore original six runtime files and100% boost after the sequence.

5min stability, old periodic GC correlation, later native missing slots, thermal margin,
independent quality, complete scene transport, each Jetson deployment and M10 remain OPEN.
