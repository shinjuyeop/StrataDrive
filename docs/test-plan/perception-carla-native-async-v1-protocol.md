# Live native4K observational probe V1

Declared 2026-11-11 before execution, after the native preprocessing V1 replay.
One isolated Town04_Opt/Epic server, consumed development site38 / first existing
ClearNoon person case. No GT/holdout input. The RGB camera uses 3840×2304, FOV90,
postprocess on, sensor_tick0.05, role m7_frame5 and both existing custom frame5
flags. Pin CARLA HEAD/SDK version and sensor source/plugin binary hashes.

Initialize the fixed CUDA backend before sensor enable. Keep all first/cold calls.
One main owner advances actual world10ms steps and records snapshots. SDK callbacks
copy/offer BGRA and append a reference to a finite diagnostic recorder. The frozen
one-active/one-pending owner performs conversion/health/resize/inference/decode.
An independent monotonic50Hz observational consumer reads snapshots; it never calls
inference, joins a worker, ticks the world or sends any actuator command.

Run300..304 actual world ticks, ending at frame modulo5=4 so the last scheduled
acquisition has four following source steps. No target wall pacing or skipped
world steps. Allow200ms delivery without ticking, stop the sensor, and continue
the observer for300ms with a stopped source clock. The 64-frame diagnostic recorder
retains ALL callbacks (including failures/late frames), with explicit overflow
failure; it is separate from the one-slot production mailbox. Hash/compress/save
only after measurement. This recorder consumes up to2.27GB RAM and is not intended
for production deployment. No heavy archive work during server startup.

PASS requires complete contiguous actual tick/source history, exactly every
scheduled frame5 callback, all original raw bytes retained, exact call/input
accounting, some real tick/consumer progress overlapping inference, at least one
fresh result consumed, and at least five unavailable reads after100ms silence
while source time remains fixed. Keep explicit health/inference failures and
deadline misses in the denominator; never reinterpret them as empty scenes.
Both exclusive source+100ms and original offer-receipt+100ms deadlines remain.
SDK raw_data materialization precedes offer and is measured separately; no claim
of sensor-acquisition-to-host wall latency or hard real-time behavior is made.

Independent raw/trace audit must replay the same result. Record actual wall
world/camera/consumer rates separately from simulation10ms/50ms periods. No live20Hz,
quality, driving, Jetson, ROS2 or runtime-promotion acceptance follows from PASS.

One formal attempt. Startup180s/client900s/shutdown30s and normal exit130 are
required. Any timeout, forced stop, missed callback or audit failure remains FAIL.
Recovery, if needed, requires a separate prospective note/freeze and bounded run.
Every newly observed RGB hash enters the future-exclusion union, including any
failed attempt, based on the prior5629 list. Raw images remain development-only.
