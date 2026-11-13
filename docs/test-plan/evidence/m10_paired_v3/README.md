# M10 paired V3: finite diagnostic concurrency passes

2026-11-13. Original5ms native physics, separate2560×1536 rendering and D-FINE-M960
inference ran concurrently. The frozen auditor reports `PASS_DIAGNOSTIC_CASE_ONLY`.
This is a2s low-speed Host case, not full M10, perception-control or quality acceptance.

- 400 original intervals,238 normal, zero protective intervals/faults/deadline misses.
  Model time2.0s took2.005677 wall seconds. Original HV30ms and all native guards
  remain; observed maximum normal HV dependency age was24.199ms.
- 88 same-frame scenes exported;59 verified renderer ticks;65 real raw images,
  57 mapped to physical scenes;32 numerical calls,31 beginning during physics.
- Scene acquisition→result age: minimum87.395ms, median183.999ms, p95211.043ms,
  maximum213.668ms. These are diagnostic ages, not100ms freshness acceptance.
- Original acquisition brackets, cloned actor/camera transforms, raw hashes and
  decoded tensors rejoin. All32 calls produced zero selected detections.
- 2010 original native service rows and all400 receipts replay exactly.
- Renderer/owner exit130 in3.169s/2.220s; no forced stop; original INI restored.

All images and results remain unavailable for control: complete wheel/bone and
material state is missing, and the original100ms gate is unchanged. Native
perception acceptance is zero. No holdout data was accessed. All65 images are
retained losslessly and excluded from future independent evaluation; cumulative
exclusion is9100. This is not an independent detector-quality result.

Visual inspection found an additional placement bug after the run: the walker
was requested from an immediate post-spawn ego transform that was still identity.
Its actual source pose was near(8,3,1.099), while the ego was near(220.410,-5.086).
The clone correctly reproduced that source pose, but the intended nearby walker
was absent from the forward view. The parked car was behind the camera. V4 uses
an actual pre-bind SDK snapshot to place the walker; V3 images and verdict remain
unchanged. Concurrency/provenance passing does not establish scene completeness.

The1337-file prospective source freeze passes40 focused archive checks and453
workspace tests. Startup checking now uses bounded fresh SDK subprocesses inside
the original180s readiness horizon. Tests verify that a hung probe is killed and
reaped and cannot prevent a fresh probe from succeeding or extend the total bound.

Original-profile cache preparation separately observed initial frame6 after
37.870s, waited until distance-field/shader workers were gone plus10s, and reached
frame27731 with no camera/vehicle/walker actors. Its preparation took493.621s and
server shutdown2.370s. `cache-preparation-01.tar.gz` retains this phase. Earlier
cold-build crashes and the persistent-client monitor failure remain in V1/V2;
this does not establish an engine crash fix.
