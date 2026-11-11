# Matched2560×1536 and3840×2304 comparison V1

User requested the2K comparison. Preserve all601 parent source bytes. Source4K is
3840×2304; source2K is2560×1536, both5:3 horizontalFOV90/Epic/postprocess with identical
D-FINE-M960 FP32 graph/hash and thresholds [.60,.40,.60,.50,.50,.60]. No960 input,
model/precision/training/board optimization or old holdout changes. Fixed2K typed
packet/result/owner versions retain the original state/deadline algorithms; dimensions,
source candidate and decoder canonical scale4 are explicit. Native2K resize must be
bit-exact to Pillow11.3 bilinear including tensor arithmetic and orig_target_sizes.
Prior sources and model/raw evidence remain immutable. No default promotion.

Live order: source-4k-01, source-2k-01, source-2k-02, each on a new isolated server.
Use the same blocking-query instrumented module, largest-request targets2/1 and
original main viewport; no small-viewport flags or deferred readback. Use normal
independent bytes materialization in ALL arms, matching the faster prior4K baseline;
no prefault pool. Record all callback and backend stages and capture-to-result wall
latency. Keep actual on_tick state snapshots, asynchronous fixed10ms world, camera
frame%5, original source+100ms AND offer-receipt+100ms exclusive, state-age100ms,
active1/pendinglatest1/current1, prepared same-owner3 calls and finite240 raw refs.
Primary500..504 source frames plus300ms camera-silence tail; all cold/late, raw,
missed/boundary frames, overwrite and unavailable samples stay in denominators.
Report Mean/P95/P99/Max, camera/world/observer rates, simulation/wall, valid reads.
At least20 actual camera Hz in BOTH2K repeats is an observed-rate result, not long-term
or full-stack qualification. Do not change physics or timestamps to pass a deadline.

After live trials restore the original CARLA module. Quality collection uses the
unchanged original native camera capture/annotation with two independent new servers:
quality-4k-01(scale6) then quality-2k-01(scale4), all81 existing DEVELOPMENT cases
at site38, all3 weather/near/medium/far/occluded/mixed classes/riders. No new road,
holdout access or threshold selection. Same actor plan, camera pose, FOV/aspect,
Epic/postprocess,40 settling ticks and capture tick5. RGB+instance sensors are paired;
GT is evaluation-only, never supplied to model or live owner. Collection is synchronous
and has separate timing; its duration is not a20Hz result. Native rendering/animation
states are not pixel-identical across independent runs. Keep earlier quality failures.

Derive each native instance mask under existing angular support/IoU.5 criteria and
score all81 rows with the same frozen model/vector; keep full300 outputs, exact inputs
and errors. Report P/R, per-class, far/occluded/small, person/rider, all FP/FN and visibility
coverage. Describe any additional miss or precision/recall regression against the matched
4K arm; no trade-off is silently accepted. All2K model feeds must match Pillow exactly.
This is already-consumed development comparison, not independent accuracy qualification.

Lifecycle remains180s startup/900s client/30s shutdown, exit130. One attempt per arm;
only one explicitly declared startup-only recovery before any client if needed. No client
retry or post-result tuning; preserve all failures. Keep each planned quality RGB/instance
pair and every live received raw frame, source/SDK/module hashes and snapshots. Diagnostic
warmup/settle sensor packets are not part of the81-case quality selection, as in its original
protocol. Future exclusion unions all new RGB hashes with8113 prior exclusions. Compress
and archive after measured live intervals only; no heavy test/archive work during UE runs.
Original module and GameUserSettings bytes must be restored at the end. Each archive is
fully verified and remotely uploaded before deleting duplicate temporary payloads.

RTX3090/i7-11700 Host observations are not Jetson deployment, ROS integration, vehicle
control or M10 closure. Real-time1× remains a goal, not intentional slow simulation.
