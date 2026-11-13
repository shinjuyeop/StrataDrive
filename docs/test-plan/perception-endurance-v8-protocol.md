# M10 bounded endurance V8

V7 still failed:6000 intervals included254 normal,5580 protected and166 INIT;
recorder queue8 overflowed after58 raw callbacks. Reduced buffer copying and
passive ORT workers did not establish stable concurrent operation. Keep the
failed case, both offline numerical checks and remaining NOT_RUN dispositions.

The user accepts a lower camera rate instead of requiring20Hz. V8 explicitly
caps renderer world.tick requests at10Hz wall time, including the eight camera
preparation ticks.2560x1536/Epic, D-FINE-M960, renderer model step50ms, original
20Hz scene-receipt query cap and native physical5ms/ECU timing remain unchanged.
Renderer model time therefore advances more slowly than wall time; no claim
of20Hz footage or rendering real-time factor1 is made. The physical world is
independent. No catch-up burst: next render is at least100ms after the preceding
tick request. Fetch the latest scene only when a new render is due; never
rewrite original source, callback, association or inference timestamps. Every
camera callback actually generated remains losslessly retained and excluded.

This workload reduction specifically tests whether avoiding CPU thermal
collapse makes original HV30ms/2ms/4ms deadlines sustainable. V7 passive threads,
buffer reuse, V6 idle-wait module and V4 ordinary scheduling/NVMe profile remain.
Kernel, clocks, thermal limits and cooling are unchanged. Declare three30s cases
then conditional300s under the same immutable failure/stop-on-first-failure
rules. All original physical, shadow, raw-provenance and exact replay audits
must pass. The existing5s inference-coverage requirement remains. Full visual
fidelity and accepted perception remain unavailable; no holdout or deployment.
