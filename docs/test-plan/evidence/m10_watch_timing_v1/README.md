# M10 monitor timing V1: one pass, held-input expiry, diagnostic fixes

Executed2026-11-16 under the [frozen protocol](../../perception-watch-timing-v1-protocol.md).
The guarded structured-state build04 and unchanged Host V1 placement completed
one30s concurrent case. The second case failed; the declared300s case was not run.
The JSON optimization remains opt-in. This is not endurance or M10 acceptance.

## Original live results

| Check | First30s | Second30s |
| --- | ---: | ---: |
| Original joint audit | PASS | FAIL |
| Normal / protection / INIT intervals |5834 /0 /166 |845 /4993 /162 |
| First protection after native initial | none |5.097018s |
| Eligible native slots missing / late |0 /0 |76 /0; all missing slots after first protection |
| Monitor missing slots |0 |6 |
| Maximum monitor wake delay |0.544103ms |2.597866ms |
| Exact native replay / state-path / structured-state integrity | PASS | PASS |
| New monitor diagnostic integrity | PASS | PASS |
| Raw frames / inferences |287 /283 |286 /282 |
| Scene-to-result median / p95 / max, ms |77.979 /96.890 /212.324 |77.439 /135.224 /321.657 |
| Results exceeding original100ms |13 |21 |
| Camera callbacks during physics |9.433Hz |9.400Hz |
| Native perception acceptance |0 |0 |

The original scenario accelerates, decelerates and then holds a stopped vehicle;
it is not continuous route driving. Both cases retain6000 original physical
intervals, all original sources, and independent raw/archive verification. Both
runtime restorations pass. The frozen audit reproduces each original verdict.
The second case's845 normal intervals are4.225 model seconds; its long protected
tail must not be called normal endurance. See [sequence disposition](sequence-disposition.json).

## First fault: the previous input, not the newly reported sample

The second case reports `native credit/gate closed leaf=2 code=5 leaf=3 code=2
leaf=4 code=14`. Drive code5 is `LocalInputsUnavailable`; the BMS/Power codes
alone do not establish separate initiating faults. At the reported protection row, the
latest HV dependency is15.427909ms old, which initially obscured the cause.

A separate [instrumented replay](held-input-analysis.json) proves the ordering:

1. At+5.095018s, the held HV dependency is29.352945ms old, with no Drive fault.
2. At+5.096015s, `observe_local` first checks the previously held input. Its
   dependency age is**30.349940ms**, exceeding the unchanged30ms limit. Drive
   latches code5 before replacing it with the incoming14.425101ms sample.
3. At+5.097018s, the outer protection report contains the refreshed15.427909ms
   sample. A late fresh sample cannot erase the preceding expiry.

The instrumented replay's original CSV and JSON are byte-identical to the
unmodified replay. Its [patch](diagnostic-replay.patch) only logs four fixed
original-time calls in a separate frozen-source checkout; it was never used
live. There were no missing/late eligible native slots before this first fault.

The production diagnostic fix now latches the first Drive fault's original
timestamp, epoch, held speed/HV identities and dependency limits, before a later
sample can replace them. It resets only on a successfully accepted new session.
The wall owner and replay write this snapshot after execution, without live
file I/O or a new clock read in the control path. Existing fault selection,
expiry, numerical behavior and output timestamps stay unchanged. Both retained
cases [replay byte-identically](postfix-replay.json) after this fix; the clean
case's new sidecar is null and the failed case records the30.349940ms dependency.
This diagnostic correction has not itself undergone another live trial.

## Timing and host observations

The new optional monitor instrumentation stores requested release, actual wake,
original completion, next grid target, actual CPU, thread CPU time, context
switches and minor faults in a preallocated/touched buffer. The independent
audit joins every completed monitor slot to the original execution watch.
Missing slots remain missing. Both actual monitor threads report FIFO18 and
affinity1,9. The preceding native-only1s prerequisite completes500 eligible slots
with no misses or late completions; maximum wake delay is91.440µs. It establishes
unloaded behavior only.

In the failed concurrent case,50ms host samples show all16 reported CPU clocks
near800MHz during approximately+5.028–5.529s,+15.044–15.345s and+23.057–23.357s.
The first episode overlaps99°C followed by a sharp temperature fall and higher
owner processing time: its physics interval wall/CPU medians are3.597/3.556ms,
with maximum wall5.724ms. Subsequent missing monitor slots cluster near the later
episodes. These correlations support investigating host clock/thermal behavior;
they do not identify a firmware mechanism or prove every wake delay has the
same cause. Existing fast throttle counters cover CPU0, not every core. Selected
kernel-thread counters show no idle-inject/ACPI execution increment in the
worst-wake brackets; this does not rule out interrupts or firmware stalls.

Post-run review found a separate observer bug: a single `pread` on the procfs
sequence file returned only4079bytes/17 IRQ rows, silently omitting35 later rows
including NVIDIA and local timers. Original partial observations remain retained
and cannot exclude IRQ interference. The corrected reader opens a complete
bounded snapshot and handles short reads until EOF. Regression checks exercise
short reads, a fresh second snapshot and size overflow; a real-host check reads
11839bytes/52 rows and observes timer advancement. Quiet p95 read cost rises from
the incomplete224.677µs to1.690ms, max1.877ms; neither is a live overhead bound.
See [read correction](interrupt-read-correction.json). Host privileges, scheduling,
IRQ affinity, frequency, power and cooling settings were not changed.

## Optimization evidence and remaining work

For the prospectively selected701 normal moving tickets200–900, median summed
owner CPU time falls from1.745ms in state-path V3 to1.025/1.033ms in these cases.
Acquisition-to-publication median falls from347.022µs to45.485/45.449µs. These are
between-run descriptive comparisons with uncontrolled clock/thermal histories,
not a controlled causal percentage or an endurance guarantee. The first case
demonstrates finite normal execution of guarded direct JSON; the second shows
that this alone does not sustain all original timing requirements.

Next, investigate the recurring host clock drops and preparation heat using the
corrected observer, with a separately declared mitigation and bounded repeat
sequence. Retain HV30ms, native2/4ms, physics5ms/320 substeps and all failure
records. Do not repeat the same candidate until it happens to pass. Full
wheel/bone/material scene admission, independent quality, native perception
acceptance, each Jetson deployment and M10 closure remain open.

## Verification and storage

Before live work: native40, Python486, frozen focused70, actual30/300s allocation
preflight and native-only prerequisite passed. After the diagnostic fixes:
Python487, Drive47, native40 and affected async/energy tests pass. The new Drive
test checks exact30ms acceptance, expiry one nanosecond later before fresh
replacement, immutable first evidence and successful-session-only reset.
See `postfix-*-tests.txt`, `postfix-*_test.txt` and `postfix-replay.json`.

The live1439-file source freeze and runtime identities remain unchanged. Separate
post-live revisions retain the diagnostic corrections. Git review bundles hold
28 original metadata/trace files per case, including partial IRQ observations,
plus81/77 unchanged receipt rows around the declared diagnostic anchors. Full
source/run/raw archives remain local; Git alone cannot reproduce raw verification.
All573 new images are excluded from future quality evaluation:15211→15784.
Lossless raw compaction and hash-verified duplicate cleanup are recorded in
`storage-closeout.json`; no original image or failed verdict is discarded.
