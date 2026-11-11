# Finite Host memory recorder after observed streaming overflow

Declared before new memory runs, after native-startup V1's two original attempts
and separately bounded recovery finished. Keep all547 parent source bytes and
all original outcomes: prepared-01 startup FAIL/no client; prepared-02 complete
240-image PASS; prepared-01-recovery FAIL at1161 ticks/232 images after the8-slot
NVMe writer overflowed on frame1300. All232 original images survived, including
the overflow image, with no write errors. Final counters are231 sensor calls,
226 publications,4 late,1 obsolete,1 cancelled pending. The original client did
not retain its per-completion decision trace on this early failure; do not invent
it or claim independent decision-cause replay for that run. Stop V1 recovery here.

The new revision changes only the finite diagnostic recorder and failure evidence:
retain up to240 immutable packet references in RAM during measurement, then hash
and compress after sensor/state/consumer stop. Normal measured disk-frame count
must be0. Maximum raw retention is8,493,465,600B (240×3840×2304×4). This is a Host
probe resource bound, not a production/Jetson memory requirement. Production
inference remains active1/pending1/current1; no model or preprocessing changes.
Unexpected extra images fail the run and spill through the old bounded recorder,
including its emergency synchronous storage; do not drop unseen raw bytes.
Close is bounded, and post-measurement iteration releases retained frames. The
client now retains worker status/decision trace after close even on early failure.

Perform memory-01 and memory-02, each on a new isolated server with unchanged
site38/first person, Epic, shared RTX3090, native4K, D-FINE-M960, class thresholds,
explicit same-owner3-call preparation and exclusive source AND receipt100ms.
Keep1200..1204 ticks/240 scheduled images, six200-tick fresh-consumption segments,
independent actual tick/50Hz observation, all sample/age metrics,200ms delivery and
300ms stopped-source silence, startup180s/client900s/shutdown30s, exit130 and
forced-stop FAIL. Camera/window/clock definitions are unchanged. Recorder workloads
differ from V1, so do not interpret changes as preparation-only or rate-only effects.

One formal attempt per condition. If and only if an attempt fails before client
launch, allow one additional startup-only recovery for that condition under a new
output name ending -startup-recovery, after the original process exits and ports
are free. Record the original report hash in a declaration before recovery. No
client/camera failure retries, no second recovery, no prefetch or deadline change.
All failures remain failures; OS cache is uncontrolled and cold startup is not
qualified. This bound does not permit rerunning the failed V1 condition.

Freeze this additive revision before execution. Preserve all old472 raw and new
raw, all calls/counters, lifecycle logs and source versions. Recompute complete
future exclusion from5761 prior hashes. Fresh archived-source audit must distinguish
V1 failure preservation, V1 success and the two memory-condition results; compare
all observed raw BGRA/RGB hashes and exact native/Pillow input tensors. Run new
recorder tests plus full Python regression and unchanged C++ boundary checks.
No GT/old holdout use, runtime promotion, quality acceptance, control/ROS connection,
board optimization or wall20Hz/long-term acceptance is introduced.
