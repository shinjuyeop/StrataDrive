# M10 admission window V2 — audit the actual receipt schema

The original[V1](evidence/m10_admission_window_v1/README.md)30s physical audit passed:
6000 receipts,5830 normal,170 INIT,0 protection, no native first fault and exact replay.
The prospective sequence nevertheless stopped because its new audit required server
configuration fields on receipts that do not contain them. Preserve that FAIL, its
frozen reproduction and the two NOT RUN cases. Corrected post-run audit is separate
evidence and must not overwrite or relabel the original sequence disposition.

Correct only the auditor: require structured_state=true,wall_preview_reserve_ns=2000000,
model_step_ns=5000000 and whole-interval-v1 on BOTH original binding and final_server.
For every original receipt, require its existing5ms/profile fields and original authority
through the full5ms plus2ms extra reserve. Missing/changed server readbacks, short
expiry, old actuator input or incomplete receipt counts must still fail. Exercise the
actual split server-response/receipt shape, including independent start/end mutations,
and reproduce all6000 retained original receipts with the correction before freezing.

No runtime C++ or model change. Reuse module
`29df236c28bdc92c29784f0ab7e087f3f18c8bf0187c84aa24a957b6d7e45e98`, original native/replay
binaries, unchanged physics/final-admission bodies and V1's27 admission regressions.
Verify all119 build inputs and18 generated files and the reused module hash. The V1
empty-renderer validation and actual30s startup/shutdown validate this identical
runtime; no new empty-server validation is claimed. Every new launcher invocation
still performs fresh asset preparation before authentication and fresh PID creation.

Repeat the full prospective30s→30s→300s sequence after the correction. All other
[V1 conditions](perception-admission-window-v1-protocol.md) remain: stop first failure;
same host CPU/FIFO placement,2K/D-FINE-M960, camera10Hz,renderer20Hz/MaxFPS60,
owner serial GC/61.1s, original5ms physics/HV30ms/native2/4ms,70% bounded boost,
600s separate preparation,300s preparation freshness,180s physical startup,30s
shutdown, original resource reserves, no independent build/tests/compression during
measurement, complete raw/archive/frozen reproduction and six-file/100% restoration.
The root helper, PID binding, owner-exit and1800s lease limit are unchanged.

Future quality exclusions continue from20840 including all284 V1 images. Original
physical pass is a finite observation, not5min/GC/thermal stability. Native perception
acceptance, full scene, independent quality, each Jetson deployment and M10 remain OPEN.
