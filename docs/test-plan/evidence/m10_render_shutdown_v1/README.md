# M10 renderer shutdown diagnosis V1: earlier hang not reproduced

2026-11-12. One declared `shutdown-01` trial completed the same renderer-only
diagnostic and exited130 in **1.467300121s** after SIGINT. This is a finite
renderer lifecycle PASS; **the preceding intermittent hang remains unexplained**.
No debugger attached because the process exited before the10s trigger. No blocked
thread evidence exists for this run, and no engine/driver fix is claimed.

The [protocol](../../perception-render-shutdown-v1-protocol.md) froze1333 source
files plus the GDB/runtime identities.29 focused tests passed from the separate
archive. Four new lifecycle tests include real attach/detach to a runner-owned
child, clean exit without tracing, forced failure at the unchanged deadline,
and dead-PID/bounded-file handling. The host ptrace_scope is not modified.

`renderer_shutdown_v1.py` is opt-in. A new owned child permits ptrace; if still
alive10s after SIGINT, capture bounded thread status/maps and up to16 stack frames
per thread using the pinned debugger, with an8s/8MiB cap. Debugger time counts
inside the original30s shutdown limit. Overrun remains a forced failure. The
debugger never attaches during normal rendering and records no memory/environment
dump. This conditional mechanism is preparation for a future recurrence, not an
observation of the previous blocked process.

All19 actual2K callbacks are retained, including7 warmup/unmapped and12 associated
with original physical frames810/1009/1209. Original source/acquisition and actual
clone pose checks remain exact. All12 old scenes stay unavailable;0 inference,
0 native publications, no concurrent physical owner or complete scene. These
limitations match the [preceding replay](../m10_render_replay_v2/README.md).

The reader verifies image hashes/content, original pose matrices and timestamps,
normal exit bounds and twelve rejected evidence mutations. All19 RGB hashes join
future quality exclusions, now9016; no holdout accessed. Four runtime binaries are
unchanged and persistent settings restored. `run.tar.gz` retains original logs and
results; `raw-camera-01.tar` retains every lossless packet via Git LFS. Integrity
PASS does not turn the earlier FAIL into a success.

```bash
git lfs pull --include='docs/test-plan/evidence/m10_render_shutdown_v1/raw-camera-01.tar'
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_render_shutdown_v1/check-evidence.py --work /tmp/shutdown-v1-source-NEW
build/m10-perception/cuda-venv/bin/python \
  docs/test-plan/evidence/m10_render_shutdown_v1/check-live.py --work /tmp/shutdown-v1-audit-NEW
```

Next, the [separately declared V2](../m10_render_shutdown_v2/README.md) removes
unrequested asynchronous renderer advancement during post-capture storage.
