# M10 fence and camera comparison V1

Declared after096ab9d, before build or live measurement. TC-PER-096 adds opt-in,
bounded game-thread instrumentation inside UE frame synchronization and RenderCore
fences. Distinguish begin-fence, game-thread task processing, async loading, fence
wait and event waits, and record the selected render-only/RHI/GPU route. Do not
change any synchronization, task order, cvar, vehicle command or input deadline.
Use separate same-thread CPU durations and host CLOCK_MONOTONIC brackets; do not
join engine/CARLA frame numbers. Overflow/incomplete journals invalidate attribution.

TC-PER-097 is two fresh bounded servers in this predeclared order:
1. `camera-absent-01`: no camera actor; renderer remains enabled.
2. `camera-2k-01`: existing2560×1536/FOV90/Epic/postprocess camera, frame5/sensor0.05s.

Both retain D-FINE-M960 FP32 loading and three synthetic preparation calls, the
same state observer/publisher/native shadow reader, Town03_Opt spawn0/ClearNoon,
150 passive pre-camera ticks,200-interval target,10ms model/320 substeps/HV30ms,
original authority and source/receipt100ms. Neither arm uses no-rendering mode.
Startup180s/client900s/native18s/shutdown30s;96 raw slots. One attempt per arm;
failed runs remain failed, no retry or post-result threshold change. No camera
warmup or received-frame exclusion. Record original frame phase/session identities;
one pair is diagnostic evidence, not a randomized performance/quality estimate.

Freeze all source/runtime inputs and separately verify focused tests before the
first run. Preserve journals, raw camera inputs, native CSV/Actual and lifecycle.
All new raw RGB enters future quality exclusion (prior8978); no holdout. Restore
UE executable, CARLA module, Engine and RenderCore libraries, and original settings
byte-for-byte after the two declared attempts. No source edits in external trees.

Decide the next separation boundary from observed route and waits. This protocol
does not authorize claiming continuous real time or removing a rendering fence.
Required remains opt-in logical SIL; quality/metric perception/Jetson are separate.
