# M10 renderer replay V1: retained clone creation failure

2026-11-12. **FAIL_CLONE_SPAWN_COLLISION**, one declared `renderer-01` attempt.
The renderer loaded Town03_Opt, but CARLA rejected creating a clone at the original
already-settled body pose. The failure occurred before camera creation:0 images,
0 frame associations,0 inference and no live physical owner. Client exit1/server
SIGINT exit130; no forced stop or cleanup error. Original runtime/settings restored.

The [V1 protocol](../../perception-render-replay-v1-protocol.md) and1327-file source
archive were frozen before launch.23 focused tests passed locally and from the
archive; Python436 regression tests passed. Those checks did not exercise actual
CARLA spawn collision. The separate [V2 correction](../m10_render_replay_v2/README.md)
adds spawn preparation and keeps this failed attempt/source archive unchanged.

The new typed image association preserves original physical and renderer clocks,
and cannot publish incomplete kinematic scenes as perception. The intended
diagnostic reuses original owner5ms receipts810/1009/1209 with unchanged acquisition
times; it does not supply live physics, complete scene fidelity or camera freshness.

`run.tar.gz` retains every original server/client/readiness log and result; its
member hashes are in `run-manifest.json`. The integrity reader reproduces the
original pose bytes and failure without starting a server. Evidence integrity
PASS does not alter the live FAIL verdict. No holdout or new image; future quality
exclusion remains8978. `restoration.json` records the four unchanged server binaries.

```bash
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_render_replay_v1/check-evidence.py --work /tmp/render-v1-source-NEW
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_render_replay_v1/check-live.py --work /tmp/render-v1-audit-NEW
```
