# M10 Host profiling: selected placement and finite repetitions

Eight prospective Host experiments locate avoidable CPU work and select a
configuration that passes the original joint audit in three finite30s trials
F/G/H. Earlier A–E failures remain preserved. This is the best measured candidate
in this comparison, not a global optimum, a300s result or M10 closure.

## Result

| Case | Change | Normal / protection / INIT | Images / inference | Scene→result median / p95 / max, ms | Original audit |
| --- | --- | ---: | ---: | ---: | --- |
| A | previous shared placement, Zstd live recording | 140 / 5698 / 162 | 299 / 291 | 136.28 / 177.33 / 545.38 | FAIL HV dependency |
| B | parked preparation, blocking CUDA wait, renderer cap | 492 / 5342 / 166 | 299 / 290 | 140.60 / 203.16 / 561.61 | FAIL native acceptance |
| C | separate two-core renderer and two-core image pipeline | 0 / 0 / 154 | 16 / 9 | 165.13 / 172.85 / 174.92 | FAIL Actual age |
| D | shared placement, raw BGRA on NVMe | 3393 / 2437 / 170 | 303 / 296 | 138.52 / 164.80 / 170.96 | FAIL HV dependency |
| E | D with owner RR8 scheduling | 65 / 5769 / 166 | 301 / 294 | 137.67 / 165.96 / 362.60 | FAIL HV dependency |
| F | D with renderer20Hz / camera100ms model period | 5838 / 0 / 162 | 285 / 281 | 76.89 / 85.93 / 120.02 | PASS diagnostic case |
| G | first prospective repetition of F | 5838 / 0 / 162 | 284 / 280 | 77.08 / 87.47 / 158.83 | PASS diagnostic case |
| H | second prospective repetition of F | 5830 / 0 / 170 | 283 / 279 | 77.48 / 93.32 / 328.89 | PASS diagnostic case |

Each F/G/H trial completes6000 physical intervals in30.001–30.002 wall seconds,
with zero protection, late/missing execution slots or expired physics. INIT is
included in the30s duration; normal model time is29.15–29.19s. Original5ms physics,
2/4ms native deadlines, HV30ms and perception100ms bounds are unchanged.

The camera target remains10Hz: a100ms model sensor period with50ms renderer model
steps and a20Hz wall cap. Measured camera callbacks during physics are9.30–9.37Hz;
renderer ticks are18.60–18.77Hz. This gives the renderer/readback path more frequent
opportunities to deliver an image without generating20 images/s. Source→callback
median falls from98.30ms in A to34.62–34.83ms; callback→inference-start median is
1.31–1.35ms. Compute median is40.77–40.83ms, including roughly15.3ms preprocessing
and25.2ms CUDA session work. Marginal medians are not additive.

F/G/H retain852 images and840 numerical results.20/840 results exceed100ms
(3/281,6/280,11/279); the worst is328.89ms. A p95 below100ms is not a hard deadline
guarantee. All native accepted perception counts remain0 because complete visual
scene admission is unavailable, independently of result age.

## Selected Host configuration

Use [the existing V1 CPU profile](../../../../profiles/perception-endurance-host-v1.json)
on this i7-11700/RTX3090 machine. These affinities apply to owned processes, not
exclusive reservation of the operating system's cores.

| Work | Physical cores | Logical CPU IDs | Policy |
| --- | --- | --- | --- |
| authoritative physics owner | 2,3 | 2,3,10,11 | ordinary CFS |
| native ECU/control | 1 | 1,9 | existing FIFO18 |
| renderer and image pipeline together | 4,5,6,7 | 4,5,6,7,12,13,14,15 | shared CFS pool |
| observer and profiling process | 0 | 0,8 | CFS |

Keep SMT siblings together. C's stricter split and E's raised owner priority did
not pass their single declared experiments; neither is selected. The new V3
profile exists to reproduce C, not as the recommended default.

The selected runner options are:

```text
--resource-profile profiles/perception-endurance-host-v1.json
--idle-wait --passive-ort --park-preparation --renderer-max-fps 60
--preprocess-cv-threads 4 --resize-threads 4 --cuda-blocking
--raw-recording --renderer-wall-hz 20 --camera-period-ms 100 --profile-host
```

The complete original command and exact model/library identities are in each
`case.json` and archived `server.json`. D-FINE-M960/CUDA,2K2560×1536/Epic and all
original raw/tensor hashes remain in use. No default model or Jetson configuration
is promoted. Both required candidate libraries are retained separately; the
shared runtime has been restored, so a future live test must deliberately install
the recorded CARLA and DXC candidates again.

## Why the CPU was hot

The Vulkan log selects RTX3090 device1, and ONNXRuntime uses CUDA. Intel device0
being enumerated does not mean that it renders this scene. GPU utilization during
F/G/H has median33.5–34%, peak36–44%; those are whole-device samples, not a kernel
occupancy measurement. CPU time remains necessary for simulation, image handling,
hashing, compression and host-side waits.

- Offline measurements reuse six already-excluded V8 images. CUDA blocking host
  wait reduces mean process CPU per session call from19.75 to10.16ms, while median
  wall duration changes19.49→20.67ms. It changes only the process CUDA scheduling
  flag, preserving other flags (observed8→12). See NVIDIA's
  [device scheduling API](https://docs.nvidia.com/cuda/archive/12.3.0/cuda-runtime-api/group__CUDART__DEVICE.html)
  and [stream synchronization API](https://docs.nvidia.com/cuda/archive/12.2.1/cuda-runtime-api/group__CUDART__STREAM.html).
- Live Zstd1 compression consumes about43ms CPU/frame in A, in addition to image
  conversion and hashing. Recording the original BGRA bytes to NVMe removes that
  compression work from the live interval. Both BGRA and RGB identity hashes are
  still calculated live; no generated frame or alpha channel is discarded.
- Image-process CPU averages1.580 logical-core equivalents in A and0.890–0.933 in
  F/G/H, a41–44% reduction. All monitored owned processes together average2.957
  cores in A and2.345–2.439 in F/G/H, about18–21% lower. These compare whole physical
  spans with different protection histories; they are not identical-load causal
  estimates. Offline stage measurements separately identify avoidable work.
- Parking empty worlds prevents unnecessary asynchronous startup loops. A's
  preparation takes33.90s; B's serialized parked preparation takes61.57s. Lower
  average preparation load comes with slower startup, not a startup speedup.
- Sampled physical-span peak CPU temperatures are100°C in A and95–97°C in F/G/H.
  Package thermal-throttle counter deltas are206 versus0/15/0. Cooling is improved
  in these runs but not solved. Counter15 in G and H's latency tail remain visible.

Heat is not the only source of timing failures. D's first protection near17.835s
follows a19.876ms physical-source gap while sampled temperatures are84–86°C with
no local throttle-counter increase. Apply→source time is only0.823ms and source
acquisition0.150ms: the evidence points to waiting/release timing, not a long
physics arithmetic operation. E also fails without a physical-span throttle
counter increase. We have not attributed every OS scheduling delay to a kernel
call stack.

## Measurement and verification limits

`profile_host_v1.py` samples the owned process tree, every thread's CPU runtime,
affinity, temperature/frequency/counters and NVML at500ms. PID start identities
avoid mixing reused processes. Process CPU is divided by the full phase length;
boundary samples are omitted, slightly undercounting CPU. Monitor overhead and
phase-specific thread totals are retained in each `analysis.json`. All summaries
use linear-interpolated p95; original audits are unchanged.

These are sequential trials with the prepared engine caches and the retained
preflight conditions, not randomized trials or a cold-cache startup guarantee.

`perf_event_paranoid=4` denies even task-clock, and `sched_schedstats=0` disables
runqueue wait accounting. Zero scheduler wait fields do not prove no contention.
No kernel permission, CPU power/clock, other-process affinity or fan setting was
changed. Fan RPM and RAPL energy counters were unavailable. This is measured
process/stage profiling, not a complete kernel-level performance trace.

All preprocessing thread-grid tensors are bit-exact. Offline CUDA outputs are
not bit-exact; decoded classes/counts match on these six excluded inputs, with
maximum score difference2.384e-7 and box difference3.052e-5 in640-coordinate units.
No independent quality or holdout inference follows from this diagnostic check.

B requested OpenCV2 but backend construction restored4. Its actual4 report is
preserved, V1 C was NOT_RUN, and V2 corrected override ordering and explicitly
requested4. There is no replacement of a failed case or post-hoc PASS rewrite.

A/B/D/E/F/G/H native timestamp/solver replays are exact. C is explicitly nonexact:
804 calls/154 receipts retain original source fields but31 replay rows differ,
starting at773. The original wall execution watchdog observes a missed start;
the replay does not reproduce that external monitor wakeup. Original C remains
FAIL, and its nonexact replay is not presented as acceptance. All eight independent
archive/source/raw checks reproduce their original audit verdicts.

Full Python verification passes477 tests. Frozen-source boundary tests pass58
in V1,60 in V2/V3 and61 in V4/V5. No new C++ code was changed in this profiling
series. [Restoration identities](restoration.json) verify original module, DXC,
executable, Engine, RenderCore and INI, with no owned UE4Editor remaining.

## Retention and reproduction

[observations.json](observations.json) links all eight results. V1–V5 each contain
the prospective protocol's source archive, source manifest, runner and original
audit/replay/archive verdicts. Every generated image is retained:2070 new packets,
11844 cumulative future-evaluation exclusions, no holdout access. The new checked
recordings have no recorder overflow.

Raw BGRA costs about4.45–4.48GB per30s selected run. Only after all live work ends,
`compact_endurance_archive_v1.py` wraps sealed raw tar bytes in lossless gzip.
Original live metadata and `run.tar.gz` are untouched. Each compressed transport
is decompressed and hashed against the original complete tar before removing its
uncompressed duplicate. `raw-manifest-uncompressed.json`, `archive-compaction.json`
and `compaction-validation.json` preserve both identities. Original archive checks
refer to the pre-compaction seal; the byte-for-byte expansion proof and dedicated
RawReader/manifest tests verify the changed storage transport. This compression
saves archive space but does not reduce the live NVMe capacity requirement.
A further full independent audit of H using the compressed transports verifies
all283 images and reproduces the original PASS_DIAGNOSTIC_CASE_ONLY verdict; see
[h-repeat2/compressed-archive-validation.json](h-repeat2/compressed-archive-validation.json).
Across D–H it reduces22.90GB of raw tar transport to10.78GB, saving12.13GB
(11.29GiB); see [storage-summary.json](storage-summary.json).

After fetching Git LFS payloads, an independent audit of a retained case is:

```sh
python tests/integration/perception/check_endurance_archive_v1.py \
  --series docs/test-plan/evidence/m10_host_profile_v5 \
  --bundle docs/test-plan/evidence/m10_host_profile_v5/h-repeat2 \
  --work build/m10-profile-independent-h
python docs/test-plan/evidence/m10_host_profile_v5/analyze.py \
  --case h-repeat2 --run build/m10-profile-independent-h/run \
  --output build/m10-profile-independent-h/analysis.json
```

The next live step is a separately declared300s trial of the same selected
configuration, after a temperature and NVMe/raw-archive capacity preflight.
At10Hz,300s needs roughly47GB of raw image payload plus trace, preparation and
safety margin; current finite runs cannot establish that duration's behavior.
Complete visual state, independent detector quality,100ms control availability,
thermal margin and eventual deployment to each Jetson remain separate work.
