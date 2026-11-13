# M10 Host profiling V4: first finite30s pass

F separates renderer progression (20Hz wall cap,50ms model step) from camera
cadence (100ms model period,10Hz wall target), retaining D's shared CPU placement,
CFS owner, raw NVMe recording and all original deadlines. It passes the original
joint diagnostic audit:6000 intervals,5838 normal/162 INIT, zero protection or
late/missing slots. All285 images/281 numerical results are retained. Native
replay is exact and independent archive verification reproduces PASS.

Scene→result median76.891ms/p95 85.934ms/max120.017ms does not meet a hard100ms
bound on every result. All native perception remains unavailable. This first
pass motivated V5's two prospectively declared repetitions; it does not erase
A–E failures. Post-run raw compression preserves whole-tar expansion identities.

See [the complete profiling report and replications](../m10_host_profile_v5/README.md)
and [the prospective protocol](../../perception-host-profile-v4-protocol.md).
