# M10 renderer replay V2: image association verified, shutdown failed

2026-11-12. **Overall FAIL_SERVER_SHUTDOWN.** One separately declared corrected
attempt `renderer-02` completed its camera diagnostic, then the server remained
alive beyond the30s SIGINT shutdown limit and required SIGKILL (exit-9). This is
not a live physics/rendering isolation PASS. The first clone-spawn failure is
preserved in [V1](../m10_render_replay_v1/README.md).

## What was observed

| Measurement | Result |
| --- | ---: |
| Native image size / FOV |2560×1536 /90°|
| Actual received images, all retained |19|
| Warmup/unmapped images |7|
| Mapped images / actual renderer ticks with mapped poses |12 /12|
| Original physical receipt frames |810 /1009 /1209|
| Maximum actual-vs-requested transform matrix element error |9.9602471e-7|
| Expired original scenes correctly unavailable |12 /12|
| Inference / native perception publications |0 /0|
| Concurrent physical owner |none|

The experiment requested8 warmup ticks and4 ticks for each of3 retained poses.
It received19 callbacks; it does not claim a camera packet for every requested
tick. All received raw bytes, including warmup, are retained. Frozen-reader checks
verify native image dimensions, exact compression/byte hashes and nonblank image
content. Visual inspection of frame162 confirms an ordinary rendered road scene;
this is not object-detection quality evaluation or proof of original scene fidelity.

The renderer was a distinct process at2300 with Epic settings and a50ms renderer
step. Each clone was created at map spawn point0, had physics disabled, then
received the unchanged original body pose. Actual clone matrices were read back
after each tick and retained for independent comparison. Renderer frame/source
and original physical frame/source/acquisition remained separate. All original
scene timestamps are old; a new callback correctly did not make them fresh.

## Scope and remaining failures

The camera path passed `PASS_RENDERER_DIAGNOSTIC_ONLY`; the overall lifecycle
failed. Server logs reached Vulkan resource cleanup warnings, SDL teardown and
RequestExit130, but those messages do not explain why process termination failed.
There is no retained blocked-thread stack, so no underlying driver/thread cause
is claimed. No retry or increased shutdown timeout was used to obtain a PASS.
The dedicated process was stopped and the settings restored byte-for-byte; all
four original runtime binaries remain unchanged.

Original receipts contain ego body kinematics, not complete wheel animation,
dynamic actor/traffic-light/weather state or verified body-to-mesh/camera offsets.
The diagnostic explicitly uses ClearNoon/frozen-red lights. The new provenance
type therefore always denies perception admission until complete authoritative
scene export exists. It cannot be encoded as the old same-world ECU IPC result.
The numeric sensor ID is bound in the frozen callback but was not recorded in
the report; independent checks rely on that single-camera runner binding.
No20Hz, end-to-end latency, simultaneous-physics, quality or Jetson claim follows.

## Verification and retained artifacts

[V2 protocol](../../perception-render-replay-v2-protocol.md),1329-file prospective
archive,25 focused tests independently reproduced and final Python438 tests passed.
No native ECU implementation or deadline changed. Ten evidence mutations were
rejected: false complete-scene/control promotion, lifecycle relabel, renewed
physical source/acquisition/state receipt, renderer-source mismatch, late-scene
promotion, missing image and clone-pose drift. `live-validation.json` is an
integrity result, not a successful live-trial verdict.

`run.tar.gz` contains original logs/results. `raw-camera-01.tar` is a Git LFS
archive of all19 lossless BGRA packets (133918720bytes); `raw-manifest.json`
identifies every member. All19 RGB hashes are added to future quality exclusions,
now8997. No holdout was accessed. Source archives are not rewritten after trials;
`evidence-manifest.json` separately seals the post-run evidence/readers/docs.

```bash
git lfs pull --include='docs/test-plan/evidence/m10_render_replay_v2/raw-camera-01.tar'
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_render_replay_v2/check-evidence.py --work /tmp/render-v2-source-NEW
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_render_replay_v2/check-live.py --work /tmp/render-v2-audit-NEW
```

Next: diagnose shutdown with bounded thread evidence, implement complete
same-frame authoritative scene export and camera/asset mapping, then declare
the simultaneous owner/render stall-and-exit test. The previous400-interval
nonvideo owner PASS remains limited to its own conditions.
