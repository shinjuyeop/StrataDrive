# M4 진단·시험 프로토콜 이력

이 문서는 당시 결정과 검토를 보존한 기록이다. 현재 상태는 [프로젝트 상태](../project-status.md), 현재 계약은 [문서 안내](../README.md)를 따른다. 과거의 “다음 작업/미구현”은 현재 지시가 아니다.

- [M4 remote-contract review and open-failure diagnostics](#m4_contract_review_protocol)
- [M4 Host kernel observation — bounded OFF/ON pair](#m4_kernel_capture)
- [M4 middleware candidate probe protocol](#m4_middleware_probe_protocol)
- [M4 pending-command settlement follow-up](#m4_settlement_protocol)

<a id="m4_contract_review_protocol"></a>

## M4 remote-contract review and open-failure diagnostics

Fixed before the cohorts run (2026-10-20). Baseline4a399af; previous cohorts and
M4 NOT CLOSED remain. No M5 controller adapter. System32 requirements/29 TC,
Target and learner acceptance are unchanged.

1. Each of the three remote defects first gets a failing regression against its
   original implementation, then focused correction tests. Preserve original948
   test names/assertions. The correction boundary has963 tests (15 new).
2. Full normal and ASan/UBSan run in fresh directories. A failure is retained,
   diagnosed and any follow-up execution uses a separate path/source identity.
   Changed-boundary TSan covers remote/codec/AsyncOwner/AsyncZone tests, process-local
   `setarch x86_64 -R`; no system ASLR change or warning suppression.
3. Native CommandDelivery diagnostic adds opt-in, per-owner bounded trace storage
   (no shared logger/no hot allocation), capturing original source/inner expiry,
   first enqueue/envelope deadline, dispatch, Leaf receive/completion, Zone result
   enqueue and Central result arrival. Overflow invalidates trace coverage.
   Trace changes get logical and full regressions; instrumentation cost is explicit.
4. **20 normal +20 TSan independent processes**, paired alternating order, each the
   existing `M4AsyncWall.IndependentOwnersRunActualNormalPath` test:1.8s, inherited
   allowed CPU set, OTHER/0, no injected load, no execution guard enabled (same
   original test). First run onward `STRATADRIVE_M4_RESULTS` and transport trace ON.
   PASS requires original assertions, no sanitizer diagnostics and complete trace.
   No retries, dropped failures or pooled denominator with historical results.
   Source fingerprint/environment/settings/JUnit/physical/events/transport retained.
   Compare source→enqueue→receive→dispatch→completion→receipt, not just duration.
   This is diagnostic wall timing, not the 2ms/4ms guard acceptance cohort.
5. After source changes, run the existing **48-run** native protocol unchanged in
   a separate new directory using `check_m4_faults.py --run-timing`: normal/ASan,
   CPU0/1, OTHER/FIFO,7ms/10ms load,normal/Drive-stop/Monitor-overrun,3 repeats,
   2.54s and original guard/protection limits. Transport trace is OFF for this
   cohort; do not attribute prior603fe24/77d411c results to the new source.
   No builds or other tests while either timing cohort executes.
6. Middleware analysis starts from preserved SDK stacks and exact version source.
   Distinguish wrapper synchronization, SDK lifetime/reclamation and TSan visibility.
   Do not suppress/close a warning from lack of reproduction or a source hypothesis.
   No new SDK runtime cohort is required unless a distinct testable hypothesis and
   fixed protocol justify it; missing Rust/kernel permissions are recorded precisely.

Host IO/FIFO technical acceptance is a proposal only; unsupported timing, SDK and
native TSan conditions remain open until their explicit acceptance decisions.

<a id="m4_contract_review_protocol-follow-up-logical-causal-probe-after-the-fixed40-runs"></a>

### Follow-up logical causal probe (after the fixed40 runs)

The fixed40 native runs atf895dc6 all passed; do not extend/retry that denominator.
Before executing a new probe, fix two **logical** conditions: no added delay and
12ms delivery delay on Command TxResult only for both Zones from elapsed1000ms;
all requests/feedback/Leaf execution unchanged. Run existing real Network/owners,
original1.8s duration and original deadlines. Record full trace. Inspect whether
next20ms allocation encounters a still-pending sequential Front→Rear batch while
its individual20ms result deadline and inner command expiry are still live. This
is a deliberate contract-pressure scenario, not a replay of the untraced original
native scheduling incident and not performance evidence. Add the resulting
protection/latch behavior to logical regression without changing timeouts.

The12ms hypothesis probe selected protection earlier through the previous Rear
command expiry, not the hypothesized busy-submit path. Keep its failed hypothesis
JUnit and actual trace. Preserve that observed expiry path as a logical regression.
One distinct second logical condition is fixed before execution: **Rear Command
TxResult only19.8ms delay**, Front results unchanged, start1000ms. This tests the
narrow next-allocation/pending-result boundary while fresh Rear command application
already occurred. It does not modify any runtime budget or extend the native40 cohort.

<a id="m4_kernel_capture"></a>

## M4 Host kernel observation — bounded OFF/ON pair

<a id="m4_kernel_capture-fixed-follow-up-campaign-after-1a4afe5"></a>

### Fixed follow-up campaign (after `1a4afe5`)

For a separately planned privileged campaign, the command is:

```bash
cd /d/shin/StrataDrive
sudo /usr/bin/timeout --signal=TERM --kill-after=20s 360s \
  /usr/bin/python3 tools/m4_kernel_campaign.py \
  "$PWD/build/m4-kernel-fixed-$(date +%Y%m%d-%H%M%S)" \
  --user-parent "$$"
```

The original shell must remain alive and actually have RTPRIO20/20. Its UID,
capabilities, ancestry, start time, limits, groups and affinity are verified from
`/proc`/`prlimit`, not trusted from a supplied file. Only the forked worker child
gets those verified20/20 limits before `setgroups/setgid/setuid`; neither the root
collector nor global configuration is changed. Worker and actual runtime/load
credentials and limits are retained. No password, sudoers edit or privileged broker.

The prospective plan is **OTHER loaded OFF→ON once, then normal-build FIFO
monitor-overrun OFF→ON ten times** (11 pairs/22 workloads). Initial OTHER analysis
runs unprivileged between pairs: it must be VALID before FIFO starts. A valid
workload FAIL does not prevent FIFO. An invalid initial trace leaves FIFO NOT RUN.
Every subsequent FIFO attempt remains in the denominator, including failures;
no replacement runs. Cleanup conflict stops remaining work, which remains NOT RUN.

Overall limit360s (external kill grace20s), disk guard3GiB with512MiB reserved
headroom, original worker12s/trace watchdog15s/file32MiB/trace128MiB/buffer64MiB
caps apply. The fixed program has no arbitrary command argument. Storage is checked
between trials and every200ms during execution; the reserved space covers the
fixed worker output files and final trace export. Workspace
`build/.m4-exclusive.lock` also excludes agent build/sanitizer jobs. Do not run
unrelated builds/tests/tracers concurrently.

`campaign.json` lists the plan and every attempt. Exit2 means incomplete/invalid
collection or operational failure; exit1 means at least one worker failed;
exit0 means collection workers succeeded, **not timing acceptance**. The console
also reports status, stop reason, INVALID/NOT RUN counts and available analysis
errors; an already-failed initial validation is not labelled only "pending".
Except for the
initial OTHER validation, analysis follows collection as the original user:
`python3 tools/m4_kernel_analysis.py build/<campaign>/<pair>`.
Trace loss, missing alignment/identity, changed source or cleanup errors remain
INVALID even if a workload reports PASS. [Preparation/evidence](../test-plan/evidence/m4_kernel_campaign/README.md).
For the entire fixed plan, run the unprivileged
`tools/m4_kernel_campaign_analysis.py CAPTURE NEW_OUTPUT` after collection.
It preserves inputs, retains NOT RUN attempts, and separates deadlines preceding
the observed Monitor injection from later misses; later does not automatically
mean intentional.

The following single-pair command and original results are retained as history;
that older CLI does not preserve the invoking user's RT limit across sudo.

Status: **corrected fixed campaign213425: all11 pairs VALID; OTHER2 FAIL, FIFO20 PASS**.
The [completed campaign](../test-plan/evidence/m4_kernel_campaign/completed_213425/README.md)
verified the new buffer allocation, user RT boundary, actual FIFO placement and
cleanup. FIFO pre-injection misses were0; historical FIFO cause remains OPEN.
No additional sudo run is needed to analyze these saved results.
The20261020-212418 fixed campaign executed OTHER OFF/ON only (FAIL180/320 misses).
It verified user/capabilities/20/20 restoration and both markers/cleanup, but
CPU9 lost1963 events and FIFO10 pairs were NOT RUN. Background buffers are now
enlarged within the original total cap; the separate213425 campaign subsequently
validated11 ON windows without event loss. [Originals, correction and112 Python checks](../test-plan/evidence/m4_kernel_campaign/README.md).
The user executed the collector on kernel6.8.0-138-generic. The earlier185513 valid
capture has729726 events,0 drops and11951 linked executed jobs. Its first missed
CPU1 opportunity is dominated by runnable CPU waiting; see the
[timeline, CSV and plot](../test-plan/evidence/m4_kernel_valid/README.md).
The original lossy trace and145058 unparsed syscall lines remain in
[earlier evidence](../test-plan/evidence/m4_kernel_capture_followup/README.md).
Two subsequent attempts failed while writing the end marker. The agent's
noninteractive `sudo -n` still requires a password. M4 remains **NOT CLOSED**, previous timing/native/SDK TSan
failures remain OPEN, and Target/system/learner states are unchanged.

<a id="m4_kernel_capture-execute-from-the-original-users-terminal"></a>

### Execute from the original user's terminal

No rebuild or kernel change is required for the current unchanged M4 binary.
Do not run builds, other tests or another tracer concurrently. The output must
be new and directly under the existing user-owned `build/` directory.

```bash
cd /d/shin/StrataDrive
sudo /usr/bin/python3 tools/m4_kernel_capture.py capture \
  "$PWD/build/m4-kernel-other-v2-$(date +%Y%m%d-%H%M%S)" \
  --case other-loaded --profile normal
```

This executes exactly **OFF once → ON once**, no retries. A workload FAIL does
not suppress the ON run. Exit0 means both workloads and collection/analysis
passed; **exit1 means a workload failed and its evidence was retained** (expected
for this OTHER loaded reproducer); exit2 means conflict, incomplete collection,
invalid/missing trace evidence or an operational error. Read `collection.json`
and `analysis.json`, rather than interpreting exit1 as failed cleanup.

An inventory-only command is also available. It changes no trace settings:

```bash
sudo /usr/bin/python3 tools/m4_kernel_capture.py probe \
  "$PWD/build/m4-kernel-probe-$(date +%Y%m%d-%H%M%S)"
```

After obtaining a loss-free OTHER pair, the preserved FIFO condition is selected
as below. **Do not run it yet with the observed sudo RT limit0/0**: the original
unprivileged baseline had20/20, while both actual sudo workers inherited0/0.
OTHER/0 is unaffected; FIFO would fail setup. Restoring the original user's
verified RT budget across sudo is a prerequisite, not permission to increase it.
The collector currently records but does not restore that limit.

```bash
sudo /usr/bin/python3 tools/m4_kernel_capture.py capture \
  "$PWD/build/m4-kernel-fifo-$(date +%Y%m%d-%H%M%S)" \
  --case fifo-monitor-overrun --profile normal
```

This is the same normal-build/FIFO/quiet/Monitor6ms-at1200ms condition as the
`1989477` FIFO failure; the unexpected Front/Rear miss at662ms preceded its
intended injection. A single pair cannot prove that intermittent failure absent.
`--profile sanitized` is optional for a **separate** cohort, not a replacement
for the initial normal-build condition. Future repetitions/order changes must be
declared before execution and keep every attempt.

<a id="m4_kernel_capture-fixed-workload-and-privilege-boundary"></a>

### Fixed workload and privilege boundary

The unprivileged worker invokes the existing
`tests/integration/runtime/check_m4_faults.py::timing_run`, preserving its oracle:

| Case | Runtime | Placement / scheduling | Load |
| --- | --- | --- | --- |
| `other-loaded` | normal,2540ms, guards ON, transport trace OFF | Front/Rear/Physical/Monitor CPU0; five Leaf and Central CPU1; OTHER/0 | original separate user process, CPU1 OTHER,7ms busy/10ms |
| `fifo-monitor-overrun` | same duration/guards, Monitor6ms injection at1200ms | same CPUs; original priorities18,18,10,10,10,9,10,11,19,20 | quiet |

The original2ms opportunities,4ms completion deadline,1211 slots per owner,
source/command expiry, session/arm and protection conditions do not change.
The launcher stays OTHER/0. `SUDO_UID` identifies the original user; the worker
drops UID/GID/supplementary groups before any application execution and requires
zero effective capabilities. Its original inherited CPU affinity is restored
before the existing runner applies owner-specific placement. RT limits are
recorded, not raised. FIFO setup failure is not PASS.

The root collector and independent cleanup watchdog run on a spare allowed CPU,
away from0/1. They do not promote or execute the vehicle workload as root.
Both modes retain worker identity, actual owner TIDs/policy/affinity, source
commit/fingerprint before/after, actual binary SHA256, CLI, load controls and
the existing physical/event/execution CSVs.

<a id="m4_kernel_capture-event-discovery-clock-and-bounded-cleanup"></a>

### Event discovery, clock and bounded cleanup

`inventory.json` records actual available, selected and missing events. Required:
`timer:hrtimer_init/start/cancel/expire_entry/expire_exit`,
`sched:sched_wakeup/sched_switch`, `irq:irq_handler_entry/exit`.
Available migration/new-task wakeup, softirq and `irq_vectors:*_entry/*_exit` are
also selected. Compact-v2 omits duplicate `sched_waking`, low-resolution timers
and nanosleep syscall events; `available_not_selected` records this explicitly.
Required timer/wakeup/switch/IRQ edges remain selected on all CPUs. The updated
parser also supports the syscall pretty-printers in the original capture.
Local APIC timer/reschedule vectors
are distinct from generic device IRQ handlers. Each selected event's actual
kernel `format` is retained. Missing required events stop the run without a
substitute or guessed format.

A fresh `stratadrive-m4-<uuid>` tracefs instance uses **trace_clock=mono** and
all available CPUs, including cross-CPU wake sources. Markers at both ends have
userspace CLOCK_MONOTONIC before/after bounds. The parser verifies each marker's
trace timestamp lies within its bounds with1µs text precision. It never aligns data
by wall-clock/date or by subtracting unrelated process start times.

The collector refuses configured global tracing/function profiling, existing
instances and known active `perf`/`trace-cmd`/`bpftrace` processes. An advisory
lock prevents competing invocations of this collector. It never clears an old
buffer, edits global settings or removes foreign instances. Concurrent external
changes are reported, not overwritten with a stale snapshot. These checks do
not constitute a system-wide exclusion mechanism for arbitrary external tools.

- Each application worker has a12s timeout and32MiB per-file limit.
- ON uses16MiB on CPU0,32MiB on CPU1,2MiB on the collector/marker CPU and up to1MiB
  on each other CPU from the remaining budget; total kernel ring storage must
  be≤64MiB (nominal63MiB on this16-CPU Host). Larger CPU counts get uniform256KiB
  increments within the cap or are rejected if even256KiB cannot fit.
  Actual rounded allocation is checked and recorded before capture.
  This replaces the256KiB background rings that lost1963 events on CPU9.
  Overwrite is disabled. The valid v2 run used256KiB on its collector CPU2
  and consumed244372bytes there. Extra marker headroom is a mitigation to
  validate, not proof that EBADF is eliminated. Any new loss remains INVALID.
- Export is≤128MiB of trace text. Overflow/dropped events or truncated export
  makes analysis invalid, never successful silence.
- Normal exit, exception, SIGINT/SIGTERM/SIGHUP stop tracing, preserve available
  partial output, terminate the owned workload group and disable/remove only the
  new instance. Before/after global settings and cleanup outcomes are recorded.
- If the end marker fails, stop and export available raw trace/statistics before
  propagating the error. `marker_errors` and pre-stop `tracing_on` are retained.
  The missing marker remains an alignment failure; it is never synthesized.
  The write is unbuffered so the stack locates the original failure.
- `free_buffer`/`disable_on_free` and a detached watchdog provide fail-stop on
  collector death. The watchdog has a **15s total cap** including export, kills
  the owned workload group on emergency, disables/removes the owned instance
  and writes `watchdog.json`. Emergency intervention is not a valid capture.
  A machine crash or simultaneous destruction of collector/watchdog is outside
  this guarantee; inspect the recorded exact instance if cleanup reports an error.

The tracefs behavior follows the kernel's
[ftrace interface/instances/clock documentation](https://www.kernel.org/doc/html/latest/trace/ftrace.html)
and [event formats and enabling](https://www.kernel.org/doc/html/latest/trace/events.html).
The actual local kernel format remains authoritative. No permission, sysctl,
RT throttling, kernel, CPU map or safety deadline is changed.

<a id="m4_kernel_capture-analyze-the-output"></a>

### Analyze the output

The collector automatically runs the analyzer as the original user after both
workloads stop. To repeat analysis offline, no sudo is needed:

```bash
python3 tools/m4_kernel_analysis.py build/m4-kernel-other-YYYYMMDD-HHMMSS
```

| File | Interpretation |
| --- | --- |
| `off/`, `on/` → `run/` | unchanged runner commands, epoch/runtime/load logs, actual result/physical/event/execution CSVs |
| `worker-identity.json`, `source.json`, `owner-tids.csv` | actual user/capabilities, source/binary identity, owner→TID→CPU/policy |
| `on/kernel.trace`, `event-formats.json`, `trace-integrity.json` | full raw events, kernel schemas, clock brackets, per-CPU overrun/drop statistics |
| `on/owner-jobs.csv` | each existing execution row plus observed timer/wake/scheduling/body intervals |
| `on/miss-context.csv` | missed slot/deadline/detection and following *real* execution row; no fictitious wake for an unexecuted slot |
| `on/first-miss-kernel.csv` | first missed deadline−4ms to+10ms,≤20000 raw events; full trace is retained |
| `collection.json`, `analysis.json` | cleanup, controls, timing verdict separately from trace/clock/coverage validity |

Owner mapping:0 Front,1 Rear,2 Steering,3 Brake,4 Drive,5 BMS,6 Power,
7 Central,8 Physical,9 independent Monitor.

For an actual owner TID, the analyzer follows the same timer address's latest
arm and effective CLOCK_MONOTONIC base, its `hrtimer_wakeup` callback, the
targeted `sched_wakeup` within that callback, and the following `sched_switch`
onto CPU. Reused addresses, missing callback/wake/clock and unobserved edges
stay **NOT OBSERVED**. Linux maps relative CLOCK_REALTIME timers to a monotonic
base in `__hrtimer_init`; the init trace still prints the original clock argument.
The analyzer now handles that rule and retains raw clock/mode and effective
clock separately. Absolute CLOCK_REALTIME, unknown clocks and missing init are
not converted by guessing an offset. Loss/clock mismatch makes derived chains
**UNTRUSTED**, including9076 chains reconstructed from the original lossy capture.

Interpret the components separately:

1. **Requested wake → kernel soft expiry:** userspace sleep calculation/arming
   offset. This is not automatically kernel timer lateness.
2. **Soft → hard expiry:** allowed timer coalescing/slack. Callback−soft includes
   this allowance; **callback−hard** isolates the observed excess beyond it.
   A delayed callback still needs its IRQ/context evidence for a causal explanation.
3. **Callback → wakeup → switch-in:** wake path then observable runnable CPU
   allocation delay. Inspect the intervening switch/IRQ events and competing TIDs.
4. **Switch-in → body start, then body start → end:** user resumption and actual
   owner work. Scheduled/off-CPU intervals distinguish runnable preemption from
   blocking. Nested hardirq/softirq/vector overlaps are unioned, not double counted.
   Original thread CPU time remains alongside these values; unobserved NMI/VM
   effects and accounting differences must not be invented from a residual.

OFF/ON failures and magnitudes may differ because tracing is intrusive. A trace
that changes or hides the failure is **not a fix**. Missing IRQ boundaries during
an owner body or missing scheduler coverage remain incomplete; tail IRQ activity
after the workload is reported separately. No automatic “OS cause” conclusion,
M4 closure or replacement of the original48-run cohort follows from this pair.

<a id="m4_kernel_capture-preparation-validation"></a>

### Preparation validation

[Preparation evidence](../test-plan/evidence/m4_kernel_capture/README.md) preserves the original
90-test preparation and nonroot smoke. [Follow-up evidence](../test-plan/evidence/m4_kernel_capture_followup/README.md)
records95/95 Python tests and corrected offline parsing. The
[first VALID observation](../test-plan/evidence/m4_kernel_valid/README.md) retains another
three attempts, including two end-marker EBADF stacks and the valid OTHER trace.
Global state was unchanged and owned instances removed. Source/trace analysis
locates EBADF at marker write; buffer reservation/collector ring saturation is
a candidate, not a confirmed root cause without failed-attempt statistics.
The final marker export/headroom change has97/97 Python tests but actual tracefs
validation is NOT RUN. The observed OTHER CPU-wait case does not close FIFO,
TSan or M4 acceptance, and the application binary is unchanged.

<a id="m4_middleware_probe_protocol"></a>

## M4 middleware candidate probe protocol

Date: 2026-10-20. Freeze before the first cohort. This is the TBD-05 API/queue/netns experiment, **not M5 ECU deployment or system TC acceptance**.

- Cyclone DDS 11.0.1 direct C API, Zenoh-C 1.10.1 stable C API; pinned official dependency inputs/hash and build commands retained with evidence. No ROS 2, router, system install or default build dependency.
- Same canonical owner-wire v1 request, original epoch/sequence/source/exclusive expiry. Common kernel monotonic clock, explicit boot/clock fixture domain, trusted CLI epoch42; role/schema CRC are not authentication.
- Two independent processes in user+network namespaces, veth10.88.0.1/30↔.2, multicast scouting/discovery disabled, explicit peers. Bind application owners to CPU1, OTHER/priority0. Middleware background threads inherit OTHER; no RT guarantee.
- Each pair4.2s, startup discovery lead1.5s;100 valid Vehicle requests at50Hz, expiry/source-age30ms. Additional duplicate(seq10), previous Epoch(seq20) and100ms-old packet(seq30). Zone echoes unchanged bytes even when rejected: **echo is not Actual or an acceptance ACK**. Trace preserves receive, source and expiry times.
- DDS: RELIABLE/KEEP_ALL, volatile,8 samples/1 instance/8 per instance, max_blocking_time0. Zenoh: peer TCP, publisher DROP (nonblocking congestion policy), bounded callback queue8 guarded by mutex. These are explicit different transport policies, not equivalent delivery guarantees. Application owner drains≤8/200μs poll in both. Count all channel errors/drops.
- Two candidates × six conditions(normal, down-loss, up-loss, down-delay, overflow, loaded) × three repetitions = **36 planned runs**, no retry/replacement. Alternate candidate order by repetition.
- Network loss: at measured central-process-start+2.2s apply100% egress drop for300ms on selected Central→Zone or Zone→Central veth. This also drops that direction's DDS protocol/TCP control traffic. Delay: Central egress100ms for300ms. Save actual tc start/end and qdisc config/counters; never equate script target with injection time.
- Overflow: Zone consumer does not take from2.2–2.5s relative to its own recorded start; callbacks/DDS continue. Loaded: separate CPU1 OTHER process busy7ms/10ms; record actual affinity/policy/CPU/wall time. Do not build/run other verification concurrently.
- Normal/loaded: all100 valid inputs accepted, exactly3 invalid/replayed inputs rejected,103 unchanged echoes, zero channel error/drop; startup/process/CPU/load setup must match. These are functional counts, not a4ms timing criterion.
- Loss/delay: changed network qdisc must be observed, loss/backlog/staleness visible, **zero accepted packet** with old epoch, duplicate sequence, future source or receive≥expiry/age>30ms. Reply loss and input acceptance are distinct. Recovery to traffic is measured only; it grants no normal vehicle permission.
- Overflow: nonzero middleware/queue failures required, no stale/duplicate/old input accepted. A production adapter must permanently fail the link and recreate after owner join; the probe only measures capacity, does not implement recovery authority.
- Report RTT/source-age median/P95/P99/max and all denominators, keep FAIL/BLOCKED. No throughput superiority inferred from36 short probes. Full authority/INIT/rejoin is separately tested at the Leaf component, not claimed by a bare echo.

M4 exit must still review execution timing exceptions and remote session integration. M5 full controller/Actual round-trip, remote restart/rejoin, Host bridge, Target clock synchronization remain NOT RUN until actually executed.

<a id="m4_settlement_protocol"></a>

## M4 pending-command settlement follow-up

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
