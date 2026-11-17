# M10 parallel GC V1 — compare the default collector after admission fixes

Admission window V2 passed both 30s cases, but the 300s case first entered HV
protection 60.236004058s after initialization. Direct GC delegates bracket that
fault inside the first serial collection: 38.242956ms wall / 38.238533ms thread
CPU. The other three collections took 38.620542, 32.994507 and 32.549041ms.
All exceed the unchanged 30ms HV dependency limit. Preserve the failed case,
its exact native replay and all raw evidence; serial GC is not accepted.

Change one runtime choice: omit `--owner-serial-gc`, removing the owner-only
`gc.AllowParallelGC 0` override. Engine source initializes that setting to 1;
the original run must read back parallel=1 and period=61.1s with no `gc.`
override on either owner or renderer. Keep the direct bounded GC journal.
Do not extend the GC period, force a collection, suppress collection, change
original sensor clocks, extend HV age or reorder old-held-expiry checks.

Reuse module `29df236c28bdc92c29784f0ab7e087f3f18c8bf0187c84aa24a957b6d7e45e98`.
Keep the post-ingress wall timestamp and structured preview's additional 2ms
reserve, original final admission and full 5ms physics coverage, HV30ms and
native2/4ms. Verify every build input/generated file and external binary hash.
The existing auditor already checks both collector policies; add positive
parallel-journal and wrong-policy regression assertions before source freeze.
Prior parallel runs' 17–22ms outside-tick spans were only GC correlations, not
direct collection measurements or proof this candidate will pass.

Repeat prospective 30s → 30s → 300s, stopping after the first failed case.
Keep V2's CPU/FIFO placement, 2K 2560×1536 / D-FINE-M960 CUDA, camera10Hz,
renderer20Hz/MaxFPS60 and bounded 70% boost. Keep preparation600s,
freshness300s, physical startup180s and shutdown30s. Every actual launch
prepares assets afresh before authentication and creates a fresh lease owner.
Reuse V1's identical-module empty-renderer validation and subsequent actual
startup/shutdown evidence; do not claim a new empty-server validation.
No independent builds, tests or archive compression during measured work.
Retain complete raw/run/source archives, independent archive and frozen audit
reproduction, six-file restoration and original 100% host policy. The root
helper and its PID/UID/start-tick identity, owner-exit and 1800s limit stay unchanged.

Continue future quality exclusions from V2's final `future-exclusion.json`,
including every image from all three cases. Analyze original native missed/late
slots before and after first fault separately. Do not label latency throughout
protected hold as normal driving. Passing a finite hold scenario would not
close continuous driving, full scene, independent quality, native perception
acceptance, thermal endurance, each Jetson deployment or M10.
