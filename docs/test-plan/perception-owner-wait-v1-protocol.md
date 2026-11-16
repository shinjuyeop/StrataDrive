# M10 owner wait V1

Host clock V2 retained first30s PASS and second30s FAIL at1.794012249s.
Held HV dependency age30.490079ms comprised21.597022ms already present at
acquisition plus8.893057ms afterward. The native's150010 eligible slots had
zero missing/late calls; no observed all-core low-clock sample or thermal counter
increase. Frame657 tick wall7.940ms/thread CPU1.982ms and frame658 prior-complete
to-admitted5.158ms require owner wait attribution. Do not infer a kernel cause
from wall-minus-CPU alone, or accept a70% cap as a solution.

This candidate adds only opt-in state-path diagnostics to the server module:
per-phase thread rusage counters and CPU identity; fixed-size pump reason counts;
aggregate active, explicit idle sleep, and outside-pump durations, with exact
begin/end counters for each group's longest observation. After receipt complete,
the next outside-pump interval starts there, avoiding double-counting its physical
tick. Preserve original acquisition clocks in their existing fields; the separate
scheduling sample is explicitly later. No file I/O or per-pump allocation.
One ineligible reason string is bounded95 bytes and truncation rejects integrity.

Observe reasons: unavailable/proof unreadable/EV settlement/stopped/invalid/not
due/declared gap/protection/ineligible/staging/ready. Existing decisions, order,
source stamps, model integration, native binary and HV30ms remain. Each retained
physical interval must have one ready pump and complete active/idle counts,
monotonic valid counters and an unchanged<=50us requested sleep per false pump.
Original physical/renderer/shadow/replay audits remain authoritative. Reproduce
the added audit from frozen source and compare exact results after relocation.
The 50ms IRQ profiler remains a native-CPU observer, not full scheduling tracing.

Build one isolated module, retain baseline bytes and install only with no server.
All Python504 and focused frozen88 tests must pass. Test the real fixed-size C++
aggregate and invalid evidence mutations. Measure10000 quiet owner stamps with
p95<5us; record actual OwnerPath size and reserve<=128MiB for60000 intervals.
Reuse prior207 native C++ tests and30/300 allocation checks for the identical
native binary. Freeze all source, protocol, runner, candidate module and helper.

Use the already authorized bounded70% helper with a fresh owner PID after full
preparation; host minimum16%, turbo enabled, original100% restored on owner exit,
handled signal or1800s bound. No global scheduler/IRQ/fan changes. Keep selected
Host V1 placement, corrected model setup,2K/Epic/D-FINE-M960/CUDA, camera100ms,
renderer/query20Hz, passive ORT/CUDA blocking, parked preparation, MaxFPS60,
CV4/resize4 and NVMe raw. Physics5ms/320steps/native2/4ms/perception100ms unchanged.

Preflight CPU<=70C/180s, RAM>=4GiB, horizon storage+4GiB; startup180s, shutdown30s,
and live reserve2GiB unchanged. One30s, another30s only after all checks pass,
then300s only after both; stop first failure with no same-candidate retries.
Do not build, test or run independent archive work during live concurrent work.
Preserve every raw frame and failure; chain future exclusions from16633.
Finite diagnostic PASS does not close long-term stability, native perception,
complete scene, independent quality, each Jetson deployment or M10.
