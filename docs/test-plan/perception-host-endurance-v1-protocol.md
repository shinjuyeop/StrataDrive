# M10 Host endurance V1: one prospective 300-second case

After the original F/G/H 30-second diagnostic passes, declare exactly one new
300-second normal case, `normal-300s-01`. All A–E failures and the C non-exact
replay remain evidence. No replacement attempt, deadline relaxation, timestamp
rewrite, dropped raw frame or retrospective selection is permitted.

Use H's exact runtime and settings: 2560×1536/Epic, D-FINE-M960/CUDA, physical
5ms, native 2/4ms, HV30ms, perception100ms; source query cap20Hz, renderer50ms
model step with20Hz wall cap, camera100ms model period (target10Hz). Keep Host V1
CPU placement, CFS owner, original FIFO18 native, parked empty-world preparation,
renderer MaxFPS60, passive ORT, CUDA blocking wait, OpenCV4, resize4 and the raw
NVMe BGRA spool with both live hashes. Only the diagnostic horizon changes to
300s/60000 intervals, with the existing duration-derived limits.

Before the single attempt: freeze source, runner, protocol, profile and external
runtime identities; verify the previous original runtime, then install the
already recorded CARLA and DXC candidates. Run the existing frozen boundary
tests. Require CPU package/core samples ≤70°C (wait at most180s, otherwise NOT_RUN),
available RAM ≥4GiB, and NVMe/archive free bytes ≥the existing stored-byte bound
plus4GiB. The 300s stored bound is57,227,083,776bytes; required free space is
61,522,051,072bytes. Existing live RAM/disk2GiB reserve checks remain active.
Do not change cooling, host power/clocks, kernel permissions or unrelated jobs.

Profile the owned process tree every500ms, on observer cores0/8. Do no builds,
compression, archive audit or other discretionary heavy work during the live
case. Preserve startup, the complete physical interval, inference, shutdown,
original faults and missing coverage. A completed runner is not a PASS: apply
the unchanged joint, shadow, native exact-replay and frozen archive audits.
Report normal/INIT/protection counts, actual cadence, freshness distribution and
over100ms count, recorder losses, CPU/GPU cost, thermal counters, resource minima
and original shutdown outcomes. A failure ends this declared live sequence.

Restore and hash-check the shared CARLA module, DXC and INI after the servers
stop, including a failed case. Keep the NVMe source until sealing and independent
raw/member/BGRA/RGB/exclusion checks pass. Only then remove that redundant spool.
Post-run lossless gzip may replace a raw tar only after the existing compactor
verifies the entire original byte stream. Retain all raw frames and add every
RGB hash to H's future-exclusion chain; no holdout access.

Follow [artifact storage](artifact-storage.md): raw/run archives remain local and
ignored, with immutable manifests and restoration instructions; publish source,
protocol, case, summaries, audits and selected metadata/core traces. Do not
force-add generated archives. One finite300s diagnostic pass is not indefinite
real-time stability, full visual-scene fidelity, independent quality, native
perception acceptance, Jetson deployment or M10 closure. Native perception
acceptance stays unavailable until the complete scene contract is satisfied.
