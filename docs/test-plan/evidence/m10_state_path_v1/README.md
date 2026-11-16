# M10 state-path V1: startup failure retained

The [declared protocol](../../perception-state-path-v1-protocol.md) adds optional,
bounded owner/native timing records and a read-only50ms CPU clock/thermal sampler.
It retains5ms physics, native2/4ms, HV30ms and perception100ms. It does not change
the earlier [300s failure](../m10_host_endurance_v1/README.md) or open perception
control admission.

The first30s case **failed before physical execution**: the renderer did not
become ready within the unchanged180s bound. Its log records asset loading,
local derived-data-cache access and a skeletal-mesh rebuild. This does not prove
that a single cache or mesh operation explains the entire timeout. Shutdown then
required a forced stop at the original30s limit; the retained GDB trace is available
in the metadata archive. No physical interval, camera frame or inference ran.
The second case is `NOT_RUN_STOP_ON_FIRST_FAILURE`.

Original CARLA/DXC/INI identities were restored. The run archive was independently
checked with the frozen source, reproducing the original failed audits. The missing
capture error originally contained the absolute extraction path; the runner's
strict JSON equality therefore failed after the archive check. A separately
recorded comparison canonicalized only that root prefix and confirmed the same
missing-file failure. The frozen V1 code and original errors remain unchanged.
V2 tests and freezes that postprocessing correction before its own execution.

Preflight completed40 native boundary tests, profile-enabled30/300s native
allocation/start/stop checks,480 Python tests and64 frozen focused tests. The
clock microbenchmark's p95 CPU cost was1.959µs for11 paired stamps plus measurement
stamps. These checks are instrumentation evidence, not a live stability pass.

`sources.json`/`sources.tar.gz` retain the exact source/runtime identities.
`normal-30s-01/` contains the case, original failures, archive validation,
restoration and unchanged14633 future exclusions. `retained-metadata.tar.gz`
contains checked startup/exit logs and configuration, with original member hashes
in `MANIFEST.json`. The complete `run.tar.gz` stays local and ignored under the
[artifact policy](../../artifact-storage.md).

The subsequent [V2 protocol](../../perception-state-path-v2-protocol.md) explicitly
declares a separate empty-renderer asset preparation and warm-cache diagnostics.
It does not rerate this cold-start attempt or extend the normal readiness limit.
M10 remains OPEN.
