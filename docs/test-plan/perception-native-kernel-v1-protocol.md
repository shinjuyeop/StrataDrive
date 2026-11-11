# Native4K resize and completion telemetry V1

Declared 2026-11-11 before formal execution. Parent is the514-file
[native preprocessing live freeze](evidence/m10_native_preprocess_v1/live-freeze.json).
Never edit parent bytes. Keep3840×2304, the fixed D-FINE-M960 FP32 model/decoder,
confidence, healthy-image decision, latest1 owner and exclusive original
source+100ms AND receipt+100ms. No board optimization, training or runtime promotion.

## Implementation under test

The portable C++ CPU kernel reads original BGRA and directly computes RGB960 using
Pillow11.3.0's bilinear coefficients, horizontal then vertical22-bit uint8 rounding.
Keep the upstream Resample.c/license/provenance. Four OpenMP threads with PASSIVE
wait, no fast-math, FMA contraction or architecture-specific flags. The ctypes CDLL
call releases the GIL. Scratch/output belong to one inference owner; never alias
or concurrently call the same NativeResize instance. No full-resolution RGB copy.
The original BGRA grayscale/health and NumPy float32 tensor arithmetic are unchanged.

The traced owner adds at most512 completion records; overflow is explicit and must
be zero in probes. Preserve all V1 admission logic and inheritance tests. Record the
actual admission source/wall clocks, queue-start clocks, backend return monotonic
time and disposition. Recompute source-only/receipt-only/both expiry independently.
Completion telemetry is diagnostic; it grants no new authority or extra lifetime.

## Required checks before live execution

- Every84 existing development4K pilot/comparison model input tensor and health
  decision must be exactly equal to the prior Pillow path. Include all first calls
  in paired diagnostic timings; no GT/holdout reads and no quality claims.
- Seeded noise, channel/alpha patterns, boundary impulses, constant extremes and
  checkerboard must match Pillow at1 and4 CPU threads. Test ABI null/layout/threads
  rejection and buffers under standalone ASan+UBSan.
- Replay the existing21 owner tests against telemetry plus explicit source-only,
  receipt-only/both boundary and bounded trace overflow checks.
- Four6-second replay conditions: normal, additional150ms, blocked until periodic
  owners finish, and25ms exception. Keep all cold calls/overwrites/expired inputs.
  Normal must publish and consume fresh results; faults preserve original gates.
  Audit every completion cause and compare every real model output's final
  detections with the prior3 development CUDA outputs (score atol1e-4/box0.6px).

## Two declared live conditions

Run one traced prior Pillow baseline, then one traced native kernel, each on a new
isolated Town04_Opt/Epic server, consumed development site38/first person fixture.
Same model/camera/frame5 source and shared RTX3090 as the preceding failed probe.
No GPU warmup or first-call exclusions. The baseline is **diagnostic only** and
may have zero fresh outputs; it cannot change the previous live FAIL. The kernel
requires at least one freshly published result consumed. Other integrity gates
remain: exact contiguous actual world steps, every frame5 acquisition, complete
call accounting, original result/clock identity, independent actual tick and50Hz
observational consumer progress during inference, and stopped-source wall expiry.

Each condition runs180..184 actual10ms ticks ending modulo5=4, hence36 camera
acquisitions, followed by the existing200ms delivery and300ms source/camera-silence
phases. Diagnostic recorder capacity40, overflowFAIL. Save every original raw
callback after measurement. Use the root filesystem for temporary capture data
because /d has limited space; no archive work during UE startup. No vehicle control.
The shorter finite probes are integration diagnostics, not live20Hz qualification.

Startup180s/client900s/shutdown30s and exit130 remain. One formal attempt per
condition; failures stay FAIL. Any required recovery is separately declared before
execution. Add all newly seen RGB hashes, including failed attempts, to prior5689
future exclusions. Preserve source/binary versions, logs, all calls and raw bytes.
Fresh archived-source/raw replay and source-parent hashes are required before commit.
