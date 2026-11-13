# M10 endurance V7: retained failed experiment

Passive ORT threads and lossless compression-buffer reuse. See the [prospective protocol](../../perception-endurance-v7-protocol.md)
and [combined diagnosis](../m10_remediation_v1/README.md).

The first declared30s case failed. The remaining two30s cases and conditional
300s case are NOT_RUN, not replacement retries. Original verdict:
`original native physical acceptance`.

- Original intervals: 6000 (254 normal / 5580 protection / 166 INIT).
- First native fault: initial+2129.016907ms; `native credit/gate closed leaf=2 code=5`.
- Raw callbacks: 58; numerical calls: 46 (46 begin during physics).
- Recorder overflow frames: [352]; all generated camera callbacks retained.
- Exact native replay: 30003 services / 6000 receipts.
- Independent frozen archive check: PASS; original failed verdict reproduced.
- Cumulative future-evaluation exclusions: 9474; accepted perception0, no holdout.

All original HV30ms,2/4ms execution bounds and100ms perception expiry remain.
Physical span may include protection and cannot be called successful endurance.
`case.json`, frozen source archive, all raw shards, numerical outputs and original
traces remain in this bundle. The NVMe spool was removed only after independent
archive/raw/verdict verification. The shared original CARLA module was restored
after the series of experiments; see the combined restoration record.

Metadata note: the original `case.json` retained the V4 protocol label.
[metadata-erratum.json](metadata-erratum.json) identifies this series' applicable
protocol, already present in its frozen sources. Original case bytes and verdict
are unchanged.
