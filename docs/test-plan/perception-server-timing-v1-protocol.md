# M10 server timing V1

Prospective declaration after startup correction6603ae7, before instrumentation
build/live. TC-PER-094: opt-in bounded game-thread journals in isolated CARLA and
UE Launch builds. Record original CLOCK_MONOTONIC brackets and separate thread CPU
durations around engine tick, frame-end sync, tick-rate wait, deferred tick, CARLA
pre/post tick, sensor dispatch and PumpWall gaps. Keep original readback brackets.
No control/clock/renderer configuration changes; output only on orderly exit.
Capacity8192 per component; overflow/incomplete traces invalidate attribution.

TC-PER-095: freeze source/build/runtime inputs after focused tests and isolated
build. One bounded `server-timing-01` live trial: existing Town03_Opt,150 passive
pre-camera ticks,200 physical interval target,2K2560×1536/FOV90/Epic/D-FINE-M960,
10ms physical step/320 substeps/HV30ms, all original authority and100ms perception
deadlines, same96-frame recorder. Startup180s/client900s/native18s/shutdown30s.
One attempt, no retry or unmeasured change to force success. All raw retained and
added to future quality exclusion (prior8977); no holdout/Required/Target claim.

Separate observation completeness, stage attribution, valid shadow delivery and
driving acceptance. Correlation with a render span alone is not proof of the wait
cause; a directly bracketed engine synchronization call can identify that call's
duration, but not an unobserved GPU/driver internal cause. CPU duration is not
wall time. Preserve incomplete/failed outcomes. Restore both UE executable and
CARLA module byte-for-byte, plus original settings; no external source edits.

After this declared run, propose any scheduling/renderer change separately based
on measured evidence. Existing protection deadlines must remain effective.
