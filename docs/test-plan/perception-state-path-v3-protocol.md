# M10 state-path V3: preserve original receipts and HV provenance

V1 cold renderer startup remains FAIL. V2 ran6000 intervals without native
protection but its joint audit failed `cached original receipt unchanged`:
the instrumentation appended diagnostic JSON to an already exported receipt.
Its diagnostic HV join also incorrectly expected actuator/coil source times to
be physical acquisition timestamps. Both original failures, archives and raw
images remain retained. V2's second case is NOT_RUN. Do not rerate those runs.

Fix only the diagnostic path: put `state_path` beside the immutable receipt in
the post-run RPC/trace row; keep receipt bytes/fields unchanged. Derive each HV
source/dependency from its original work end, acquisition, oldest actuator and
coil source, using the existing physical audit's exact rule and bootstrap
application-time fallback. Check all native calls, including unchanged cached
HV samples. No timestamp refresh, input replacement or control-policy change.
Keep the joint/physical audits unchanged. Add regression checks for original
receipt preservation, non-acquisition HV dependencies and incorrect identities.

Use the same selected Host V1 placement and F/G/H settings,5ms physics,
native2/4ms, HV30ms, perception100ms,2K/Epic/D-FINE-M960,20Hz render progression,
100ms model camera period, NVMe BGRA recording and original180s/30s server
readiness/shutdown bounds. This is explicitly the warm-cache condition after
V2's retained empty-renderer preparation; no new preparation or cache deletion.
State-path preallocation, post-run serialization and read-only50ms host sampling
remain unchanged. No host power, cooling, privilege or Jetson optimization.

Build the corrected CARLA module in isolation, retain its manifest and re-freeze
all source/runtime/protocol/runner identities. Run the complete Python regression
and frozen focused suite. The unchanged native binary retains its40 boundary
tests and profile-enabled30/300s allocation/start/stop preflight. Keep the prior
clock-cost result. Require the same CPU≤70°C/180s, RAM≥4GiB and storage preflight.
No build or compression may overlap the live interval.

Declare one30s case and, only if original joint/shadow/exact-replay and new
state-path audits all pass, one same-condition30s repetition. Stop on the first
failure. No300s escalation or replacement case. Retain every actual image,
including failed/unavailable diagnostics; chain exclusions from V2's14918.
Restore original runtime after each case, independently reproduce each original
verdict and all raw hashes, then losslessly compact the checked archives and
remove only verified duplicate temporary files. Raw/run archives remain local;
Git keeps review evidence under artifact-storage.md.

Report stage wall/CPU distributions, original source→publication→native timing,
HV provenance and clock/thermal observations. Frequency is sequential sysfs
sampling, not an exact cause attribution; inaccessible energy remains unknown.
Neither two finite passes nor integrity fixes close the earlier300s HV fault,
cold-start failure, native perception admission, complete scene, independent
quality, each Jetson deployment or M10.
