# M4 pending-command settlement follow-up

Baseline29b8221, clean tree, Ubuntu Host. Fixed before execution on2026-10-20.
M4 NOT CLOSED, original timing/native/SDK TSan failures retained. No M5 adapter,
kernel replacement or MCU port. Deployment remains Host PC + one Jetson containing
multiple vECUs; generic Jetson kernel/PREEMPT_RT comparison is Target work, NOT RUN.

1. Preserve the original966 test names/results. Capture both existing logical
   delays (Rear19.8ms, Front/Rear12ms) before editing control behavior. Add a
   failing normal-pending regression using real owners (Front0.2ms/Rear19.6ms
   result delivery delay), and a port-level pending/expiry boundary regression.
2. Candidate policy: one in-flight normal batch; defer the due allocation while
   its result is pending, without preparing another command or advancing the
   nominal release. Retry with fresh inputs after completion. Poll allocator
   authority and30ms execution-gap checks while waiting. Original transport20ms,
   actual command expiry, session/arm, parent/lease and CAN/P05 remain unchanged.
   Actual command expiry still protects even if a transport response is pending.
3. Correct diagnostic exit status without short-circuiting planned trials. Test
   actual child process exit code for all-pass, individual failure/timeout,
   missing required output/execution and TSan warning. Mocked runners test
   bookkeeping only, not vehicle concurrency or timing acceptance.
4. Full normal/ASan·UBSan regression and existing durable rejoin CLI, then changed
   boundaries and related actual wall tests under TSan (`setarch x86_64 -R`).
   Preserve failed attempts; new run directories after changes.
5. Freeze source before **normal20 + TSan20** alternating independent processes,
   original1.8s native normal test, OTHER/0, inherited affinity, no load/guards,
   full transport trace from first run. Original assertions, required output,
   full trace, actual settings and no sanitizer warning are mandatory. No retries.
6. Then unchanged **48-run** guard protocol: normal/ASan, CPUs0/1, OTHER/FIFO,
   quiet or7ms/10ms contention, normal/Drive pause/Monitor6ms overrun,3 repeats,
   2.54s,2ms opportunities/4ms completion deadline,1211 slots/owner, trace OFF.
   No compile or other test during either cohort. Keep every failure in denominator.
7. Attempt read-only kernel/perf/tool availability checks with exact commands.
   Do not infer OS cause or close old native TSan from new logical tests/PASS runs.
   Examine available middleware synchronization evidence without suppressions;
   unsupported instrumented SDK/Rust/Target work remains NOT RUN.

Each evidence directory records source commit/digest, environment, commands and
raw output. Logical clock, native diagnostic, sanitizer and guard timing are
separate verdicts. No prior timing result is attributed to the new source.
