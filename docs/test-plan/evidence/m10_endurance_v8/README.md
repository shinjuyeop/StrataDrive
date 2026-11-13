# M10 endurance V8: retained failed experiment

2K/Epic renderer capped at10Hz wall time; physical5ms unchanged. See the [prospective protocol](../../perception-endurance-v8-protocol.md)
and [combined diagnosis](../m10_remediation_v1/README.md).

The first declared30s case failed. The remaining two30s cases and conditional
300s case are NOT_RUN, not replacement retries. Original verdict:
`original native physical acceptance`.

- Original intervals: 6000 (667 normal / 5163 protection / 170 INIT).
- First native fault: initial+4212.012388ms; `native credit/gate closed leaf=0 code=9 leaf=1 code=9 leaf=2 code=5 leaf=3 code=2 leaf=4 code=14`.
- Raw callbacks: 300; numerical calls: 293 (292 begin during physics).
- Recorder overflow frames: []; all generated camera callbacks retained.
- Exact native replay: 30004 services / 6000 receipts.
- Independent frozen archive check: PASS; original failed verdict reproduced.
- Cumulative future-evaluation exclusions: 9774; accepted perception0, no holdout.

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
