# Largest-request render-target allocation, V1

Follow the frozen574-file readback comparison without editing it. Its first baseline
log repeatedly reallocates scene targets between856×640 and3840×2304. UE4's pinned
SceneRenderTargets.cpp defines r.SceneRenderTargetResizeMethod=2 as grow to largest
requested dimensions, trading retained GPU memory for fewer allocation stalls.
This follow-up is prospectively declared before either pooled client runs.

Run pool-baseline-01 then pool-deferred-01, independent isolated servers and the same
instrumented binary. Add only the console settings r.SceneRenderTargetResizeMethod=2
and r.SceneRenderTargetResizeMethodForceOverride=1; require their actual console
readback in server logs. Keep source4K, Epic, postprocessing, fixed10ms asynchronous
world, source/receipt/state100ms, original frame/timestamp/pose, model/confidence and
all other readback V1 controls. No FPS cap or time relabeling. Render-target allocation
size is not camera output resolution. This is a host memory/performance experiment;
no measured image quality equivalence or Jetson-memory suitability is claimed.

Use the same500..504-frame and300ms tail windows, finite3 GPU readbacks/240 raw frames,
180/900/30s lifecycle budgets, all raw retention, append-only source freeze, one
attempt each and at most one declared startup-only recovery. Do not retry client
failures. Compare world/camera wall rates, real-time factor, original deadlines and
fresh availability, render/query/fence/copy latency, delivered/missing frames and
reallocation log counts. All observations, including semantic failures, are retained.
A short single pair does not establish long-term real-time operation. Archive every
received raw image, exact-input audit and cumulative future exclusion before cleanup.
