# M10 Host profiling V3: owner priority does not pass

E repeats D's shared placement/raw recording with owner RR8. It fails the
unchanged HV dependency bound with65 normal/5769 protected/166 INIT intervals.
No physical-span thermal-throttle counter increase is sampled. All301 images
and294 inference outputs are retained, native replay is exact, and independent
archive verification reproduces FAIL. Raised owner priority is not selected.
Post-run gzip transport retains the exact original tar bytes on decompression.

See [the complete profiling report](../m10_host_profile_v5/README.md) and
[the prospective protocol](../../perception-host-profile-v3-protocol.md).
