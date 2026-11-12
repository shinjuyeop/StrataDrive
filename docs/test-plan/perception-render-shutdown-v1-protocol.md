# M10 bounded renderer shutdown diagnosis V1

Declared before one new `shutdown-01` trial. Preserve renderer replay V2's original
FAIL_SERVER_SHUTDOWN. Same original runtime binaries, Town03_Opt/Epic,2K camera,
retained source receipts,8 warmup+12 mapped-pose ticks,32-packet recorder bound and
no inference/native publication/concurrent physics. Retain every raw callback.

TC-PER-107: add an opt-in diagnostic only after SIGINT. Set PR_SET_PTRACER on the
new owned renderer child; never change host ptrace_scope or attach to an unrelated
process. Preserve process identity through the live Popen child. If still running
at10s after SIGINT, retain bounded /proc thread state/maps and invoke the pinned
GDB for at most8s, up to16 frames per thread and8MiB output. No memory/environment
dump or debugger during normal rendering. Record debugger failure or timeout;
detach/resume if needed. The original30s shutdown wall budget includes debugger
time. An overrun remains forced termination/failure, not a successful exit.

TC-PER-108: freeze sources, debugger and original runtime before launch; reproduce
the4 shutdown tests plus existing25 renderer/scene tests from the archive. The
real subprocess test must prove permitted attach/detach without changing host
Yama policy. Launch once, retaining source, lifecycle, original logs/images and
any post-exit-request thread evidence. If no hang occurs, report that fact without
claiming to explain the earlier hang. No retry under this protocol.

New raw images are development diagnostics and join future quality exclusions.
No holdout access,20Hz claim, complete scene admission or Jetson optimization.
Any fix requires a separately declared source change and confirmation experiment.
