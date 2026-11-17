# M10 incremental purge slice V1

Parallel GC V1 passed both 30s cases. The 300s case failed at 60.241006517s:
held HV dependency age 30.095850ms exceeded the original 30ms limit. The first
collection took 21.210843ms; the fault followed its end by 8.736304ms. The next
frame's outside-pump work took 2.564712ms wall / 2.565197ms thread CPU. The
engine's incremental purge defaults to 2ms. This is a causal candidate, not
direct attribution of that old span: the previous delegates did not bracket
incremental purge. Preserve the original FAIL and its later 18 missed native
slots, which are a separate unresolved problem.

Exact replay matched 60,000 original admissions, 36,009 ingress entries and the
native CSV. Counterfactual eligibility probes every 50us found a short renewal
window after the first post-GC receipt. The actual next pump missed even the
zero-extra-reserve window. Reducing preview slack alone cannot fix that trace.

Enable owner-only `--owner-purge-slice` / `-StrataM10PurgeSlice`, requiring
profiled parallel GC, structured state and the finite endurance path. Keep all
defaults unchanged when this flag is absent. For an observed collection with
pending incremental work, execute `IncrementalPurgeGarbage(true, 0.0001f)` once
per engine `GFrameCounter` at the owner pump. Then use `DelayGarbageCollection`
to replace that same frame's default incremental slice, avoiding duplicate
work. Never call it without pending work at entry. The engine's full/forced
collection branches precede this flag; no collection is requested or disabled,
no period/timer is changed, and startup collections remain engine-owned.
The requested 0.1ms is a cooperative budget, not a hard execution bound.

Record each collection's pending state and every slice's count, first/last
frame, wall/thread CPU totals, worst stamps and completion in a fixed POD
journal (<32KiB; GC plus purge <64KiB). Repeated pump polls in the same engine
frame must not run extra slices. A missing, invalid, unfinished or overlapping
purge fails integrity. Require four completed periodic purges in 300s, each
draining before the next collection and collection frame gaps exactly 12,220
(61.1s at 5ms). Thus spreading work cannot silently postpone collection.

Only this flag selects an additional structured preview reserve of 1ms instead
of 2ms. The text path stays 4ms. Preserve the final admission body, full original
5ms physics coverage, HV30ms, native2/4ms, source clocks, old-held-expiry-before-
replacement order and post-ingress monotonic timestamp. Audit both actual
server configuration and all original receipts against the declared reserve.
No protected result is accepted as normal driving.

Build an isolated module and verify original native/plant sources and compiled
behavior. Run Python, native admission and frozen-source tests before any root
step. Validate empty-renderer startup/shutdown with the new module. Then run
30s → 30s → 300s, stop after the first failed case. Keep prior CPU/FIFO placement,
2K 2560×1536 / D-FINE-M960 CUDA, camera10Hz, renderer20Hz/MaxFPS60, 70% bounded
boost, preparation600s/freshness300s/startup180s/shutdown30s. No independent
builds/tests/compression during measured work. Retain complete source/run/raw,
exact native replay, frozen audit reproduction, six-file restoration and 100%
host restoration. The root helper remains unchanged and requires operator sudo
authentication; no password storage. Continue future exclusions from parallel
GC V1. Finite hold success would not close M10, continuous driving, independent
quality, native perception acceptance or deployment on each Jetson.
