# Remaining causal and acceptance questions

Source: `97afb35`. The pending-allocation code defect is corrected by
[ADR-0059](../../../adr/ADR-0059-pending-command-allocation-settlement.md).
That finding does not identify the cause of the untraced `d7115ff` native TSan
CommandDelivery failure.

## Native diagnostic

The predeclared alternating Normal20 + TSan20 cohort used the original 1.8s
wall-clock workload, OTHER/0, inherited CPUs0–15, guards OFF, full transport
trace from the first run. All40 executed and passed; the corrected runner
returned exit0. No retries or discarded trials. Required artifacts/settings
and bounded trace coverage passed, with no TSan warnings.

Command enqueue→Central result reception maximum was0.442994ms for Normal
(1968 command transactions) and0.446838ms for TSan (1960 transactions).
These are observed maxima of this cohort, not worst-case bounds. The per-run
`transactions.csv` preserves root source, CAN payload source, inner expiry,
sent/deadline, Zone receive/dispatch, Leaf handling/output publication and result
arrival. An output publication is not a physical response or remote ACK.

The original untraced failure remains **OPEN-M4-TSAN-01**. Neither these PASS
results nor logical result-delay injection proves TSan overhead caused it.
On recurrence, retain full trace and the first failing original identity, then
classify queue/dispatch/response lateness versus an already expired applied
command, without extending timeouts. A trace buffer overflow invalidates coverage.

## Kernel observability

Read-only attempts and actual exit codes are in `environment/attempts.json`:

| Attempt | Actual result |
| --- | --- |
| `cat /proc/sys/kernel/perf_event_paranoid` | `4` |
| `head -n 5 /sys/kernel/tracing/available_events` | exit1, permission denied |
| `perf stat -e task-clock -- true` | exit255, access denied |
| `sudo -n test -r /sys/kernel/tracing/trace` | exit1, password required |
| `ulimit -r` |20; FIFO setting is independently verified in each timing run |

No sysctl, scheduler budget, kernel or permission was changed. A privileged
capture on the same Host must correlate timer expiry/wakeup, `sched_switch`,
IRQ/preemption and owner TID execution intervals on one monotonic timebase.
Requested wake and measured owner body alone cannot distinguish timer delay,
run-queue delay, interruption and application work. FIFO opportunity misses are
not attributed to the OS without this evidence. `trace-cmd` is absent; tracefs
access or an equivalent approved perf/ftrace collection facility is needed.
Kernel capture remains **NOT RUN**, and **OPEN-M4-TIM-01** remains open.

The new48-run cohort is42 PASS/6 FAIL, FIFO24/24. All6 failures are OTHER loaded
normal runs, three per build; all settings/load/grid/buffer controls passed.
[First-failure extraction](timing48/failures.csv) identifies Steering(owner2)
completion opportunities with release118–210ms/deadline122–214ms, start/end0.
All6 failed before the first normal arm (`active=0`). The preceding recorded body
was0.001046–0.003566ms; the next observed requested-wake delay was2.717912–3.782913ms.
Those measurements locate an unexecuted opportunity but cannot decompose the
unobserved timer/scheduler interval. First detection and physical override are
both recorded in the same timebase. Protection success is not a normal-run PASS.
The prior `1989477` FIFO Front/Rear slot281 failure is preserved separately;
its absence in this cohort does not close its cause.

## Middleware

The nine preserved SDK source fingerprints match9/9 (`environment/sdk-source-audit.json`).
The original [stack/source analysis](../m4_contract_review/middleware/analysis.md)
therefore remains applicable. Wrapper TSan4 FAIL and SDK-rebuilt DDS2 FAIL are
preserved; no new SDK runtime cohort was executed.

Cyclone DDS11.0.1's GCC selector uses `ddsrt/atomics/gcc.h`. Vendor volatile
load/store helpers explicitly exclude ThreadSanitizer; x86 fence/compiler
barriers do not provide complete sanitizer-visible synchronization. The
SDK-owned bucket lookup versus GC free stack still has two unresolved
interpretations: a reclamation/lifetime defect, or unobserved synchronization.
The stack does not establish a wrapper queue race. A vendor-supported
TSan-aware configuration or a reviewed equivalent memory-order implementation,
minimal concurrent index/GC reproducer and original-versus-instrumented comparison
are needed. Merely strengthening atomics or suppressing the warning would not
resolve the original contract.

Zenoh-C1.10.1's binary provenance/debug information and matching instrumented
Rust std/Tokio/Mio/Zenoh dependencies are needed to examine the async handoff.
`cargo` and `rustc` are absent. Full Rust TSan is **NOT RUN**. Existing wrapper
locking/copying and an SDK instrumentation gap are not proof of lifetime safety.
**OPEN-M4-MWTSAN-01** remains open, with no suppression or false-positive ruling.

## Acceptance scope

Host functional component PASS, boundary concurrency checks and Host timing
are separate. A Host IO/FIFO-only technical acceptance proposal still requires
causal examination of the preserved FIFO misses, a fixed-cohort remeasurement,
and an explicit review of supported profiles and SDK exceptions. No current
support profile or exit criterion is silently narrowed.

Deployment remains Host PC + one Jetson with multiple vECUs. Generic Jetson
kernel versus PREEMPT_RT is a planned Target performance comparison using the
same workload, placement, original deadlines and retained failures; **NOT RUN**.
There is no kernel replacement, MCU port or M5 adapter in this change.
Learner review and whole-system32 requirements/29 tests remain pending/NOT RUN.
