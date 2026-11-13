# M10 bounded endurance V4

V1/V3 durations, workloads, acceptance and controller guards remain unchanged.
V3 failed all three cases: physical acquisition slowed to5–9ms around the first
HV30ms expiration; one recorder subsequently overflowed; one renderer timed out
during libdxcompiler llvm_shutdown. None is reclassified by this experiment.

This series changes host placement and evidence storage, not the controller:
the frozen perception-endurance-host-v1 profile assigns complete distinct SMT
cores to owner, native, renderer and observer children. Affinity is applied with
taskset at exec, including nested children, avoiding Python preexec callbacks
in threaded camera clients. It does not reserve CPUs against other host users.
Process resource samples retain actual affinity. Existing native FIFO18 remains.

All live output is written under /tmp/stratadrive-m10-endurance-v4 on the checked
nonrotating NVMe filesystem. All callbacks, raw bytes, compression, queue8,
two workers and frame/byte limits remain in the measured workload. After each
run exits, copy shards to /d evidence, fsync and compare source/destination
SHA256, independently audit every raw frame and original verdict, then permit
removal only of that verified run's NVMe spool. Never copy/archive concurrently
with the next measured run. Full disk budget and2GiB runtime reserve apply to
both the archive and spool volumes. No source times are shifted.

Declare three independent30s cases prospectively. A300s uninterrupted case
requires all three physical/shadow audits, exact native replays, recorder
integrity and normal server shutdowns. After the first failure, remaining cases
may be explicitly NOT_RUN for causal diagnosis; the failed case is immutable.
No identical retries count as replacements. Any further change starts a new
series and freeze. Accepted perception outputs remain zero; full visual-scene
fidelity, detector-quality promotion, holdout and Jetson deployment remain out
of scope. The suspected shader shutdown defect is not claimed fixed by this
host configuration. Original30s shutdown deadline remains enforced.
