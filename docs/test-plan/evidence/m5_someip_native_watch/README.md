# SOME/IP Host native execution watch

2026-10-21. **Native execution watch is connected and exercised; overall operational
qualification is incomplete.** Keep Host functional SIL conditional adoption.
Normal FIFO quiet/loaded normal operation passed3/3 each on the precisely bounded
profile below. This supports that measured normal-operation scope, not acceptance
of every fault/recovery condition. Final functional Normal12/13, ASan13/13,
TSan10/13; adapted48 is31PASS/17FAIL. No result was repaired by repeating until PASS. Total new SDK runner requests153
(raw113 exit0/40 exit1, including1 intrusive GDB run and1 weak-oracle baseline PASS);
the6 existing-native impact runs are a separate denominator.
M4 whole NOT CLOSED, Rear network/Jetson/real IO/whole system NOT RUN; DDS historical
FAIL/OPEN and CLOSED control gate are unchanged.

Started clean at HEAD=origin/main `767d3347780a505f1eaf521ebdb0a4b1ea76d74a`;
fetched again before committing, still0/0. Implementation
`2dbc5e034b34187b2cd7229f1c454228870db846`. [Provenance](provenance.json) verifies
all final measured C++ hashes against the committed source and records all three
binary hashes. Final Python-only early-failure bookkeeping is tested separately and
re-adjudicated offline; raw exits are immutable. No user changes were present or removed.

## Connected path and ownership

| Process/thread | Actual work | Guard and surviving protection |
| --- | --- | --- |
| Central main, CPU1 | Central/Rear/Drive/BMS/Power/CentralIngress serially, actual SessionCoordinator/RunLeaseIssuer/allocation and local CAN/P05 owners | One actual group7 completion, not six fabricated completions; independent monitor9 CPU0 closes atomic gates/requests protection |
| Front main, CPU2 | FrontZone/Steering/Brake serially, existing participant/RunLeaseGate/owner/Leaf logic | One actual group0 completion; its monitor9 CPU0 survives main-owner pause |
| Persistent SIL physical main, CPU3 | Existing steering/brake/drive/energy models, sensor/actuation IO | group8 and its own monitor9; observes actual ECU monitor completion slots and applies existing output override |
| Central SDK/dispatch/sender, CPU4; Front equivalents, CPU5 | vSomeIP callbacks validate binding/codec and bounded enqueue; sender calls SDK | OTHER/0; no controller/session state mutation and no direct SDK send from the control-owner probe path |
| Plant auxiliary/background, CPU6 | Sanitizer/runtime auxiliary threads inherited at creation | OTHER/0; physical main explicitly moves toCPU3 |

The eight real Release ACKs (mask255), original RunLease issuance, actual arm and
EpochStore rejoin remain mandatory. Central allocation→owner-wire/TCP→Front→existing
CAN/P05→Leaf→persistent SIL model→Actual/health→Central validators remains intact.
There is no grant file, fake ACK, refreshed expiry or transport-derived authority.

`interfaces/someip/{owner_transport,wire_binding}.hpp` holds reusable transport;
`simulation/runtime/native_execution_watch.hpp` bridges the existing
TaskSchedule/DeadlineMonitor/M4ExecutionWatch. Scenarios, injection and verdicts stay
under tests. Original2ms opportunities/4ms deadline refer to execution service,
not the controllers'10/20ms periods. Owner/model service uses absolute200/500µs
wakes. A late wake completes its originally requested slot; skipped slots remain
missing. Requests beyond the finite observation window cannot complete its last slot.

A200ms stopped Front owner produces no fabricated local ACK. Its live monitor can
close gates and request protection; the physical process supplies the actual output
override while the owner cannot run. On whole-ECU SIGKILL its monitor also dies:
surviving peer authority/feedback checks and persistent physical observer protect.
On monitor6ms delay the physical observer detects the monitor's original deadline.
No same-Epoch recovery reopens a veto. Actual new-Epoch INIT/Release/credit/arm is required.

The shared Linux lock-free atomic mmap is execution/output-driver observation only,
not another session or command transport. It is a Host-specific, same-binary ABI;
TSan cannot establish synchronization across separate processes. SIGKILL of the
physical process itself has no surviving modeled physical actuator: real hardware
watchdog/driver coverage remains outside this SIL scope.

## Execution profile and costs

Pinned unchanged COVESA vSomeIP3.7.6,
`4187431d2815bd351845a09d01aa85b2a3163cab`; Boost1.85.0; GCC11.4, C++20 adapter /
C++17 common runtime. Exact compile/link/library hashes are in provenance.
Project+vSomeIP+Boost filesystem/atomic built perNormal, ASan/UBSan, TSan profile;
system libc/libstdc++ remain uninstrumented. Per-process maps prove loaded libraries.
TSan uses process-local `setarch x86_64 -R`, no suppression or kernel setting change.

Host: Ubuntu22.04.5, Linux6.8.0-138 PREEMPT_DYNAMIC, i7-11700 (8physical/16SMT),
allowedCPU0–15. Original user uid1000 has actual RLIMIT_RTPRIO20/20. FIFO main
priorities Central11, Front18, physical19, monitors20. Actual TIDs, affinity,
policy and priority are recorded perprocess/generation; SDK threads remainOTHER0.
No administrator command was needed. SMT siblings8–15 are not isolated and no hard
real-time platform guarantee is asserted. Separating SDK work consumes additional
cores compared with the former two-CPU owner+SDK placement.

Owner observation2540ms,100ms lead,20ms tail,1211 owner+1211 monitor slots perECU;
physical observation continues through peer shutdown/rejoin within18s. This is the
finite Host diagnostic execution path, not a continuously operating production
scheduler. Session setup and teardown are separately bounded. Active guarded work
includes owner ingress/egress and cleanup service; SDK stop/join and evidence flush
follow protection/quiescence. No sleep/timeout extension is counted as SDK success.

Loaded condition: two checked OTHER/0 processes onCPU1/2,7ms busy per10ms; alive/CPU
consumption/affinity/actual policy recorded. No build or broad filesystem search ran
concurrently with final measurement. Bounded transport/event records65536, model
steps40000, model events/trace4000; output flush after quiescence. No hot-loop per-
message flush. Overflow of observation storage fails, never silently truncates PASS.

Transport remains netns/veth10.88.0.1/30↔10.88.0.2/30, separate routing managers and
mount-isolated `/tmp`/`/dev/shm`, TCP30501–30504 plus SD UDP30490. Per-case packet,
socket and namespace evidence proves IP traffic. Ordinary/authority RX/TX capacity8,
SDK8192 bytes, original timestamp/20ms envelope/internal expiry/RunLease source-age/
Epoch/token/operation/CRC/route/clock checks are unchanged.

## Corrections and retained failures

1. **Actual overflow.** Pause ordinary consumption, observe exactly8 queued, inject
   one explicit ninth test message. Reject that message, latch overflow and record
   original8 FIFO tokens/drained tokens, first rejection time/token, no overwrite.
   Local Front protection must precede Central protection. Normal producer limit
   remains8; the ninth is a finite test hook. Eight admitted diagnostic requests are
   accounted as rejection/expiry, plus exactly1 RX rejection. Full-close separately
   verifies a full queue, bounded ongoing peer traffic, SDK stop/join and restart.
   The original weak-oracle PASS (overflow=false) remains raw PASS but is excluded
   from overflow acceptance; strict offline assertion fails it.
2. **Shared physical override priority.** First native functional Normal12/13 failed
   Central-stop at brake.target-output: successful step531341511047599, new nominal
   input531341511268054, failed call531341511550569 (dt0.502970ms, IOerrors0), after
   physical override531341504536485. A still-live Front nominal target was applied
   to an already protected brake model. Pre-fix unit fails. Give the already selected
   override priority over same-Epoch nominal actuation; only genuine higher release
   recovers. This is distinct from the historic61ms failure.
3. **Original requested completion identity.** Preserve overdue target instead of
   crediting the current job. Also reject finite-window final-slot alias, seen in
   old TSan traces. Existing test names/assertions retained; specific regressions added.
4. **TSan/FIFO placement.** Original same-CPU owner+SDK final TSan0/13 has no race
   warnings, but about1.2s owner thread CPU stalls. One intrusive GDB run shows owner
   in libtsan MetaMap/MutexPreLock read-lock sched_yield, sender in that same metadata
   write-lock path, dispatcher waiting application mutex. Split OTHER SDK CPU4/5
   comparison removes the observed stall/4ms misses; normal still fails on Rear
   result rejection (token270/Commands, result before original deadline), so is FAIL.
   This supports a scheduler/instrumentation interaction, not a general false-positive
   exemption or proof of SDK safety. No mutex annotation/SDK redesign was applied.
5. **Runner/lifecycle defects.** Freeze only normal scenario inputs during overflow;
   continue real core monitoring/credit. Keep Central receiving until protected Front
   SDK stop/join returns to avoid a non-injected85-byte Feedback reset. Preserve that
   earlier TSan FAIL. Final runner rejects normal protection before declared injection
   immediately, including during the1200ms wait. Previously it timed out and could
   fill bounded trace storage after the primary fault. All those raw failures remain.

## Results and denominators

[Prospective protocol](protocol.md), per-attempt plans and raw process exit codes
precede execution. All final C++ comparisons use the committed implementation.
[All cohorts](results-summary.json), [48 table](timing-results.csv),
[first-fault/session time axis](timeline.csv), [detailed audit](audit.json) and
[final stricter offline adjudication](adjudication.json) are machine readable.

| Cohort | Result | Interpretation |
| --- | --- | --- |
| StageA actual overflow, corrected Normal/ASan/TSan |1/1 each | Ninth rejection/latch/FIFO preservation/local protection, API stop/join and Epoch2 recovery; earlier weak oracle/timeout/reset failures retained |
| First native OTHER/FIFO smoke |OTHER0/1, FIFO1/1 | OTHER missing slots are actual FAIL; neither is a campaign substitute |
| First native functional Normal |12/13 | Revealed physical override bug |
| After physical fix, same-CPU SDK cohorts |Normal13/13, ASan13/13, TSan0/13 | TSan stall failures retained |
| GDB / split-placement normal comparison |1 intrusive /0/1 | Excluded GDB; placement comparison control FAIL, no observed guard miss |
| Final split-placement functional |Normal12/13, ASan13/13, TSan10/13 | Full39 requests; no sanitizer diagnostics or unexpected SDK errors; not39PASS |
| Final controlled61ms model-delay |Normal1/1, ASan1/1 | Expected failure evidence oracle, raw plant exit1; not normal operation PASS |
| Final adapted timing |31/48 | New adapter, not prior scheduler; table below |
| Existing native impact |6/6 | Normal/ASan×FIFO normal/Drive200ms pause/monitor6ms delay |
| Full common-code CTest |Normal978/978, ASan978/978 | Original973 plus5 new tests; earlier976/977 cohorts also retained |
| Python working/fresh checkout without build/ |48/48 each |19SOME/IP+7DDS lifecycle+22middleware bookkeeping; standalone4274 binding assertions; not SDK execution |

Final functional Normal overflow fails before injection (4batches, local protection,
no native miss); actual overflow is NOT EXERCISED in that specific run. ASan overflow
passes completely. Final TSan overflow directly proves8+1 rejection/latch/local
protection/orderly stop, then Epoch2 normal control fails after49batches; whole case
remains FAIL. TSan delay/monitor-overrun fail before injection. No missing fault
coverage is claimed. Close-full, restart-live, Central-stop, command/result/status/
lease loss and owner-pause pass in all three final profiles. Invalid-message and
normal paths also pass in those three cohorts. The final all-case gate remains open.

| Build/policy | Normal quiet | Normal loaded | Owner200ms pause | Monitor6ms delay |
| --- | --- | --- | --- | --- |
| Normal OTHER |1/3 |0/3 |2/3 |0/3 |
| Normal FIFO |3/3 |3/3 |3/3 |2/3 |
| ASan OTHER |2/3 |0/3 |1/3 |2/3 |
| ASan FIFO |3/3 |3/3 |3/3 |3/3 |

FIFO23/24 vsOTHER8/24. Normal FIFO monitor failure occurred before injection
(normal local protection after4batches), not an observed missed injected-monitor
detection. Some OTHER failures are original4ms deadline misses; other fault cases
never reached their prerequisite. No permission-related NOT RUN: actual RT setup
succeeded. ASan timings are instrumentation observations, not Normal performance.

Normal FIFO six normal runs:510 Front Commands accepted results, original sent→
Central acceptance0.177779–1.007075ms. These are correlated result delivery bounds
in those runs, not a general loss/recovery guarantee. Physical CSV and actual CAN
feedback remain separate from result admission. The final Normal armed interval
shows angle0.0539–0.1rad, pressure0–200000Pa and torque0–60Nm (audit ranges). Functional native fault examples:
Normal owner pause detects16.614µs after deadline, physical override58.141µs later;
monitor delay detects263.808µs after deadline, override12.919µs later. Exact monotonic
points and ASan/TSan bounds are in audit/timeline. Surviving protection never turns
an ordinary normal deadline/command failure into PASS.

## Model observations and unresolved causes

Controlled61ms pause identifies **energy.step**: Normal dt61.631411ms,
ASan61.552165ms. It retains original input=last-success time, previous/current call,
component last success/return, Epoch1, selected protection, original output sources/
modes, step gaps and nonblocking model-IO busy/error records. Both have IOerrors0;
busy is observed contention, not proof of the historic cause. The controlled failure
returns raw plant1; other owners protect. No normal-result laundering occurs.
**OPEN-SOMEIP-HOST-01 remains OPEN:** a similar injected symptom does not establish
the earlier61ms incident's initiating cause.

**OPEN-SOMEIP-NATIVE-01:** occasional normal local-protection/management failure
before intended injection, or after Epoch2 restart, with no native4ms miss. The
preserved traces show Central LocalProtection/Management, and one separate placement
case shows Rear rejected Commands before its20ms deadline. Existing Leaf logs identify original command expiry as the immediate trigger in
Normal overflow, TSan delay/monitor-overrun and the TSan overflow Epoch2 failure
([expiry extraction](expiry-failures.json)). For example Normal Steering expires
at532747859008926 against its unchanged532747858840282 deadline, then protection
is selected532747859014544. Its previous accepted input is532747835633794.
The FIFO48 monitor precondition failure selects local protection before the later
Leaf expiry, so that earliest gateway cause remains unresolved. Model errors and
sanitizer warnings are absent in those runs. Do not label this an SDK fault or relax
original authority/feedback windows. Next targeted work: correlate allocation release/defer, permission source/expiry
and gateway first-fault reason with the already preserved Leaf expiry; test one
phase-specific scheduling hypothesis while retaining original10/20ms periods and
all source/deadline values, then fix only the demonstrated defect.
Do not repeat the entire campaign just to obtain allPASS.

**OPEN-SOMEIP-NATIVE-02:** OTHER normal/load timing remains unsuitable under the
measured profile; missed original opportunities are retained. Split-CPU FIFO normal
operation has limited positive evidence, but all-fault/TSan qualification is not met.
A continuously operating guard, physical-process/hardware failure handling, real
Host IO, Rear network and Jetson are outside this finite SIL evidence.

No new Daybreak/content access restriction occurred. No SDK patches, warnings
suppression, privileged setting changes, external issues/messages or acceptance
criteria relaxation were made. Previous201 attempts188/13, final TSan12/13 plus
follow-up3/3, original DDS42/23/19 and all historical OPEN records are unchanged.

## Reproduction and raw preservation

```sh
python3 tests/integration/someip/build.py normal
python3 tests/integration/someip/build.py asan
python3 tests/integration/someip/build.py tsan
python3 tests/integration/someip/front_run.py build/new-native-normal --profile normal --native-watch --fifo --cases normal overflow close-full restart-live central-stop owner-pause monitor-overrun
python3 tests/integration/someip/front_run.py build/new-native-tsan --profile tsan --fixed-layout --native-watch --fifo --cases normal overflow owner-pause monitor-overrun
python3 tests/integration/someip/native_campaign.py build/new-native48
PYTHONPATH=tests/unit python3 -m unittest someip_pilot_test dds_lifecycle_test middleware_probe_test -v
```

Commands are recipes, not authorization to repeat a failed campaign without a
specific correction/hypothesis. Existing full regression uses build/m4-readiness and
build/m1-angle-sanitized, cmake build then CTest; exact commands/logs/JUnit preserved.
Build/runtime use the same exclusive build/.m4-exclusive.lock; Python tests and
standalone binding checks do not require build/ or an installed SDK. Runtime setup
uses existing unprivileged user/net/mount namespaces; original user RT limits persist.

Four raw archives avoid oversized single artifacts. [Archive hashes](archives.json)
and [per-file SHA256 manifest](raw-manifest.json) preserve every collected raw exit,
stdout/stderr, plans, CSV, maps, per-thread policies, socket/IP capture, failures,
timeouts, GDB stacks and regression logs. No forced cleanup is orderly-stop success.
Recompute the cohort summary without running a process under test:

```sh
python3 docs/test-plan/evidence/m5_someip_native_watch/analyze.py \
  --archives docs/test-plan/evidence/m5_someip_native_watch/raw-investigation.tar.gz \
  docs/test-plan/evidence/m5_someip_native_watch/raw-qualified.tar.gz \
  docs/test-plan/evidence/m5_someip_native_watch/raw-timing.tar.gz \
  --output /tmp/stratadrive-native-offline
```

`normal_timing_ok` in raw native subresults describes guard slots only; it is not
an overall normal-control verdict. Use top-level immutable exit/pass and the explicit
fault-injection prerequisite. Final offline89-case re-adjudication revokes0PASS and
preserves every raw FAIL. Full old native40 is NOT RUN again; the impact-based6 and
actual new48 are distinct evidence, never substituted for one another.
