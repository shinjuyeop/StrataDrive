# M10 endurance V4: retained failed experiment

Owned-process core placement and verified NVMe-to-HDD archival. See the [prospective protocol](../../perception-endurance-v4-protocol.md)
and [combined diagnosis](../m10_remediation_v1/README.md).

The first declared30s case failed. The remaining two30s cases and conditional
300s case are NOT_RUN, not replacement retries. Original verdict:
`original ingress clock`.

- Original intervals: 87 (0 normal / 0 protection / 87 INIT).
- First native fault: initial+449.015741ms; `native credit/gate closed leaf=2 code=5`.
- Raw callbacks: 16; numerical calls: 8 (7 begin during physics).
- Recorder overflow frames: []; all generated camera callbacks retained.
- Exact native replay: 483 services / 87 receipts.
- Independent frozen archive check: PASS; original failed verdict reproduced.
- Cumulative future-evaluation exclusions: 9367; accepted perception0, no holdout.

All original HV30ms,2/4ms execution bounds and100ms perception expiry remain.
Physical span may include protection and cannot be called successful endurance.
`case.json`, frozen source archive, all raw shards, numerical outputs and original
traces remain in this bundle. The NVMe spool was removed only after independent
archive/raw/verdict verification. The shared original CARLA module was restored
after the series of experiments; see the combined restoration record.
