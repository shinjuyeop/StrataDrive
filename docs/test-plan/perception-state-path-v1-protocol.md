# M10 state-path profiling V1

The original300s trial remains FAIL: HV dependency32.720ms, first protection at
4.599s, with a nearby all-core800MHz observation. Its immutable evidence and all
earlier failures remain retained. This protocol diagnoses the path without
changing control logic, source timestamps, periods, deadlines or host settings.

Declare `normal-30s-01` once. If and only if its original physical/shadow/replay
audits and state-path trace integrity pass, execute one `normal-30s-02` repetition
with the same frozen inputs. Stop this sequence on the first failed case. No
replacement trial,300s escalation, holdout access or Jetson optimization here.

Use the selected F/G/H 2K/Epic/D-FINE-M960 settings, Host V1 CPU placement,
5ms physics, original native2/4ms/HV30ms/perception100ms, camera100ms model period,
renderer50ms model step/20Hz wall cap, raw NVMe BGRA, parked preparation, passive
ORT, CUDA blocking, OpenCV4/resize4 and renderer MaxFPS60. Install the new isolated
CARLA/native build and the previously verified DXC candidate, after checking the
original runtime. Freeze all source, protocol, runner and external identities.

Opt in with `--profile-state-path`. The CARLA owner preallocates one fixed-size
POD timing record per allowed frame; serialization occurs on retained trace
queries after the physical interval. Record monotonic and thread-CPU clocks at
admission, staging, pre/post physics, original acquisition, solver-work formatting,
publication and completion. Preserve the original acquisition stamps. Native
records one bounded row per existing service call: wake/read, consumed frame and
source, service, proof publication and thread CPU. Join by original frame/source;
do not add shared-memory ABI fields or grant any perception authority.

Keep the existing500ms owned-tree/NVML profiler, now also recording already-read
minor/major fault counters. Add a separate observer-core20Hz sysfs sampler using
cached file descriptors. Record sequential sample brackets, read failures,
unavailable energy counters and its CPU cost. Do not grant privileges or change
clock/power/cooling policy. Frequency samples alone do not identify cause.

Before live: Python regression and native boundary tests, profile-enabled30/300s
allocation/start/stop checks without CARLA, and a quiet clock-cost microbenchmark
(11 paired stamps plus two benchmark stamps; p95 thread CPU below50us). Require
CPU≤70°C within180s, RAM available≥4GiB, NVMe/archive free≥existing30s stored bound
plus4GiB. Keep the original live2GiB reserves. No build/compression during live.

Each case keeps the unchanged joint/shadow/replay verdict separately from new
diagnostic trace integrity. Record incomplete/missing clocks or associations as
diagnostic failures, not as a physical PASS. Compare wall/thread CPU by stage,
source→publication→native and HV dependency age, plus nearby50ms host counters.
A finite pass without the earlier clock-drop event does not explain that event.

Restore original CARLA/DXC/INI after each case. Seal, independently verify every
raw BGRA/RGB hash and frozen original verdict, then remove only the duplicate
NVMe spool. Chain all images from the previous14633 exclusions. Post-run lossless
tar compression requires whole-byte equivalence. Follow artifact-storage.md:
raw/run archives stay local and ignored; publish code, conditions, summaries,
core review traces and hashes. M10 and native perception acceptance remain OPEN.
