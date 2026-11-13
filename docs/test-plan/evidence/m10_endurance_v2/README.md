# M10 endurance V2: schedule storage failure retained

V2 fixed the request-profile and WallRig diagnostic horizons while preserving all
native guards. Its first30s setup then failed before physical INIT because the
original TaskSchedule had capacity for10000 jobs, less than the declared35s
recording window on its2ms grid. Zero physical intervals, six preparation frames,
no inference. Cases2/3 and300s were not run.

The [protocol](../../perception-endurance-v2-protocol.md), source/runtime freeze,
original stderr and raw images are retained. C++59 and archived-source51 checks
passed. `preparation/` also preserves an earlier, unused source snapshot and
incorrect missing-input test fixture; no live attempt used that snapshot.

Extraction reproduced the original frozen audit failure and verified every raw
BGRA/RGB hash. Cumulative future exclusion is9283. No holdout was accessed.
[V3](../m10_endurance_v3/README.md) adds explicitly bounded watch storage and a
complete executable initialization preflight before any further live attempt.
