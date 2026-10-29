# M4 kernel capture preparation evidence

The [capture protocol and exact sudo commands](../../../archive/m4-test-protocols.md#m4_kernel_capture)
define a separate diagnostic OFF/ON pair. **Actual privileged inventory/capture,
real tracefs cleanup and kernel attribution are NOT RUN.** Interactive root
access was reported successful by the user; the agent's noninteractive probe
returned1/password-required (`access-attempt.json`).

The tool implementation is `d20156b`; `cb0ad7c` corrects sleeping→runnable
accounting and explicitly records both worker12s and watchdog15s limits.
No M4 C++ source/binary, CPU placement, load, deadline or safety condition changed.
M4 stays NOT CLOSED; original timing/native/SDK TSan failures remain OPEN.

## What was executed

| Check | Actual result / scope |
| --- | --- |
| Python unit suite | **90/90 PASS**, existing71 + new19. `python-full.txt` |
| Interval correction regression | Previous `d20156b` analyzer:1 expected FAIL; current:PASS. Wakeup must split a sleeping interval from the following runnable wait. `blocked-runnable-before.txt` |
| New parser/collector tests | Synthetic kernel-format clock, timer identity/reuse, slack, queue delay, body preemption/blocking, IRQ union, loss/truncation, nonroot refusal, conflict detection, owned cleanup, interruption and watchdog EOF |
| Real unprivileged worker smoke | **one Normal/OTHER loaded run, timing FAIL**, exit1. Same original2540ms/2ms opportunities/4ms deadline,12110 jobs,266 misses/skips; setup/load/grid/buffer controls PASS |
| Real privileged pair | **NOT RUN**, not included in the smoke denominator |
| C++ full / TSan /48 timing cohort | No new execution: application binary unchanged. Prior source-specific973/973,108+9,40 and48 results remain in [settlement evidence](../m4_settlement/README.md) |

The smoke ran at `d20156b`, UID/EUID1000, effective capabilities0, RT limit20/20,
launcher OTHER/0, original allowed CPUs0–15 and actual owner CPUs0/1.
Its `actuator_demo` SHA256 is
`4736b40e8b5b2b67c4cf603ff96a7b1516d619541fdb10a8de80ff01b8f76347`,
exactly matching the preserved `97afb35` executable. `source.json` records the
diagnostic source fingerprint separately from the binary identity.
This smoke preceded the kernel-only analyzer correction; it is not relabeled as
a new binary performance result or the planned two-run pair.

The failure preceded normal arm (`active=0`). No kernel trace was collected,
so timer delay, runnable CPU wait, IRQ/preemption and other causes remain
unresolved. The original failure oracle was not changed to make the smoke PASS.

## Files and reproduction

`worker-smoke.tar.gz` contains the exact unprivileged process command/exit,
source/binary/UID/capability metadata, original epoch/runtime/load logs, owner TIDs,
result/physical/events/execution CSVs and trace-OFF analysis. All raw files are
preserved; there is no suppressed failed attempt.

`synthetic.trace`, `synthetic-integrity.json` and `synthetic-owner-job.csv` are
explicit **synthetic unit inputs/outputs**, not Host kernel observations.
They show callback−soft200µs, callback−hard150µs, wake→CPU390µs, in-body runnable
wait200µs and nested IRQ union180µs. These numbers only verify arithmetic.

From the repository root:

```bash
python3 -m unittest discover -s tests/unit -p '*_test.py' -v
```

The user-facing paired collector command is in the protocol. The `_worker`
entry is an internal diagnostic worker, requires a nonroot user and never
configures tracing. Raw trace data, after real collection, must be interpreted
using `collection.json`, actual event formats, loss/clock checks and both modes.
Missing edges stay unknown; an ON run that hides a failure is not a correction.

`validation.json` records source identity and commands. `SHA256SUMS` covers this
directory. Parent/foreign trace settings were only tested with a temporary
filesystem/mock in unit tests; no claim of actual kernel cleanup is made yet.
