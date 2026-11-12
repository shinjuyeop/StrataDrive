# M10 quiescent renderer lifecycle V2

Declared after `shutdown-01` completed its19-image diagnostic and exited130 in
1.467300121s without debugger attachment. That run did not reproduce the earlier
hang and does not establish its cause or resolution. Preserve all earlier trials.

TC-PER-109: the renderer is a dedicated owned process that will exit after capture.
Do not restore its original asynchronous WorldSettings during raw-image storage.
Keep its existing synchronous50ms configuration; do not call ApplySettings to
"pause" it, because pinned LibCarla World.cpp:56–83 can tick inside ApplySettings.
Read the actual world/frame/source before and after storing all packets, and fail
if the world or its clock advanced. Restore the persistent settings file as before.
No change to physical owner, ECU deadlines, capture tick count or image admission.
Persist renderer instance/world/camera/calibration identity explicitly in the report.

TC-PER-110: one `shutdown-02` confirmation after new source freeze and32 focused
tests (4 shutdown,3 lifecycle,25 provenance/scene). Same20 renderer ticks and all
raw retention as the preceding run, plus the opt-in quiescent cleanup. Keep the
10s conditional debugger/8s trace/30s total shutdown bounds unchanged. If clean,
accept only this finite renderer lifecycle and recorded hold. If a hang occurs,
retain it and the bounded thread evidence; no retry under this protocol.

The prior intermittent shutdown failure remains unexplained unless direct thread
evidence supports a cause. This change removes unrequested renderer advancement
during storage by design; it is not a claimed deadlock repair. Full scene export,
body/camera asset mapping and concurrent owner/render stall tests remain OPEN.
All new images join future quality exclusions; no holdout/20Hz/Target claim.
