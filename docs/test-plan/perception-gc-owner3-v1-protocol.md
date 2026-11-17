# M10 GC owner three-core V1

Purge slice V1 passed both 30s cases. In 300s, all four periodic collections and
incremental purges were directly observed and completed; the first purge used
407 slices with a maximum153.288us call and drained in2.011s. Nevertheless the
original HV30ms check failed at60.226014049s. At the first collection's entry,
the held HV dependency was already10.019119ms old. The19.107547ms collection
left873.334us before that held dependency expired. The first purge started
636.933us after collection end; the first fault was30.002478ms dependency age.
Preserve the original FAIL, exact native replay and0 missing/late slots among
1,500,000 eligible native deadlines. No claim that intermittent native gaps are
permanently solved. Observed CPU peak91°C and unchanged thermal counters do not
establish long-term cooling margin.

Change only the owned-process CPU plan to `perception-endurance-host-v4.json`:

| Role | Logical CPU IDs | Physical cores |
|---|---|---:|
| Owner | 2,3,4,10,11,12 | 3 |
| Native | 1,9 | 1 |
| Renderer and image pipeline | 5,6,7,13,14,15 | 3 |
| Observer | 0,8 | 1 |

Transfer core4 and SMT sibling12 from the renderer/image pool to the owner.
All roles remain disjoint, including SMT siblings. No reservation of the host
or changes to unrelated processes, IRQs, scheduler policy or Jetson settings.
Normal pre-fault renderer/image work averaged about1.90 cores in the previous
case; this supports trying three image cores but does not prove burst latency
will remain acceptable. Compare complete source-to-result latency, camera rate,
thermal observations and native missed/late slots as well as GC pauses.

Reuse module `0520f2a91d3e918510e6f4631d869205bff524f1724adf8d395f8e1647a0066f`,
the same native binary, model, resize library and engine. Keep parallel GC and
61.1s cadence,100us requested incremental slices (not a hard execution bound),
1ms additional structured preview reserve, original5ms final physics coverage,
HV30ms, native2/4ms, sensor clocks and old-held-expiry-before-replacement order.
No forced/pre-warmed/suppressed collection and no period extension. Preserve
the original four completed purges and12,220-frame collection-gap checks.

Extend GC observation validation only for the two explicit disjoint CPU plans;
the default two-core validator still rejects a GC stamp on core4. The new trial
must match the exact three-core plan, observed owner/renderer/observer masks
and unchanged SCHED_OTHER policy during the measured interval. Original native
FIFO placement remains separately checked on1,9. A good scheduling-integrity
report cannot override an original physical FAIL.

Run Python and frozen-source checks, retain the identical28 native admission
tests, and verify every reused build input/generated file and external hash.
Validate empty renderer startup/shutdown with its new three-core mask before
operator authentication. Then run30s →30s →300s with stop after the first failed
case. Keep70% temporary boost, source2560×1536, D-FINE-M960 CUDA, camera10Hz,
renderer20Hz/MaxFPS60, CV/resize4 threads, preparation600s/freshness300s,
startup180s/shutdown30s. No independent builds/tests/archive compression during
measured work. Complete source/run/raw retention, independent archive checking,
frozen-auditor reproduction, six-file restoration and original100% boost apply.
Use the unchanged PID/UID/start-tick-bound root helper with1800s maximum and
owner-exit restoration; no stored credentials. Continue future exclusions from
Purge slice V1. This remains a finite hold comparison, not continuous driving,
native perception acceptance, full-scene/independent-quality acceptance, each
Jetson deployment or M10 completion.
