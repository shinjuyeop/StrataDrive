# M10 Host profiling V4: separate camera cadence from render/readback cadence

V3 E (RR8 physical server) remains FAIL with0.325s normal, despite no sampled
thermal-counter increase during execution. Retain every earlier failed case;
priority alone is not a demonstrated remedy. D remains the preferred measured
CPU/recording candidate, with CFS physical scheduling and shared renderer cores.

D's source-to-camera-callback median is99.604ms, callback-to-inference1.326ms,
and preprocessing/inference pipeline36.884ms. This motivates one new F 30s
diagnostic case: retain camera10Hz but request renderer ticks up to20Hz. Renderer
model step stays50ms; set actual camera sensor_tick to100ms model time, so it
captures once every two model ticks. Render pacing becomes50ms wall time, with
the original latest-scene20Hz query cap. Verify actual sensor attributes, frame
associations and original timestamps. A faster render/readback opportunity is
not a new image, dropped image, repeated capture or timestamp rewrite.

All other D settings stay:2K/Epic, CFS physical server, native FIFO18, Host V1
shared cores4–7, parked preparation, renderer MaxFPS60, raw NVMe spool, OpenCV4,
resize4, passive ORT, CUDA blocking host wait. Raw mode permits only the declared
(renderer10Hz,camera50ms) or(renderer20Hz,camera100ms) pairs, both targeting actual
camera10Hz. Existing byte/queue/frame budgets and live hash checks stay.

Original physical5ms, ECU2/4ms, HV30ms and perception100ms bounds are unchanged.
Full visual fidelity and perception acceptance remain unavailable. Freeze sources
before the one F attempt, retain failures and exact replay outcomes, and restore
the shared original module/DXC/INI. Compare actual callback cadence, freshness
distribution, CPU/GPU cost and native stability; no 300s or general optimum claim.
