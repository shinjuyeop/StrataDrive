# Immutable4K snapshot copies and stage timing, V1

Preserve all580 readback/pool parent files. Use the same instrumented CARLA module,
blocking Vulkan query and largest-request render target settings2/1. Keep3840×2304
BGRA/Epic/postprocessing, fixed10ms server-asynchronous world, frame%5 camera,
D-FINE-M960 FP32 and thresholds, native/Pillow exact resize, actual state cache,
source+100ms AND original offer-receipt+100ms exclusive, state-age100ms, preparation
and active1/pendinglatest1/current1. Do not change sensor timestamps or move offer
receipt to completion. No old holdout/GT, new accuracy, model/board optimization,
ROS/vehicle integration or runtime promotion.

The pinned CARLA SDK raw_data getter exposes a read-only memoryview without owning
the Image allocation. Do not pass this borrowed view to the worker. The new CPython
helper pins both the view and the SDK Image for the duration of memcpy, then returns
a new independently owned immutable bytes object. Caller exclusively owns the SDK
exporter during copying; read-only view alone is not proof of underlying immutability.
The helper never retains an SDK pointer or rewrites a published bytes object.

Before enabling the camera, allocate and touch120 private35,389,440-byte destinations.
This finite Host diagnostic pool is4,246,732,800 bytes, not a Jetson/production queue.
Slots publish once and never recycle. GIL protects reservation/publication; the
memcpy releases it so state and consumer callbacks can progress. Allocation has a
separate10s budget and is included in preparation reporting. The existing finite240
recorder retains original snapshots; no normal measured image disk writes. Pool
exhaustion or copy failure fails the run and falls back only to preserve the received
raw image; stop the run, never claim the fallback as optimized success.

Synthetic64-copy evidence is development-only: independent XY gradient,16 retained
copies each in baseline/prefault/prefault/baseline order, allocation reported separately,
1ms auxiliary heartbeat and exact snapshot identity. No live20Hz inference from it.

Run copy-baseline-01, copy-prefault-01, copy-prefault-02 sequentially on fresh isolated
servers. All use the same staged backend arithmetic; only materialization changes.
Record callback/view/copy/offer/recorder times; record grayscale, health, native resize,
tensor construction, inference and decode on the same inference owner including all
3 synthetic preparation calls. Join original identity to GPU trace and state. The
new timing labels are host intervals, not GPU kernel times. Verify staged feed/health
exactly against the frozen kernel/Pillow path. Retain allocation, initial waits and
all publication/expiry/consumer decisions, including failures.

Use parent500..504 source-frame primary windows,300ms camera-silence tail,
180s startup/900s client/30s shutdown and exit130. One attempt per condition; at most
one startup-only recovery if no client started, declared with original failure hash
before recovery. No client retry or post-result parameter tuning. Every received
frame is archived and added to the7613 prior RGB exclusions. Compare full-window
valid reads, missing/late frames, state/observer wall cadence, camera/world wall Hz,
original source/receipt ages and capture-to-result latency. Preserve all failures;
short finite progress does not establish real-time1×, wall20Hz or deployment safety.
Restore the exact original CARLA module after all trials. Fresh-source replay checks
all raw hashes, original BGRA/RGB and exact native/Pillow model inputs, including
failed captures. Regression tests run with no live UE server.
