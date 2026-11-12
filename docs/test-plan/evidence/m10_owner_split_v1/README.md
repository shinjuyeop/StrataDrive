# M10 owner-only5ms V1: retained observer failure

2026-11-12. **FAIL**, one live attempt `owner5ms-01`. The original native owner
completed one physical interval and8 service rows without a native fault. The
Python observer rejected the first5ms snapshot because its clock still required
10ms. The client stopped explicitly on the observer error. No image, live model
call or normal physical interval occurred. Server exit130/native exit0 and cleanup
were clean; settings were restored and all four server binaries remained original.

## Diagnosis preceding this attempt

The previous camera-absent80-interval failure is preserved in
[the fence pair](../m10_fence_compare_v1/README.md). Its1537 native service rows and
80 solver receipts reproduce exactly before and after adding5ms replay support.
The original status first reports `native_command_interval_or_causal`, then
`native_wheel_interval`, then terminal `native_protection_authority`.

[Decoded original commands](command-audit.json) at native observation
1483256182313225 show all three commands expiring at1483256194611800. Their remaining
coverage is12.298575ms, less than the10ms physical interval plus unchanged4ms preview
by1.701425ms. The5ms+4ms command-only margin at that observation is3.298575ms. This
is not the exact server admission timestamp or a guarantee that all other inputs
would permit5ms execution. The existing coupled admission test and historical
[nonvideo wall5 investigation](../m7_carla_wall_guard/carla-runtime/nonvideo-wall5/README.md)
already describe this feedback/admission dependency; it is not a newly fixed ECU bug.

The explicit owner profile therefore selects existing5ms physics with400 intervals,
NullRHI/inline rendering and no camera. Controller20ms, Zone/ECU10ms, owner2ms/4ms,
preview4ms, HV30ms, source/receipt100ms and320 substeps remain. The default10ms camera
profile is unchanged. This does not adopt the historical opt-in HV50 allowance.

## Evidence and limits

- [Prospective protocol](../../perception-owner-split-v1-protocol.md),1315-file
  source/runtime freeze, separate archive build with27 Python/23 C++ admission
  tests;38 wheel tests also passed in the existing build.
- The first27-test run had a test-fixture parent-directory error; its log is kept.
  The real5ms callback path was missing from those tests. The new
  [V2 correction](../m10_owner_split_v2/README.md) adds that regression and retains
  this failed run and source archive unchanged.
- `run.tar.gz` retains original server/client logs, state/IPC/error record,
  complete physical/solver/CAN/native data and lifecycle. `run-manifest.json`
  identifies every original member by size/SHA256. The shared-memory bridge file
  is excluded; original exported messages and receipts are retained.
- The shadow integrity audit passes with zero camera results. A fresh frozen-source
  native replay reproduces all8 rows/one receipt and startup observations exactly.
  Neither integrity result changes the observer failure to a driving PASS.
- No raw image or holdout; future exclusion remains8978. Restoration hashes are in
  `restoration.json`. `evidence-manifest.json` seals post-run files separately from
  the prospective freeze.

Reproduce without launching CARLA:

```bash
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_owner_split_v1/check-evidence.py --work /tmp/owner-v1-NEW
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_owner_split_v1/check-live.py --work /tmp/owner-v1-audit-NEW \
  --replay-binary /tmp/owner-v1-NEW/build/tests/integration/carla/m7_1g/m7_wall_startup_replay
```
