# M10 Host profiling V3: physical-owner scheduling follow-up

Retain V1 A/B and V2 C/D as failures. D's raw NVMe recording reduces image-pipeline
CPU from A's1.580 to0.897 average logical-core equivalents during the physical
span, while retaining303 camera frames and296 calls. Normal control lasts16.965
model seconds, then original HV/dependency protection still fails. Around that
failure CPU samples are84–86C and the package thermal counter does not increase;
thermal throttling alone does not explain all remaining failures.

Declare one new E 30s diagnostic case, not a replacement for D. Keep D's shared
Host V1 CPU roles, parked preparation, renderer MaxFPS60,2K/Epic/10Hz camera,
raw BGRA spool, OpenCV4/resize4, passive ORT and blocking CUDA host wait. Use Host
V2's existing explicit owner SCHED_RR8 instead of CFS. Native FIFO18 stays higher;
only the new owned physical server inherits RR8. Verify the real scheduling
policy/priority before native execution. Do not change unrelated processes,
host kernel policy, clocks, power limits, model steps, release grids or deadlines.

Earlier V5 RR8 failed under a different recording/startup workload; it remains a
failed experiment. This comparison tests whether priority helps after removing
measured recording/preparation costs. All original5ms/30ms/2ms/4ms/100ms guards,
lossless byte checks, raw retention/exclusion, frozen audits and source timestamps
remain. Sample the same process/thread/GPU telemetry. Any failure is retained;
no normal-endurance or conditional300s acceptance follows from this one trial.
Restore original shared module, DXC and INI after the trial.
