# M10 bounded endurance V1

Prospective series: three separately started30s normal cases, followed by one
continuous300s case only if all three original audits pass. A failed case is
retained, never replaced by a retry. A harness defect requires a new freeze and
an explicit disposition of remaining cases. This is Host diagnostic concurrency,
not full M10, route driving, perception-control or independent detector quality.

Each case has one native INIT and one continuous physical session:6000 or60000
original5ms intervals. No resets, epoch stitching or replays count as elapsed
live time. HV30ms, original ECU periods,4ms execution/preview checks, command
expiry and exclusive100ms perception freshness remain unchanged. The source
world is camera-free; the separate Epic2560×1536 renderer uses50ms model steps,
20Hz capped original receipt queries and D-FINE-M960 diagnostic inference.

The scene has the same ego, parked car, walker, camera calibration and frozen
environment as paired V7. The request scenario retains original acceleration
until3.5s and deceleration until4.5s, then holds braking demand0.5 with hold=true.
It keeps rendering, inference and native watchdogs active after stopping without
driving the short fixed fixture off its road. It does not claim sustained driving
or perception quality across varied scenes. All inference remains unavailable
for control; full same-frame bone/wheel/material state is still absent.

The diagnostic harness is explicitly extended, not a vehicle safety timeout:
an opt-in CARLA flag selects6000/60000 retained solver entries and a finite ingress
capacity of5×frames+4096; default950-frame admission/1024-entry storage remains.
Raw solver entries are preallocated before native START and are never overwritten.
Native recording/watch capacity covers duration+5s, with a1s pre-start allocation
lead instead of50ms. Its actual release periods/deadlines are unchanged. Python
execution is bounded by duration+4s and the existing700ms no-progress condition.
Native post-STOP file export gets30s; normal server SIGINT shutdown still gets30s.
The original engine binaries remain; only the declared CARLA module and native
diagnostic executable are rebuilt and bound into the prospective source freeze.
The original CARLA module is restored after the series, including failures.

Every real camera callback is retained losslessly. Two recording workers use
Zstandard level1 into immutable256MiB tar shards, with queue8 and finite frame/
byte budgets. Actual RGB hashes of all callbacks join cumulative future-evaluation
exclusion. Raw buffers awaiting association are bounded8, and inference retains
one active and one pending latest input. Every numerical output is retained.
Queue/frame/byte overflow is FAIL; emergency retention preserves the triggering
frame. Recording is part of the measured workload. Raw artifacts are linked into
evidence without a second full disk copy. Every raw/tensor/hash chain is audited.

Post-measurement physical trace extraction streams gzip JSONL one receipt at a
time. Duplicate harvest responses are represented by indices in the event log;
their complete original receipts/substeps remain in trace/ingress evidence.
Declared capacities bound observation, IPC, stage and numerical records. Resource
sampling reports one-second owned-process RSS/CPU and available RAM/disk; it
stops on less than2GiB RAM or disk reserve. This does not itself prove absence of
memory leaks: expected retained-metadata growth and measurement duration matter.

PASS requires all requested original intervals, zero protection/fault/missing/
late/expired intervals, original physical and shadow audits, exact native replay,
zero accepted perception results, all scene/image/numeric provenance joins,
no recorder loss or unrelated cleanup error, restored INI and normal server exits.
At least one real inference must begin in every5s measurement window;20Hz camera
or inference throughput and sub100ms latency are observations, not pass targets.
Partial execution is FAIL even when its retained prefix replays exactly.

Build/header-cache preparation and recorder throughput tests precede live cases.
The recorder preflight repeats an already excluded V7 image, not a new sensor
observation. Earlier V4/V6 failures remain unchanged and are not cured by this
new configuration or by any passing short case.
