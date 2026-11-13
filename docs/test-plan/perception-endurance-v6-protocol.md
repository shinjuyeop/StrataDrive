# M10 bounded endurance V6

V5 RR8 failed after28 original intervals: acquisition itself remained below
1.7ms, then no new receipt arrived before HV30ms expired. Owner RR8 was verified;
the observed maximum pump gap was53.45ms. System RT bandwidth is950ms/1s, but
these observations alone do not prove throttling caused that gap. V5 is retained
as FAIL; the other cases are NOT_RUN. Its10 raw callbacks join exclusion history.

V6 returns to V4 ordinary owner scheduling and its complete-core/NVMe profile.
The new explicit -StrataM10IdleWait module option prevents the synchronous loop
from busy-spinning when RPC io_context.run_for has no work. Only after PumpWall
returns false, sleep at most50us for a bound owner (clamped to the next future
physics release), or500us for a renderer/pre-bind server. Never sleep after a
physical tick is admitted. An OS wakeup may overshoot; original deadline audits
must detect that, not retime sources or extend budgets. Default mode is unchanged.
The CARLA module is rebuilt from source, frozen and restored after the series.

One-second read-only telemetry adds CPU frequencies, core/package temperatures
and thermal-throttle counters. No clock, cooling, power or kernel policy changes
are made. The existing host reports a large historical throttle counter; only
new interval deltas can support a claim about this experiment.

V1/V3 acceptance, V4 lossless NVMe archival and stop-on-first-failure apply to
three prospectively declared30s cases and conditional300s. Model5ms, HV30ms,
native FIFO18,2/4ms checks and100ms perception expiry remain unchanged. All raw
images and exact native timestamps are retained. No retry replaces a failure.
No accepted perception result, quality promotion, holdout, complete-visual-scene
claim or Jetson deployment is authorized by this diagnostic series.
