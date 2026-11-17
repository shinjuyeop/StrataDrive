# M10 owner GC V2 — fresh asset preparation

GC V1 stopped before any control, model preparation or camera capture: the renderer
exhausted the unchanged 180s readiness horizon and needed forced shutdown after
30s. Preserve that failure, zero raw images and unchanged future exclusion 19991.
The main thread was directly observed in disk sleep, `folio_wait_bit_common`, in
a read syscall. Cache read speed reported 5.99MB/s versus 2993.01MB/s in the previous
warm run; this comparison is not a controlled storage benchmark. Cold asset I/O is
the leading startup explanation. No owner GC effect was measured in V1.

Before each operator launch, run one separate empty-renderer asset preparation
with a 600s bound and the original 100% host cap. Do not change power settings.
Use the same renderer command, selected CPUs 4–7/12–15, Epic and MaxFPS 60. Verify
zero vehicles, walkers and sensors, park the empty world, shut down within 30s,
and restore all six shared runtime files. No native, camera, inference, forced GC
or physical acceptance occurs in preparation. Preserve each preparation attempt;
abort on failure. Authenticate via sudo only after this preparation, then create
a fresh unprivileged sequence PID and invoke the unchanged 1800s/70% helper.
Preparation must be at most 300s old after authentication and at first-case entry;
a delayed password response must not start a trial using a stale preparation.

The new sequence retains every GC V1 physical condition and the identical module
`8089cd0dda69eebd5c8799f3927f91e2c0b920e6a8ad8e6da8bcdbd702eb917b`.
Only the owner uses serial GC; period 61.1s, fixed GC/trim brackets, HV 30ms,
physics 5ms/320 steps, native 2/4ms, original timestamps/check order, tensor
workspace and all camera/model/Host settings are unchanged. Four natural GC
cycles must be observed within a 300s run. The physical startup limit remains
180s. Keep the original temperature, storage, memory, shutdown and runtime guards.

Freeze sources/protocol/runners, check all 514 Python tests and 102 focused
frozen tests, and validate empty-renderer preparation separately before deployment.
Re-use the identical native binary's earlier 207 tests, allocation checks and
module computation/layout proof. Run 30s, 30s, then 300s only if each prior case
passes every original audit/replay and frozen reproduction. Stop on first failure;
never relabel a preparation or a preserved failed trial as physical PASS.

The first HV fault at 60.232s, later 18 missing native jobs and 90°C peak in owner
wait V2 remain unresolved. Native perception acceptance, complete scene/quality,
continuous routes, each Jetson deployment and M10 remain OPEN.
