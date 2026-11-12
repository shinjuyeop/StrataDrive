# M10 owner-only5ms V2 and bounded snapshot prototype

2026-11-12. **PASS for one finite nonvideo owner case. Live rendering isolation and
continuous driving remain OPEN.** The new explicit5ms state-clock binding fixes
[V1's observer integration failure](../m10_owner_split_v1/README.md). Defaults and
all native freshness, authority and execution budgets remain unchanged.

## Actual owner result

| Measurement | `owner5ms-02` |
| --- | ---: |
| Completed/settled physical intervals |400 /400|
| Normal / protective intervals |234 /0|
| Model duration / elapsed wall duration |2.000000s /2.002217126s|
| Model-to-wall progress ratio |0.998893|
| Missing / late owner slots |0 /0 of10020|
| Expired applied physical intervals |0|
| Largest whole-interval original source age |19.403577ms|
| Minimum original command margin |5.564189ms|
| Largest physical acquisition→native EV commit |1.225510ms|
| Maximum normal HV source / dependency age |11.046136ms /21.134719ms|
| Maximum forward speed |0.427273m/s|
| Camera packets / live inference calls |0 /0|

The measured case is short and low speed; this is not a sustained real-time or
Reference ODD acceptance.400 includes8 empty INIT intervals and other non-driving
INIT Actual intervals. The previous camera10ms trials keep their original failures.

The [physical audit](physical-audit.json) verifies original CAN/P05/command parents,
30ms/HV30 coverage, actual5ms solver dt and all320 substeps, one EV settlement per
receipt, ten owners' original2ms/4ms deadlines, and exclusive writer containment.
External vehicle control, client world.tick and external stage_native were all
rejected after10 normal intervals. Original timestamps were not renewed.

All400 actual world-state observations reached the observer. The native shadow
receiver initialized from post-enable actual state and accepted no perception
results, as expected without a camera. Three synthetic preparation calls completed.
Server SIGINT130/native0, pause/reset/close and observer cleanup passed. No forced
stop, native fault or protection. Four runtime binaries remained original and the
settings file was restored byte-for-byte.

## What changed

- `owner5ms` explicitly selects camera absence, no-render world, NullRHI/inline
  rendering and400 intervals. It rejects a camera, mixed step, HV50 or changed
  fault/warmup profile. `shadow10ms` remains the default200-interval configuration.
- `ObservedWorldClock` accepts a trusted constructor step of5ms or10ms. It never
  infers a period from incoming data. Mismatch/regression still latches, missing
  observations are not filled, and duplicates do not refresh receipt time.
- The retained-work replay supports an explicit5ms model while preserving the
  original10ms default. Every2007 native service row,400 physical receipts and
  startup observation reproduces exactly from the separately built frozen sources.
- The existing physical auditor gains an explicit camera-free owner sensor schema;
  wire, physical, timing, energy and single-writer checks are unchanged. The shadow
  audit separately checks the private IPC's original bytes and absence of results.

The [V2 protocol](../../perception-owner-split-v2-protocol.md) declared one corrected
attempt after the V1 failure. Overall live attempts:2; corrected-profile attempts:1.
No repeated trials or altered deadlines were used to select a successful sample.
1317 source files were frozen before live and separately rebuilt:69 Python tests
and23 coupled admission tests passed. The direct callback regression uses the real
prepared worker and IPC observation boundary. The initial version of that test
left a Mock provider list non-serializable during cleanup; the failure log is kept.

## Snapshot transport component after live

The new `scene_mailbox_v1` is a **kinematic transport prototype**, not a connected
CARLA renderer or a complete dynamic-scene adapter. Its source is recorded in
`scene-source.json` separately from the prelive source archive.

An immutable snapshot carries session/epoch/world/generation, fixed physical step,
configuration/model hashes, complete declared actor IDs, original source/acquisition
times and unmodified poses/velocities. A private nonblocking SOCK_SEQPACKET channel
has one in-flight snapshot and one pending latest snapshot. Completion acknowledgement
only frees transport capacity; it grants no ECU/control credit. A stalled consumer
causes pending replacement, not an expanding FIFO or a producer wait.

Scene acquisition age is checked against the original wall bracket with an exclusive
100ms limit. Expiry, wrong identity, regression, malformed data or disconnect cannot
produce a fresh current snapshot. The type cannot be encoded as a perception result.
Payloads are bounded to14492bytes/128 actors. Each endpoint has one mutation owner.

Ten component tests cover corruption/session mismatch, finite inventory, real
consumer-process stalling, latest replacement, expiry, disconnect and clock/source
regression. Replaying all400 original ego receipts with a paused consumer sends2
snapshots, replaces398 pending snapshots and discards the expired first snapshot;
the last frame1209 retains exact original acquisition, pose and velocity bytes.
This is retained replay, not simultaneous live physics plus rendering. Dynamic
actors, traffic-light/weather consistency and a renderer-frame-to-physical-snapshot
mapping still require a complete scene adapter before live camera use.

## Verification and reproduction

Python regression423 tests passed, and the final snapshot component's10 tests were
also reproduced from its sealed source overlay. C++ admission23 and wheel38 tests
passed; no ECU control implementation changed. Retained-trial checks reproduce
both shadow/physical reports and native replay, and reject13 corruptions of step,
HV budget, writer checks, state/physical source time, missing receipt, native fault,
camera/preparation identity and server lifecycle.

`run.tar.gz` is a lossless archive of the original logs/JSON/CSV/solver records;
`run-manifest.json` verifies every extracted file. Source freezes are not rewritten
after live. No new raw image or holdout; future quality exclusion remains8978.

```bash
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_owner_split_v2/check-evidence.py --work /tmp/owner-v2-NEW
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_owner_split_v2/check-live.py --work /tmp/owner-v2-audit-NEW \
  --replay-binary /tmp/owner-v2-NEW/build/tests/integration/carla/m7_1g/m7_wall_startup_replay
```

Next: implement and verify complete scene acquisition/application and provenance in
a separate rendering process, then declare a live2K/render-stall experiment. Keep
the validated finite owner profile, bounded transport and original protection.
Required perception, independent quality and Jetson deployment remain separate.
