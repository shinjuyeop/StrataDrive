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

Python tests cover fresh-checkout directory creation, oracle/failure bookkeeping
and timeout cleanup; they are not SDK runtime tests. Whole 973/native40/timing48
are out of scope unless product code changes require them.
