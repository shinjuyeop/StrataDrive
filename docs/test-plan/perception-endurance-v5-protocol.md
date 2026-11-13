# M10 bounded endurance V5

V4's first case failed after87 original intervals. No raw frame was lost and
both servers exited normally, but unchanged HV30ms still expired during INIT;
the incomplete Actual export then failed closed. The other30s cases and300s
case were NOT_RUN. This is not evidence that NVMe or CPU affinity solved the
timing failure. All16 V4 raw frames remain retained and excluded.

V5 retains V1/V3 acceptance and V4 NVMe storage/complete-core assignment. Its
only scheduling change is the explicitly frozen host-v2 profile: the owned
physics server starts with Linux SCHED_RR priority8. Native FIFO18 remains
unchanged on its distinct core; renderer, observer and unrelated processes are
unchanged. No kernel setting or other user's process is modified. The runner
verifies RR8 before native START; resource samples retain actual scheduler,
priority and affinity. Round-robin sharing is used among inherited owner
threads. Resource/finite-run/shutdown bounds remain enforced by the separate
ordinary-priority runner. Original model5ms, HV30ms, ECU periods,2/4ms native
checks, timestamp identity and perception100ms remain unchanged.

Declare three30s cases, then conditionally300s, with the same V4 stop-on-first-
failure rule, immutable failed evidence, complete raw retention and independent
archive checks. Any change after a failure requires another prospective freeze.
Shader shutdown is still under diagnosis, not claimed repaired. No visual
fidelity, detector-quality, holdout or Jetson deployment promotion is allowed.
