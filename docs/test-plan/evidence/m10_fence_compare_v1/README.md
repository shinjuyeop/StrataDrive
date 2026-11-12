# M10 frame fence and camera comparison V1

2026-11-12. **The measured wait targets the render thread; both driving attempts
remain FAIL/OPEN.** The declared camera-absent/2K pair preserves renderer ON,
D-FINE-M960 preparation, native protection, state observation and shadow IPC.

## Measured result and limits

| Observation | Camera absent | Same2K camera actor |
| --- | ---: | ---: |
| Completed physical intervals |80|2|
| Normal physical intervals |0|0|
| ECU armed observed |yes|no|
| Largest journal PumpWall gap during native service |3.006280ms|45.949771ms|
| Frame-sync union inside that gap |0.007512ms|42.362087ms|
| Fence wait inside that gap |0.001101ms|42.353841ms|
| Render-thread task wait inside that gap |0ms|42.351933ms|
| Event-wait union inside that gap |0ms|42.210599ms|
| Selected synchronization route |render-only|render-only|
| Received images / live inference calls |0 / 0|0 / 0|

The2K event wait covers91.86% of the largest gap. Its enclosing frame-sync CPU
duration is0.633803ms. The direct RHI/GPU fence route was **not selected**: the
observed `GameThreadWaitForTask` waits for the render-thread completion event.
This does not rule out GPU, driver, resource initialization or scheduling work
behind that render thread; none of those internal causes was measured here.
Nested wall brackets are not additive, and CPU and wall clocks are never mixed.

The2K trial bound at CARLA frame200 and completed only201/202. Its frame5 camera
produced no readback record or callback before protection; the absence arm bound
at270 and completed271–350. Consequently this is **not a steady camera throughput,
inference-latency or randomized causal estimate**. It is one ordered, fresh-server
pair, with the actual startup phases retained. Three synthetic model preparation
calls completed in both arms; no live inference contributed to either failure.

The active window is original native initial time through its last service row.
Only fully contained PumpWall gap records enter the comparison. The server's
lifetime maximum uses a different bracket/window and is12.953444ms absent versus
46.072906ms2K; neither value is silently substituted for the audited3.006/45.950ms.
Post-STOP cleanup RPCs are excluded from the active comparison. Full journals remain
available for other windows. A small pump gap does not prove an eligible physics
release: the no-camera run still failed its original authority/input conditions.

## Original vehicle and lifecycle outcomes

- Absent: first protection at enable+817.007363ms; Drive LocalInputsUnavailable
  (code5), BMS protection (2), Power continuity loss (14). At first protection the
  recorded wheel source age is22.806115ms and HV dependency age32.702261ms. These
  observations do not establish which eligibility rejection first stopped further
  physical release. No normal interval was completed despite observed ECU arm.
- 2K: first protection at enable+30.994079ms, during the measured render wait.
  Original upstream protection/continuity faults remain; no ECU arm. Both actual
  state snapshots preceded INIT enable, so the shadow receiver never initialized.
- Both: all five startup first-body faults are0; native exit0/server SIGINT130;
  no forced stop, cleanup error or camera ownership error. The absent receiver did
  initialize from actual post-enable state but had no camera result. Fresh/accepted
  perception results are0 in both trials. No live actuation authority was added.
- UE executable, Carla module, Engine/RenderCore libraries and original settings
  were restored byte-for-byte, verified in [restoration.json](restoration.json).

[Comparison](comparison.json), [derived timeline](timeline.json), each trial's
`fence-audit.json`/`audit.json`, complete server/native logs and original receipts
preserve the failed verdicts independently of evidence-integrity PASS.

## Instrumentation and reproduction

The [prospective protocol](../../perception-fence-compare-v1-protocol.md) declares
TC-PER-096/097 and one attempt per condition. The isolated Engine/RenderCore build
adds bounded same-thread timing around the original frame-sync calls and branches.
It retains the prior verified outer Launch/Carla instrumentation. No external
source, fence/task ordering, cvar, sensor resolution, threshold or deadline changed.
The override requires all four runtime hashes in the prospective freeze; ordinary
runner behavior remains the prior baseline.

Four8192-row journals retain20,136 rows absent and12,189 rows2K, all complete with
zero overflow. RenderCore records only calls within the selected frame-sync scope.
Timed event waits retain their actual original loops; instrumentation has nonzero
overhead and this experiment makes no uninstrumented performance claim.

- 23 focused tests passed, including compiled bounded C++ journal, preparation/
  camera absence, exact four-binary freeze binding, unchanged fence calls, original
  cleanup/readback tests and union clipping. The1308-file prospective source archive
  reproduced all23 tests in a separate extraction before live.
- 1537 native rows/80 original receipts absent and768 rows/2 receipts2K reproduce
  exactly with the previously corrected replay binary. Every startup observation
  matches. This is original-time replay, not a new live trial or changed ECU code.
- Frozen readers reproduce both shadow audits, timing audits, the full comparison
  and timeline. The retained-evidence checker also rejects21 corruptions of journal
  completeness/timestamps, renderer/preparation/camera configuration and pair identity.
- The first isolated Engine link failed to resolve the new RenderCore selector
  because it searched the installed baseline library. The corrected builder links
  the isolated RenderCore first; the failed script, generated sources and logs are
  retained in `build-01` and `checks`. It launched no server. `build-02/manifest.json`
  pins successful commands, generated sources and all four runtime hashes.
- There are no new raw images to archive. [Raw manifest](raw-manifest.json) records
  zero packets, and future quality exclusion remains **8978** with a hash-linked
  copy of the prior list. No holdout was accessed or recycled.

The source archive is not a standalone UE distribution. Rebuilding instrumented
libraries requires the external UE/CARLA/object inputs pinned in the build manifest.
Retained-log audits and source tests do not require launching a server:

```bash
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_fence_compare_v1/check-evidence.py \
  --work build/m10-fence-compare-v1/reproduce-NEW
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_fence_compare_v1/check-live.py \
  --work build/m10-fence-compare-v1/audit-NEW
```

## Next implementation boundary

The selected prototype direction is a separate rendering process consuming bounded,
immutable snapshots from one authoritative physical owner. See the
[ownership, scene provenance and verification contract](../../../interfaces/perception-render-isolation-v1.md).
First resolve the camera-free eligibility/input failure from retained replay. Then
verify the owner alone and a render-stall injection before another declared2K
trial. No fence removal, fabricated fresh state, longer deadline or continuous
driving acceptance follows from this comparison.
