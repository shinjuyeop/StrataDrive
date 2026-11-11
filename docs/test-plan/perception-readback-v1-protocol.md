# CARLA RGB readback V1: prospective finite comparison

Preserve all565 parent source hashes from m10_world_async_v1. Keep D-FINE-M960 FP32,
3840×2304 BGRA, Epic/postprocessing, Town04 development site38/first person fixture,
10ms fixed asynchronous world, actual frame-divisible-by5 camera schedule, original
source+100ms AND offer-receipt+100ms exclusive deadlines, state age100ms, preparation,
active1/pendinglatest1/current1 and every received raw image. No holdout/GT, accuracy
scoring, ROS/vehicle integration, runtime promotion or Jetson optimization.

Build an isolated CARLA unity translation unit. Opt-in flag routes only RGB cameras
through a value-owned stream/header/dimensions captured on the game thread. The
completion task never accesses a Sensor UObject. CaptureScene then readback-copy
commands stay ordered on the render thread; EndPlay's existing render flush protects
the target until copy submission. The readback owns its staging resource until ready,
mapped, copied and released. Original frame/timestamp/pose are never completion time.
Original camera path remains the default when no profiling flag is supplied.

Compare baseline-01, deferred-01, deferred-02, baseline-02 in that order, each in a
fresh isolated server. Both use the same instrumented stream/copy path and100us
fence polling, capacity3 including queued captures, at most4096 trace lines. Baseline
retains Vulkan absolute-time query, RHI flush and blocking query-result wait. Deferred
uses SubmitCommandsHint without that query/wait. All overflow/null-map/texture/query
errors fail; do not release GPU resources merely because a timeout has elapsed.
The raw diagnostic recorder remains finite240, measured disk image writes0.

Record CPU steady-clock nanosecond stages for each actual capture: enqueue, render
entry, copy enqueue, RHI flush/submit, query end, task entry, fence ready, mapping end,
buffer copy/send end, resource release. These are host intervals, not GPU kernel
execution durations. stderr telemetry is emitted identically in both conditions.
Correlate original frame/timestamp against SDK camera callbacks and count any capture
without a delivered callback. Compare render wait, acquisition-to-callback latency,
actual camera/world wall Hz, simulation/wall factor and all-window fresh availability.
The target is real-time1×; faster-than-real-time or slower-than-real-time results are
not silently accepted or paced by changing the source clock. No prospective FPS cap
is added; if the renderer becomes faster than real time, pacing is separate work.

Use the parent500..504-source-frame primary window plus300ms camera-silence tail,
180s startup/900s client/30s shutdown budgets, exit130, all original raw/failure
retention. One attempt per condition, with at most one startup-only recovery if no
client launched, original failure hash recorded before recovery. Never tune source
or budgets after observing a client failure in this revision. Stop/review any GPU
hang before later conditions. Restore the exact original module after experiments.
All measurements remain evidence even if a path fails semantic/lifecycle checks.
Preserve received raw payloads in LFS, verify BGRA/RGB hashes and exact native/Pillow
inputs from fresh archived sources; union all RGB into the7013 prior exclusions.
