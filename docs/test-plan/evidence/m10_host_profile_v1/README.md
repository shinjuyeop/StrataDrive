# M10 Host profiling V1: retained shared-placement failures

A and B both fail the original joint audit. A has140 normal/5698 protected
intervals; B has492/5342. Every raw image is retained (299 each), both native
replays are exact and both independent archive checks reproduce the failures.
B requested OpenCV2, but backend construction restored4. The actual4 metadata
is retained, the V1 split case is NOT_RUN, and V2 explicitly fixes/validates the
override ordering before a new prospective split experiment.

See [the complete profiling report](../m10_host_profile_v5/README.md),
[the prospective protocol](../../perception-host-profile-v1-protocol.md),
`disposition.json` and each original case/audit/analysis. The original archive
contains full500ms process/thread/host/GPU profiles. No full milestone acceptance.
