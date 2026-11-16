# M10 bounded host boost-cap V1

Watch timing V1 passed the first30s and failed the second at5.097s. Exact replay
identified the held HV dependency at30.349940ms before fresh replacement. Later
monitor misses clustered with reported all-core800MHz episodes. Preserve all
original failures. The unloaded sensor probe did not reproduce these misses;
it is not evidence that BIOS stalls or thermal clamping are absent under load.

The next candidate changes only the host's Intel P-state maximum performance
request from100% to70% for a bounded experiment. Minimum16%, turbo enablement,
governor/EPP, IRQ affinity, cooling and thermal protections remain unchanged.
This is a host-wide setting, not a Jetson or default deployment setting. The
purpose is to test whether limiting peak boost avoids repeated hot/slow episodes
while preserving enough physics throughput. It is a hypothesis, not a fix claim.

An explicit privileged invocation of `tools/m10_boost_lease.py` is required;
the current agent account cannot write the sysfs setting or use passwordless
sudo. The reviewed helper writes only max_perf_pct, retains the original100,
and restores on owner-process exit, handled stop signals or1800s timeout.
It rejects a different starting policy and concurrent leases, and will not
overwrite a different cap set by another process. SIGKILL/power loss cannot run
a finally block; restoration status must be independently checked. No password
is stored or passed to the agent. CARLA and the experiment runner remain unprivileged.

Use tested native-postfix from watch timing V1 (first Drive fault snapshot),
guarded structured-state build04 and the original selected Host V1 CPU roles.
Keep2K2560x1536/Epic/D-FINE-M960/CUDA, camera100ms model period, renderer20Hz,
query20Hz, parked preparation, MaxFPS60, passive ORT/CUDA blocking, raw NVMe and
OpenCV/resize4. Physics5ms/320 substeps, native2/4ms, HV30ms and perception100ms
remain unchanged. No source restamping, missing-frame removal, delayed failure
clear or acceptance relaxation.

The corrected50ms IRQ observer reads the complete bounded procfs snapshot.
Extend the50ms clock observer to all16 logical CPU thermal counters, requested
P-state limits and the kernel-maintained intel_powerclamp state. Do not poll Dell
fan/SMM attributes during live work. Measure each observer's quiet p95 cost<2ms
before launch; this does not bound live overhead. Keep qualified per-CPU counter
names rather than collapsing all cores to one basename. Require samples before
and after the physical span, no read errors or gap>200ms, and observed70/16/0
max/min/no_turbo values throughout. This observation integrity is an additional
diagnostic check; original physical/replay verdicts remain authoritative.

Run all Python493, focused frozen77 and actual30/300s allocation/start/stop checks
before freezing source, protocol, orchestration, helper and runtime identities.
Prior C++207 tests and byte-exact replays apply to the unchanged native binary.
Require the single5s native sensor probe to have no missed/late monitor slots.
The freeze may use a temporary candidate install while no server runs; restore
before waiting for the privileged lease. Record the operator invocation and
helper events, and verify the cap before every launch. A missing cap means NOT_RUN.

Preflight CPU<=70C within180s, RAM>=4GiB, free space>=horizon raw bound+4GiB,
readiness180s, shutdown30s and live2GiB reserves remain. Do not build, run tests,
compress or query SMM sensors during concurrent execution. Declare one30s case,
a second30s only if all original and new checks pass, and one300s only after both
pass. Stop on the first failure; no same-candidate retries. Exact native replay
also compares the immutable first Drive fault sidecar. Restore original CARLA,
DXC and INI after each case and verify original host cap after the sequence.

Chain exclusions from15784. Retain every raw frame, failure and original source;
independently reproduce original archive results before lossless compaction or
duplicate deletion. Compare the declared701 moving tickets200–900 only if all
remain normal, with uncontrolled host-history caveats. The hold scenario is not
continuous route driving. A finite pass does not accept perception, complete
visual scene, independent quality, each Jetson deployment or M10 closure.
