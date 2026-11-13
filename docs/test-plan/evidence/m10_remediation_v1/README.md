# M10 remediation: thermal bottleneck isolated, recording improved

Five prospectively frozen experiments remain **FAIL** under unchanged native
acceptance. No failed case was retried as a replacement; the other declared
30s cases and every conditional300s case are NOT_RUN. M10 remains OPEN.

| Series | Normal / protection / INIT intervals | Raw / inference calls | First fault after initial | Recorder overflow |
| --- | ---: | ---: | ---: | --- |
|V4|0 / 0 / 87|16 / 8|0.449s|none|
|V5|0 / 0 / 28|10 / 3|0.159s|none|
|V6|57 / 5781 / 162|39 / 27|1.135s|[341]|
|V7|254 / 5580 / 166|58 / 46|2.129s|[352]|
|V8|667 / 5163 / 170|300 / 293|4.212s|none|

V8 preserves2K2560x1536/Epic and limits renderer ticks to10Hz wall time. It records
300 actual camera callbacks and293 numerical calls,292 beginning during physical
execution, with zero lost raw packets and no recorder overflow. Both servers exit
normally. Its6000 intervals contain667 normal and5163 protection intervals; only
3.335 model seconds are normal. It is not a passing30s control test. Scene-to-
result latency median141.725ms/max487.287ms also does not meet the original100ms
freshness bound. All perception results remain unavailable for control.

## Observed causes and implemented changes

- Original raw storage was on a rotational HDD. New owned-process CPU placement
  keeps SMT siblings together; actual evidence is recorded to verified NVMe and
  copied, fsynced, hashed and independently checked before removing its spool.
  This alone did not cure the timing failure (V4).
- RR8 priority alone did not help (V5); it is an explicit rejected experiment,
  not the recommended default. Original native FIFO18 remains unchanged.
- The CARLA synchronous loop busy-spins when the RPC queue is empty. A new
  explicit idle-wait flag sleeps only after no tick was admitted,50us for a
  bound physical owner or500us before binding/in the renderer. No source time,
  model step, authority, expiry or deadline is changed (V6).
- V6 recorded CPU100C at initial+0.432s, then all sampled cores around0.8GHz at
  +1.449s/+2.462s and increasing thermal-throttle counters. V8 also shows counter
  increases and a subsequent0.8GHz interval near the4.212s native fault. This is
  real host throttling, not merely an inference timestamp issue. One-second
  samples do not determine the cause of every individual missed interval.
- V7 disables ORT idle-worker spinning explicitly, verifies the live setting,
  and reuses per-thread Zstd buffers while copying only compressed bytes. The
  model/precision/thread count, lossless codec and all raw checks remain.
  The offline numerical comparison does not claim raw bit-exactness; decoded
  object identity is retained within the recorded small floating differences.
- V8 reduces actual image generation, preserving every frame that is generated.
  This eliminates recording overflow in that one30s run but still fails control.
- Missing native packets are now distinguished from CRC/decoding, clock-domain,
  route and payload errors. The same fail-closed decisions remain;24 C++ tests
  pass and a new CARLA module compiles. This diagnostic-only header change was
  made after the live series and is not claimed as a live fix for absent input.

## Evidence and verification

See [observations.json](observations.json), the V4–V8 sibling bundles and their
immutable protocols, source archives, `case.json`, original verdicts, exact
native replays and independent archive checks.423 newly generated camera frames
are retained; cumulative future-evaluation exclusion is9774. No holdout was read.
The active CARLA module/INI were restored exactly; [restoration.json](restoration.json)
records identities. Candidate builds are retained outside the active runtime.

Python469 and C++24 checks pass. Original replay and all raw/tensor/hash chains
are separately preserved. Tests do not convert live failures into acceptance.

The [DXC lifetime fix](../m10_dxc_lifetime_v1/README.md) reproduces the original
shutdown deadlock with two negative controls, passes all six candidate standalone
exits, and passes two actual empty CARLA server exits in 2.569s and 2.219s. A second
scripted standalone verification reproduces the same outcome. The single fixture
shader is byte-identical; this is not a full shader-equivalence or control test.
The original DXC library is also restored and its identity rechecked.

Remaining normal-operation work needs a host that sustains load without thermal clock
collapse, followed by new30s repetitions and only then300s. Full same-frame
wheel/bone/material fidelity, independent detector quality, native perception
acceptance and each Jetson deployment remain outside these diagnostic passes.
