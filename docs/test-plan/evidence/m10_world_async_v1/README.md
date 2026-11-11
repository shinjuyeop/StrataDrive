# M10 fixed-step asynchronous world observation V1

2026-11-11. Finite Host integration PASS; performance improvement **not established**.
Server-asynchronous mode is available for the4K perception path. Original M9/C++640
runtime, model/quality failures and all prior evidence remain unchanged. M10 stays OPEN.

## Declared comparison and observations

The [prospective protocol](../../perception-world-async-v1-protocol.md) fixes D-FINE-M960
FP32,3840×2304 BGRA, Epic, RTX3090, site38/first person, same-owner synthetic3-call
preparation, CPU resize and both original exclusive100ms deadlines. State comes from
actual `world.on_tick` in both modes; only synchronous mode explicitly requests ticks.
Source window500..504 frames; primary availability includes the entire enabled window.
No GT, holdout inspection, accuracy scoring, training or board optimization occurred.

| Condition | World wall Hz | Camera wall Hz | Observer wall Hz | Primary valid reads | Published / calls | Unique consumed incl. tail | Explicit ticks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| sync-01 | 61.67 | 12.35 | 50.00 | 182/407 (44.72%) | 99/100 | 99 | 532 |
| async-01 | 56.39 | 11.30 | 48.91 | 167/435 (38.39%) | 95/100 | 93 | 0 |
| async-02 | 60.43 | 12.13 | 50.00 | 190/414 (45.89%) | 100/100 | 100 | 0 |

All three original attempts passed the finite integration gates; no retries/recovery
were used. Each received100 raw images with no scheduled missing or extra boundary
images; state gap/duplicate/reorder counts were0. The primary windows span503/502/501
source frames; state observations including camera-silence tail were532/546/543.
Independent fresh consumption occurred in all five100-source-frame segments.
Startup180s/client900s/shutdown30s budgets held; each server exited130 without forced
kill and ports2300–2302 were free after cleanup. Original logs are retained per run.

The asynchronous runs made **zero explicit client tick calls** and continued actual
state/observer progress while inference ran. Source simulation/wall factors were
0.6167/0.5639/0.6043. Fixed10ms does not mean wall100Hz or real-time1×. This short
sequential comparison provides no evidence of increased speed or smoother rendering.
OS cache and shared resources were uncontrolled; do not infer the cause from mode alone.

The synchronous run retained1 source-only late completion; async-01 retained5 receipt-only
late completions and one observed state-silence interval. The stale read invalidated
old generation/current/pending; a subsequent actual snapshot allowed new input without
reviving old output. Async-02 had0 late completions. Backend errors and true clock faults
were0. Observer skipped slots were0/10/0. Primary longest unavailable *sample spans*
were220.112/1239.984/140.094ms, not exact continuous outage durations. Preparation took
520.238/446.573/451.247ms with all nine synthetic calls retained and never published.
Receipt-to-backend-return P95 was59.627/74.968/61.642ms. Callback job means were
12.621/15.014/12.759ms; these combine SDK raw materialization, offer and recording work,
not isolated copy cost. Source/SDK/renderer delay attribution remains open.

## Ownership and expiry

The [new clock/owner](../../../../physical_ai/perception/world_async_v1.py) caches128
actual snapshots. It counts forward gaps without inventing matching timestamps, ignores
consistent duplicate/reordered observations without renewing age, and latches conflicting
episode/period/time. Atomic state/result/read-time samples prevent a concurrent state
update from pairing a new result with an old sampled source time. State silence100ms
returns unavailable; original acquisition+100ms AND offer receipt+100ms remain exclusive.
Preparation READY and later state recovery never grant driving permission.

The500-frame probe retains at most240 immutable raw references; actual peak was100
frames/3,538,944,000B in each run. Normal measured disk image writes were0. Compression
occurs after measurement; the recorder is a finite Host diagnostic, not a Jetson runtime
buffer. Inference remains active1/pendinglatest1/current1. The300ms camera-silence tail
keeps actual state moving and confirms old perception expires.

## Reproducibility

- [Source freeze](freeze.json):554 parent files unchanged plus11 additive files =565;
  [source archive](sources.tar.gz), [parent freeze](parent-freeze.json) and pinned external
  Sensor.cpp/library hashes are preserved. No post-capture acceptance change.
- [Live summary](live-summary.json), [run inventory](runs.json), original `result.json`,
  server/readiness/client logs and copied client source remain per condition.
- [Preflight](preflight.json):335 Python tests including17 new clock/owner/payload tests.
  Existing C++/boundary12 tests each pass Debug/Release/ASan, with separate logs.
- [Post-capture mutation checks](report-mutation-check.json):36 malformed reports rejected;
  actual Hz and timing distributions recomputed. This additional audit test does not
  change capture settings or the frozen565-file implementation.
- [Fresh archive audit](validation.json): all300 stored BGRA/RGB hashes, decompression
  bounds, exact native/Pillow tensor/health and original inference/read deadlines checked.
  No GPU re-inference or new quality claim is made by this audit.
- [Future exclusions](future-exclusion.json):6713 prior +300 actualRGB =7013. All received
  bytes are represented, including non-published late results.

The five [raw payload inventories](raw-archives.json) total5,149,460,480B. Worktree files
may be canonical Git LFS pointers because `/d` is nearly full. The actual payloads live
in the configured local LFS object cache and are uploaded with the commit. `SHA256SUMS`
checks metadata/source bytes; raw archive payload SHA/size is checked through the hashed
`raw-archives.json`, so both materialized archives and pointers resolve identically.
The auditor never treats a pointer hash as verification of raw contents.

```sh
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_world_async_v1/check-evidence.py \
  docs/test-plan/evidence/m10_world_async_v1 /tmp/world-async-audit-new.json
```

Optional final argument: local LFS `objects` directory. Otherwise the repository's
`git lfs env` LocalMediaDir is used. Missing objects must be fetched before verification.
The output path must be new. The checker extracts only safe regular files into a fresh
source directory, then uses those archived implementations for deadline/raw replay.

Remaining: connect unavailable to existing state/protection ownership; distinguish
renderer/SDK acquisition age and scheduling delay; new independent quality qualification,
long-duration/whole-stack wall20Hz and deployment on each Jetson. No actuation/ROS2 or
board-specific optimization is included in this change.
