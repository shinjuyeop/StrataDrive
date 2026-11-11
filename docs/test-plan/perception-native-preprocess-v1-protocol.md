# Native4K equivalent preprocessing V1

Declared 2026-11-11 before formal execution. Parent is the 503-file
[async fault V2 freeze](evidence/m10_async_native_v1/fault-v2-freeze.json).
Parent files, model, fixed confidence vector, PIL bilinear 960 resize, tensor
arithmetic, source identities, single inference/pending/snapshot capacities and
exclusive source AND receipt 100ms expiry remain unchanged.

The opt-in backend decodes BGRA directly through PIL BGRX and computes image
health from exact 256-bin counts. OpenCV uses four CPU threads, set before input
enable. NumPy 1.23.5, Pillow 11.3.0, OpenCV 4.11.0 are required. Every bin count
is exact below 2^24 pixels. Integer moments avoid full-image float64 statistics;
std within 1e-9 of 2 uses the original NumPy reduction. Alpha is ignored.

Validation, with no GT or holdout access:

1. Unit tests exhaust all RGB codes for grayscale equivalence, native tensor
   bytes, ignored alpha and exact std/98% image-health boundaries.
2. All three development4K pilot and 81 development4K comparison images must
   produce identical RGB and model tensor bytes; health values differ at most
   1e-10 with identical admission. Keep all 84 paired timings including first.
   Timing is diagnostic, excludes disk/decompression/inference, and is not a
   new quality denominator.
3. Four independent six-second recorded-media probes: normal, additional150ms
   delay, blocked backend until periodic owners finish, and25ms delayed exception.
   State100Hz/camera20Hz/observational consumer50Hz target periods are unchanged.
   Keep every cold call, missed slot, overwrite, exception and expired result.
   Normal additionally requires at least one fresh publication AND consumption.
   Faults require the original V1 accounting, fail-closed and overlap checks.
   Replay all traces using the frozen independent auditor. Compare every real
   model call's final detections to the corresponding prior CUDA pilot outputs
   with native box atol0.6px, score atol1e-4 and identical labels/counts.

One formal attempt per condition. Any failure remains a failure. A revised
fixture requires a separate prospective protocol/freeze; no selective rerun.
This is host CPU optimization with a fixed CUDA model, not Jetson optimization,
ROS integration, actual driving, live-camera proof, quality acceptance or20Hz
qualification. M10 remains open and runtime promotion remains false.
