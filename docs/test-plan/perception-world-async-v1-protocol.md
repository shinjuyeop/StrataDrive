# Observed asynchronous CARLA world, fixed10ms V1

Declared before live execution. Preserve the554-file native-memory parent byte for
byte. Add an opt-in server-asynchronous path and a matched synchronous baseline.
This is finite Host observational integration, not vehicle/ROS control integration,
quality acceptance, runtime promotion, wall20Hz qualification or Jetson optimization.
D-FINE-M960 FP32, class thresholds,3840×2304 BGRA, Epic, sharedRTX3090, development
site38/first person, exact native resize and explicit same-owner3-call preparation
stay fixed. Do not inspect old holdout/GT or score new accuracy.

Both modes use fixed_delta_seconds=.01, substepping, rendered camera every actual
frame divisible by5 under the pinned external Sensor.cpp flags. Sensor cadence is
simulation time; server asynchronous mode does not promise real-time1× execution.
The active state owner is world.on_tick in both modes. Async mode calls no explicit
world.tick; sync mode has one explicit tick requester. Initial setup is paused
synchronous mode; preparation finishes before subscription/camera activation.
The first actually delivered state snapshot starts the session. A camera arriving
earlier is rejected and retained. Never relabel cached setup state as newly received.

Clock identity is actual episode/frame/elapsed/delta. Forward gaps are counted,
never interpolated; a camera requires its own observed cached snapshot. Consistent
old/duplicate snapshots are ignored and cannot renew state age. Conflicting time,
wrong episode, invalid10ms delta or clock regression latches failure. Cache128 actual
snapshots. Source+100ms AND original offer-receipt+100ms remain exclusive; neither is
renewed by completion. Add state-observation silence100ms: invalidate current/pending
and active generation, return unavailable; new actual state permits new packets but
cannot revive old results. This recovery grants no driving authority. State/result/
read-time are sampled under one short mailbox lock. Active1/pendinglatest1/current1.
All state and liveness/decision traces are bounded4096; overflow fails evidence.

Run sync-01, async-01, async-02 sequentially on independent isolated servers2300–2302.
Each primary window begins at camera enable (including first-output wait), spans
500..504 actual source frame numbers ending modulo4, and has a30s wall bound after
mode switch. The main thread stops the camera after observed target passage. Sensor
callback delivery may omit late boundary images: explicitly list scheduled missing,
extra boundary and received counts, never claim these losses are successes or invent
images. Preserve every received raw frame including rejected/tail/failure images.
After camera stop, continue actual world state and50Hz observational reads for300ms;
old results must expire. Diagnostic recorder capacity240 immutable references gives
headroom; normal measurement has no disk image writes. Overflow fails and spills
through the prior recorder. Maximum diagnostic raw RAM8,493,465,600B, not deployment RAM.

PASS requires lifecycle cleanup, matching readback, complete received input/call/raw
accounting, no true clock or backend fault, no recorder/trace overflow, independent
state and observer progress during inference, some fresh consumption in each of five
100-source-frame segments, original deadlines on every publication/read, and no
result100ms after camera stop. Explicit stale-state invalidations can reduce
availability; trace them rather than misclassify them as successful outputs. Report
actual state/camera/observer wall rates, simulation/wall factor, gaps, intervals,
callback time, receipt delay, all-window availability, original ages and invalid spans.
No availability threshold is selected after results. Short paired runs do not prove
long-term smoothness or causality; renderer/copy/GPU load and OS cache remain factors.

Lifecycle budgets180s startup/900s client/30s shutdown remain; exit130 required,
forced kill is FAIL. One attempt per condition. Only if no client was launched,
allow one declared startup recovery with original report hash and new output name;
no client/camera retry, no source/deadline changes within this revision. Retain failures.

Archive the additive frozen sources and all raw payloads, verify full BGRA/RGB and
exact native/Pillow inputs from fresh extracted sources, and union every actualRGB
with the6713 prior exclusions. Git LFS payloads may remain canonical pointers in the
worktree when disk is scarce; auditors must resolve and hash their actual local cache
objects, not count pointer hashes as raw validation. Run Python regression and frozen
C++ boundary checks with no live server. No board optimization or model change.
