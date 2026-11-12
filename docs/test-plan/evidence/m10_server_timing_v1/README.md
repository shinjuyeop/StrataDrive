# M10 server execution timing V1

2026-11-12. **Execution gap localized to UE frame synchronization; continuous wall
driving remains FAIL/OPEN.** One separately declared instrumentation-only trial.
The existing2K/Epic/D-FINE-M960 setup and every control/input deadline were kept.

## Measured result

The largest active-session interval between PumpWall calls was **65.160600ms**.
A directly bracketed `FFrameEndSync::Sync` call occupied **61.713717ms**, or **94.71%**
of that gap. Its game-thread CPU duration was **0.733139ms**. This identifies the
game/render synchronization call as the dominant wait location in this trial,
rather than CPU work in the native ECU service or the inference worker.

| Observed operation inside the gap | Wall duration | Thread CPU duration |
| --- | ---: | ---: |
| UE frame synchronization |61.713717ms|0.733139ms|
| CARLA post tick (inclusive) |0.567882ms|0.564017ms|
| Completed physics processing (inside post tick) |0.463694ms|0.460704ms|
| World snapshot publication (inside post tick) |0.098917ms|0.098619ms|
| Engine tick-rate handling |0.008258ms|0.007977ms|
| Sensor dispatch on frame201 (inside post tick) |0.000900ms|0.000658ms|

Nested spans are **not additive**. Engine and CARLA frame counters are different;
interval intersections use their original same-host CLOCK_MONOTONIC timestamps,
not equal frame numbers. CPU durations come from CLOCK_THREAD_CPUTIME_ID and are
never subtracted from wall timestamps. Low CPU use indicates waiting/descheduling
within the measured call; this does not identify an unmeasured GPU/driver function.

The camera request for frame200 preceded its render-command execution by41.808590ms.
The explicitly blocking GPU query took6.870265ms. Frame synchronization ended
21.438525ms after that query returned, so removing that query alone is not established
as a solution to the entire gap. The instrumented UE source retains its original
frame-end fence and one-frame-lag setting. No synchronization was disabled.

## Vehicle, perception and lifecycle

- 2 completed physical intervals,0 normal intervals, no arm. Startup first-body
  faults remain0 for all five ECUs. Existing missing-dependency protection selected
  at enable+30.988742ms, the first service opportunity past the original30ms limit.
  The native first fault is the same upstream-protection/continuity result as the
  preceding trial, without the corrected ControlDeadline startup failure.
- 1 actual camera packet,1 model call with0 detections,1 original raw image retained.
  The first live inference began18.815150ms after native protection. Native receiver
  remained uninitialized because both actual world snapshots preceded INIT enable:
  40 reads,0 fresh/accepted results. The previous trial that delivered one result
  keeps its original verdict; this trial demonstrates no fresh delivery.
- Server SIGINT exit130, native exit0; pause/reset/close and camera destruction after
  ownership release succeeded. No forced stop or cleanup error. Both UE executable
  and CARLA module, and the original settings file, were restored byte-for-byte.

[Timing audit](server-timing-01/timing-audit.json), [shadow audit](server-timing-01/audit.json),
[derived timeline](timeline.json), [server lifecycle](server-timing-01/server.json),
and [restoration](restoration.json) preserve the separate outcomes. The actual
driving attempt is **FAIL**, even though timing attribution and integrity passed.

## Instrumentation and verification

The [prospective protocol](../../perception-server-timing-v1-protocol.md) fixes one
`server-timing-01` trial with the same200-interval target,150 passive pre-camera
settling ticks,10ms model/320 substeps/HV30ms, source/receipt100ms and96 raw slots.
There was no second live retry or camera warmup exclusion.

Two isolated unity objects instrumented UE Launch and CARLA Engine. The existing
pinned readback source was recompiled as the third object. External source files
were never edited. The new flag is opt-in; the ordinary runner still requires its
previous module. An override requires the instrumented build manifest in the
prospective source/runtime freeze and verifies the exact executable/module paths.

Each game-thread journal has8192 preallocated entries. Record operations perform
no allocation, file IO or locking; output occurs on orderly process exit. Two
extra monotonic samples bracket each PumpWall call, and gaps>=0.5ms are retained.
Scoped stages also sample thread CPU time. The journals retained **5,555 rows**
(CARLA2,412/Launch3,143), with both end markers and0 overflow. This is an instrumented
measurement; there is no claim that measurement overhead is exactly zero.

- 17 focused tests passed, including a compiled C++ bounded journal, malformed or
  incomplete timing records, frozen runtime override, camera cleanup and readback.
- 1,303 source/import/build files were frozen before live. Separate archive extraction
  reproduced all17 tests. `build-02/manifest.json` pins actual build inputs, generated
  sources, commands and installed runtime hashes. The externally pinned UE/CARLA
  dependencies are required to rebuild those binaries; the source tar is not a
  standalone engine distribution.
- All788 native service rows/2 original physical receipts and every startup observation
  reproduced exactly with the prior corrected replay binary. No new ECU behavior.
- Frozen readers reproduced both full audit reports;11 semantic/raw corruptions were
  rejected, including missing end marker, overflow, wrong row count, duplicate row,
  invalid time/stage, omitted raw, wire corruption and changed raw content.
- The initial build script selected shell `set -o` before the linker line and stopped
  before linking or launch. `build-01` and the original builder/log are retained.
  The initial test expected the pure patch function itself to reject already patched
  input, although the builder's source hash check owns that check; the corrected test
  verifies ambiguous anchors and linker selection. The initial failure log remains.
- Original BGRA is Git LFS `raw-server-timing-01.tar` (7,147,520bytes), with compressed,
  BGRA and RGB hashes verified. Future quality exclusion **8,977→8,978**; no holdout.

Run the frozen tests and retained-trial audits (hydrate the raw archive with Git LFS):

```bash
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_server_timing_v1/check-evidence.py \
  --work build/m10-server-timing-v1/reproduce-NEW
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_server_timing_v1/check-live.py \
  --work build/m10-server-timing-v1/audit-NEW
```

Next: compare a declared camera-free control against identical2K capture, and split
the frame synchronization fence/RHI wait before selecting a way to separate camera
rendering from physical tick delivery. Keep bounded queues, original acquisition
times, freshness and protection; do not simply remove the fence or extend deadlines.
Independent quality, metric perception, Required live authority and Jetson work
remain outside this result.
