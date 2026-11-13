# M10 endurance V1: setup failure retained

The first declared30s case failed before native INIT because its310000ms request
phase exceeded the existing10000ms profile validator. Zero physical intervals,
six preparation camera frames, no inference. The remaining two30s cases and
conditional300s case were not run. No failed physical case was retried as a pass.

The [protocol](../../perception-endurance-v1-protocol.md), source/runtime freeze,
build recipe and original setup output are retained. The recorder preflight
successfully preserved120 repeated, already-excluded frames at20Hz; this was not
a live workload guarantee. C++57 and Python464 regression checks passed before
the attempted setup. The source archive reproduces51 focused checks.

The frozen auditor's missing-native-file failure was reproduced after extraction.
All six lossless originals and RGB hashes were verified. The post-run checker
only normalizes the extraction prefix of missing-file error paths; its identity
is in `verification-tool.json`. Cumulative future exclusion is9277, holdout
access=false. [V2](../m10_endurance_v2/README.md) corrects the harness horizon.

The isolated CARLA module build used original link objects and regenerated UHT
headers after earlier cache cleanup. The retained build manifest identifies the
exact inputs/generated unity membership. Original engine binaries were not
rebuilt. [Final restoration](../m10_endurance_v3/restoration.json) verifies the
original CARLA module, engine libraries, executable and INI after the whole series.
