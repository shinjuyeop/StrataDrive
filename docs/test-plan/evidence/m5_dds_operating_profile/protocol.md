# Prospective Host DDS operating-profile audit — 2026-10-21

Base/origin `c10688d`, initially clean tree. Prior 42 attempts (23 PASS/19 FAIL),
OTHER/FIFO/native exceptions and DDS control gate CLOSED remain unchanged.
Prior Daybreak stop is inherited; stop any newly restricted operation, retain
time/request/notice/completed work, and do not reroute it. No root changes.

## Candidate fixed before execution

Host transport candidate: Central CPU1, Zone CPU2 (distinct physical cores on
i7-11700; siblings9/10 are not isolated), OTHER/0 including inherited DDS threads,
20ms publication, minimal observer. Domain37, isolated user/net/mount namespaces,
veth10.88.0.1/30–10.88.0.2/30, UDP/unicast discovery, volatile reliable KEEP_ALL,
resources8/1/8, blocking0, application queues8, take budget8, poll200us unchanged.
This tests a bounded correlated request/result lane; not the complete vECU
deployment, a controller, an RT guarantee or all message families' QoS.

20ms corresponds to Central allocation; the diagnostic echo is not the actual
Zone's task or CAN/Leaf service. Retain source, exclusive20ms envelope, inner30ms
expiry, Epoch/token/order/route gates. No re-timestamp, renewed deadline or ACK
fabrication. Minimum observation retains packet timestamps in fixed storage,
flushes before delete, reads public QoS/status and samples all live threads at
readiness and before close; no allocator unwind/private object inspection in
normal minimal mode. Full retains per-message flush/finest/allocator snapshots.

## Fixed comparisons

Normal unsanitized only: 3 repetitions of each row, interleaved by repetition.
All use unchanged60-message all-accepted-and-echoed oracle and 1.6s active window.

| Row | Central/Zone CPU | Period | Observer | Comparison |
| --- | --- | --- | --- | --- |
| A | 1/1 | 5ms | full | legacy stress anchor with new public observations |
| B | 1/1 | 5ms | minimal | A→B observation level only |
| C | 1/2 | 5ms | minimal | B→C process placement only |
| D | 1/2 | 20ms | minimal | C→D publication period only; candidate |

Report accepted/sent, original deadline misses, RTT max/p95, reader rejected/lost,
write failures/duration, applied QoS/thread policy/mask, close progress and exits.
Small trials locate effects, not statistical assurance or prior-failure closure.
Do not claim that a combined observer comparison isolates each observer cost.

One candidate run each per Normal/ASan+UBSan/TSan: normal (normal row D reused,
no extra normal repetition), delayed take400ms, peer-stop, peer-kill, raw restart,
coordinated restart, partial reply-writer deletion, callback-delete, and
close-saturated. Saturated close keeps Central publishing while Zone stops taking
after20 messages, awaits public sample-rejected evidence then closes. A negative
SDK outcome remains FAIL. Coordinated restart uses existing sender quiesce/drain;
its grace is not a fix for raw or saturated close. Old42 must fail after new43.
Sanitizer overflow must reject stale commands at original deadlines; availability
loss is diagnostic only, never a physical protection ACK.

The confirmed partial-path defect (one `deleted` flag disables reading after only
writer deletion) is fixed with separate entity state. One pre-fix normal partial
run with new instrumentation and one post-fix normal run directly check continued
ingress, independently of whether the old process happened to close successfully.

Every runtime attempt: 35s outer cap; readiness12s, transition10s, process wait15s
unchanged. Campaign cap600s/512MiB. Build all profiles before execution; exclusive
`build/.m4-exclusive.lock`; no concurrent build/timing. No retry without new evidence.
Plan/results with NOT RUN placeholders, exact sources/build/library hashes and
commands precede execution. Any nonzero unexpected exit, timeout, missing result,
QoS/readback failure or unexplained sanitizer warning is FAIL. Sanitizer functional
and memory/race verdicts are separate; no sanitizer timing acceptance.

Deterministic runner unit regression: launch two real waiting child processes,
force readiness timeout through actual wait_for deadline, execute inside's real
finally kill/wait/save path, require FAIL/nonzero, both exits and no live children.
This verifies cleanup bookkeeping, not resolution of SDK close timeout.
Run affected Python runner regressions and C/C++ diagnostic builds only; production
source is unchanged, so no unrelated973/native40/timing48 rerun.
