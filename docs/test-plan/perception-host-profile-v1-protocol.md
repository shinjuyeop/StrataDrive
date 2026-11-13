# M10 Host profiling and placement comparison V1

This is a diagnostic comparison, not an endurance acceptance series. Retain all
three declared distinct configurations even if one fails; no replacement retry
can erase a failed run. The existing five failed V4–V8 trials remain unchanged.
Use one 30s attempt per configuration. A later normal-endurance series still
requires three passing 30s cases before its conditional 300s case.

All runs retain physical 5ms, HV30ms, original native 2/4ms bounds, ECU scheduling,
command expiry and perception100ms guards. Camera 2560x1536/Epic, renderer wall
cap10Hz/model step50ms, source query cap20Hz, D-FINE-M960 and numerical precision
are unchanged. Every generated raw image and model output is retained. No full
visual-scene claim or accepted perception, holdout access or Jetson change.

Freeze the final sources and external artifacts before A. Use the compiled
remediation CARLA module (including the idle-wait and missing-packet diagnostics)
and verified DXC lifetime candidate for all cases. Restore original shared
libraries and INI after the comparison. Preserve all hashes and exit outcomes.

| Case | Placement | Preparation and CPU policy |
| --- | --- | --- |
| A shared baseline | Host V1: renderer and image pipeline share cores4–7 | Existing parallel server launch, default OpenCV/resize, passive ORT |
| B parked shared | Same Host V1 | Sequential ready/park empty worlds; renderer MaxFPS60; OpenCV2/resize4; blocking CUDA host wait; passive ORT |
| C parked split | Host V3: renderer cores4–5, image pipeline cores6–7 | Same preparation/CPU policy as B |

Parking occurs only before native binding and before any real camera exists.
It prevents empty asynchronous worlds from consuming CPU while waiting for the
other server/model. The normal clients subsequently configure/tick their worlds;
no physical release or source timestamp is rewritten. The renderer-only MaxFPS60
cap is distinct from the unchanged physical world and its 200Hz release.

The CUDA policy changes only the current inference process's scheduling flag to
cudaDeviceScheduleBlockingSync. Before/after flags and loaded runtime are recorded.
It changes CPU waiting, not model arithmetic. Preliminary excluded-input tests
compare tensor hashes and numerical outputs; a live result is still diagnostic.
Reference: https://docs.nvidia.com/cuda/archive/12.3.0/cuda-runtime-api/group__CUDART__DEVICE.html

Sample the owned process tree and all its threads every 500ms from launch through
shutdown: cumulative CPU ticks, thread identities/affinities, CPU temperatures,
frequencies, thermal-counter deltas and NVML GPU utilization/power/temperature.
Record monitor CPU cost. Host perf_event_paranoid4 denies perf counters; do not
change kernel permissions. sched_schedstats0 disables reliable run-queue wait
accounting: retain raw schedstat but do not interpret zero wait as no contention.
No debugger samples during normal execution, environment dumps or unrelated
process changes. Thread-level inference and recorder stage timing supplement
sampling. GPU utilization is sampled device utilization, not kernel attribution.

Compare preparation, first normal execution and protected execution separately;
a failed/idle tail cannot make a configuration appear cheaper at doing useful
work. Rank original acceptance first, then recording completeness, normal duration,
original latency tails, thermal-counter deltas and CPU cost. No global-optimum
claim follows from these three cases. Further candidates require new declarations.
