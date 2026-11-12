# M10 actual-owner2K shadow IPC V1

2026-11-12. **Private same-host IPC/component PASS; one live result delivered;
continuous wall driving FAIL/OPEN.** D-FINE-M960 FP32,2560×1536/FOV90/Epic and the
original two100ms deadlines are unchanged. No Required promotion,20Hz chase,
quality acceptance, metric tracking or Jetson deployment/optimization occurred.

## What ran

A separate Python publisher sends original result/state records through inherited
nonblocking SOCK_SEQPACKET. The actual `m7_carla_wall_owner` drains at most4 records
per20ms poll, binds to native INIT and exposes the2K receiver beside original
P05Actual. No perception code writes a vehicle request or protection command.
See [wire/ownership contract](../../../interfaces/perception-shadow-ipc-v1.md) and
[prospective bounded protocol](../../perception-control-shadow-v1-protocol.md).

One fresh Town03_Opt server,150 passive pre-bind settling ticks without a camera,
then a200-interval target and96-frame finite recorder. Existing server wall owner
controls physical ticks; Python inference never ticks the world. This differs from
the earlier free-running camera benchmark. The unchanged native wall guards were
allowed to fail; no hidden live retry or simulation-time replacement was used.

## Actual outcome

- The server completed3 physics intervals,0 normal driving intervals, and the
  native process never armed. It selected protection at initial+64.014273ms:
  `native credit/gate closed leaf=0 code=4 leaf=1 code=4 leaf=2 code=11 leaf=4 code=12`.
  These codes are Steering/Brake/Drive/Power `ControlDeadline`.
- One camera frame205 was retained and inferred, with0 detections. Its first live
  model call began at initial+114.339922ms, after protection. C++ accepted it at
  +160.017119ms with original source/receipt and both deadlines intact. This is
  delivery of a valid empty result, not evidence of live object detection quality.
- Native observer:39 reads,1 fresh read/1 accepted frame,0 receiver rejects. Parent
  sent42 packets;41 reached native before STOP. The remaining packet is recorded,
  not claimed as consumed. There is no steady-state availability/rate claim.
- Worker receipt→backend return30.828262ms; receipt→native read45.787417ms for this
  one frame. State age at that read96.340881ms<100ms; later silence becomes stale.
  These are not camera-acquisition latency or representative performance estimates.
- IPC service max107868ns, median4143ns across39 polls. Existing wall watch records
  3880 jobs/0 detected overruns. The leaf logical tick-gap/INIT path still produced
  `ControlDeadline`; this does not prove the root cause or whole-system real time.
- 35 original Drive P05Actual packets were decoded and checked. Steering/Brake
  Actual remained absent. No full three-actuator stop-response claim is made.
- Server SIGINT exit130, native exit0; pause/reset/close succeeded. Sensor destruction
  before exclusive-owner close was rejected: the original run remains FAIL, including
  that cleanup error. The original module and GameUserSettings were restored exactly.

[Original live audit](run-01/audit.json), [timeline](timeline.json), and
[server lifecycle](run-01/server.json) preserve these separate outcomes. Hypothesis
for the next investigation: delayed INIT admission versus the first ECU runnable
and original enable time. Protection preceded live inference by50.325649ms; do not
attribute this failure to image inference or loosen deadlines to get a pass.

## Verification and provenance

- New C++ IPC13, previous native2K receiver15/control SIL9, legacy receiver11,
  speed supervisor22, vehicle coordinator31: **101 C++ tests PASS**.
- Full workspace Python **395 PASS** (391 before the live attempt and4 new cleanup
  tests afterward). **37 ASan+UBSan tests PASS**, including IPC13 and prior2K24.
- Real Python/C++ child process/socket test preserves original acquisition and
  receipt, repeated polls, exact expiry, no resurrection, malformed input and EOF.
- Before the live attempt,1235 source/import/build inputs were archived, separately
  built, and checked with101 C++/13 Python boundary tests and process interop.
  [sources.json](sources.json) and `sources.tar.gz` are the actual frozen live inputs;
  [validation.json](validation.json) is the pre-live successful rebuild.
- Two pre-live archive harness failures are preserved in `prelive-archive-01/02`.
  Attempt01 full discovery lacked historical quality assets/generated resize library
  and build directory (25 errors); attempt02 fixed the directory but still lacked
  unrelated historical assets/library (24 errors). Full391-test workspace regression
  passed. The archived test scope was corrected to the13 self-contained boundary
  tests; no live failure was retried or erased.
- A post-live cleanup correction stops callbacks, then releases native ownership,
  then destroys the camera only if still present.4 tests passed, including applying
  the exact overlay to the archived sources. [post-live/manifest.json](post-live/manifest.json)
  records before/after hashes; it does not change the original live inputs or outcome.
  This correction has not yet been exercised by another live server.
- Raw original BGRA is in Git LFS `raw-run-01.tar` (7116800bytes); member/decoded BGRA/
  RGB identities were checked. The one received RGB frame is excluded from future
  quality evaluation:8975→**8976**, [future-exclusion.json](future-exclusion.json).
  No holdout was accessed. Frozen-source replay reproduced the exact live audit;14
  semantic/raw mutations were rejected ([live-validation.json](live-validation.json)).

Rebuild the frozen boundary and verify the subsequent cleanup overlay:

```bash
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_live_shadow_v1/check-evidence.py \
  --work build/m10-live-shadow-v1/reproduce-NEW
```

Audit the retained trial with its original frozen auditor (hydrate the raw archive
with Git LFS first if it is only a pointer):

```bash
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_live_shadow_v1/check-live.py \
  --work build/m10-live-shadow-v1/audit-NEW
```

Next: instrument accepted INIT and first actual leaf runnable timestamps, reproduce
why original logical deadlines close despite the wall execution-watch passing, then
run a separately declared bounded trial with the cleanup correction. Preserve the
current2K/model/deadline choices; Required remains opt-in logical SIL only.
