# M10 quiescent renderer cleanup V2

2026-11-12. **PASS for one finite renderer cleanup/lifecycle case**, `shutdown-02`.
The renderer held actual frame163/source2423182888ns for **3.587107726s** while
saving all image packets, then exited130 in **1.617304896s** after SIGINT. No forced
stop, cleanup error or debugger attachment. This does not explain or resolve the
earlier intermittent shutdown failure: the preceding unmodified-cleanup
[diagnostic](../m10_render_shutdown_v1/README.md) also exited normally.

## Change and actual result

The dedicated renderer process is about to terminate after capture. Its old
cleanup restored asynchronous WorldSettings before compressing/storing images,
allowing additional unrequested simulation/rendering. The opt-in
`--quiescent-shutdown` keeps the existing synchronous50ms settings and reads actual
frame/source before and after storage. A changed world/frame/source or regressing
wall clock fails cleanup. It does not call ApplySettings to pause: pinned
LibCarla `client/World.cpp:56–83` can issue ticks inside that API. Persistent INI
settings are still restored by the parent after process termination.

| Measurement | Result |
| --- | ---: |
| Actual image dimensions |2560×1536|
| Received/retained images |19|
| Associated images across3 original physical poses |12|
| Frame/source advancement during3.5871s storage |0 /0|
| Shutdown wall duration |1.6173s|
| Server exit / forced stop |130 /none|
| Debugger attachments |0|
| Inference / native publications |0 /0|

Renderer instance/world/camera/calibration identity is now explicitly persisted
and validated. This closes the earlier report omission, not the complete-scene
gap. Original ego body kinematics do not reconstruct wheel animation, all dynamic
actors, original traffic-light/weather state or verified mesh/camera offsets.
All old scene times remain expired; incomplete scenes still cannot enter the
same-world ECU IPC. No concurrent physical owner, whole-system/20Hz, quality or
Jetson acceptance is claimed.

## Evidence and verification

The [V2 protocol](../../perception-render-shutdown-v2-protocol.md) and1337-file
archive were frozen before this sole confirmation attempt.32 focused tests were
reproduced from the archive, including actual debugger permission tests, no-tick
cleanup and pose/frame provenance. Final Python regression:445 PASS. No native
ECU or server binary implementation changed and all original deadlines remain.

Independent retained-data checks verify all19 raw image packets,12 mappings,
original physical acquisition/state receipts, actual clone transform matrices,
held frame and bounded clean shutdown. Fifteen corruptions are rejected, including
false lifecycle/scene/control promotion, shutdown-budget or diagnostic changes,
held-frame/time/calibration changes and source-time renewal. All19 new RGB hashes
join future quality exclusions, now9035; no holdout accessed.

`run.tar.gz` contains all original logs/results; `raw-camera-01.tar` retains every
lossless BGRA packet through Git LFS. Member and overall SHA256 manifests accompany
both. `restoration.json` checks unchanged original runtime binaries and exact INI
restoration. Prospective source archives and earlier failure verdicts are retained.

```bash
git lfs pull --include='docs/test-plan/evidence/m10_render_shutdown_v2/raw-camera-01.tar'
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_render_shutdown_v2/check-evidence.py --work /tmp/shutdown-v2-source-NEW
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_render_shutdown_v2/check-live.py --work /tmp/shutdown-v2-audit-NEW
```

Next: capture complete authoritative same-frame scene/visual state and verify
body-to-actor/camera and asset mapping, then declare simultaneous owner/render
stall/exit testing. Carry bounded shutdown diagnostics forward; only direct
evidence from a recurrence can explain the earlier hang.
