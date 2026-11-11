# Native4K explicit preparation and availability V1

Declared 2026-11-11 before formal execution. Append to the533-file
[native kernel freeze](evidence/m10_native_kernel_v1/freeze.json); keep all parent
bytes. Preserve3840×2304 BGRA, pinned D-FINE-M960 FP32, confidence, native exact
resize, typed results, latest1 capacities and exclusive original source+100ms AND
original offer receipt+100ms. No runtime promotion, GT/old holdout access, training,
board optimization, ROS or vehicle-controller integration.

## Explicit preparation

An opt-in owner starts NOT_REQUESTED, accepts one preparation request and handles
three independent synthetic native BGRA XY gradients before admitting a sensor
session. The same thread and backend subsequently handle sensor packets. Reuse
only the existing generic Preparation state machine: entire preparation<10s,
calls2/3 each<100ms, no retry in the same worker, exceptions/deadline/clock faults
fail closed and late completion cannot restore READY. The first gradient generation
is inside the first call's elapsed time. Model/session construction is separately
recorded. Never publish a synthetic result or allow it to become a camera snapshot.
READY is initialization readiness, not valid perception or driving permission.

Preserve every cold call in a complete separate preparation denominator, including
full results, identity, owner thread and time. Sensor admission counters start at
zero; total backend calls=sum(preparation calls,sensor calls). This is an explicit
new lifecycle contract, not a retroactive warmup exclusion from prior evidence.

## Replay and sampled availability

One6s recorded-development probe per camera rate10,13,20Hz, in that order, each
with a new backend/owner and explicit preparation. State100Hz, observation50Hz.
Use exactly the three already consumed pilot4K inputs, preloaded before measurement.
No wall clock synchrony with a rendering simulator is claimed. Keep all sensor
startup, overwritten, late, rejected and empty reads; report missed wall slots.
Verify every sensor result against the existing3 CUDA references (score1e-4,
native box0.6px); no new quality scoring. Independently replay original admission
and all telemetry, preparation isolation and owner identity.

Primary diagnostic is available sampled reads/all scheduled executed observation
reads, with source/receipt age distributions and consecutive unavailable samples.
First-to-last unavailable sample spans are observed spans, not exact continuous
outage durations. Replay window is all6seconds after explicit preparation.
No availability acceptance threshold is invented. Reference SYS-PERF-00220Hz is
unchanged;10Hz is a comparison condition, not a new accepted Reference profile.
An ideal single-clock constant-delay example is illustrative only; actual CARLA
simulation/source time and monotonic wall time must remain distinct.

## Two longer finite live probes

Run prepared-01 then prepared-02 on separately started isolated Town04_Opt/Epic
servers. Use only consumed development site38/first person fixture, frame5 RGB,
actual100Hz10ms simulation steps, no actuation RPC, independent50Hz observational
consumer. Prepare on the inference owner before enabling the camera. Each run
contains1200..1204 contiguous ticks ending frame modulo5=4,240 acquisitions,
then200ms delivery without ticks and300ms stopped-source/camera silence.
This increases the preceding180..184-tick probe; it is not long-term qualification.

Store immutable raw callback bytes through a bounded8-slot diagnostic writer to
local NVMe uncompressed files. Inference mailbox remains latest1. This writer's
I/O is part of the measured environment. Queue overflow fails the run and performs
emergency synchronous storage of that image; no silent raw loss. Close is bounded
and retryable after timeout. Compress/hash only after measurement. Keep every raw,
including failures, and add every newly seen RGB hash to prior5761 future exclusions.
Do not run cache migration or heavy archive work during UE startup/measurement.

Integrity gates: original identity/timestamps, all scheduled frame5 images and
calls accounted, independent actual ticks/consumer during inference, zero recorder
loss/overflow/error, preparation READY with same owner, fresh consumed results in
each of the six complete200-tick segments, and at least5 invalid observation reads
more than100ms after sensor stop while source time is frozen. These are component
integration checks; availability is diagnostic and live wall20Hz remains unaccepted.

Primary live availability window: camera enabled through last actual tick completion.
Also report enabled through sensor stop, including the200ms delivery tail. No
post-first-publication trimming. Disclose source rate, camera wall rate and50Hz
consumer separately. One formal attempt per condition; failures remain FAIL.
Any recovery needs a separately declared protocol before execution.

Keep startup180s/client900s/shutdown30s, server exit130 and forced-stop FAIL. Preserve
full preparation and sensor calls, server/client logs, source archive and all raw
bytes. Required before commit: Python regression and three CTest configurations,
fresh archived-source trace replay, every live raw hash and exact old/native input
comparison, parent-freeze integrity and complete future-exclusion union.
