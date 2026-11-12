# Bounded2K latency study — retain the existing development path

This study follows the user's request for worthwhile latency reduction without
requiring20Hz. The existing2K path remains recommended. Reusing the tensor buffer
saved2.475ms in the live comparison, below the prospectively declared3ms adoption
criterion. Deferred GPU readback with an engine tick-rate ceiling made latency and
freshness worse and failed the original segment-consumption requirement. No candidate
was selected; the conditional confirmation was NOT RUN. No further tuning was pursued.

| Same2560×1536/Epic/D-FINE-M960 FP32 | Existing baseline | Reused tensor | Reused tensor + deferred readback + cap100 |
| --- | ---: | ---: | ---: |
| Original integration outcome | PASS | PASS | FAIL |
| Camera wall Hz | 17.552 | 17.682 | 17.545 |
| Simulation/wall ratio | 0.876 | 0.882 | 0.877 |
| Capture→backend mean ms, all100 calls | 94.202 | 91.726 | 127.740 |
| Capture→backend P95 ms | 98.117 | 95.637 | 185.844 |
| Capture→backend max ms | 101.542 | 104.521 | 205.637 |
| Capture→first consumption mean ms | 104.219 | 101.883 | 133.521 |
| Published / uniquely consumed | 100 /100 | 100 /100 | 45 /27 |
| Sampled active fresh-read fraction | 47.74% | 48.76% | 10.53% |
| Tensor construction mean ms | 5.361 | 2.467 | See original stage trace |

All measurements are short, fixed500..504-source-frame observations (about5 simulation
seconds), with a300ms camera-silence tail. These are not long-term or independent driving
qualification. Capture→backend includes every call, including cold/late results. First
consumption includes only frames actually consumed; it is not a replacement denominator.
The existing world and state/camera/observer ownership remain asynchronous. Only the GPU
readback experiment used a different completion strategy; the engine cap is a ceiling,
not a forced minimum rate or a source-clock retiming.

The tensor-only implementation uses one preallocated float32 NCHW output and direct
NumPy division with the same values and contiguous layout. Its single synchronous owner
consumes the borrowed buffer before reuse; another thread cannot overwrite an established
owner's input. The source image, exact Pillow resize, health checks, model, FP32 precision,
class thresholds and decoded results are unchanged. The implementation remains opt-in,
not the recommended default, because the predeclared practical-effect criterion was not
met.3ms is this experiment's selection margin, not a physical or system safety minimum.

The GPU experiment removed the blocking query wait (19.13→0ms), but the fence wait became
19.73ms and offer→backend-start mean rose from0.19 to22.12ms. Capture→callback mean rose
39.42→44.24ms. Thus removing one explicit wait did not remove the work: delivery and
inference scheduling worsened. The mean inference stage also rose34.50→36.83ms. These are
observed stage changes, not a claim of a uniquely proven hardware cause. The FAIL is
retained: at least one100-source-frame segment had no fresh result consumed. All other
original contracts are replayed and this failure is not relabelled as integration PASS.

## Scope and evidence

The [prospective protocol](../../perception-latency-2k-v1-protocol.md) fixes the three
initial variants and at most one eligible confirmation. `selection.json` recomputes the
same mean/P95/rate/freshness criteria. Neither candidate qualified, so `confirmation.json`
is null and `runs.json` explicitly records confirm-01 as NOT RUN.20Hz is not a selection
gate. The existing100ms source/receipt deadlines, actual on_tick snapshots, state100ms,
active1/pending-latest1/current1 and all cold calls stay intact. No retry or new engine
implementation was introduced; the already pinned V2 module supplied both readback modes.

The636-source freeze preserves all626 previous files and prospectively includes the
previously omitted common helper plus nine new files. The older provenance gap remains
recorded in its original bundle. Fresh archived client/runner/auditor imports and19 tests
passed BEFORE the first live run. All378 Python tests passed. No new native code or model
precision was introduced, so this study does not claim a fresh native sanitizer run.

All81 prior2K development tensors match the unchanged model inputs exactly, and all300
new RGB inputs match both the original staged path and Pillow. Prior quality scores are
not newly measured quality results: no new GT capture, inference, training or holdout use
was needed for input-equivalent preprocessing. `prior-input-equivalence.json` retains all
81 tensor hashes. Its offline timing is secondary and is not live end-to-end performance.

All300 newly received packets, including the failed variant, are retained in12 LFS
archives (2,253,793,280 bytes). RGB future exclusion is8675→8975. Raw payloads, member hashes,
BGRA/RGB, exact input tensors, all original timing statistics and the rejected outcome are
replayed from a fresh636-file source extraction.88 report/trace mutations are rejected.
A replay PASS means the evidence agrees with the recorded PASS/FAIL outcomes; it does not
promote the rejected variant or close M10.

## Storage and restoration

Disk space initially had only about14MB free on the system volume. Before new trials,
72 old temporary native-kernel packets were verified against the preserved archive and
committed hashes, and its LFS object was uploaded/verified again. Only those duplicate
temporary packets were removed; the hydrated old worktree archive was returned to its
canonical LFS pointer. Its complete payload remains in the local LFS cache and remote.
`storage-maintenance.json` records every removed duplicate and the retained payload.

Each new archive was verified and uploaded before temporary duplicates were removed.
Per-run `local-storage.json` records project-volume payload placement and retained canonical
cache symlinks. No user-owned unrelated files or original evidence were deleted. The
original CARLA module and exact GameUserSettings bytes were restored after all three
servers exited130; no UE4Editor process remained. See `environment-restoration.json`.

The practical recommendation is2K with the existing GPU readback path, roughly17.5Hz and
94ms mean capture→backend in this observation. Stop this bounded optimization pass and
continue functional integration with explicit unavailable-result handling. The tensor
option is retained for future development comparisons. Actual vehicle control, ROS,
independent quality, long-term real-time qualification and per-Jetson deployment remain
separate work; no board optimization or production runtime promotion occurred.
