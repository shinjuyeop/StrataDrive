# M10 Host 300-second diagnostic: original FAIL retained

Executed 2026-11-16 under the [prospective protocol](../../perception-host-endurance-v1-protocol.md).
One attempt used exactly the selected F/G/H runtime and settings, changing only
the supported horizon from30s to300s. The earlier three30s passes remain valid
for their finite runs; they did not establish300s stability. No replacement run
or deadline change was made.

## Result

| Measurement | Original result |
| --- | --- |
| Joint audit | **FAIL**: `normal HV source/dependency budget including preceding sample` |
| Physical interval | 60000 receipts,300.001266s wall including INIT |
| Normal / INIT / protection | 748 /166 /59086; normal model duration3.740s |
| First native protection | 4.599019s after initial; `native credit/gate closed leaf=2 code=5` |
| Native execution slots | 1500020 eligible,0 missing,0 late; body maximum0.299ms |
| Native replay | Exact,300003 calls,60000 receipts,0 different rows; original source fields equal |
| Frozen archive audit | PASS reproducing the original FAIL; all2789 BGRA/RGB pairs and165 raw tar archives checked |
| Camera / inference | 2789 raw images /2785 outputs; recorder overflow0 |
| Physical-span camera / render rate | 9.283Hz /18.567Hz |
| Scene→result median /p95 /max | 78.210 /83.938 /347.206ms;24 of2785 above100ms |
| Physical-span CPU / GPU | Peak98°C; package throttle counter+60, core0 counter+4; GPU median34%, maximum42% |
| Preparation | 88.241s, peak100°C, package throttle counter+38 |
| Resource minima through client collection | RAM available6.428GB, NVMe free25.308GB |
| Shutdown | Renderer28.674s, owner1.818s; both exit130, no forced server stop |
| Shared runtime restoration | Original CARLA module, DXC, INI and recorded engine identities match |

The live runner completed, but its completion does not accept the physical run.
The shadow integrity audit passes while recording the native fault and zero
accepted perception results. Almost the entire300s is protected operation;
aggregate latency/CPU numbers must not be presented as300s normal driving.
The renderer emitted Vulkan allocation-leak warnings during exit; the requested
post10s GDB diagnostic timed out with no stack output. It still exited within
the unchanged30s limit. This is not a clean bill of health for all renderer exits.

## First fault and next investigation

[Fault measurements](normal-300s-01/fault-analysis.json) preserve the first native
row and nearby original receipt times. At protection, the last HV source was
22.175ms old and its dependency32.720ms old, exceeding the unchanged30ms bound.
Receipt914 followed a20.293ms source-end gap; its apply→source duration was5.804ms
and acquisition duration1.075ms. The preceding two receipts also show longer
apply/acquisition durations. Native deadline slots before the fault have no
missing/late completion.

The nearby500ms temperature samples are83/89°C before and74°C after protection,
with unchanged thermal counters. At+249ms and+749ms all16 logical CPUs report
approximately800MHz; the preceding sample's maximum was3.9GHz. This is a host
clock-drop clue, not proof of its cause or exact ordering. The500ms samples do
not distinguish power, thermal, scheduler or IO causes. Later heat remains an
observed problem. Existing schedstat waiting measurements are disabled; no kernel
waiting time attribution can be inferred from zero counters.
Seventeen of the24 over100ms image results end between0.228s before and2.001s
after the first fault, including the347.206ms maximum. The image pipeline also
slowed in this window; this correlation does not make it the physical fault's cause.

Next instrument the physical owner admission/application/acquisition/publication
and native receipt/HV derivation boundaries with bounded, low-overhead monotonic
records, correlated with host frequency/power/thermal observations. Determine
which segment consumes the30ms freshness budget before
choosing an implementation change. Keep5ms physics,2/4ms native, HV30ms and
perception100ms unchanged. Then declare new finite trials, retaining this failure.
Full wheel/bone/material scene fidelity and native perception integration follow
the stability investigation; independent quality and each Jetson deployment stay
separate. No holdout was accessed and no board optimization was attempted.

## Evidence and reproduction

- [Case](normal-300s-01/case.json), [preflight](normal-300s-01/preflight.json),
  [joint audit](normal-300s-01/audit.json), [shadow](normal-300s-01/shadow-integrity.json),
  [replay](normal-300s-01/replay.json), [profile](normal-300s-01/profile-analysis.json).
- `sources.json` / `sources.tar.gz` freeze1401 files and the external identities
  before live execution. The frozen61 boundary tests pass. `prospective-runner.py`
  is part of this snapshot. `analyze-fault.py` is explicitly post-run analysis.
- `run-manifest.json` and `raw-manifest.json` identify the local run and every raw
  member. [Full raw archive verification](normal-300s-01/archive-validation.json)
  passes and the redundant NVMe spool was removed afterward. Future exclusion
  grows from11844 to14633, adding all2789 distinct RGB hashes. Lossless transport
  [compaction](normal-300s-01/compaction-validation.json) verifies all165 original
  tar byte streams before replacement:43.869GB→20.715GB, saving23.154GB. The
  uncompressed manifest and whole-stream equivalence proofs are retained.
  These checks are not physical acceptance.
- Follow [artifact storage](../../artifact-storage.md): raw/run archives remain
  local, ignored by Git. `retained-metadata.tar.gz` is a37.009MB checked review
  subset with25 original metadata/trace members and58 unchanged first-fault
  trace rows. Its internal manifest names the full originals and their hashes.
  Full raw replay requires the local original archives and prior
  exclusion file. Git LFS pull does not restore these new raw/run bundles.
- [Storage closeout](storage-closeout.json) removes1.276GB of byte-checked duplicate
  extractions/replay/profile files. Final observed free space is70.273GB on NVMe
  and444.489GB on `/d`; all local compressed raw/run originals remain retained.
  [Final validation](final-validation.json) rechecks the original runtime hashes
  and records the failed physical verdict separately from successful evidence checks.

To reproduce from the retained local originals, use a fresh work directory:

```bash
build/m10-perception/cuda-venv/bin/python \
  tests/integration/perception/check_endurance_archive_v1.py \
  --series docs/test-plan/evidence/m10_host_endurance_v1 \
  --bundle docs/test-plan/evidence/m10_host_endurance_v1/normal-300s-01 \
  --work build/m10-host-endurance-recheck
```

An archive verification PASS means all original bytes and the **FAIL** verdict
were reproduced. It does not mean the300s stability test passed. M10 remains OPEN.
