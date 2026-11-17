# M10 GC owner4 V1 — four owner / two image cores

Recovery V3 passed both30s cases and their original/frozen audits, but its300s
case failed at60.242013606s with original held HV expiry. First GC took17.925938ms.
Four normal frames after GC still inherited a pre-GC actuator dependency. The
held dependency reached30.883485ms at the recorded first Drive fault,12.777518ms
after GC ended. The original300us preview and final gate both remain authoritative;
do not reduce freshness requirements or relabel sensor time to hide this failure.
At the exact next-pump stamp,6.955483ms after GC, read-only queries on the
original published proof reject both300us and0 extra reserve with
`native_wheel_interval`. Exact native/proof replay remains equal. This diagnoses
the observed trajectory; it does not establish an alternate physical outcome.

Compare one physical-core transfer: owner[2,3,4,5,10,11,12,13], shared
renderer/image[6,7,14,15], native[1,9], observer[0,8]. Keep SMT siblings together
and all roles disjoint. Native remains FIFO18; owner/renderer/observer remain
SCHED_OTHER. This is an explicit Host experiment, not a new production default
or a Jetson optimization. More owner parallel capacity may shorten GC; fewer image
cores may increase preprocessing/recording latency. Both effects require actual
measurement. Mean CPU use or an offline gate probe does not establish recovery.

Keep the exact recovery module, native binaries, model, tensor workspace, library
bytes and all runtime code. Only the CPU profile and strict placement auditor
selection change. Preserve the original three-core auditor default. Permit the
new layout only as an exact complete plan; reject overlap, wrong process affinity,
wrong native scheduling, GC stamps on image cores and missing measured placement.
Reuse the library and purge/final-gate audits with a fixed four-core validator.

Physics5ms, HV30ms, native2/4ms, source clocks, held expiry before replacement,
final prephysics guard and300us extra preview stay unchanged. Keep parallel
GC61.1s/12220frames, incremental purge100us,2560×1536 D-FINE-M960 CUDA,
camera target10Hz, renderer20Hz/MaxFPS60, CV/resize4, passive ORT and CUDA blocking.
No GC suppression, pre-trigger, interval extension or forced warmup is allowed.

Verify source/module/model equivalence and actual CPU topology. Run the actual
owner and renderer model setup paths on the new image CPUs at100%, with original
three-call10s/100ms preparation and renderer30s readiness. Run empty-renderer
preparation/shutdown on those CPUs, with its separate600s preparation deadline.
These are preparation checks, not physical acceptance. Reuse unchanged C++29
only after source and binary identities match. Freeze all source and external
inputs; test all standalone audit entrypoints outside the repository and run
regressions from the frozen tree before requesting the bounded70% lease.

The actual launcher prepares assets again, then authenticates and starts a fresh
owner. Run30s →30s →300s, stopping later cases on the first original failure.
Restore100% on owner exit, Ctrl+C or30min. Preserve original failures, exact
native/first-fault replay, raw images and the accumulated V3 future-quality
exclusions. Compare pre-fault video latency separately from protected hold.
Compress only after all live work; remove only byte-verified duplicate data.

Five-minute stability, cooling margin, continuous driving, full visual state,
native perception acceptance, independent quality, each Jetson deployment and
M10 completion remain OPEN.
