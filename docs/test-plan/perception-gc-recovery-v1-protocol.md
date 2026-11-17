# M10 GC recovery preview V1

Prospective comparison after [GC owner3 V1](evidence/m10_gc_owner3_v1/README.md).
Two30s cases passed. The300s case recorded HV expiry at60.196015917s. Its first
parallel GC took16.652656ms, followed by three normal physical frames. Those
frames retained wheel/actuator source time from before GC. The next update waited
for command interval/causal eligibility; the original held HV age reached
30.383242ms at the first fault. Preserve that original failure.

Exact replay reproduces60,000 admissions,36,006 ingress events, native output and
the first fault. On original inputs the1ms extra preview closes at approximately
GC end+4.60ms. The next pump begins near+4.92ms. A0.5ms preview opens only a narrow
window after that point; the0.3ms diagnostic is the prospective candidate.
These probes do not alter physics and do not prove another trajectory succeeds.
The original first post-GC frames spent approximately90–111us from the final
admission clock to physical application. Across all11,874 normal frames before the fault, final-check-to-application
latency was p99=162.665us and maximum251.494us. The300us candidate exceeds that
observed maximum; it is not a future execution bound. Timing variation remains
a live gate.

## Single behavioral change

Require `--owner-recovery-preview` / `-StrataM10RecoveryPreview`, together with
the existing profiled parallel GC, structured state and incremental purge option.
Only this explicit combination changes the two owner preview checks from1ms to
300us extra reserve. Binding and final server responses must report the selected
option and reserve. The renderer must not receive the flag. Existing plain
structured2ms, text4ms and purge1ms paths retain their original values.

`Admission` and the prephysics guard remain byte-identical source bodies. Final
acceptance must still cover the whole original5ms interval, all original command
and permission expiries, wheel/actuator30ms ages and causal relationships. The
prephysics check uses its later real clock and contains an expired selection.
Native's held-HV30ms expiry-before-replacement order, native2/4ms deadlines,
source timestamps, numerical integration and GC61.1s/12220-frame cadence remain.
No restamping, expired-packet substitution, forced/warmed/suppressed GC or longer
collection period is introduced. Incremental purge still requests100us once per
engine frame and must complete before the next collection.

Use the same Host profile: owner3 physical cores, renderer/image3, native1,
observer1, including disjoint SMT siblings. Keep2560×1536, D-FINE-M960 CUDA,
camera target10Hz, renderer20Hz/MaxFPS60, CV/resize4 threads, passive workers,
NVMe raw BGRA and current source/frame/identity contracts. This is not a Jetson
profile or a production default.

## Preparation, trial and preservation

Build the isolated module; verify only the declared source delta and unchanged
native/engine/model inputs. Run Python regressions and the29 native admission
tests, including staging time and unchanged exclusive expiry. Freeze sources
and reproduce focused tests. Validate empty renderer startup/shutdown and exact
runtime restoration without native control or GC intervention.

After prior measured work, archive validation and restoration finish, authenticate
the unchanged bounded70% Host lease with a fresh owner PID. Run30s→30s→300s and
stop subsequent cases after the first failure. The limit remains30 minutes;
owner exit or operator cancellation also restores the prior100% setting. The
lease and every measured/server-shutdown timestamp must bracket correctly.

Require original physical, shadow, clock, native deadline, state-path and
workspace audits; exact native/first-fault replay; four completed GC/purge cycles
in300s; declared CPU masks and actual process policies;300us configuration on
both binding and final responses. Report camera rate, latency before/after any
fault, CPU peak and thermal counters. Added scheduling integrity does not
replace physical acceptance.

Retain all source/run/raw bytes, independently verify archives and reproduce
audits from frozen sources. Carry every observed image into future-quality
exclusion. Only byte-checked duplicate extractions and losslessly verified raw
transport may be compacted after measured work. Continuous route driving,
long-run stability, full scene replication, independent quality, native perception
acceptance, each Jetson deployment and overall M10 remain OPEN.
