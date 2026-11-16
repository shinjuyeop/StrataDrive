# M10 owner wait V2

Owner wait V1 failed before native startup: the second synthetic preparation call
was151.561ms, including119.010ms tensor conversion and21.156ms model inference.
Pipeline CPU placement and CV4/resize4 were already correct. Retain that original
FAIL, zero receipts and zero raw images; it supplies no new HV diagnosis. Original
wall stamps do not identify allocation, kernel or scheduling as the root cause.

This separate candidate enables the existing TensorWorkspace only through
`--tensor-workspace`. Both physical-owner preparation and renderer inference
select the same backend explicitly. Reuse one contiguous float32 NCHW buffer and
the original target-size array; enforce a single synchronous inference owner.
All256 byte values and random images must remain exactly equal to the original
float32 division; no precision, resolution, detector, output or provenance change.
Support the existing finite4096..6400 trace capacity for the300s run. Record the
effective workspace flag in both process reports. Record restored observer CPU
affinity even when preparation fails. Defaults remain unchanged.

The prior latency study's mean-speed decision remains unchanged: it did not meet
its3ms threshold. This candidate addresses recurring preparation tails. The
fixed40-process alternating study at original cap100 without CARLA passed20/20
baseline and20/20 workspace. Maximum settled calls were37.993/34.908ms. This
quiet study did not reproduce the live tail and does not prove its cause or fix.
Do not retry or relabel the failed V1 run. Preserve the10s total, exactly three
preparation calls and last-two<100ms gate.

Reuse the exact owner-wait V1 module (SHA256
297e5179ab76d4e818fcd53e6a23794c75068d0d9b20408679bcff921256bfb3)
and unchanged native binary. All505 Python tests and93 focused frozen tests must
pass. Reuse the identical module's10000-stamp cost measurement, fixed-size budget,
207 native tests and30/300s allocation checks. Freeze all effective sources and
the separate runner/protocol before live execution; original V1 freeze remains.

Keep the owner-wait V1 counters, original clocks, HV30ms, gate/check order,
physics5ms/320steps, native2/4ms, model100ms,2K2560x1536/Epic/D-FINE-M960/CUDA,
camera100ms and renderer/query20Hz. Keep selected Host V1 placement, passive ORT,
CUDA blocking, parked preparation, renderer MaxFPS60, CV4/resize4 and NVMe raw.
Keep the existing bounded70% helper, original minimum16% and turbo enabled.
Only the narrow root helper changes max_perf_pct100->70->100; it binds to the new
unprivileged sequence owner and restores on owner exit, handled signal or1800s.

Use unchanged preflight CPU<=70C/180s, RAM>=4GiB, horizon storage+4GiB,
startup180s, shutdown30s and live reserve2GiB. Run30s then another30s then300s,
advancing only after all original audits, replay and frozen reproductions PASS.
Stop the first original failure without same-candidate retries. Do not build,
test or run independent archive jobs during live concurrent work. After each
run verify both effective workspace flags, preparation deadlines and restored
observer affinity from original reports; absent metadata cannot establish that
the candidate ran. Preserve all failures/raw images and chain exclusions16633.

Finite diagnostics do not establish long-term stability, native perception
acceptance, complete scene/independent quality, each Jetson deployment or M10.
