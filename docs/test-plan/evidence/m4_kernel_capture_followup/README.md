# First real M4 kernel capture and diagnostic corrections

Status: **runtime FAIL; original trace INVALID; compact-v2 recapture NOT RUN**.
M4 remains NOT CLOSED. Original timing/native/SDK TSan failures, system/Target
NOT RUN and learner-review states are unchanged. This is kernel observation
work, not a new application timing acceptance cohort.

## Actual attempts, without discarding failures

Source `034b588`, fingerprint
`3e5b0cd9e2c38f66b6c50bab5006e64b3d5777ba5b53d1354d64b8d8b59adebc`,
kernel `6.8.0-138-generic`, actual user/EUID1000, effective capabilities0,
OTHER/0, original CPU map/load/grid/deadlines. Binary SHA256:
`4736b40e8b5b2b67c4cf603ff96a7b1516d619541fdb10a8de80ff01b8f76347`.
The actual argv, environment controls, runtime source identity, TIDs, execution
CSV, event schemas, ring statistics and original analysis are in the archive.

| Directory suffix | OFF | ON | Collection |
| --- | --- | --- | --- |
| `20261020-183033` | FAIL,271 misses/skips | FAIL,301 misses/skips | Export EBADF, no kernel trace saved; cause OPEN |
| `20261020-183050` | FAIL,176 misses/skips | FAIL,311 misses/skips | Trace saved, but CPU1 dropped256668 events; original parser rejected145058 lines |

All four workloads had12110 jobs and passed setup/load/grid/growth controls.
Both attempts record global tracing unchanged and owned instance removed.
The183050 pair never reached normal arm (`active=0`); first fault/selection was
128.656741ms OFF and129.659433ms ON relative to runtime origin. Do not interpret
the miss-count difference as quantified observer overhead from a single pair.
The preceding preparation smoke and historical48-run cohort stay separate.

`original-attempts.tar.gz` contains **both complete original directories**.
The183033 export error was discovered during inspection, not omitted because
only183050 was pasted in chat. Its original log lacks a stack, so the failing
operation/cause cannot be assigned reliably. Future collector exceptions now
save `collector-error.txt` with the traceback. That instrumentation is not a
claim that EBADF is fixed.

## Confirmed diagnostic defects and changes

1. **Syscall printing.** Actual kernel lines use
   `sys_clock_nanosleep(...)` / `sys_clock_nanosleep -> 0x0`, not the normal
   `event: body` form. `a26a206` explicitly parses these entry/exit forms,
   preserves unknown-line errors and reports bounded unknown examples/counts.
   Offline reparsing changes145058 unparsed lines to0; all762977 stored events
   parse. It cannot recover256668 events absent from the file.
2. **Ring capacity.** CPU1's16MiB non-overwrite ring filled, while CPU0 used
   about12MiB. Compact-v2 uses CPU0=16MiB, CPU1=32MiB and other CPUs=256KiB
   (51.5MiB total on this16-CPU Host, still≤64MiB; text still≤128MiB).
   Optional duplicate `sched_waking`, nanosleep syscalls and low-resolution
   timer events are omitted. Required hrtimer init/start/cancel/entry/exit,
   sched_wakeup/switch and IRQ events remain, with softirq/vector events.
   All CPUs remain traced to retain cross-CPU wake sources. Actual inventory
   lists selected and intentionally unselected events. New loss still fails;
   reduced volume/capacity adequacy needs a real recapture.
3. **Relative clock semantics.** Actual owner timers initialize with
   `CLOCK_REALTIME mode=REL`. Linux's
   [`__hrtimer_init`](https://github.com/torvalds/linux/blob/v6.8/kernel/time/hrtimer.c#L1565)
   maps these to a monotonic base; the initialization trace retains the caller's
   original clock argument. `984d5ac` handles this rule, recording raw clock,
   init mode and effective clock separately. ABS realtime, missing init and
   unknown clocks remain rejected. No wall-clock offset is guessed.
   `kernel-source.json` identifies the inspected upstream source, distinct from
   Ubuntu binary provenance.

After both parser/clock corrections,9076 job chains can be reconstructed but
remain **UNTRUSTED** because the whole capture has recorded loss. Trusted
chains remain0, aggregate trusted maxima remain null, trace remains INVALID
and analyzer process exit remains2. `representative-chains-UNTRUSTED.csv` and
`first-miss-kernel-UNTRUSTED.csv` are diagnostic examples, not causal evidence
for an OS/timer/scheduler conclusion. The original analysis files are unchanged
(verified by `original-hashes.json`).

## Tests and reproduction

- Before syscall/policy changes:22 focused tests,5 failed assertions (including
  subtests) and1 error; `before.txt`.
- Before relative-clock correction:23 focused tests,1 failure;
  `relative-clock-before.txt`.
- Final Python suite: **95/95 PASS**, previous90 +5 tests;
  `python-full.txt`. Includes a verbatim real trace excerpt, syscall formats,
  effective clock, actual loss remaining invalid and mandatory event retention.
- Existing `test_missing_wake_or_wrong_clock_is_not_a_timer_chain` keeps its name
  and rejection assertions. Its wrong-clock fixture is now explicitly ABS
  CLOCK_REALTIME: REL CLOCK_REALTIME is a valid monotonic-base case, not evidence
  of a mismatched clock.
- C++/ASan/TSan/48-run timing: **no new execution**, application source and binary
  unchanged. No historical result is relabeled as new performance validation.
- New privileged compact-v2 run/cleanup: **NOT RUN**. Noninteractive sudo probe
  still returns1/password-required; see `access-attempt.txt`.

```bash
python3 -m unittest discover -s tests/unit -p '*_test.py' -v
```

To reproduce offline analysis while preserving the original archived files:

```bash
mkdir -p build/m4-kernel-replay
tar -xzf docs/test-plan/evidence/m4_kernel_capture_followup/original-attempts.tar.gz \
  -C build/m4-kernel-replay
cp -a build/m4-kernel-replay/m4-kernel-other-20261020-183050 \
  build/m4-kernel-replay/corrected-analysis
python3 tools/m4_kernel_analysis.py build/m4-kernel-replay/corrected-analysis
```

Expected exit2: **unparsed0, dropped events remain, trusted chains0,
untrusted9076, INVALID**. `parser-only-analysis.json` preserves the intermediate
stage and `corrected-analysis.json` the final result. `validation.json` records
analysis source identity separately from capture identity.

## Next observation and remaining limits

Use the [compact-v2 sudo command](../../../archive/m4-test-protocols.md#m4_kernel_capture) for one newly
declared OFF→ON pair, keeping both outcomes and checking losses/cleanup/clock
alignment before interpreting timer, runnable and in-body intervals. Do not
retry silently until a passing sample appears.

FIFO is **NOT RUN** here. Sudo workers inherited RT limit0/0, while the original
nonroot preparation worker had20/20. OTHER/0 controls passed; this does not
establish FIFO readiness. Preserve the original user's verified RT budget
across the privilege boundary before that condition, rather than increasing
the scheduling budget or changing deadlines. The previous protocol also
misdescribed Central on CPU0; actual unchanged runner/TID evidence places it
on CPU1 with the five Leaf owners. The current protocol corrects that text.

No kernel replacement, application scheduling change, suppression, deadline
relaxation or M4 closure follows from these diagnostic fixes.
