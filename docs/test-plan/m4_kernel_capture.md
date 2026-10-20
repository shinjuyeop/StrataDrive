# M4 Host kernel observation — bounded OFF/ON pair

## Fixed follow-up campaign (after `1a4afe5`)

The preferred next command is now:

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
exit0 means collection workers succeeded, **not timing acceptance**. Except for the
initial OTHER validation, analysis follows collection as the original user:
`python3 tools/m4_kernel_analysis.py build/<campaign>/<pair>`.
Trace loss, missing alignment/identity, changed source or cleanup errors remain
INVALID even if a workload reports PASS. [Preparation/evidence](evidence/m4_kernel_campaign/README.md).

The following single-pair command and original results are retained as history;
that older CLI does not preserve the invoking user's RT limit across sudo.

Status: **compact-v2 OTHER capture VALID / runtime FAIL; latest marker fix NOT RUN on tracefs**.
The user executed the collector on kernel6.8.0-138-generic. The latest valid
capture has729726 events,0 drops and11951 linked executed jobs. The first missed
CPU1 opportunity is dominated by runnable CPU waiting; see the
[timeline, CSV and plot](evidence/m4_kernel_valid/README.md).
The original lossy trace and145058 unparsed syscall lines remain in
[earlier evidence](evidence/m4_kernel_capture_followup/README.md).
Two subsequent attempts failed while writing the end marker. The agent's
noninteractive `sudo -n` still requires a password. M4 remains **NOT CLOSED**, previous timing/native/SDK TSan
failures remain OPEN, and Target/system/learner states are unchanged.

## Execute from the original user's terminal

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

## Fixed workload and privilege boundary

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

## Event discovery, clock and bounded cleanup

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
- ON uses16MiB on CPU0,32MiB on CPU1,2MiB on the collector/marker CPU and256KiB
  on other CPUs; total kernel ring storage must be≤64MiB (nominal53.25MiB on
  this16-CPU Host; actual rounded allocation is checked and recorded).
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

## Analyze the output

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

## Preparation validation

[Preparation evidence](evidence/m4_kernel_capture/README.md) preserves the original
90-test preparation and nonroot smoke. [Follow-up evidence](evidence/m4_kernel_capture_followup/README.md)
records95/95 Python tests and corrected offline parsing. The
[first VALID observation](evidence/m4_kernel_valid/README.md) retains another
three attempts, including two end-marker EBADF stacks and the valid OTHER trace.
Global state was unchanged and owned instances removed. Source/trace analysis
locates EBADF at marker write; buffer reservation/collector ring saturation is
a candidate, not a confirmed root cause without failed-attempt statistics.
The final marker export/headroom change has97/97 Python tests but actual tracefs
validation is NOT RUN. The observed OTHER CPU-wait case does not close FIFO,
TSan or M4 acceptance, and the application binary is unchanged.
