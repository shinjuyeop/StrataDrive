# M10 endurance V3: repeated normal operation failed

Three independently started30s cases were declared under one freeze. None passed.
The conditional uninterrupted300s case was **NOT RUN**. The earlier finite2s
concurrency passes remain valid within their scope; repeated/long operation is
not accepted, and M10 remains open.

| Case | Original intervals | Model / physical wall span | Normal / protection / INIT | Raw / inference | Verdict |
| --- | ---: | --- | --- | --- | --- |
| 01 |6000|30.000 /29.9943s|20 /5818 /162|35 /24|FAIL: original HV30ms bound; recorder overflow |
| 02 |106|0.530 /0.5391s|0 /0 /106|17 /10|FAIL: startup protection, incomplete Actual ingress; renderer forced exit |
| 03 |87|0.435 /0.4477s|0 /0 /87|16 /9|FAIL: startup protection, incomplete Actual ingress |

Physical wall span is first actual acquisition start through final completion;
it includes INIT/protection and is not the duration of successful perception.
Case01's renderer/inference stopped early. Its6000 intervals do not establish
30s of normal simultaneous operation. Cases02/03 never armed normal authority.

Case01 first exceeds the HV dependency limit at30.096845ms and reaches31.097248ms
in the last armed samples. Native protection is recorded935.016234ms after its
initial origin. The lossless recording queue later reaches8 and emergency-retains
frame334, about1081.980ms after that first native fault. Write duration has
median102.576ms and maximum728.140ms; scene→result median108.829ms, maximum543.473ms.
The isolated20Hz recorder preflight did not predict throughput under the combined
live workload. This chronology does not prove that queue overflow caused HV expiry.

Cases02/03 report Drive local-input failure before normal operation. Their final
rejected ingress has missing steering/brake Actual packets; the available Drive
packet passes CRC/domain/route checks. `native_owner_wire_route_crc` is a combined
decoder label, **not evidence of corrupt CRC bytes** here. The original audit
rejects `accepted=false` as `original ingress clock`. No missing input is fabricated.

Case02's renderer did not exit within the unchanged30s shutdown allowance and
was killed. The retained stack shows the main thread waiting on a mutex in
`libdxcompiler.so` during finalization, with a TraceLog thread still present;
this is a location observation, not a confirmed engine root cause. The other
servers exited normally. All INIs and original runtime modules were restored.

Available system RAM stayed above11.99GiB and `/d` above73.77GiB during the
observed windows. No reserve stop occurred. These samples, shortened rendering,
and retained-metadata growth do not establish absence of leaks or GPU memory
stability. No sustained20Hz or100ms latency guarantee is claimed.

The [V3 protocol](../../perception-endurance-v3-protocol.md) retains the V1/V2
physical5ms, HV30ms, original2ms/4ms monitor, expiry and exclusive100ms limits.
Only finite diagnostic horizons/storage are extended. Default10000-job schedule
capacity remains; explicit long storage is160000 jobs, with one original slot per
release. The real native executable passed30s/300s allocation/START/STOP preflight
without CARLA. This preflight is not counted as endurance. C++91, Python464 and
frozen-source51 checks passed; source archive contains1362 files.

Original native replay is exact for all30002/584/486 service calls and6000/106/87
receipts, including failures. Replay input/output and manifests are retained per
case. All three frozen paired audit failures reproduce from archived evidence.
Separate shadow integrity passes with zero accepted perception results. Every
raw BGRA/RGB hash was independently checked even when physical audit failed
first. The68 live images plus12 setup images are all retained; cumulative future
exclusion is9351 and no holdout was accessed. Full scene/inference provenance
acceptance is not claimed for these failed cases.

`observations.json` is post-run analysis from `analyze.py`; it does not replace
the frozen auditor. `disposition.json` records the conditional stop. Raw shards
are hard-linked into evidence to avoid a duplicate full image store. To reproduce
the frozen source checks:

```sh
build/m10-perception/cuda-venv/bin/python docs/test-plan/evidence/m10_endurance_v3/check-evidence.py --work /tmp/m10-endurance-source-check
build/m10-perception/cuda-venv/bin/python tests/integration/perception/check_endurance_archive_v1.py --series docs/test-plan/evidence/m10_endurance_v3 --bundle docs/test-plan/evidence/m10_endurance_v3/normal-30s-01 --work /tmp/m10-endurance-case01-check
```

The next work is to trace original HV acquisition/dependency ages and startup
Actual availability, then isolate recording CPU/I/O contention and renderer exit.
Retain the original limits and declare a new series only after a concrete fix.
Complete wheel/bone/material provenance, independent detector quality and Jetson
deployment remain subsequent work; no board optimization or control promotion
was performed in this experiment.
