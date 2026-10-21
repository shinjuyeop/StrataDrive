# SOME/IP pilot prospective protocol

Recorded before the first SDK runtime execution, 2026-10-21 KST.
Base: 017e3b0471c2fa344a1a34049b7a73d2a5cf5b54; clean main = fetched origin/main.
No DDS historical result or gate is replaced.

## Fixed scope and configuration

- vSomeIP 3.7.6, commit 4187431d2815bd351845a09d01aa85b2a3163cab;
  Boost 1.85.0 archive SHA256 7009fe1faa1697476bdc7027703a2badb84e849b7b0baad5086b087b971f8617.
- Separate normal, ASan/UBSan, TSan SDK, Boost filesystem and project builds.
  C++20 SDK/pilot, project libraries retain C++17. System libc/libstdc++ remain
  uninstrumented. No suppression, no default SDK replacement.
- Central CPU1 / Front CPU2, SCHED_OTHER/0, 20 ms command publication.
  Host i7-11700 SMT siblings 9/10 remain available: no isolation claim.
- Two netns, veth 10.88.0.1/30 ↔ 10.88.0.2/30, TCP port 30501;
  SD multicast 239.255.1.1:30490. Distinct network/routing/application IDs
  and isolated per-node /tmp and /dev/shm. Packet capture + socket/thread snapshots.
- App receive capacity eight, payload <=512 owner-wire bytes, SDK external/local
  send queue 8192 bytes, reliable payload limit 512. These byte limits are not
  DDS RELIABLE/KEEP_ALL resource semantics. TCP has head-of-line blocking; deadline
  checks, bounded app queues and independent local protection remain necessary.
- Readiness requires discovered service and received request/response; no sleep
  establishes readiness. Readiness timeout 3 s, response observation timeout 1 s
  (does NOT extend 20 ms acceptance deadline), case supervisor timeout 15 s.
- Trusted launcher fixture grant is a separate local file/CLI Epoch. It initializes
  only Front, Steering and Brake component objects, never global Release ACKs or
  RunLease. No normal vehicle RUNNING/arm authority is inferred from SOME/IP.
  Sensor inputs are explicit constant-zero SIL fixture observations, not Host IO.
  Existing 10 ms Leaf runnable and <=10 ms gateway poll retained.

## Planned cases / oracle

Normal: three runs in normal build, one in each sanitizer build. Eight publication
cycles at 20 ms; every Vehicle parent and ScopedCommands result must match original
Epoch/token/operation, be received within original min(deadline,sent+20 ms), and
report two real accepted CAN/P05 frames for Commands. At least one canonical
Leaf Actual response; no normal command loss/expiry permitted.

One run per build for each other case: late peer (500 ms intentional start delay,
then same normal oracle); readiness timeout (no peer, API stop returns); invalid
(old Epoch, duplicate, corrupt CRC, wrong route/clock domain, then expired command;
each rejected, no duplicate CAN application, expiry selects protection); delay
(30 ms receive consumption delay, original command rejected/protected); overflow
(pause consumption, send nine requests, capacity8 never grows, ninth latches
protection; drained old requests cannot regain authority); close-busy (Front API
stop/join while Central still sends; normal shutdown distinct from forced cleanup);
restart (stop old Front, launch explicit newer Epoch, replay old bytes rejected,
fresh requests accepted; no automatic old-session resurrection).

Normal performance and sanitizer memory/race verdicts are separate. Sanitizer
slowness never authorizes late commands. Missing results, unexpected timeout,
nonzero child exit, sanitizer diagnostics => runner exit1 with raw evidence.
Expected injected rejections/peer absence are separately named, not normal loss.
Supervisor kill is cleanup only, never normal stop. No retry-to-pass: further runs
require a documented code/config correction or a new bounded hypothesis. Build
errors are retained separately from SDK runtime case counts.

## Amendment A, after attempt-01 (before attempt-02)

First normal SDK execution FAILED: the two sequential parent/command round trips
were ~10.9 ms each; the shared original envelope expired at Central (21.75 ms).
vSomeIP's documented default nPDU retention is 5 ms per direction (debounce 2 ms).
Hypothesis: default packet aggregation consumes the command/result budget.
Set the officially supported four `npdu-default-timings` values to zero; keep
original timestamps, queue sizes, CPUs and oracle unchanged. Run three normal
comparisons once, then the fixed remaining cases. This is a configuration fix,
not evidence of universal SOME/IP deadline guarantees.

Independent harness correction: tcpdump's setgroups privilege drop failed in the
unprivileged user namespace. Replace capture with a bounded AF_PACKET PCAP writer
inside that same caller-owned netns; do not change host privileges/security.
The configured client IDs also require matching diagnosis 0x13 (SDK emitted
`Invalid client id` with default 0x01). Keep distinct node IDs 0x1311/0x1322.
Initial SDK configure failed with ENABLE_MULTIPLE_ROUTING_MANAGERS=ON because its
example target depends on absent vsomeip3-cfg. OFF is sufficient with independent
mount namespaces, one routing manager per node. Original build log retained.

## Amendment B, after attempt-02 (before subsequent builds/runs)

Attempt-02's ten raw runner results are functional PASS, but their SDK error logs
make them insufficient for adoption. The SDK source `is_valid_client_id` requires
different diagnosis addresses for remote hosts. Correct Front to diagnosis0x14 /
client0x1422 while Central stays0x13 /0x1311. Add SDK `[error]` to runner failure
criteria (previous oracle omission), with no suppression. Retain raw PASS rows and
report this audit qualification separately. Repeat the fixed ten normal cases once
and eight cases for each fully instrumented build.

Strengthen two bookkeeping assertions before those runs: record protection calls
before orderly-stop protection, so teardown cannot satisfy the delay/overflow
oracle; restart replays the exact preserved epoch42.packet bytes and writes
separate per-Epoch transaction logs. Previous restart generated a fresh old-Epoch
message, which only covered old-Epoch rejection, not unchanged-byte replay.

The final candidate also runs the existing ControlAllocation for the eight normal
cycles instead of constructing allocated actuator fields directly. The explicit
SIL inputs are adapted from its existing unit fixture (including Rear readiness,
management and permission); they are NOT observed full-system readiness or remote
Release ACKs. The received Front Actual is independently validated, not fed into
an end-to-end vehicle loop in this pilot. Minimum20ms allocator interval and30ms
execution-gap guard remain unchanged. All three final builds use this same source.

## Amendment C, after tsan-final (before tsan-fixed-layout)

Normal-final10/10 and ASan-final8/8 passed. TSan-final8/8 FAILED before a usable
pilot result: unexpected memory mapping at randomized PIE addresses, and two
children required supervisor cleanup; one child terminated with SIGSEGV before
summary. This is NOT race-free execution.
Existing repository DDS TSan runners already use process-local `setarch x86_64 -R`;
the [GCC instrumentation manual](https://gcc.gnu.org/onlinedocs/gcc/Instrumentation-Options.html)
documents that launch facility. Hypothesis: fixed per-process virtual layout lets
the existing GCC11 TSan runtime initialize. Change only this launch option, keep
the same binary/SDK/config/oracle; run the eight fixed cases once. No global ASLR,
kernel/security/sudoers changes, no non-PIE rebuild, no suppression or retry loop.
An attempted read of /proc/sys/vm/mmap_rnd_bits was denied; it is not retried or
required for this process-local comparison. No Daybreak/model-content notice occurred.

## Amendment D, after tsan-fixed-layout (before bounded-busy comparisons)

Fixed layout produced real SDK execution: seven PASS and one close-busy FAIL,
zero TSan diagnostics. Both close-busy DDS-unrelated vSomeIP stop APIs returned;
failure was SDK8192-byte queue drops: the diagnostic sender continued blind1ms
replays after peer disconnect. This sender violated the intended bounded pending
transaction contract (not an SDK race). Repair only that branch: cap pending at8,
correlate rejection responses, after20ms missing response close the send lane and
record each expected injected-peer-loss expiry. Original command bytes/deadline
remain unchanged. The busy marker now requires a received duplicate rejection,
so the supervisor cannot close Front before traffic actually reaches it.

Run close-busy once per normal/ASan/TSan build (TSan fixed layout); no unrelated
repeat. Require <=8 pending, sent=rejected+explicit fault expiries, both stop/join
return while Central is alive, no SDK `[error]` or sanitizer diagnostic. The old
failed case remains FAIL. This is a sender fix, not a queue increase or relaxed
SDK-error oracle. Normal transaction loss/expiry still fails unconditionally.

## Final receive-boundary review

Code review found that status checked outer CRC/route/domain and CAN source age,
but did not explicitly require the expected application Epoch, and replies did
not explicitly check their method ID. Add both checks. No wire/config/timing
change. Run one normal case per build to exercise the edited receive paths;
these three focused regressions do not replace the earlier fixed campaign.

## Surviving-peer rejoin coverage

The original restart case rebuilt both Central and Front. Add `restart-live` to
cover the requested surviving-peer condition explicitly: Central remains in the
same SDK application/process, Front42 is killed after8 successful cycles, Central
must observe availability loss, a separate local grant authorizes Epoch43,
Front43 is discovered and bidirectionally ready, old42 bytes are rejected and
eight new cycles pass. No global Release ACK or automatic authority renewal.
Run this new case once per build, plus one normal per build after extracting the
shared eight-cycle helper. Timeout/oracle/CPU/config/expiry stay unchanged.

Python tests cover fresh-checkout directory creation, oracle/failure bookkeeping
and timeout cleanup; they are not SDK runtime tests. Whole 973/native40/timing48
are out of scope unless product code changes require them.
